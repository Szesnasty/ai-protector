"""SSE formatter — converts event payloads to SSE wire format."""

from __future__ import annotations

import json
from dataclasses import asdict

from src.red_team.progress.events import ProgressEvent, event_type_for


def format_sse(event: ProgressEvent) -> str:
    """Format a progress event as an SSE string.

    Returns a string like::

        event: scenario_start
        data: {"scenario_id": "sqli-basic", "index": 1, "total_applicable": 12}

    (Terminated by double newline per SSE spec.)
    """
    event_type = event_type_for(event).value
    data = json.dumps(asdict(event), default=str, separators=(",", ":"))
    return f"event: {event_type}\ndata: {data}\n\n"
