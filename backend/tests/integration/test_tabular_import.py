"""Account-private, atomic, repeatable import against real PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from tests.support import Client, sql

CONTENT='date,title,start,end,duration_minutes,tag,project,story,report_type,fill_minutes\n1405/08/03,کار,09:00,11:00,60.25,برچسب,پروژه,استوری,فنی,5\n'.encode('utf-8-sig')


def request(client,action,content=CONTENT,revision=None,filename='history.csv',mapping=None,year=''):
    data={'mapping':json.dumps(mapping or {}),'year':year}
    if revision is not None:data['revision']=revision
    return client.post('/api/me/import/'+action,files={'file':(filename,content)},data=data)


def test_preview_is_read_only_then_commit_preserves_source_and_catalog(alice,bob,admin):
    result=request(alice,'preview');assert result.status_code==200,result.text
    preview=result.get_json();assert preview['new_rows']==1 and preview['new_minutes']==60.25
    assert not sql('SELECT * FROM tasks') and not sql('SELECT * FROM tags')
    result=request(alice,'commit',revision=preview['revision']);assert result.status_code==200,result.text
    assert result.get_json()['imported']==1
    task=alice.get('/api/tasks').get_json()[0]
    assert task['duration_minutes']==60.25 and task['fill_minutes']==5 and task['status']=='done'
    assert task['start_time']=='09:00' and task['end_time']=='11:00'
    assert task['company_project']=='پروژه' and task['company_story']=='استوری'
    assert bob.get('/api/tasks').get_json()==[] and admin.get('/api/tasks').get_json()==[]
    assert bob.get('/api/catalog').get_json()['projects']==[]


def test_repeat_upload_is_a_noop_with_no_new_audit_or_rows(alice):
    first=request(alice,'preview').get_json();assert request(alice,'commit',revision=first['revision']).status_code==200
    before=sql('SELECT count(*) c FROM audit_log')[0]['c']
    again=request(alice,'preview').get_json();assert again['new_rows']==0 and again['duplicate_rows']==1
    assert request(alice,'commit',revision=again['revision']).get_json()['imported']==0
    assert sql('SELECT count(*) c FROM audit_log')[0]['c']==before
    assert sql('SELECT count(*) c FROM tasks')[0]['c']==1


def test_new_file_does_not_overwrite_an_existing_record(alice):
    first=request(alice,'preview').get_json();request(alice,'commit',revision=first['revision'])
    changed=CONTENT.replace('کار'.encode(), 'کار جدید'.encode())
    second=request(alice,'preview',changed).get_json();assert second['new_rows']==1
    assert request(alice,'commit',changed,revision=second['revision']).status_code==200
    assert [r['title'] for r in sql('SELECT title FROM tasks ORDER BY id')]==['کار','کار جدید']


def test_one_bad_row_blocks_the_entire_batch(alice):
    content=CONTENT+b'invalid,bad,09:00,10:00,60,,,,,0\n'
    preview=request(alice,'preview',content).get_json();assert preview['error_count']==1
    result=request(alice,'commit',content,revision=preview['revision']);assert result.status_code==400
    assert not sql('SELECT * FROM tasks') and not sql('SELECT * FROM tags')


def test_modified_file_wrong_account_and_stale_preview_are_rejected(alice,bob):
    preview=request(alice,'preview').get_json()
    assert request(bob,'commit',revision=preview['revision']).status_code==409
    assert request(alice,'commit',CONTENT.replace(b'60.25',b'62'),revision=preview['revision']).status_code==409
    assert request(alice,'commit',revision=preview['revision']).status_code==200
    assert request(alice,'commit',revision=preview['revision']).get_json()['already_imported'] is True
    assert sql('SELECT count(*) c FROM tasks')[0]['c']==1


def test_parallel_import_commits_only_once(alice):
    revision=request(alice,'preview').get_json()['revision']
    clients=[]
    for _ in range(3):
        client=Client();client.http.cookies.update(alice.http.cookies);clients.append(client)
    with ThreadPoolExecutor(max_workers=3) as pool:responses=list(pool.map(lambda c:request(c,'commit',revision=revision),clients))
    assert all(r.status_code==200 for r in responses)
    assert sum(r.get_json()['imported'] for r in responses)==1
    assert sql('SELECT count(*) c FROM tasks')[0]['c']==1


def test_own_native_excel_export_roundtrips_to_another_account(alice,bob):
    preview=request(alice,'preview').get_json();request(alice,'commit',revision=preview['revision'])
    exported=alice.get('/api/export').content
    p=request(bob,'preview',exported,filename='desktop.xlsx').get_json();assert p['new_rows']==1 and not p['errors']
    assert request(bob,'commit',exported,filename='desktop.xlsx',revision=p['revision']).status_code==200
    a=alice.get('/api/tasks').get_json()[0];b=bob.get('/api/tasks').get_json()[0]
    for key in ('title','duration_minutes','fill_minutes','company_story','company_project','start_time','end_time'):assert a[key]==b[key]
    assert a['user_id']!=b['user_id']


def test_import_never_retags_existing_records(alice):
    tag=alice.post('/api/tags',json={'name':'برچسب'}).get_json()
    before=sql('SELECT * FROM tags')
    p=request(alice,'preview').get_json();assert p['error_count']==1
    assert request(alice,'commit',revision=p['revision']).status_code==400
    assert sql('SELECT * FROM tags')==before and not sql('SELECT * FROM tasks')


@pytest.mark.parametrize('format_', ['xlsx','csv','txt'])
def test_templates_require_login_and_can_be_downloaded(alice,format_):
    assert Client().get('/api/me/import/template/'+format_).status_code==401
    result=alice.get('/api/me/import/template/'+format_);assert result.status_code==200 and result.content
    assert 'no-store' in result.headers['cache-control']


def test_import_upload_requires_csrf_header(alice):
    alice.http.headers.pop('X-Requested-With')
    assert request(alice,'preview').status_code==403
    assert not sql('SELECT * FROM tasks')


def test_identical_source_rows_keep_multiplicity_and_exact_totals(alice):
    content=b'date,title,duration\n1405/08/03,work,60.25\n1405/08/03,work,60.25\n'
    preview=request(alice,'preview',content).get_json();assert preview['new_rows']==2
    assert request(alice,'commit',content,revision=preview['revision']).get_json()['imported']==2
    assert sql('SELECT sum(duration_minutes) total FROM tasks')[0]['total']==120.5
    again=request(alice,'preview',content).get_json();assert again['new_rows']==0 and again['duplicate_rows']==2


def test_same_file_does_not_resurrect_a_record_edited_after_import(alice):
    p=request(alice,'preview').get_json();request(alice,'commit',revision=p['revision'])
    task=alice.get('/api/tasks').get_json()[0]
    assert alice.put(f"/api/tasks/{task['id']}",json={'title':'edited by owner'}).status_code==200
    p=request(alice,'preview').get_json();assert p['new_rows']==0
    assert request(alice,'commit',revision=p['revision']).get_json()['imported']==0
    assert sql('SELECT title FROM tasks')[0]['title']=='edited by owner'


def test_imported_duration_only_tasks_can_be_renamed_without_inventing_times(alice):
    content=b'date,title,duration\n1405/08/03,work,60.25\n'
    p=request(alice,'preview',content).get_json();request(alice,'commit',content,revision=p['revision'])
    task=alice.get('/api/tasks').get_json()[0]
    result=alice.put(f"/api/tasks/{task['id']}",json={'title':'renamed'})
    assert result.status_code==200
    task=result.get_json();assert task['duration_minutes']==60.25 and task['start_time'] is None and task['end_time'] is None


def test_renaming_imported_time_disagreement_never_repairs_the_source(alice):
    content=CONTENT.replace(b'60.25',b'180.25')
    p=request(alice,'preview',content).get_json();request(alice,'commit',content,revision=p['revision'])
    task=alice.get('/api/tasks').get_json()[0]
    result=alice.put(f"/api/tasks/{task['id']}",json={'title':'renamed'})
    assert result.status_code==200 and result.get_json()['duration_minutes']==180.25


def test_stale_device_cannot_overwrite_a_newer_task_edit(alice):
    task=alice.post('/api/tasks',json={'title':'before','start_time':'09:00','end_time':'10:00'}).get_json()
    first=alice.put(f"/api/tasks/{task['id']}",json={'title':'desktop','_revision':task['revision']})
    assert first.status_code==200
    stale=alice.put(f"/api/tasks/{task['id']}",json={'title':'phone stale','_revision':task['revision']})
    assert stale.status_code==409
    current=alice.get('/api/tasks').get_json()[0]
    assert current['title']=='desktop' and current['duration_minutes']==60
    assert alice.put(f"/api/tasks/{task['id']}",json={'title':'fresh phone','_revision':current['revision']}).status_code==200


def test_metadata_edit_keeps_all_imported_fractional_precision(alice):
    content=b'date,title,duration\n1405/08/03,work,60.12345\n'
    p=request(alice,'preview',content).get_json();request(alice,'commit',content,revision=p['revision'])
    task=alice.get('/api/tasks').get_json()[0]
    response=alice.put(f"/api/tasks/{task['id']}",json={'title':'metadata only'})
    assert response.status_code==200
    assert response.get_json()['duration_minutes']==60.12345
    assert response.get_json()['accumulated_minutes']==60.12345
