QUERY_CASES = [
    {
        "id": "query-1",
        "input": "What does the eval seed note say about hybrid search?",
        "expected_answer_contains": ["hybrid", "search"],
        "expected_citations_have_tag": "eval-seed",
        "max_latency_seconds": 20,
    },
    {
        "id": "query-2",
        "input": "What embedding model is used for local vector search?",
        "expected_answer_contains": ["MiniLM", "sentence"],
        "expected_citations_have_tag": "eval-seed",
        "max_latency_seconds": 20,
    },
    {
        "id": "query-3",
        "input": "What topics are covered in my engineering knowledge area?",
        "expected_answer_contains": [],
        "expected_citations_have_tag": None,
        "max_latency_seconds": 20,
    },
]
