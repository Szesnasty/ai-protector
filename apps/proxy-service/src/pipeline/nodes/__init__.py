"""Pipeline nodes package — reusable helpers shared by all nodes."""

from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

from src.pipeline.state import PipelineState

# Type alias for a pipeline node function
NodeFunc = Callable[[PipelineState], Coroutine[Any, Any, PipelineState]]


def timed_node(name: str) -> Callable[[NodeFunc], NodeFunc]:
    """Decorator that measures node execution time in ms.

    The elapsed time is stored in ``state["node_timings"][name]``.
    """

    def decorator(func: NodeFunc) -> NodeFunc:
        @wraps(func)
        async def wrapper(state: PipelineState) -> PipelineState:
            start = time.perf_counter()
            result = await func(state)
            elapsed_ms = (time.perf_counter() - start) * 1000
            timings = {**result.get("node_timings", {}), name: round(elapsed_ms, 2)}
            return {**result, "node_timings": timings}

        return wrapper

    return decorator


__all__ = ["timed_node"]
