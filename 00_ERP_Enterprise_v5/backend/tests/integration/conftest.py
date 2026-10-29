import os
import re

import pytest
from sqlalchemy.engine import make_url


@pytest.fixture(scope="module", autouse=True)
def require_explicit_disposable_postgres_target():
    database_url = os.getenv("PHASE13_DATABASE_URL")
    if not database_url:
        return
    if os.getenv("PHASE13_ALLOW_DATABASE_RESET") != "1":
        pytest.fail(
            "PostgreSQL integration tests reset public schema. Set "
            "PHASE13_ALLOW_DATABASE_RESET=1 only for a dedicated disposable database.",
            pytrace=False,
        )
    try:
        database_name = make_url(database_url).database or ""
    except Exception as exc:
        pytest.fail(
            "PHASE13_DATABASE_URL is invalid; refusing destructive test setup.",
            pytrace=False,
        )
    if not re.search(r"(^|[_-])(test|testing|e2e|ci)([_-]|$)", database_name, re.IGNORECASE):
        pytest.fail(
            "PHASE13_DATABASE_URL must target a database whose name contains "
            "a delimited test, testing, e2e, or ci segment.",
            pytrace=False,
        )
