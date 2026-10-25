"""Preview and atomically import finished tasks into the authenticated account only."""
import csv
from collections import Counter
from datetime import date
import hashlib
import io
import json

import openpyxl

from ..core.backup import fingerprint
from ..core.errors import ApiError
from ..core.time import g2j
from ..db.session import Db
from .catalog_helpers import import_catalog
from .tabular_parser import FIELDS, parse_file
from .timecalc import TASK_SELECT, company_type


def signature(row):
    return tuple(row.get(k) for k in ('date','title','start','end','duration','tag','project','story','report_type','fill','planned','outside','entered'))


def existing_data(db, uid):
    tags = db.execute('SELECT tags.*, projects.name AS project, stories.name AS story, report_types.name AS report_type '
                      'FROM tags LEFT JOIN stories ON tags.story_id=stories.id '
                      'LEFT JOIN projects ON stories.project_id=projects.id '
                      'LEFT JOIN report_types ON tags.report_type_id=report_types.id WHERE tags.user_id=?', (uid,)).fetchall()
    existing = Counter()
    for row in db.execute(TASK_SELECT + " WHERE tasks.user_id=? AND tasks.status='done'", (uid,)).fetchall():
        existing[signature({'date': row['gregorian_date'].isoformat(), 'title':row['title'],
            'start':row['start_time'], 'end':row['end_time'], 'duration':row['duration_minutes'],
            'tag':row['tag_name'] or '', 'project':row['tag_project'] or '', 'story':row['tag_story'] or '',
            'report_type':company_type(row) or '', 'fill':row['fill_minutes'] or 0,
            'planned':row['planned_flag'], 'outside':row['outside_company'], 'entered':row['entered_main_system']})] += 1
    return {row['name']:row for row in tags}, existing


def prepare(db, uid, content, filename, mapping, year):
    parsed = parse_file(content, filename, mapping, year)
    tags, seen = existing_data(db, uid)
    bindings = {name:(row['project'] or '', row['story'] or '') for name,row in tags.items()}
    source_revision = fingerprint({'user':uid,'file':hashlib.sha256(content).hexdigest(), 'mapping':parsed['mapping'],'year':year})
    already_imported = bool(db.execute("SELECT 1 FROM audit_log WHERE user_id=? AND kind='file_import' AND payload->>'source_revision'=? LIMIT 1", (uid,source_revision)).fetchone())
    parsed['source_revision'] = source_revision
    parsed['already_imported'] = already_imported
    occurrences = Counter()
    decisions = []
    for row in parsed['rows']:
        tag = tags.get(row['tag'])
        binding = bindings.get(row['tag'])
        if tag:
            if not row['project'] and not row['story']:
                row['project'], row['story'] = binding
            if not row['report_type']:
                row['report_type'] = tag['report_type'] or ''
        if not already_imported and row['tag'] and binding is not None and binding != (row['project'],row['story']):
            parsed['errors'].append({'sheet':row['sheet'],'row':row['row'],
                                     'message':'این تگ به پروژه یا استوری دیگری متصل است؛ نام تگ جدا انتخاب کنید'})
        if row['tag']:
            bindings.setdefault(row['tag'], (row['project'],row['story']))
        key = signature(row)
        occurrences[key] += 1
        row['duplicate'] = already_imported or occurrences[key] <= seen[key]
        decisions.append({'record':row,'duplicate':row['duplicate']})
    parsed['revision'] = fingerprint({'user':uid,'file':hashlib.sha256(content).hexdigest(),
                                     'mapping':parsed['mapping'],'year':year,'decisions':decisions,'errors':parsed['errors']})
    return parsed


def public_preview(parsed):
    rows=parsed['rows']
    return {k:parsed[k] for k in ('columns','mapping','fields','revision','total_rows')} | {
        'preview':rows[:50], 'errors':parsed['errors'][:200], 'error_count':len(parsed['errors']),
        'warnings':parsed['warnings'][:100], 'warning_count':len(parsed['warnings']),
        'new_rows':sum(not row['duplicate'] for row in rows), 'duplicate_rows':sum(row['duplicate'] for row in rows),
        'new_minutes':sum(row['duration'] for row in rows if not row['duplicate']),
    }


def preview(db: Db, user: dict, content: bytes, filename: str, mapping=None, year=None):
    return public_preview(prepare(db,user['id'],content,filename,mapping,year))


