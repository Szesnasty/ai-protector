"""LangGraph pipeline — builds and compiles the firewall StateGraph."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.pipeline.nodes.decision import decision_node
from src.pipeline.nodes.intent import intent_node
from src.pipeline.nodes.llm_call import llm_call_node
from src.pipeline.nodes.logging_node import logging_node
from src.pipeline.nodes.output_filter import output_filter_node
from src.pipeline.nodes.parse import parse_node
from src.pipeline.nodes.rules import rules_node
from src.pipeline.nodes.scanners import parallel_scanners_node
from src.pipeline.nodes.transform import transform_node
from src.pipeline.state import PipelineState


def route_after_decision(state: PipelineState) -> str:
    """Conditional routing after DecisionNode."""
    decision = state.get("decision")
    if decision == "BLOCK":
        return "block"
    if decision == "MODIFY":
        return "modify"
    return "allow"


def build_pipeline() -> StateGraph:
    """Build and compile the firewall pipeline.

    .. code-block:: text

        parse → intent → rules → scanners → decision
                                               ├─ BLOCK  → logging → END
                                               ├─ MODIFY → transform → llm_call → output_filter → logging → END
                                               └─ ALLOW  → llm_call → output_filter → logging → END
    """
    graph = StateGraph(PipelineState)

    # Input pipeline
    graph.add_node("parse", parse_node)
    graph.add_node("intent", intent_node)
    graph.add_node("rules", rules_node)
    graph.add_node("scanners", parallel_scanners_node)
    graph.add_node("decision", decision_node)
    graph.add_node("transform", transform_node)
    graph.add_node("llm_call", llm_call_node)

    # Output pipeline
    graph.add_node("output_filter", output_filter_node)
    graph.add_node("logging", logging_node)

    # Input edges
    graph.add_edge("parse", "intent")
    graph.add_edge("intent", "rules")
    graph.add_edge("rules", "scanners")
    graph.add_edge("scanners", "decision")

    # Decision routing
    graph.add_conditional_edges(
        "decision",
        route_after_decision,
        {
            "block": "logging",      # BLOCK → logging → END
            "modify": "transform",   # MODIFY → transform → ...
            "allow": "llm_call",     # ALLOW → llm_call → ...
        },
    )

    # MODIFY path
    graph.add_edge("transform", "llm_call")

    # After LLM call → output filter → logging
    graph.add_edge("llm_call", "output_filter")
    graph.add_edge("output_filter", "logging")

    # Logging → END (terminal node for all paths)
    graph.add_edge("logging", END)

    graph.set_entry_point("parse")
    return graph.compile()


# Compile once at module level
pipeline = build_pipeline()
