import json
import shutil
import subprocess


def _int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def classify_dynamic_range(video):
    if not isinstance(video, dict):
        return "SDR"
    blob = json.dumps(video, sort_keys=True).lower()
    # Dolby Vision must win before PQ/HDR10 because many DV profiles carry an
    # HDR10-compatible base layer/colorimetry.
    if any(token in blob for token in ("dovi", "dolby vision", "dv_profile", "dv_level", "dvcC".lower(), "dvvC".lower())):
        return "DV"
    if any(token in blob for token in ("hdr10+", "smpte2094", "dynamic hdr10+", "hdr10plus")):
        return "HDR10+"
    transfer = str(video.get("color_transfer") or video.get("color_trc") or "").lower()
    primaries = str(video.get("color_primaries") or "").lower()
    space = str(video.get("color_space") or video.get("colorspace") or "").lower()
    pix_fmt = str(video.get("pix_fmt") or "").lower()
    pq = transfer in {"smpte2084", "smpte-st-2084"} or "smpte2084" in blob
    bt2020 = "bt2020" in primaries or "bt2020" in space or "bt2020" in blob
    if pq and bt2020:
        return "HDR10"
    if transfer in {"arib-std-b67", "hlg"} or "arib-std-b67" in blob or "hlg" in blob:
        return "HDR"
    if pq or bt2020:
        return "HDR"
    return "SDR"


def resolution_label(video):
    width = _int(video.get("width")) if isinstance(video, dict) else 0
    height = _int(video.get("height")) if isinstance(video, dict) else 0
    if width >= 3800 or height >= 2100:
        return "2160p"
    if width >= 1900 or height >= 1000:
        return "1080p"
    if width >= 1200 or height >= 700:
        return "720p"
    if height:
        return f"{height}p"
    return "Unknown"


def video_codec_label(video):
    codec = str((video or {}).get("codec_name") or (video or {}).get("codec") or "").lower()
    if codec in {"hevc", "h265", "h.265"}:
        return "HEVC"
    if codec in {"h264", "avc", "h.264"}:
        return "H264"
    if codec == "av1":
        return "AV1"
    if codec in {"mpeg2video", "mpeg2"}:
        return "MPEG2"
    return codec.upper() if codec else "VIDEO"


def audio_label(audio):
    if not isinstance(audio, dict) or not audio:
        return None
    codec = str(audio.get("codec_name") or audio.get("codec") or "").lower()
    names = {
        "aac": "AAC",
        "ac3": "DD",
        "eac3": "DDP",
        "truehd": "TrueHD",
        "dts": "DTS",
        "opus": "OPUS",
        "flac": "FLAC",
        "mp3": "MP3",
    }
    label = names.get(codec, codec.upper() if codec else "AUDIO")
    channels = _int(audio.get("channels"))
    layout = str(audio.get("channel_layout") or "").lower()
    if channels >= 8 or "7.1" in layout:
        suffix = "7.1"
    elif channels >= 6 or "5.1" in layout:
        suffix = "5.1"
    elif channels == 2 or "stereo" in layout:
        suffix = "2.0"
    elif channels == 1 or "mono" in layout:
        suffix = "1.0"
    else:
        suffix = str(channels) if channels else ""
    return f"{label}{suffix}" if suffix else label


def probe_media(url, settings):
    executable = str(settings.get("ffprobe_path") or "ffprobe")
    resolved = shutil.which(executable) or (executable if "/" in executable else None)
    if not resolved:
        return {"status": "error", "error": "ffprobe not found"}
    timeout = max(1, int(settings.get("probe_timeout") or 20))
    command = [
        resolved,
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        url,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "ffprobe timeout"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    if result.returncode != 0:
        return {"status": "error", "error": "ffprobe failed"}
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {"status": "error", "error": "invalid ffprobe JSON"}
    streams = payload.get("streams") or []
    videos = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"]
    audios = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"]
    video = videos[0] if videos else {}
    audio = next((a for a in audios if (a.get("disposition") or {}).get("default") == 1), audios[0] if audios else {})
    fmt = payload.get("format") or {}
    return {
        "status": "ok" if video else "error",
        "video": video,
        "audio": audio,
        "audio_streams": audios,
        "format": fmt,
        "size": _int(fmt.get("size")),
        "bit_rate": _int(fmt.get("bit_rate")),
        "duration": float(fmt.get("duration") or 0) if str(fmt.get("duration") or "").replace(".", "", 1).isdigit() else 0,
    }
