SUPERVISOR_CASES = [
    {
        "id": "supervisor-1",
        "input": "/query what is in my vault about vector databases?",
        "expected_agent": "query",
        "max_latency_seconds": 20,
    },
    {
        "id": "supervisor-2",
        "input": "/research AI agent memory architectures",
        "expected_agent": "research",
        "max_latency_seconds": 20,
    },
    {
        "id": "supervisor-3",
        "input": "/ingest https://example.com/page",
        "expected_agent": "ingest",
        "max_latency_seconds": 20,
    },
]
