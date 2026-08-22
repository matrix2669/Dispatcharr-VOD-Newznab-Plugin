import importlib
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from servarr_bridge.config import (
    DEFAULTS,
    _new_api_key,
    infer_sab_state_from_output_path,
    sab_category_dir,
    sab_output_path,
)
from servarr_bridge.descriptors import decode_descriptor, descriptor_nzb, encode_descriptor, extract_descriptor_from_nzb
from servarr_bridge.probe import _resolve_ffprobe, classify_dynamic_range
from servarr_bridge.recent import _episode_result, _movie_result
from servarr_bridge.releases import (
    build_episode_release,
    build_movie_release,
    build_unprobed_episode_release,
    build_unprobed_movie_release,
    clean_series_name,
)


class ConfigTests(unittest.TestCase):
    def test_system_ffprobe_default(self):
        self.assertEqual(DEFAULTS["ffprobe_path"], "/usr/bin/ffprobe")

    def test_dispatcharr_proxy_requires_explicit_url(self):
        self.assertEqual(DEFAULTS["dispatcharr_url"], "")

    def test_api_key_generator_is_url_safe_and_non_repeating(self):
        first = _new_api_key()
        second = _new_api_key()
        self.assertNotEqual(first, second)
        self.assertGreaterEqual(len(first), 40)
        self.assertRegex(first, re.compile(r"^[A-Za-z0-9_-]+$"))

    def test_sab_category_directory(self):
        self.assertEqual(sab_category_dir("radarr"), "mustarrd/radarr")

    def test_sab_output_layout(self):
        release = "Zootopia.2.2025.2160p.WEB-DL.DV.HEVC.DDP5.1-MUSTARRD"
        self.assertEqual(
            sab_output_path("radarr", release, "mkv"),
            f"mustarrd/radarr/{release}/{release}.mkv",
        )

    def test_sab_category_is_sanitized(self):
        self.assertEqual(sab_category_dir("../radarr"), "mustarrd/_radarr")

    def test_sab_state_recovers_from_mustarrd_output_path(self):
        release = "Zootopia.2.2025.1080p.WEB-DL.SDR.H264.AAC5.1-MUSTARRD"
        state = infer_sab_state_from_output_path(
            f"/app/completed/mustarrd/radarr/{release}/{release}.mkv"
        )
        self.assertEqual(state["category"], "radarr")
        self.assertEqual(state["title"], release)
        self.assertEqual(
            state["relative_output_path"],
            f"mustarrd/radarr/{release}/{release}.mkv",
        )

    def test_non_servarr_output_is_not_inferred(self):
        self.assertEqual(
            infer_sab_state_from_output_path(
                "/app/completed/TV Shows/First Things First/Season 00/show.mkv"
            ),
            {},
        )


class ProbeRuntimeTests(unittest.TestCase):
    def test_missing_absolute_ffprobe_falls_back_to_path(self):
        with patch("servarr_bridge.probe.os.path.isfile", return_value=False), patch(
            "servarr_bridge.probe.shutil.which", return_value="/usr/local/bin/ffprobe"
        ) as which:
            resolved = _resolve_ffprobe({"ffprobe_path": "/usr/bin/ffprobe"})

        self.assertEqual(resolved, "/usr/local/bin/ffprobe")
        which.assert_called_with("ffprobe")

    def test_existing_absolute_ffprobe_is_preferred(self):
        with patch("servarr_bridge.probe.os.path.isfile", return_value=True), patch(
            "servarr_bridge.probe.os.access", return_value=True
        ), patch("servarr_bridge.probe.shutil.which") as which:
            resolved = _resolve_ffprobe({"ffprobe_path": "/custom/bin/ffprobe"})

        self.assertEqual(resolved, "/custom/bin/ffprobe")
        which.assert_not_called()

    def test_named_ffprobe_resolves_from_path(self):
        with patch(
            "servarr_bridge.probe.shutil.which", return_value="/usr/local/bin/ffprobe"
        ) as which:
            resolved = _resolve_ffprobe({"ffprobe_path": "ffprobe"})

        self.assertEqual(resolved, "/usr/local/bin/ffprobe")
        which.assert_called_once_with("ffprobe")


