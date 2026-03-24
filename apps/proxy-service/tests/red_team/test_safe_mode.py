"""Tests for P2-04 Safe Mode Filtering.

Verifies that:
- mutating scenarios are skipped when safe_mode=True
- all scenarios run when safe_mode=False
- skipped_mutating count is accurate
- score excludes skipped scenarios
- core_security is mostly non-mutating
- agent_threats has both mutating and non-mutating scenarios
"""

from __future__ import annotations

import pytest

from src.red_team.packs.loader import TargetConfig, clear_cache, filter_pack, load_pack

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_pack_cache():
    clear_cache()
    yield
    clear_cache()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_safe_mode_skips_mutating():
    """mutating=true scenarios skipped when safe_mode=true."""
    pack = load_pack("agent_threats")
    config = TargetConfig(agent_type="tool_calling", safe_mode=True)
    result = filter_pack(pack, config)

    # All remaining scenarios should be non-mutating
    for scenario in result.scenarios:
        assert not scenario.mutating, f"Scenario {scenario.id} is mutating but was not skipped"

    # At least some should have been skipped with reason 'safe_mode'
    assert result.skipped_reasons.get("safe_mode", 0) > 0


def test_safe_mode_off_runs_all():
    """All scenarios run when safe_mode=false."""
    pack = load_pack("agent_threats")
    config = TargetConfig(agent_type="tool_calling", safe_mode=False)
    result = filter_pack(pack, config)

    assert result.skipped_reasons.get("safe_mode", 0) == 0
    assert result.total_applicable == result.total_in_pack


def test_skipped_mutating_count():
    """skipped_reasons['safe_mode'] == number of mutating scenarios skipped."""
    pack = load_pack("agent_threats")
    mutating_count = sum(1 for s in pack.scenarios if s.mutating)

    config = TargetConfig(agent_type="tool_calling", safe_mode=True)
    result = filter_pack(pack, config)

    assert result.skipped_reasons.get("safe_mode", 0) == mutating_count
    assert result.total_in_pack == result.total_applicable + result.skipped_count


def test_score_excludes_skipped():
    """Score should be computed from executed scenarios only (total_applicable)."""
    pack = load_pack("agent_threats")
    config = TargetConfig(agent_type="tool_calling", safe_mode=True)
    result = filter_pack(pack, config)

    # total_applicable should be less than total_in_pack when mutating are skipped
    if result.skipped_reasons.get("safe_mode", 0) > 0:
        assert result.total_applicable < result.total_in_pack

    # The scenarios list should only contain non-mutating ones
    assert len(result.scenarios) == result.total_applicable


def test_core_security_mostly_safe():
    """Most Core Security scenarios are not mutating."""
    pack = load_pack("core_security")
    mutating_count = sum(1 for s in pack.scenarios if s.mutating)
    non_mutating = len(pack.scenarios) - mutating_count

    # At least 80% should be non-mutating
    assert non_mutating >= len(pack.scenarios) * 0.8, (
        f"Expected mostly non-mutating, got {mutating_count} mutating out of {len(pack.scenarios)}"
    )


def test_agent_threats_safe_variant():
    """Agent Threats in safe mode still has executable scenarios."""
    pack = load_pack("agent_threats")
    config = TargetConfig(agent_type="tool_calling", safe_mode=True)
    result = filter_pack(pack, config)

    # Should have at least 1 executable scenario remaining
    assert result.total_applicable > 0, "Agent Threats in safe mode has no executable scenarios"
    # Should also have skipped some
    assert result.skipped_count > 0, "Agent Threats should have some mutating scenarios skipped"


def test_safe_mode_no_effect_on_non_mutating_pack():
    """Safe mode on a pack with no mutating scenarios changes nothing."""
    pack = load_pack("core_security")
    normal = filter_pack(pack, TargetConfig(agent_type="chatbot_api", safe_mode=False))
    safe = filter_pack(pack, TargetConfig(agent_type="chatbot_api", safe_mode=True))

    # If core_security has no mutating scenarios, both should be identical
    if all(not s.mutating for s in pack.scenarios):
        assert normal.total_applicable == safe.total_applicable
        assert safe.skipped_reasons.get("safe_mode", 0) == 0
