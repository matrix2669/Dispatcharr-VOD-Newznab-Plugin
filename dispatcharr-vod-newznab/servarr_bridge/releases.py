import re
from .probe import audio_label, classify_dynamic_range, resolution_label, video_codec_label


_SERIES_PREFIX_RE = re.compile(
    r"^(?:(?:4K-)?(?:EN|NF|D\+|DISNEY\+|AMZN|HULU|MAX|HMAX|ATVP|APPLETV|VIP|VOD|FHD|HD|UHD|4K|A\+|4K-A\+))\s*[-|:]\s*",
    flags=re.I,
)
_COUNTRY_SUFFIX_RE = re.compile(r"\s*[\[(]([A-Z]{2})[\])]\s*$", flags=re.I)


def clean_name(value, year=None):
    text = str(value or "Unknown").strip()
    text = re.sub(r"^(?:4K|FHD|HD|UHD|A\+|4K-A\+|VIP|VOD)\s*[-|:]\s*", "", text, flags=re.I)
    if year:
        text = re.sub(rf"\s*\({re.escape(str(year))}\)\s*$", "", text).strip()
    return text or "Unknown"


def clean_series_name(value, year=None):
    """Remove provider decorations without changing the actual series title."""
    text = str(value or "Unknown").strip()
    text = _SERIES_PREFIX_RE.sub("", text).strip()

    while True:
        cleaned = _COUNTRY_SUFFIX_RE.sub("", text).strip()
        if cleaned == text:
            break
        text = cleaned

    if year:
        text = re.sub(rf"\s*[\[(]{re.escape(str(year))}[\])]\s*$", "", text).strip()

    return text or "Unknown"


def _dot(value):
    text = re.sub(r"[^A-Za-z0-9+\-]+", ".", str(value or "Unknown")).strip(".")
    return re.sub(r"\.{2,}", ".", text) or "Unknown"


def _media_suffix(video, audio):
    parts = [resolution_label(video), "WEB-DL", classify_dynamic_range(video), video_codec_label(video)]
    audio_name = audio_label(audio)
    if audio_name:
        parts.append(audio_name)
    return ".".join(_dot(p) for p in parts if p)


def build_movie_release(title, year, video, audio):
    base = _dot(clean_name(title, year))
    if year:
        base += f".{year}"
    return f"{base}.{_media_suffix(video, audio)}-MUSTARRD"


def build_episode_release(series, year, season, episode, video, audio):
    base = _dot(clean_series_name(series, year))
    base += f".S{int(season):02d}E{int(episode):02d}"
    return f"{base}.{_media_suffix(video, audio)}-MUSTARRD"


def build_unprobed_movie_release(title, year):
    """Build a conservative recent-feed title without inventing media traits."""
    base = _dot(clean_name(title, year))
    if year:
        base += f".{year}"
    return f"{base}.WEB-DL-MUSTARRD"


def build_unprobed_episode_release(series, year, season, episode):
    """Build a conservative recent-feed episode title without probing media."""
    base = _dot(clean_series_name(series, year))
    base += f".S{int(season):02d}E{int(episode):02d}"
    return f"{base}.WEB-DL-MUSTARRD"