class RecentFeedTests(unittest.TestCase):
    def test_unprobed_release_names_do_not_invent_media_traits(self):
        self.assertEqual(
            build_unprobed_movie_release("Example Movie", 2026),
            "Example.Movie.2026.WEB-DL-MUSTARRD",
        )
        self.assertEqual(
            build_unprobed_episode_release("EN - Example Show (2020) (US)", 2020, 3, 7),
            "Example.Show.S03E07.WEB-DL-MUSTARRD",
        )

    def test_lightweight_movie_result_is_downloadable_parent_movie_category(self):
        result = _movie_result(
            7,
            "12345",
            "mkv",
            "Example Movie",
            2026,
            "999",
            1786741200,
            "secret",
        )
        payload = decode_descriptor(result["token"], "secret")
        self.assertEqual(result["category"], "2000")
        self.assertEqual(payload["kind"], "movie")
        self.assertEqual(payload["media_id"], "12345")
        self.assertEqual(payload["dispatcharr_account_id"], 7)

    def test_lightweight_episode_result_is_downloadable_parent_tv_category(self):
        result = _episode_result(
            7,
            "series-22",
            "episode-44",
            "mkv",
            "Example Show",
            2020,
            3,
            7,
            "888",
            "Episode Seven",
            1786741200,
            "secret",
            duration_seconds=3600,
        )
        payload = decode_descriptor(result["token"], "secret")
        self.assertEqual(result["category"], "5000")
        self.assertEqual(payload["kind"], "episode")
        self.assertEqual(payload["media_id"], "episode-44")
        self.assertEqual(payload["season"], 3)
        self.assertEqual(payload["episode"], 7)
        self.assertEqual(payload["duration_minutes"], 60)


class PluginRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._state_dir = tempfile.TemporaryDirectory()
        cls._env = patch.dict(
            os.environ,
            {"ARR_STACK_CONNECTOR_STATE_DIR": cls._state_dir.name},
        )
        cls._env.start()
        cls.plugin_module = importlib.import_module("plugin")

    @classmethod
    def tearDownClass(cls):
        cls._env.stop()
        cls._state_dir.cleanup()

    def test_dispatcharr_app_root_is_discovered_from_runtime_sys_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_root = Path(tmp)
            package = app_root / "dispatcharr"
            package.mkdir()
            (package / "settings.py").write_text("# synthetic Dispatcharr settings\n")

            runtime_path = [str(app_root), *sys.path]
            with patch.object(sys, "path", runtime_path):
                roots = self.plugin_module._dispatcharr_app_roots()
                child_path = self.plugin_module.Plugin.__new__(
                    self.plugin_module.Plugin
                )._child_pythonpath().split(os.pathsep)

            self.assertIn(app_root.resolve(), roots)
            self.assertIn(str(app_root.resolve()), child_path)

    def test_service_start_failure_keeps_plugin_loaded_for_diagnostics(self):
        with patch.dict(
            os.environ,
            {"ARR_STACK_CONNECTOR_SERVICE": ""},
            clear=False,
        ):
            with patch.object(
                self.plugin_module.Plugin,
                "_ensure_service",
                side_effect=RuntimeError("synthetic startup failure"),
            ):
                instance = self.plugin_module.Plugin()

        self.assertIsInstance(instance, self.plugin_module.Plugin)

    def test_public_rename_uses_new_installed_identity(self):
        manifest = json.loads((ROOT / "plugin.json").read_text())
        self.assertEqual(manifest["name"], "Arr Stack Connector")
        self.assertEqual(self.plugin_module.PLUGIN_NAME, "Arr Stack Connector")
        self.assertEqual(ROOT.name, "arr-stack-connector")
        self.assertEqual(self.plugin_module.STATE_DIR, Path(self._state_dir.name))
        plugin_source = (ROOT / "plugin.py").read_text()
        self.assertIn("ARR_STACK_CONNECTOR_STATE_DIR", plugin_source)
        self.assertIn("/data/arr_stack_connector", plugin_source)
        self.assertNotIn("DISPATCHARR_VOD_NEWZNAB", plugin_source)
        newznab_source = (ROOT / "servarr_bridge" / "newznab.py").read_text()
        self.assertIn('title="Arr Stack Connector"', newznab_source)


