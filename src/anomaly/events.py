"""Best-effort durable event logging for Anomaly's mainline API entry points.

Every mainline call appends one phase event to ``.anomaly/events.jsonl`` so a
fresh session can reconstruct what ran, using the same JSON object shape as
resolver-selected phase attempts (sorted keys, UTC timestamp, ``phase`` field).
Logging is append-only and never raising: durable
bookkeeping must not be able to break the API call it observes.
"""
from __future__ import annotations

import functools
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from anomaly.case import _scan_case_tree
from anomaly.semantics import redact_credentials

_MAX_DETAIL = 300

F = TypeVar("F", bound=Callable[..., Any])


def log_event(
    case_root: Path, phase: str, event: str, detail: str | None = None
) -> dict[str, Any] | None:
    """Append one API event to ``.anomaly/events.jsonl``; never raise.

    Returns the written payload, or ``None`` when the event store is
    unavailable.  ``detail`` is credential-redacted and truncated before it
    lands.
    """
    try:
        _scan_case_tree(Path(case_root))
        payload: dict[str, Any] = {
            "event": _redact(event),
            "at": datetime.now(timezone.utc).isoformat(),
            "phase": _redact(phase),
            "source": "api",
        }
        if detail:
            payload["detail"] = _redact(detail)
        path = Path(case_root) / ".anomaly" / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception:
        return None
    return payload


def phase_event(phase: str, event: str) -> Callable[[F], F]:
    """Decorate a mainline entry point so the call appends its phase event.

    Success appends ``event``; a raised exception appends ``event_failed``
    with the redacted error as detail and re-raises unchanged.
    """

    def decorate(func: F) -> F:
        @functools.wraps(func)
        def wrapper(root: Path, *args: Any, **kwargs: Any) -> Any:
            _scan_case_tree(Path(root))
            try:
                result = func(root, *args, **kwargs)
            except Exception as error:
                log_event(root, phase, f"{event}_failed", detail=str(error))
                raise
            log_event(root, phase, event)
            return result

        return wrapper  # type: ignore[return-value]

    return decorate


def _redact(value: str) -> str:
    return str(redact_credentials(str(value)))[:_MAX_DETAIL]