def apply_import(db: Db, user: dict, content: bytes, filename: str, mapping, year, revision):
    uid=user['id']
    db.lock_user(uid)
    parsed=prepare(db,uid,content,filename,mapping,year)
    if parsed['already_imported'] and not parsed['errors']:
        db.commit()
        return {'imported':0,'duplicates':len(parsed['rows']),'minutes':0,'already_imported':True}
    if revision != parsed['revision']:
        raise ApiError('فایل، نگاشت یا داده‌های حساب تغییر کرده است؛ پیش‌نمایش را دوباره بگیرید',409)
    if parsed['errors'] or not parsed['total_rows']:
        raise ApiError('تا رفع خطاهای فایل هیچ ردیفی وارد نمی‌شود')
    new=[r for r in parsed['rows'] if not r['duplicate']]
    types=sorted({r['report_type'] for r in new if r['report_type']})
    projects={}
    for row in new:
        if row['project']:
            projects.setdefault(row['project'],set()).add(row['story'])
    import_catalog(db,uid,{'types':types,'projects':projects})
    type_ids={r['name']:r['id'] for r in db.execute('SELECT id,name FROM report_types WHERE user_id=?',(uid,)).fetchall()}
    story_ids={(r['project'],r['name']):r['id'] for r in db.execute(
        'SELECT stories.id,stories.name,projects.name AS project FROM stories '
        'JOIN projects ON stories.project_id=projects.id WHERE stories.user_id=?',(uid,)).fetchall()}
    tags={r['name']:r['id'] for r in db.execute('SELECT id,name FROM tags WHERE user_id=?',(uid,)).fetchall()}
    for row in new:
        if row['tag'] and row['tag'] not in tags:
            tags[row['tag']]=db.insert('INSERT INTO tags (user_id,name,story_id) VALUES (?,?,?)',
                (uid,row['tag'],story_ids.get((row['project'],row['story']))))
        day=date.fromisoformat(row['date']);j=g2j(day)
        db.execute('INSERT INTO tasks (user_id,jalali_year,jalali_month,jalali_day,gregorian_date,title,'
                   'start_time,end_time,duration_minutes,status,accumulated_minutes,tag_id,report_type_id,'
                   'fill_minutes,planned_flag,outside_company,entered_main_system) '
                   "VALUES (?,?,?,?,?,?,?,?,?,'done',?,?,?,?,?,?,?)",
                   (uid,j.year,j.month,j.day,day,row['title'],row['start'],row['end'],row['duration'],row['duration'],
                    tags.get(row['tag']),type_ids.get(row['report_type']),row['fill'],row['planned'],row['outside'],row['entered']))
    if new:
        db.execute("INSERT INTO audit_log (user_id,kind,payload) VALUES (?,'file_import',?::jsonb)",
                   (uid,json.dumps({'file_sha256':hashlib.sha256(content).hexdigest(),'source_revision':parsed['source_revision'],'imported':len(new),
                                    'minutes':sum(r['duration'] for r in new)})))
    db.commit()
    return {'imported':len(new),'duplicates':len(parsed['rows'])-len(new),'minutes':sum(r['duration'] for r in new)}


def template(format_):
    headers=[FIELDS[k][0] for k in FIELDS]
    example=['1405/08/03','نمونه: بررسی و توسعه','09:00','10:30',90,'توسعه','پروژه نمونه','استوری نمونه','کار فنی',0,'خیر','خیر','خیر']
    if format_=='txt':
        guide='''داده‌های ثبت زمان من را به یک CSV با کدگذاری UTF-8 تبدیل کن؛ فقط فایل تبدیل‌شده و فهرست ابهام‌ها را بده.
ستون‌ها دقیقاً این‌ها باشند:
'''+','.join(headers)+'''
تاریخ: YYYY/MM/DD شمسی یا YYYY-MM-DD میلادی؛ سال را حدس نزن. مثال: 1405/08/03.
ساعت شروع و پایان: HH:MM با ارقام لاتین. مدت: عدد دقیقهٔ واقعی ثبت‌شده، نه ساعت اعشاری.
اگر ساعت‌ها موجود نیستند هر دو خالی باشند و مدت دقیق وارد شود. مدت وقفه‌ها را دوباره به مدت کار اضافه نکن.
عنوان و نام تگ، پروژه و استوری را از منبع حفظ کن. نام پروژه برای استوری الزامی است.
تکمیلی در ستون جداست؛ آن را به مدت واقعی اضافه نکن. اگر منبع تکمیلی ندارد، صفر بگذار.
ستون‌های بله/خیر را با بله یا خیر پر کن. شناسه و نام کاربری لازم نیست.
فقط تسک‌های تمام‌شده را منتقل کن. حضور، وقفه‌ها و برنامه‌های آینده قالب جدا دارند و در این فایل پشتیبانی نمی‌شوند.
داده، تاریخ و زمان نامعلوم را اختراع نکن؛ ردیف‌های مبهم را برای بررسی جدا اعلام کن.
ردیف نمونه را وارد خروجی نکن. تمام ردیف‌های واقعی را حفظ کن و دقیقه‌ها را گرد نکن.
'''
        return guide.encode('utf-8'),'text/plain; charset=utf-8','timelog-import-guide.fa.txt'
    if format_=='csv':
        stream=io.StringIO(newline='');writer=csv.writer(stream);writer.writerow(headers);writer.writerow(example)
        return stream.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8','timelog-import-template.csv'
    if format_!='xlsx':
        raise ApiError('قالب نمونه نامعتبر است')
    book=openpyxl.Workbook();sheet=book.active;sheet.title='نمونه 1405';sheet.sheet_view.rightToLeft=True
    sheet.append(headers);sheet.append(example);sheet.freeze_panes='A2'
    for cells in sheet.columns:
        sheet.column_dimensions[cells[0].column_letter].width=24
    stream=io.BytesIO();book.save(stream)
    return stream.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','timelog-import-template.xlsx'
