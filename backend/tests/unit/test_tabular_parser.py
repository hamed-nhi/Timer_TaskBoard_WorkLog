"""Real file-format boundaries and exact-time parsing without a database."""
from datetime import datetime, time, timedelta
import io
import zipfile
import openpyxl
import pytest
from app.core.errors import ApiError
from app.services import tabular_parser as parser
from app.services.tabular_import import template


def workbook(rows, name='آبان 1405'):
    book=openpyxl.Workbook();sheet=book.active;sheet.title=name
    for row in rows:sheet.append(row)
    stream=io.BytesIO();book.save(stream);return stream.getvalue()


@pytest.mark.parametrize('format_', ['xlsx','csv'])
def test_downloadable_samples_are_valid_import_files(format_):
    content,_,_=template(format_)
    parsed=parser.parse_file(content,'sample.'+format_)
    assert not parsed['errors'] and len(parsed['rows'])==1
    row=parsed['rows'][0]
    assert row['duration']==90 and row['date']=='2026-10-25'
    assert row['project']=='پروژه نمونه' and row['fill']==0


def test_unicode_titles_and_fractional_minutes_remain_exact():
    content='date,title,duration_minutes,tag\n۱۴۰۵/۰۸/۰۳,مرحلهٔ ۱ با ي و ك,۰٫۵,تگ ۲\n'.encode('utf-8-sig')
    row=parser.parse_file(content,'x.csv')['rows'][0]
    assert row['title']=='مرحلهٔ ۱ با ي و ك' and row['tag']=='تگ ۲' and row['duration']==.5


def test_native_short_dates_use_worksheet_year_and_preserve_recorded_time():
    parsed=parser.parse_file(workbook([['تاریخ (ماه/روز)','شرح فعالیت','ساعت شروع','ساعت پایان','مدت (دقیقه)'],['08/03','کار',time(9),time(11),60.25]]),'old.xlsx')
    assert not parsed['errors'] and parsed['rows'][0]['duration']==60.25
    assert parsed['rows'][0]['date']=='2026-10-25' and len(parsed['warnings'])==1


def test_excel_dates_and_overnight_times_are_unambiguous():
    parsed=parser.parse_file(workbook([['date','title','start','end'],[datetime(2026,10,25),'شب','23:50','00:20']]),'x.xlsx')
    assert parsed['rows'][0]['duration']==30


@pytest.mark.parametrize('value,expected',[(time(2,30),150),(timedelta(hours=25),1500),('02:30',150),('0',0),('۱۲٫۲۵',12.25)])
def test_duration_formats(value,expected):
    assert parser.number(value)==expected


@pytest.mark.parametrize('value',['nan','inf','-1','10081','02:99',True])
def test_invalid_minutes_are_rejected(value):
    with pytest.raises(ApiError):parser.number(value)


@pytest.mark.parametrize('filename,content',[('x.xls',b'x'),('x.xlsx',b'broken'),('x.csv',b''),('x.csv',b'x'*(parser.MAX_BYTES+1))], ids=['xls','broken-xlsx','empty','oversize'])
def test_invalid_or_oversized_files_are_rejected(filename,content):
    with pytest.raises(ApiError):parser.parse_file(content,filename)


def test_formula_cells_are_not_evaluated_or_imported():
    with pytest.raises(ApiError,match='فرمول'):
        parser.parse_file(workbook([['date','title','duration'],['1405/08/03','=1+1',60]]),'x.xlsx')


def test_zip_expansion_is_bounded():
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('large.xml',b'a'*(51*1024*1024))
    with pytest.raises(ApiError,match='حجم'):parser.parse_file(stream.getvalue(),'x.xlsx')


def test_custom_mapping_and_missing_year_have_actionable_errors():
    content='when,what,length\n08/03,work,60\n'.encode()
    parsed=parser.parse_file(content,'x.csv',{'date':'when','title':'what','duration':'length'})
    assert parsed['errors'][0]['row']==2 and 'سال' in parsed['errors'][0]['message']
    parsed=parser.parse_file(content,'x.csv',{'date':'when','title':'what','duration':'length'},'۱۴۰۵')
    assert parsed['rows'][0]['date']=='2026-10-25'


@pytest.mark.parametrize('content',[
    'date,title,duration\ninvalid,x,1\n',
    'date,title,start\n1405/08/03,x,09:00\n',
    'date,title,duration,story\n1405/08/03,x,60,s\n',
    'date,title,duration,planned\n1405/08/03,x,60,maybe\n',
])
def test_bad_rows_report_their_source_line(content):
    result=parser.parse_file(content.encode(),'x.csv');assert result['errors'][0]['row']==2 and not result['rows']


def test_empty_duplicate_headers_and_invalid_mapping_fail_safely():
    for content,mapping in [(b'date,date,title\n1405/08/03,x,y\n',{}),(b'date,title\n',{'title':'absent'}),(b'date,title\n',[]),(b'',{})]:
        with pytest.raises(ApiError):parser.parse_file(content,'x.csv',mapping)


def test_encoding_and_delimiter_variants():
    for encoding,sep in [('utf-16',';'),('cp1256','\t')]:
        content=(f'date{sep}title{sep}duration\n1405/08/03{sep}کار{sep}60\n').encode(encoding)
        assert parser.parse_file(content,'x.csv')['rows'][0]['title']=='کار'


def test_errors_keep_physical_row_numbers_after_leading_blank_rows():
    content=b'\n\ndate,title,duration\ninvalid,work,60\n'
    parsed=parser.parse_file(content,'x.csv')
    assert parsed['errors'][0]['row']==4
