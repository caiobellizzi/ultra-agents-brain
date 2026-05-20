"""Typed Pydantic result models for all AgentOS agents."""

from pydantic import BaseModel


class VaultCitation(BaseModel):
    path: str
    title: str
    tags: list[str] = []
    excerpt: str = ""


class ChatReply(BaseModel):
    text: str
    citations: list[VaultCitation] = []
    suggested_actions: list[str] = []


class QueryAnswer(BaseModel):
    answer: str
    citations: list[VaultCitation] = []
    confidence: float = 1.0


class IngestResult(BaseModel):
    note_path: str
    frontmatter: dict = {}
    tags: list[str] = []
    needs_review: bool = False


class Finding(BaseModel):
    summary: str
    source: str = ""


class ResearchReport(BaseModel):
    topic: str
    findings: list[Finding] = []
    next_questions: list[str] = []


class CuratorResult(BaseModel):
    actions_taken: list[str] = []
    notes_touched: list[str] = []
    errors: list[str] = []


class SupervisorRouting(BaseModel):
    chosen_member: str
    reason: str = ""
    response: str = ""
