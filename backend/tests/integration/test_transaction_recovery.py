"""Interrupted database transactions cannot leave half-written personal records."""
import psycopg
from app.core.config import settings
from tests.support import sql


def test_backend_disconnect_rolls_back_uncommitted_write(alice):
    database = settings.database_url.replace('postgresql+psycopg://', 'postgresql://')
    connection = psycopg.connect(database)
    try:
        name = connection.execute('SELECT current_database()').fetchone()[0]
        assert name.endswith('_test') and name != 'timelog_audit_test'
        pid = connection.execute('SELECT pg_backend_pid()').fetchone()[0]
        uid = sql("SELECT id FROM users WHERE username='alice'")[0]['id']
        connection.execute("INSERT INTO planned_tasks (user_id,jalali_year,jalali_month,jalali_day,title) VALUES (%s,1405,8,3,'uncommitted interruption')", (uid,))
        assert sql('SELECT pg_terminate_backend(:pid) terminated', pid=pid)[0]['terminated']
    finally:
        connection.close()
    assert sql("SELECT count(*) c FROM planned_tasks WHERE title='uncommitted interruption'")[0]['c'] == 0
    assert alice.post('/api/planned', json={'title':'healthy subsequent request'}).status_code == 201
    assert sql('SELECT count(*) c FROM planned_tasks')[0]['c'] == 1
