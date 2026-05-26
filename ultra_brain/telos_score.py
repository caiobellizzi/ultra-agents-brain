"""TELOS-relevance heuristic scoring for vault items.

Shared module used by monitor.py (real-time ingestion) and scripts/inbox_sweep.py.
Pure Python, no LLM calls. Keyword heuristic: 0.0 = off-mission, 1.0 = core mission.
"""

from __future__ import annotations

_HIGH: list[str] = [
    "agent", "agents", "agentic", "llm", "gpt", "claude", "anthropic", "openai",
    "gemini", "multi-agent", "multi agent", "mcp", "model context protocol",
    "langchain", "langgraph", "autogen", "crewai", "swarm", "tool use",
    "function call", "tool call", "rag", "retrieval", "embedding",
    "codex", "cursor", "copilot", "coding agent", "code generation",
    "spec-driven", "spec driven", "specification", "agentos",
    "second brain", "pkm", "vault", "obsidian", "telos", "para",
    "inference", "fine-tuning", "finetuning", "rlhf", "dpo", "sft",
    "distillation", "benchmark", "eval", "evals",
    "cli", "sdk", "api", "plugin", "extension", "webhook", "worker",
    "cron", "automation", "pipeline", "workflow",
    "kiro", "devin", "swe-bench", "deepseek",
]

_MEDIUM: list[str] = [
    "software engineer", "architecture", "refactor", "clean code", "design pattern",
    "microservice", "distributed system", "event-driven", "ci/cd", "devops",
    "docker", "kubernetes", "terraform", "cloud", "aws", "gcp", "azure",
    "performance", "latency", "throughput", "scalability", "memory", "cache",
    "security", "vulnerability", "cve", "encryption", "auth",
    "python", "rust", "typescript", "javascript",
    "github", "git", "open source", "npm", "pypi",
    "deep learning", "neural network", "training",
]

_NEGATIVE: list[str] = [
    "apl", "scheme", "forth", "lisp", "80386", "6502", "dos source", "spacelab",
    "microcode", "retro computing", "retro-computing", "vintage hardware",
    "immigration", "visa", "green card", "uscis", "trump", "fbi", "cia", "nsa",
    "geopolit", "senate", "congress", "lawsuit", "court",
    "health", "medical", "drug", "cancer", "cardiac", "seed oil", "vaccine",
    "salmon run", "fishing",
    "referendum", "election", "brexit",
    "wayland", "minecraft", "3d print", "cnc", "fpga",
    "pasta", "gluten", "food",
    "airbus", "boeing", "plane crash",
    "kindle", "e-reader", "ebook",
    "blogging", "desk setup",
    "limerick", "humor", "poetry",
    "nordvpn", "vpn", "piracy",
    "oura", "wearable", "sleep apnea",
    "scammer", "spam", "phishing",
]


def score_telos_relevance(title: str, body: str, tags: list[str] | None = None) -> float:
    """Return telos_relevance score in [0.0, 1.0].

    High (≥0.6): AI agents, LLM tooling, AgentOS, spec-driven dev.
    Medium (0.3–0.6): software engineering patterns, infra, performance.
    Low (<0.3): negative priors — esoterica, news, off-thesis tech.
    """
    tag_str = " ".join(tags or [])
    combined = (title + " " + body[:500] + " " + tag_str).lower()

    score = 0.0

    high_hits = 0
    for kw in _HIGH:
        if kw in combined:
            high_hits += 1
            if high_hits <= 3:
                score += 0.3

    med_hits = 0
    for kw in _MEDIUM:
        if kw in combined:
            med_hits += 1
            if med_hits <= 3:
                score += 0.1

    for kw in _NEGATIVE:
        if kw in combined:
            score -= 0.4
            break

    return max(0.0, min(1.0, score))