class DescriptorTests(unittest.TestCase):
    def test_signed_nzb_round_trip(self):
        payload = {"version": 1, "kind": "movie", "media_id": "123", "release": "Movie.2026.1080p-MUSTARRD"}
        token = encode_descriptor(payload, "secret")
        self.assertEqual(decode_descriptor(token, "secret")["media_id"], "123")
        nzb = descriptor_nzb(token, payload["release"])
        self.assertEqual(extract_descriptor_from_nzb(nzb), token)

    def test_signature_rejected(self):
        token = encode_descriptor({"version": 1, "kind": "movie"}, "secret")
        with self.assertRaises(ValueError):
            decode_descriptor(token, "wrong")


class DynamicRangeTests(unittest.TestCase):
    def test_dv_precedes_hdr10(self):
        video = {
            "pix_fmt": "yuv420p10le",
            "color_transfer": "smpte2084",
            "color_primaries": "bt2020",
            "side_data_list": [{"side_data_type": "DOVI configuration record"}],
        }
        self.assertEqual(classify_dynamic_range(video), "DV")

    def test_hdr10_plus(self):
        self.assertEqual(classify_dynamic_range({"side_data_list": [{"side_data_type": "HDR10+ Dynamic Metadata SMPTE2094"}]}), "HDR10+")

    def test_hdr10(self):
        self.assertEqual(classify_dynamic_range({"color_transfer": "smpte2084", "color_primaries": "bt2020"}), "HDR10")

    def test_hdr(self):
        self.assertEqual(classify_dynamic_range({"color_transfer": "arib-std-b67"}), "HDR")

    def test_sdr(self):
        self.assertEqual(classify_dynamic_range({"color_transfer": "bt709", "color_primaries": "bt709"}), "SDR")


class ReleaseTests(unittest.TestCase):
    VIDEO_1080 = {"width": 1920, "height": 1080, "codec_name": "h264", "color_transfer": "bt709"}
    AUDIO_51 = {"codec_name": "aac", "channels": 6, "channel_layout": "5.1"}

    def test_movie_release(self):
        release = build_movie_release(
            "L.A. Confidential",
            1997,
            {"width": 1920, "height": 800, "codec_name": "h264", "color_transfer": "bt709"},
            self.AUDIO_51,
        )
        self.assertEqual(release, "L.A.Confidential.1997.1080p.WEB-DL.SDR.H264.AAC5.1-MUSTARRD")

    def test_survivor_provider_name_is_cleaned_for_sonarr(self):
        self.assertEqual(clean_series_name("EN - Survivor (2000) (US)", 2000), "Survivor")

    def test_service_prefix_and_country_are_cleaned(self):
        self.assertEqual(clean_series_name("4K-NF - Designated Survivor (US)", 2016), "Designated Survivor")
        self.assertEqual(
            clean_series_name("D+ - Primal Survivor: Mighty Mekong (2022) (US)", 2022),
            "Primal Survivor: Mighty Mekong",
        )
        self.assertEqual(clean_series_name("EN - Australian Survivor (2002) (AU)", 2002), "Australian Survivor")

    def test_tv_release_uses_clean_series_name_without_premiere_year(self):
        release = build_episode_release(
            "EN - Survivor (2000) (US)",
            2000,
            50,
            13,
            self.VIDEO_1080,
            self.AUDIO_51,
        )
        self.assertEqual(
            release,
            "Survivor.S50E13.1080p.WEB-DL.SDR.H264.AAC5.1-MUSTARRD",
        )


if __name__ == "__main__":
    unittest.main()
