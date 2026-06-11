"""Parallel scanner wrapper — dispatches enabled scanners concurrently.

Scanner selection is driven by the policy's ``config.nodes`` list:

| Policy   | Scanners                |
|----------|------------------------|
| fast     | none                   |
| balanced | llm_guard              |
| strict   | llm_guard + presidio   |
| paranoid | llm_guard + presidio   |

Each scanner runs as an independent ``asyncio.gather`` task.
If one scanner fails, the other's results are still merged.
"""

from __future__ import annotations

import asyncio

import structlog

from src.pipeline.nodes import timed_node
from src.pipeline.nodes.harm_ml import harm_ml_node
from src.pipeline.nodes.jailbreak_ml import jailbreak_ml_node
from src.pipeline.nodes.llm_guard import llm_guard_node
from src.pipeline.nodes.nemo_guardrails import nemo_guardrails_node
from src.pipeline.nodes.presidio import presidio_node
from src.pipeline.state import PipelineState

logger = structlog.get_logger()


@timed_node("scanners")
async def parallel_scanners_node(state: PipelineState) -> PipelineState:
    """Run enabled scanners in parallel and merge results.

    Which scanners execute is controlled by ``state["policy_config"]["nodes"]``.
    If ``nodes`` is absent or empty, no scanners run (fast-path).
    """
    policy_nodes: list[str] = state.get("policy_config", {}).get("nodes", [])

    tasks: list[tuple[str, asyncio.Task]] = []
    if "llm_guard" in policy_nodes:
        tasks.append(("llm_guard", llm_guard_node(state)))
    if "presidio" in policy_nodes:
        tasks.append(("presidio", presidio_node(state)))
    if "nemo_guardrails" in policy_nodes:
        tasks.append(("nemo_guardrails", nemo_guardrails_node(state)))
    if "jailbreak_ml" in policy_nodes:
        tasks.append(("jailbreak_ml", jailbreak_ml_node(state)))
    # Harm guard is controlled by the global HARM_ML_MODE flag (orthogonal to
    # policy). It runs here (pre-LLM) when mode == "pre_llm". In "post_llm" mode
    # it normally runs in the llm_call node (parallel with the provider) — BUT
    # the scan (/v1/scan) and streaming paths have no llm_call node, so for those
    # (pre_llm_only) we fall back to running it here, preserving harm enforcement
    # instead of silently skipping it.
    from src.config import get_settings

    mode = get_settings().harm_ml_mode
    if mode == "pre_llm" or (mode == "post_llm" and state.get("pre_llm_only")):
        tasks.append(("harm_ml", harm_ml_node(state)))

    if not tasks:
        return state  # fast policy — skip entirely

    results = await asyncio.gather(
        *[coro for _, coro in tasks],
        return_exceptions=True,
    )

    # Merge scanner results into single state
    merged_flags: dict = {**state.get("risk_flags", {})}
    merged_scanners: dict = {**state.get("scanner_results", {})}
    merged_errors: list[str] = list(state.get("errors", []))
    modified_messages = state.get("modified_messages")

    for (name, _), result in zip(tasks, results, strict=False):
        if isinstance(result, Exception):
            merged_errors.append(f"{name}: {result}")
            logger.error("scanner_parallel_error", scanner=name, error=str(result))
            continue
        merged_flags.update(result.get("risk_flags", {}))
        merged_scanners.update(result.get("scanner_results", {}))
        merged_errors.extend(result.get("errors", []))
        # Presidio may produce modified_messages (mask action)
        if result.get("modified_messages") is not None:
            modified_messages = result["modified_messages"]

    updated: dict = {
        **state,
        "risk_flags": merged_flags,
        "scanner_results": merged_scanners,
        "errors": merged_errors,
    }
    if modified_messages is not None:
        updated["modified_messages"] = modified_messages

    return updated
