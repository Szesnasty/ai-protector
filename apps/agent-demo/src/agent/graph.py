"""Agent graph — LangGraph wiring for the Customer Support Copilot."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agent.nodes.input import input_node
from src.agent.nodes.intent import intent_node
from src.agent.nodes.llm_call import llm_call_node
from src.agent.nodes.memory import memory_node
from src.agent.nodes.policy import policy_check_node
from src.agent.nodes.response import response_node
from src.agent.nodes.tools import tool_executor_node, tool_router_node
from src.agent.state import AgentState


def _should_call_tools(state: AgentState) -> str:
    """Decide whether to execute tools or skip to LLM."""
    plan = state.get("tool_plan", [])
    if plan:
        return "tool_executor"
    return "llm_call"


def _should_skip_llm(state: AgentState) -> str:
    """After tool execution, always go to LLM for response generation."""
    return "llm_call"


def _check_blocked(state: AgentState) -> str:
    """After LLM call, check if response was blocked by firewall."""
    fw = state.get("firewall_decision", {})
    if fw.get("decision") == "BLOCK":
        # Skip to memory (final_response already set by llm_call_node)
        return "memory"
    return "response"


def build_agent_graph() -> StateGraph:
    """Build and compile the agent LangGraph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("input", input_node)
    graph.add_node("intent", intent_node)
    graph.add_node("policy_check", policy_check_node)
    graph.add_node("tool_router", tool_router_node)
    graph.add_node("tool_executor", tool_executor_node)
    graph.add_node("llm_call", llm_call_node)
    graph.add_node("memory", memory_node)
    graph.add_node("response", response_node)

    # Wire edges
    graph.set_entry_point("input")
    graph.add_edge("input", "intent")
    graph.add_edge("intent", "policy_check")
    graph.add_edge("policy_check", "tool_router")

    # Conditional: tool_router → tool_executor (if tools planned) or llm_call (no tools)
    graph.add_conditional_edges("tool_router", _should_call_tools, {
        "tool_executor": "tool_executor",
        "llm_call": "llm_call",
    })

    # After tool execution → always go to LLM
    graph.add_edge("tool_executor", "llm_call")

    # After LLM → check if blocked
    graph.add_conditional_edges("llm_call", _check_blocked, {
        "memory": "memory",
        "response": "response",
    })

    graph.add_edge("response", "memory")
    graph.add_edge("memory", END)

    return graph


# Compiled graph singleton
_compiled_graph = None


def get_agent_graph():
    """Get or build the compiled agent graph (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_agent_graph()
        _compiled_graph = graph.compile()
    return _compiled_graph
