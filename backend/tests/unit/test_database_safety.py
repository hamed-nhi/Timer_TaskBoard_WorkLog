import pytest
from tests.database_safety import disposable_database

@pytest.mark.parametrize('url',[None,'postgresql://x@localhost/timelog','postgresql://x@localhost/timelog_audit_test','postgresql://x@localhost/timelog_system_test','postgresql://x@localhost/timelog_preserve_old_test','sqlite:///safe_test'])
def test_schema_reset_refuses_unsafe_or_implicit_targets(url):
    with pytest.raises(RuntimeError):disposable_database(url)


def test_verified_separate_postgresql_test_database_is_allowed():
    assert disposable_database('postgresql+psycopg://x@localhost/timelog_audit_integration_test')=='timelog_audit_integration_test'
