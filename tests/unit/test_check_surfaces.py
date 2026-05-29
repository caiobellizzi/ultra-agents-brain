"""Unit tests for check_surfaces DSN normalizer."""


def _normalize_dsn(dsn: str) -> str:
    """Copy of the helper in check_surfaces.py."""
    if "://" in dsn and "+" in dsn.split("://")[0]:
        scheme, rest = dsn.split("://", 1)
        scheme = scheme.split("+")[0]
        return f"{scheme}://{rest}"
    return dsn


def test_strips_psycopg_dialect() -> None:
    assert _normalize_dsn("postgresql+psycopg://user:pass@localhost/db") == "postgresql://user:pass@localhost/db"


def test_strips_psycopg2_dialect() -> None:
    assert _normalize_dsn("postgresql+psycopg2://user:pass@localhost/db") == "postgresql://user:pass@localhost/db"


def test_passthrough_plain_uri() -> None:
    assert _normalize_dsn("postgresql://user:pass@localhost/db") == "postgresql://user:pass@localhost/db"


def test_passthrough_connection_string() -> None:
    assert _normalize_dsn("host=localhost dbname=mydb user=u") == "host=localhost dbname=mydb user=u"
