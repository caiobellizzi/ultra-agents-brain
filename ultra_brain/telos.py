"""TELOS interview state and lightweight alignment checks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import llm


DEFAULT_QUESTIONS = [
    "What outcomes should this assistant optimize for this quarter?",
    "What work should it explicitly avoid?",
    "Which sources, people, and topics deserve priority?",
    "What privacy boundaries are non-negotiable?",
    "When should the assistant interrupt you instead of waiting?",
]


class TelosSessionStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, object]:
        if not self.path.exists():
            return {"sessions": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def start(self) -> dict[str, object]:
        data = self.load()
        sessions = data.setdefault("sessions", [])
        assert isinstance(sessions, list)
        session = {"id": len(sessions) + 1, "answers": [], "next_question": DEFAULT_QUESTIONS[0]}
        sessions.append(session)
        self.save(data)
        return session

    def answer(self, session_id: int, answer: str) -> dict[str, object]:
        data = self.load()
        sessions = data.get("sessions", [])
        if not isinstance(sessions, list):
            raise ValueError("invalid session store")
        for session in sessions:
            if isinstance(session, dict) and session.get("id") == session_id:
                answers = session.setdefault("answers", [])
                assert isinstance(answers, list)
                answers.append(answer)
                idx = min(len(answers), len(DEFAULT_QUESTIONS) - 1)
                session["next_question"] = DEFAULT_QUESTIONS[idx] if len(answers) < len(DEFAULT_QUESTIONS) else ""
                self.save(data)
                return session
        raise KeyError(f"session {session_id} not found")


@dataclass(frozen=True)
class TelosCheck:
    score: float
    rationale: str


def _words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 3}


def score_alignment(action: str, telos_root: Path, *, llm_model: str | None = None) -> TelosCheck:
    telos_text = ""
    for path in [telos_root / "telos.md", telos_root / "telos" / "mission.md", telos_root / "telos" / "quarter-goals.md"]:
        if path.exists():
            telos_text += "\n" + path.read_text(encoding="utf-8")
    dont_do = telos_root / "telos" / "dont-do.md"
    blocked = _words(dont_do.read_text(encoding="utf-8")) if dont_do.exists() else set()
    action_words = _words(action)
    if blocked & action_words:
        return TelosCheck(0.0, "action overlaps with TELOS dont-do terms: " + ", ".join(sorted(blocked & action_words)))

    if llm_model and telos_text.strip():
        try:
            response = llm.complete(
                f"TELOS:\n{telos_text[:3000]}\n\nAction: {action}",
                model=llm_model,
                system=(
                    "You are a TELOS alignment checker. Given a TELOS document and an action description, "
                    "output a JSON object with exactly two keys: 'score' (float 0.0-1.0) and 'rationale' "
                    "(string, max 120 chars). Output ONLY valid JSON."
                ),
                max_tokens=100,
            )
            data = json.loads(response)
            return TelosCheck(float(data["score"]), str(data["rationale"]))
        except Exception:
            pass

    target_words = _words(telos_text)
    if not target_words:
        return TelosCheck(0.5, "no TELOS draft exists; neutral alignment")
    overlap = target_words & action_words
    score = min(1.0, 0.35 + (len(overlap) / max(6, len(action_words))) * 1.5)
    rationale = "overlap with TELOS terms: " + (", ".join(sorted(overlap)) if overlap else "none")
    return TelosCheck(round(score, 2), rationale)
