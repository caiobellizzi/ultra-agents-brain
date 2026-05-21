INGEST_CASES = [
    {
        "id": "ingest-1",
        "input": "https://example.com/article-about-vector-databases",
        "expected_note_path_prefix": "vault/02-Resources/articles/",
        "expected_min_tags": 1,
        "max_latency_seconds": 60,
    },
    {
        "id": "ingest-2",
        "input": "I spent 2 hours today learning about pgvector and hybrid search indexing.",
        "expected_note_path_prefix": "vault/",
        "expected_min_tags": 1,
        "max_latency_seconds": 60,
    },
    {
        "id": "ingest-3",
        "input": "Note: review the eval seed documentation before the next sprint.",
        "expected_note_path_prefix": "vault/Inbox/",
        "expected_min_tags": 0,
        "max_latency_seconds": 60,
    },
]
