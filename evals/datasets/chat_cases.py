CHAT_CASES = [
    {
        "id": "chat-1",
        "input": "What is PgVector and how does hybrid search work?",
        "expected_text_contains": ["vector", "search"],
        "expected_citations_have_tag": "eval-seed",
        "max_latency_seconds": 30,
    },
    {
        "id": "chat-2",
        "input": "What areas of knowledge do I track in my vault?",
        "expected_text_contains": ["areas", "knowledge"],
        "expected_citations_have_tag": None,
        "max_latency_seconds": 30,
    },
    {
        "id": "chat-3",
        "input": "Can you summarize what I know about AI tooling?",
        "expected_text_contains": ["AI", "tool"],
        "expected_citations_have_tag": None,
        "max_latency_seconds": 30,
    },
]
