"""Unit tests for ultra_brain/spec_gen.py — Required-field coverage."""

import pytest

from ultra_brain.spec_gen import generate_spec


# ── Fixtures ─────────────────────────────────────────────────────────────────

STUB_BRIEFING = {
    "id": "2026-05-26-test-briefing",
    "type": "briefing",
    "title": "Test Agent Spec",
    "created_at": "2026-05-26T00:00:00Z",
    "project": "ultra-agents-brain",
    "tags": ["agents", "python"],
    "source_notes": ["[[ai-agents-overview]]", "[[telos]]"],
    "audience": "caio",
    "status": "draft",
    "concepts": ["agent-memory", "telos-scoring"],
    "goal": "Build an agent that scores vault items against TELOS and auto-files high-relevance captures",
    "body": "We need a system that reads new vault inbox items, scores them against TELOS goals, "
            "and automatically files items with relevance >= 0.6 into 02-Resources/.",
}

STUB_ARCH_MD = """\
# Architecture — ultra-agents-brain

Updated: 2026-05-26T00:00:00Z

---

{"project":"ultra-agents-brain","total_nodes":100,"total_edges":200}

```python
def score_item(item: dict, telos: dict) -> float:
    \"\"\"Return telos_relevance score in [0.0, 1.0].\"\"\"
    ...
```
"""


# ── Test 1: All required section headers present ─────────────────────────────

REQUIRED_HEADERS = [
    "Problem & Context",
    "In-Scope",
    "Out-of-Scope",
    "Interfaces",
    "Acceptance Criteria",
    "References",
    "Rails",
    "Code Style Example",
]


def test_spec_gen_produces_all_required_fields():
    """generate_spec() must return a string containing all 8 required section headers."""
    result = generate_spec(STUB_BRIEFING, STUB_ARCH_MD)

    assert isinstance(result, str), "generate_spec() must return a string"
    for header in REQUIRED_HEADERS:
        assert header in result, f"Required section missing from SPEC.md: '{header}'"


# ── Test 2: ARCHITECTURE.md content appears in Code Style Example ─────────────

def test_spec_gen_embeds_architecture_snippet():
    """The ARCHITECTURE.md code block must appear (or be excerpted) in Code Style Example."""
    result = generate_spec(STUB_BRIEFING, STUB_ARCH_MD)

    # The code block from ARCHITECTURE.md should appear in the output
    assert "score_item" in result, (
        "ARCHITECTURE.md code snippet should be embedded in the Code Style Example section"
    )


# ── Test 3: EARS format in Acceptance Criteria ───────────────────────────────

def test_spec_gen_ears_format():
    """At least one acceptance criterion must use EARS form: 'When ... the system shall ...'."""
    result = generate_spec(STUB_BRIEFING, STUB_ARCH_MD)

    # EARS format: "When X, the system shall Y"
    assert "the system shall" in result.lower() or "When " in result, (
        "At least one acceptance criterion must use EARS format: 'When X, the system shall Y'"
    )
    # More specific: look for the EARS pattern
    assert "system shall" in result, (
        "Acceptance Criteria section must contain EARS-formatted criteria with 'system shall'"
    )


# ── Test 4: Source wikilinks appear in References section ────────────────────

def test_spec_gen_references_source_wikilinks():
    """References section must contain all source_notes wikilinks from the briefing."""
    briefing_with_sources = {
        **STUB_BRIEFING,
        "source_notes": ["[[ai-agents-overview]]"],
    }

    result = generate_spec(briefing_with_sources, STUB_ARCH_MD)

    assert "[[ai-agents-overview]]" in result, (
        "References section must contain wikilink '[[ai-agents-overview]]' from source_notes"
    )
