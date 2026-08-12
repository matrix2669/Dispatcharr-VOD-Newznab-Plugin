import json
import logging
import os
import threading
import time
from pathlib import Path, PurePosixPath

from .config import PLUGIN_DIR, sab_category_dir, sab_output_path
from .descriptors import decode_descriptor, extract_descriptor_from_nzb
from .mustarrd import shared_client
from .provider import dispatcharr_proxy_source


logger = logging.getLogger(__name__)


class JobState:
    def __init__(self):
        self.path = PLUGIN_DIR / "servarr_jobs.json"
        self.lock = threading.RLock()

    def _load(self):
        try:
            data = json.loads(self.path.read_text())
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def get(self, job_id):
        with self.lock:
            return self._load().get(str(job_id), {})

    def set(self, job_id, value):
        with self.lock:
            data = self._load()
            data[str(job_id)] = value
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
            os.replace(tmp, self.path)

    def delete(self, job_id):
        with self.lock:
            data = self._load()
            data.pop(str(job_id), None)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
            os.replace(tmp, self.path)


STATE = JobState()


def _category_for(payload, requested, settings):
    requested = str(requested or "").strip()
    if requested:
        return requested
    return settings.get("radarr_category", "radarr") if payload.get("kind") == "movie" else settings.get("sonarr_category", "sonarr")


def addfile(nzb_data, requested_category, settings):
    token = extract_descriptor_from_nzb(nzb_data)
    payload = decode_descriptor(token, settings["api_key"])
    media_id = str(payload["media_id"])
    extension = str(payload.get("container_extension") or "mkv")
    release = payload.get("release") or "Mustarrd.VOD"
    category = _category_for(payload, requested_category, settings)

    relative_output_path = sab_output_path(category, release, extension)

    source_url = dispatcharr_proxy_source(payload, settings)
    logger.info(
        "Submitting %s stream %s to Mustarrd through Dispatcharr proxy as %s",
        payload.get("kind"),
        media_id,
        relative_output_path,
    )
    created = shared_client(settings).create_external(
        media_id=media_id,
        title=release,
        source_url=source_url,
        relative_output_path=relative_output_path,
        duration_minutes=int(payload.get("duration_minutes") or 0),
    )
    job_id = str(created["id"])
    STATE.set(job_id, {
        "category": category,
        "title": release,
        "kind": payload.get("kind"),
        "relative_output_path": relative_output_path,
        "created_at": time.time(),
    })
    return {"status": True, "nzo_ids": [job_id]}


def _queue_status(status):
    return {
        "pending": "Queued",
        "downloading": "Downloading",
        "processing": "Moving",
    }.get(str(status), "Queued")


def _history_status(status):
    return {
        "completed": "Completed",
        "failed": "Failed",
        "cancelled": "Deleted",
    }.get(str(status), "Failed")


def _category_matches(job_id, requested):
    if not requested:
        return True
    return str(STATE.get(job_id).get("category") or "") == str(requested)


def queue(settings, category=None, start=0, limit=100):
    rows = shared_client(settings).queue() or []
    slots = []
    for row in rows:
        job_id = str(row.get("id"))
        if not _category_matches(job_id, category):
            continue
        state = STATE.get(job_id)
        total = int(row.get("file_size") or 0)
        done = int(row.get("downloaded_bytes") or 0)
        progress = int(float(row.get("progress") or 0))
        mb = total / (1024 * 1024) if total else 0
        left = max(0, total - done) / (1024 * 1024) if total else 0
        slots.append({
            "status": _queue_status(row.get("status")),
            "index": len(slots),
            "timeleft": "0:00:00",
            "mb": round(mb, 3),
            "filename": state.get("title") or row.get("program_title") or f"Mustarrd-{job_id}",
            "priority": "Normal",
            "cat": state.get("category") or "",
            "mbleft": round(left, 3),
            "percentage": progress,
            "nzo_id": job_id,
        })
    start = max(0, int(start or 0))
    limit = max(1, int(limit or 100))
    return {"queue": {"paused": False, "slots": slots[start:start + limit]}}


def _storage_path(settings, state, row):
    """Return SAB's completed job directory, not the media file path."""
    rel = str(state.get("relative_output_path") or "").replace("\\", "/").lstrip("/")
    base = str(settings.get("servarr_completed_dir") or "/completed").rstrip("/")
    if rel:
        job_dir = str(PurePosixPath(rel).parent)
        return f"{base}/{job_dir}" if job_dir not in {"", "."} else base
    output = str(row.get("output_path") or "")
    return str(Path(output).parent) if output else base


def history(settings, category=None, start=0, limit=100):
    rows = shared_client(settings).history() or []
    slots = []
    for row in rows:
        job_id = str(row.get("id"))
        if not _category_matches(job_id, category):
            continue
        state = STATE.get(job_id)
        completed = row.get("completed_at")
        created = row.get("created_at")
        download_time = 0
        try:
            from datetime import datetime
            if completed and created:
                download_time = max(0, int((datetime.fromisoformat(completed) - datetime.fromisoformat(created)).total_seconds()))
        except Exception:
            download_time = 0
        status = _history_status(row.get("status"))
        title = state.get("title") or row.get("program_title") or f"Mustarrd-{job_id}"
        slots.append({
            "fail_message": row.get("error_message") or "",
            "bytes": int(row.get("file_size") or row.get("downloaded_bytes") or 0),
            "category": state.get("category") or "",
            "nzb_name": title,
            "download_time": download_time,
            "storage": _storage_path(settings, state, row),
            "status": status,
            "nzo_id": job_id,
            "name": title,
        })
    start = max(0, int(start or 0))
    limit = max(1, int(limit or 100))
    return {"history": {"paused": False, "slots": slots[start:start + limit]}}


def delete_job(settings, job_id, history=False):
    shared_client(settings).delete(job_id)
    if history:
        STATE.delete(job_id)
    return {"status": True}


def retry_job(settings, job_id):
    shared_client(settings).retry(job_id)
    return {"status": True, "nzo_id": str(job_id)}


def version():
    return {"version": "4.5.3"}


def get_config(settings):
    complete = str(settings.get("servarr_completed_dir") or "/completed")
    sonarr = str(settings.get("sonarr_category") or "sonarr")
    radarr = str(settings.get("radarr_category") or "radarr")
    categories = [
        {"priority": 0, "pp": "", "name": sonarr, "script": "", "dir": sab_category_dir(sonarr)},
        {"priority": 0, "pp": "", "name": radarr, "script": "", "dir": sab_category_dir(radarr)},
    ]
    return {
        "config": {
            "misc": {
                "complete_dir": complete,
                "tv_categories": [sonarr],
                "enable_tv_sorting": False,
                "movie_categories": [radarr],
                "enable_movie_sorting": False,
                "date_categories": [],
                "enable_date_sorting": False,
                "pre_check": False,
                "history_retention": "",
                "history_retention_option": "all",
                "history_retention_number": 0,
            },
            "categories": categories,
            "servers": [],
            "sorters": [],
        }
    }


def fullstatus(settings):
    return {"status": {"completedir": str(settings.get("servarr_completed_dir") or "/completed")}}
