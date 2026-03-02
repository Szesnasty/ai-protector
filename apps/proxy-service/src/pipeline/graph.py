"""LangGraph pipeline — builds and compiles the firewall StateGraph."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.pipeline.nodes.decision import decision_node
from src.pipeline.nodes.intent import intent_node
from src.pipeline.nodes.llm_call import llm_call_node
from src.pipeline.nodes.parse import parse_node
from src.pipeline.nodes.rules import rules_node
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

        parse → intent → rules → decision
                                    ├─ BLOCK  → END
                                    ├─ MODIFY → transform → llm_call → END
                                    └─ ALLOW  → llm_call → END
    """
    graph = StateGraph(PipelineState)

    graph.add_node("parse", parse_node)
    graph.add_node("intent", intent_node)
    graph.add_node("rules", rules_node)
    graph.add_node("decision", decision_node)
    graph.add_node("transform", transform_node)
    graph.add_node("llm_call", llm_call_node)

    graph.add_edge("parse", "intent")
    graph.add_edge("intent", "rules")
    graph.add_edge("rules", "decision")
    graph.add_conditional_edges(
        "decision",
        route_after_decision,
        {"block": END, "modify": "transform", "allow": "llm_call"},
    )
    graph.add_edge("transform", "llm_call")
    graph.add_edge("llm_call", END)

    graph.set_entry_point("parse")
    return graph.compile()


# Compile once at module level
pipeline = build_pipeline()
