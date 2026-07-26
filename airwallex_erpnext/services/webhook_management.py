from __future__ import annotations

from uuid import uuid4

import frappe

from airwallex_erpnext.frappe_support import get_client
from airwallex_erpnext.webhook_catalog import desired_events, normalize_url, subscription_matches

WEBHOOK_METHOD_PATH = "/api/method/airwallex_erpnext.api.webhook"
MINIMUM_SPEND_WEBHOOK_VERSION = "2025-11-11"


def webhook_url() -> str:
    return frappe.utils.get_url(WEBHOOK_METHOD_PATH).rstrip("/")


def inspect_subscription(settings_name: str, *, persist: bool = True) -> dict:
    settings = frappe.get_doc("Airwallex Settings", settings_name)
    client = get_client(settings)
    target_url = webhook_url()
    version = str(settings.webhook_version or MINIMUM_SPEND_WEBHOOK_VERSION)
    events = desired_events(settings)
    subscriptions = _list_subscriptions(client)
    exact = [item for item in subscriptions if normalize_url(item.get("url")) == normalize_url(target_url)]
    preferred = _choose_subscription(settings, exact)
    existing_secret = settings.get_password("webhook_secret", raise_exception=False)
    effective_secret = str((preferred or {}).get("secret") or existing_secret or "")
    configured = bool(
        preferred
        and subscription_matches(preferred, target_url=target_url, version=version, events=events)
        and effective_secret
        and len(exact) == 1
    )
    status = "Configured" if configured else ("Needs Repair" if exact else "Missing")

    if persist:
        _save_metadata(settings, preferred, status=status, secret=(preferred or {}).get("secret"))

    return {
        "status": status,
        "target_url": target_url,
        "version": version,
        "desired_events": events,
        "subscription": _public_subscription(preferred),
        "matching_url_count": len(exact),
        "other_webhook_count": max(0, len(subscriptions) - len(exact)),
        "has_signing_secret": bool(effective_secret),
    }


def ensure_subscription(settings_name: str) -> dict:
    settings = frappe.get_doc("Airwallex Settings", settings_name)
    if not int(settings.enabled or 0):
        frappe.throw("Enable the Airwallex connection before configuring its webhook")

    client = get_client(settings)
    target_url = webhook_url()
    version = str(settings.webhook_version or MINIMUM_SPEND_WEBHOOK_VERSION)
    events = desired_events(settings)
    if not events:
        frappe.throw("Enable Card Expenses or Reimbursements before creating a Spend webhook")

    subscriptions = _list_subscriptions(client)
    exact = [item for item in subscriptions if normalize_url(item.get("url")) == normalize_url(target_url)]
    matching = [
        item
        for item in exact
        if subscription_matches(item, target_url=target_url, version=version, events=events)
    ]
    existing_secret = settings.get_password("webhook_secret", raise_exception=False)
    usable = [item for item in matching if item.get("secret") or existing_secret]

    deleted_ids: list[str] = []
    if usable:
        keep = _choose_subscription(settings, usable)
        for item in exact:
            if item.get("id") and item.get("id") != keep.get("id"):
                _delete_subscription(client, str(item["id"]))
                deleted_ids.append(str(item["id"]))
        remaining_exact = _subscriptions_for_url(client, target_url)
        if len(remaining_exact) != 1 or str(remaining_exact[0].get("id") or "") != str(keep.get("id") or ""):
            frappe.throw("Airwallex webhook duplicate cleanup could not be verified")
        action = "adopted" if not settings.webhook_subscription_id else "verified"
    else:
        for item in exact:
            if item.get("id"):
                _delete_subscription(client, str(item["id"]))
                deleted_ids.append(str(item["id"]))
        if _subscriptions_for_url(client, target_url):
            frappe.throw("Airwallex webhook replacement could not remove the outdated subscription")
        keep = client.request(
            "POST",
            "/api/v1/webhooks/create",
            body={
                "url": target_url,
                "version": version,
                "events": events,
                "request_id": f"frappe-{uuid4().hex[:32]}",
            },
        )
        action = "repaired" if exact else "created"

    if not keep or not keep.get("id"):
        frappe.throw("Airwallex did not return a webhook subscription ID")
    if not keep.get("secret") and not existing_secret:
        frappe.throw("Airwallex did not return a webhook signing secret")

    verified = client.request("GET", f"/api/v1/webhooks/{keep['id']}")
    if keep.get("secret") and not verified.get("secret"):
        verified["secret"] = keep["secret"]
    if not subscription_matches(verified, target_url=target_url, version=version, events=events):
        frappe.throw("Airwallex webhook verification did not match the requested configuration")

    _save_metadata(settings, verified, status="Configured", secret=verified.get("secret"))
    return {
        "status": "Configured",
        "action": action,
        "subscription": _public_subscription(verified),
        "deleted_duplicate_or_outdated_ids": deleted_ids,
        "target_url": target_url,
        "has_signing_secret": True,
    }


