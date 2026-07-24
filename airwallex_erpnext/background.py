from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import uuid4

import frappe
from frappe.utils.background_jobs import get_job

_CACHE_PREFIX = "airwallex_erpnext:sync_job:"
_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _cache_key(job_id: str) -> str:
    return _CACHE_PREFIX + job_id


def _settings(settings: str):
    doc = frappe.get_doc("Airwallex Settings", settings)
    doc.check_permission("read")
    return doc


def _compact(value: Any, depth: int = 0) -> Any:
    """Return a bounded, non-secret summary suitable for polling APIs."""
    if depth > 4:
        return "<nested>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, list):
        statuses = Counter()
        for item in value:
            if isinstance(item, dict) and item.get("status"):
                statuses[str(item.get("status"))] += 1
        result: dict[str, Any] = {"count": len(value)}
        if statuses:
            result["status_counts"] = dict(statuses)
        return result
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(token in key_text.lower() for token in ("secret", "token", "api_key", "password", "raw")):
                continue
            output[key_text] = _compact(item, depth + 1)
        return output
    return str(value)[:500]


def _set_state(job_id: str, state: dict[str, Any]) -> None:
    frappe.cache.set_value(_cache_key(job_id), state, expires_in_sec=_CACHE_TTL_SECONDS)


@frappe.whitelist()
def enqueue_sync(settings: str, module: str = "all", dry_run: int | str | bool = 1) -> dict[str, Any]:
    """Queue a potentially long Airwallex sync instead of blocking a web worker."""
    doc = _settings(settings)
    doc.check_permission("write")

    module = str(module or "all").strip().lower()
    dry_run_value = _as_bool(dry_run)
    external_job_id = f"airwallex-sync-{uuid4().hex}"
    state = {
        "ok": True,
        "job_id": external_job_id,
        "settings": doc.name,
        "module": module,
        "dry_run": dry_run_value,
        "status": "queued",
        "queued_at": frappe.utils.now_datetime(),
        "requested_by": frappe.session.user,
    }
    _set_state(external_job_id, state)

    job = frappe.enqueue(
        "airwallex_erpnext.background.run_sync_job",
        queue="long",
        timeout=3600,
        job_id=external_job_id,
        deduplicate=False,
        settings=doc.name,
        module=module,
        dry_run=dry_run_value,
        external_job_id=external_job_id,
        requested_by=frappe.session.user,
    )
    return {
        **state,
        "rq_job_id": getattr(job, "id", None),
        "queue": "long",
        "timeout_seconds": 3600,
    }


def run_sync_job(
    settings: str,
    module: str,
    dry_run: bool,
    external_job_id: str,
    requested_by: str | None = None,
) -> dict[str, Any]:
    from airwallex_erpnext.services.sync import run_sync

    state = {
        "ok": True,
        "job_id": external_job_id,
        "settings": settings,
        "module": module,
        "dry_run": bool(dry_run),
        "status": "started",
        "started_at": frappe.utils.now_datetime(),
        "requested_by": requested_by,
    }
    _set_state(external_job_id, state)
    try:
        result = run_sync(settings, module=module, dry_run=bool(dry_run))
        state.update(
            {
                "status": "finished",
                "finished_at": frappe.utils.now_datetime(),
                "result_summary": _compact(result),
            }
        )
        _set_state(external_job_id, state)
        return result
    except Exception as exc:
        state.update(
            {
                "ok": False,
                "status": "failed",
                "finished_at": frappe.utils.now_datetime(),
                "error_type": type(exc).__name__,
                "error": str(exc)[:2000],
            }
        )
        _set_state(external_job_id, state)
        raise


@frappe.whitelist()
def sync_job_status(settings: str, job_id: str, include_result: int | str | bool = 0) -> dict[str, Any]:
    """Return a bounded job state. Full results are opt-in and available only while RQ retains them."""
    _settings(settings)
    state = frappe.cache.get_value(_cache_key(job_id)) or {
        "ok": False,
        "job_id": job_id,
        "settings": settings,
        "status": "unknown",
    }

    job = get_job(job_id)
    if job:
        status = job.get_status(refresh=True)
        state["rq_status"] = getattr(status, "value", str(status))
        if _as_bool(include_result) and job.is_finished:
            state["result"] = job.result
        if job.is_failed and not state.get("error"):
            state["error"] = "Background sync failed. Review the Frappe worker error log."
    return state
