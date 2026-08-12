import json
import logging
import os
import threading
import time
from pathlib import Path, PurePosixPath

from .config import (
    PLUGIN_DIR,
    STATE_DIR,
    infer_sab_state_from_output_path,
    sab_category_dir,
    sab_output_path,
)
from .descriptors import decode_descriptor, extract_descriptor_from_nzb
from .mustarrd import shared_client
from .provider import dispatcharr_proxy_source


logger = logging.getLogger(__name__)
SAB_ID_PREFIX = "mustarrd-"


class JobState:
    def __init__(self):
        self.path = STATE_DIR / "servarr_jobs.json"
        self.legacy_path = PLUGIN_DIR / "servarr_jobs.json"
        self.lock = threading.RLock()
        self._prepare_storage()

    def _prepare_storage(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() or not self.legacy_path.exists():
            return
        try:
            data = json.loads(self.legacy_path.read_text())
            if not isinstance(data, dict):
                return
            self._write(data)
            logger.info(
                "Migrated Servarr bridge state from %s to persistent path %s",
                self.legacy_path,
                self.path,
            )
        except Exception:
            logger.exception("Unable to migrate legacy Servarr bridge state")

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        os.replace(tmp, self.path)

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
            self._write(data)

    def delete(self, job_id):
        with self.lock:
            data = self._load()
            data.pop(str(job_id), None)
            self._write(data)


STATE = JobState()


def _category_for(payload, requested, settings):
    requested = str(requested or "").strip()
    if requested:
        return requested
    return settings.get("radarr_category", "radarr") if payload.get("kind") == "movie" else settings.get("sonarr_category", "sonarr")


def _new_sab_id(job_id):
    return f"{SAB_ID_PREFIX}{job_id}"


def _sab_id(job_id, state=None):
    """Return the stable SAB-facing ID for a Mustarrd job.

    Existing state created before v0.1.8 has no sab_id. Preserve its raw ID so
    an in-flight job keeps the same identifier across an upgrade. New jobs are
    namespaced to avoid collisions in Servarr's download tracking cache/history.
    """
    state = state if isinstance(state, dict) else STATE.get(job_id)
    saved = str(state.get("sab_id") or "").strip()
    return saved or str(job_id)


def _mustarrd_id(sab_id):
    text = str(sab_id or "").strip()
    if text.startswith(SAB_ID_PREFIX):
        text = text[len(SAB_ID_PREFIX):]
    if not text:
        raise ValueError("Missing Mustarrd job ID")
    return text


def _state_for_row(job_id, row):
    """Return bridge metadata, recovering it from Mustarrd's path if needed."""
    state = dict(STATE.get(job_id) or {})
    inferred = infer_sab_state_from_output_path(row.get("output_path"))
    if not inferred:
        return state

    changed = False
    for key, value in inferred.items():
        if value and not state.get(key):
            state[key] = value
            changed = True
    if changed:
        # Do not invent sab_id while recovering legacy jobs. A pre-v0.1.8 grab
        # may have been recorded in Servarr using the raw Mustarrd ID, and
        # changing it after completion would break that association.
        STATE.set(job_id, state)
        logger.info(
            "Recovered Servarr bridge state for Mustarrd job %s from output path (category=%s)",
            job_id,
            state.get("category"),
        )
    return state


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
    sab_id = _new_sab_id(job_id)
    STATE.set(job_id, {
        "sab_id": sab_id,
        "category": category,
        "title": release,
        "kind": payload.get("kind"),
        "relative_output_path": relative_output_path,
        "created_at": time.time(),
    })
    logger.info("Mapped Mustarrd job %s to SAB nzo_id %s", job_id, sab_id)
    return {"status": True, "nzo_ids": [sab_id]}


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


def _category_matches(state, requested):
    if not requested:
        return True
    return str(state.get("category") or "") == str(requested)


def queue(settings, category=None, start=0, limit=100):
    rows = shared_client(settings).queue() or []
    slots = []
    for row in rows:
        job_id = str(row.get("id"))
        state = _state_for_row(job_id, row)
        if not _category_matches(state, category):
            continue
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
            "nzo_id": _sab_id(job_id, state),
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
        state = _state_for_row(job_id, row)
        if not _category_matches(state, category):
            continue
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
            "nzo_id": _sab_id(job_id, state),
            "name": title,
        })
    start = max(0, int(start or 0))
    limit = max(1, int(limit or 100))
    return {"history": {"paused": False, "slots": slots[start:start + limit]}}


def delete_job(settings, job_id, history=False):
    """Remove a SAB job completely from Mustarrd.

    Mustarrd's DELETE endpoint intentionally has two phases for active jobs:
    the first call cancels the job and leaves a cancelled history row; a second
    call deletes that now-finished row. SAB queue deletion is a removal, so
    perform both phases when necessary and then discard our local mapping.
    """
    sab_id = str(job_id)
    mustarrd_id = _mustarrd_id(sab_id)
    client = shared_client(settings)
    result = client.delete(mustarrd_id) or {}
    if str(result.get("status") or "").lower() == "cancelled":
        result = client.delete(mustarrd_id) or result
    STATE.delete(mustarrd_id)
    logger.info(
        "Removed SAB job %s (Mustarrd job %s) from Mustarrd (history=%s)",
        sab_id,
        mustarrd_id,
        history,
    )
    return {"status": True}


def retry_job(settings, job_id):
    sab_id = str(job_id)
    mustarrd_id = _mustarrd_id(sab_id)
    shared_client(settings).retry(mustarrd_id)
    return {"status": True, "nzo_id": sab_id}


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