def reconcile_enabled_subscriptions(*, source: str = "scheduler") -> list[dict]:
    """Ensure enabled Airwallex connections own one exact ERPNext webhook.

    Reconciliation is intentionally best-effort so a temporary Airwallex API
    outage cannot block a Frappe migration or stop scheduled transaction
    recovery. Each connection persists a bounded status and is retried later.
    """
    settings_names = frappe.get_all(
        "Airwallex Settings",
        filters={"enabled": 1},
        pluck="name",
        limit_page_length=0,
    )
    results: list[dict] = []
    for settings_name in settings_names:
        settings = frappe.get_doc("Airwallex Settings", settings_name)
        if not desired_events(settings):
            results.append({"settings": settings_name, "status": "Skipped", "reason": "no_webhook_modules_enabled"})
            continue
        try:
            result = ensure_subscription(settings_name)
            results.append(
                {
                    "settings": settings_name,
                    "status": result.get("status"),
                    "action": result.get("action"),
                    "target_url": result.get("target_url"),
                    "has_signing_secret": bool(result.get("has_signing_secret")),
                }
            )
        except Exception as exc:
            settings = frappe.get_doc("Airwallex Settings", settings_name)
            settings.webhook_subscription_status = "Error"
            settings.last_webhook_check = frappe.utils.now_datetime()
            settings.save(ignore_permissions=True)
            results.append(
                {
                    "settings": settings_name,
                    "status": "Error",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                }
            )

    summary = {"source": source, "connections": results}
    print(f"[airwallex-webhook-reconcile] {frappe.as_json(summary)}")
    return results


def remove_subscription(settings_name: str) -> dict:
    settings = frappe.get_doc("Airwallex Settings", settings_name)
    client = get_client(settings)
    target_url = webhook_url()
    subscriptions = _list_subscriptions(client)
    ids = {
        str(item["id"])
        for item in subscriptions
        if item.get("id") and normalize_url(item.get("url")) == normalize_url(target_url)
    }
    if settings.webhook_subscription_id:
        ids.add(str(settings.webhook_subscription_id))

    deleted: list[str] = []
    for subscription_id in sorted(ids):
        _delete_subscription(client, subscription_id)
        deleted.append(subscription_id)

    if _subscriptions_for_url(client, target_url):
        frappe.throw("Airwallex webhook removal could not be verified")

    settings.webhook_subscription_id = ""
    settings.webhook_subscription_url = ""
    settings.webhook_subscription_status = "Removed"
    settings.webhook_subscribed_events = ""
    settings.last_webhook_check = frappe.utils.now_datetime()
    settings.webhook_secret = ""
    settings.save(ignore_permissions=True)

    return {"status": "Removed", "deleted_ids": deleted, "target_url": target_url}


def _list_subscriptions(client) -> list[dict]:
    return list(
        client.paginate_bookmark(
            "/api/v1/webhooks",
            params={"page_size": 100},
            max_items=500,
        )
    )


def _subscriptions_for_url(client, target_url: str) -> list[dict]:
    normalized = normalize_url(target_url)
    return [item for item in _list_subscriptions(client) if normalize_url(item.get("url")) == normalized]


def _delete_subscription(client, subscription_id: str) -> None:
    result = client.request("POST", f"/api/v1/webhooks/{subscription_id}/delete")
    returned_id = str((result or {}).get("id") or "")
    if returned_id and returned_id != subscription_id:
        frappe.throw(f"Airwallex returned an unexpected webhook ID while deleting {subscription_id}")


def _choose_subscription(settings, items: list[dict]) -> dict | None:
    if not items:
        return None
    stored_id = str(settings.webhook_subscription_id or "")
    for item in items:
        if str(item.get("id") or "") == stored_id:
            return item
    return sorted(items, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)[0]


def _public_subscription(subscription: dict | None) -> dict | None:
    if not subscription:
        return None
    return {
        "id": subscription.get("id"),
        "url": subscription.get("url"),
        "version": subscription.get("version"),
        "events": sorted(set(subscription.get("events") or [])),
        "created_at": subscription.get("created_at"),
        "updated_at": subscription.get("updated_at"),
    }


def _save_metadata(settings, subscription: dict | None, *, status: str, secret: str | None = None) -> None:
    settings.webhook_subscription_id = (subscription or {}).get("id") or ""
    settings.webhook_subscription_url = (subscription or {}).get("url") or webhook_url()
    settings.webhook_subscription_status = status
    settings.webhook_subscribed_events = "\n".join(sorted(set((subscription or {}).get("events") or [])))
    settings.last_webhook_check = frappe.utils.now_datetime()
    if secret:
        settings.webhook_secret = secret
    settings.save(ignore_permissions=True)
