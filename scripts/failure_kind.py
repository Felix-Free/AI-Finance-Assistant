"""Whitelisted short labels for measurement failures (shared by the two samplers)."""
from __future__ import annotations

import json

_TIMEOUT_MARKERS = ("timeout", "timed out")
_RESOLUTION_MARKERS = ("name resolution", "name or service not known",
                       "nodename nor servname", "temporary failure in name")


def failure_kind(exc) -> str:
    """Whitelisted failure label; never carries a body, URL or raw repr (M4).

    Allowed shapes: ``http <status> (<Class>)``, ``transport: read timeout
    (<Class>)``, ``transport: name resolution (<Class>)``, ``transport: other
    (<Class>)``, ``not_json``.
    """
    name = type(exc).__name__
    if isinstance(exc, json.JSONDecodeError):
        return "not_json"
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and not isinstance(status_code, bool):
        return "http %d (%s)" % (status_code, name)
    text = str(exc).lower()
    if any(marker in text for marker in _TIMEOUT_MARKERS):
        return "transport: read timeout (%s)" % name
    if any(marker in text for marker in _RESOLUTION_MARKERS):
        return "transport: name resolution (%s)" % name
    return "transport: other (%s)" % name
