"""Extract text fragments from a JSON structure using dot-notation paths.

Path syntax
-----------
- ``"key"`` — top-level key
- ``"a.b.c"`` — nested keys
- ``"items.*"`` — iterate every element of an array
- ``"data.items.*.text"`` — nested key inside each array element

The extractor collects all matching leaf values (stringified), joins them
with newlines, and returns the result.  If nothing matches, returns ``""``.
"""

from __future__ import annotations

from typing import Any


def extract_text(data: Any, paths: list[str]) -> str:
    """Walk *data* along each path in *paths* and return joined text.

    Parameters
    ----------
    data:
        Parsed JSON (usually a ``dict``).
    paths:
        Ordered list of dot-notation paths.  Evaluated left-to-right;
        all matching fragments are collected.

    Returns
    -------
    str
        Newline-joined string of all extracted fragments, or ``""``
        if nothing matched.
    """
    if not isinstance(data, (dict, list)) or not paths:
        return ""

    fragments: list[str] = []
    for path in paths:
        segments = path.split(".")
        _walk(data, segments, 0, fragments)
    return "\n".join(fragments)


def _walk(node: Any, segments: list[str], idx: int, out: list[str]) -> None:
    """Recursively descend into *node* following *segments* from *idx*."""
    if idx >= len(segments):
        # Reached the end of the path — collect the leaf.
        if isinstance(node, str):
            if node:
                out.append(node)
        elif node is not None:
            text = str(node)
            if text:
                out.append(text)
        return

    seg = segments[idx]

    if seg == "*":
        # Wildcard — iterate array or dict values.
        if isinstance(node, list):
            for item in node:
                _walk(item, segments, idx + 1, out)
        elif isinstance(node, dict):
            for item in node.values():
                _walk(item, segments, idx + 1, out)
        return

    if isinstance(node, dict) and seg in node:
        _walk(node[seg], segments, idx + 1, out)


# ---------------------------------------------------------------------------
# Auto-detection: find paths that contain long-ish text strings
# ---------------------------------------------------------------------------

_MIN_TEXT_LEN = 8  # ignore very short strings (ids, codes, etc.)


def detect_text_paths(data: Any, *, max_paths: int = 5) -> list[str]:
    """Walk a parsed JSON structure and return dot-notation paths to string leaves.

    Only strings longer than *_MIN_TEXT_LEN* chars are considered.
    Paths are returned longest-value-first (most likely to be the AI answer).
    Array indices are replaced with ``*`` for generality.
    """
    if not isinstance(data, (dict, list)):
        return []
    hits: list[tuple[str, int]] = []  # (path, len)
    _detect_walk(data, [], hits)
    hits.sort(key=lambda t: t[1], reverse=True)
    # Deduplicate paths (array elements produce the same wildcard path)
    seen: set[str] = set()
    result: list[str] = []
    for path, _ in hits:
        if path not in seen:
            seen.add(path)
            result.append(path)
            if len(result) >= max_paths:
                break
    return result


def _detect_walk(node: Any, segments: list[str], hits: list[tuple[str, int]]) -> None:
    if isinstance(node, str):
        if len(node) >= _MIN_TEXT_LEN:
            hits.append((".".join(segments), len(node)))
        return
    if isinstance(node, dict):
        for key, val in node.items():
            _detect_walk(val, [*segments, key], hits)
    elif isinstance(node, list):
        for item in node:
            _detect_walk(item, [*segments, "*"], hits)
