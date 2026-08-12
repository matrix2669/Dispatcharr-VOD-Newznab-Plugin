import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from servarr_bridge.config import (
    DEFAULTS,
    infer_sab_state_from_output_path,
    sab_category_dir,
    sab_output_path,
)
from servarr_bridge.descriptors import decode_descriptor, descriptor_nzb, encode_descriptor, extract_descriptor_from_nzb
from servarr_bridge.probe import classify_dynamic_range
from servarr_bridge.releases import build_movie_release


class ConfigTests(unittest.TestCase):
    def test_system_ffprobe_default(self):
        self.assertEqual(DEFAULTS["ffprobe_path"], "/usr/bin/ffprobe")

    def test_dispatcharr_proxy_requires_explicit_url(self):
        self.assertEqual(DEFAULTS["dispatcharr_url"], "")

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
    def test_movie_release(self):
        release = build_movie_release(
            "L.A. Confidential",
            1997,
            {"width": 1920, "height": 800, "codec_name": "h264", "color_transfer": "bt709"},
            {"codec_name": "aac", "channels": 6, "channel_layout": "5.1"},
        )
        self.assertEqual(release, "L.A.Confidential.1997.1080p.WEB-DL.SDR.H264.AAC5.1-MUSTARRD")


if __name__ == "__main__":
    unittest.main()
