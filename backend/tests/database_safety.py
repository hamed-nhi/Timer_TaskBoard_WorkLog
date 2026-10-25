"""Explicit guard for schema-destroying integration fixtures."""
from sqlalchemy.engine import make_url


def disposable_database(url):
    if not url:
        raise RuntimeError('Set TEST_DATABASE_URL explicitly to a verified disposable PostgreSQL database')
    parsed=make_url(url)
    name=parsed.database or ''
    protected=name in {'timelog_audit_test','timelog_system_test'} or name.startswith(('timelog_preserve_','timelog_audit_restore_'))
    if parsed.get_backend_name()!='postgresql' or not name.endswith('_test') or protected:
        raise RuntimeError('Refusing destructive tests on a non-disposable or protected database')
    return name
