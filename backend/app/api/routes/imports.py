"""Upload, preview and commit private task-history imports."""
import json
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response
from ..dependencies import DbDep, UserDep
from ...core.errors import ApiError
from ...services import tabular_import as service
from ...services.tabular_parser import MAX_BYTES

router=APIRouter(prefix='/api/me/import')


def fields(file, mapping, year):
    content=file.file.read(MAX_BYTES+1)
    try:
        selected=json.loads(mapping)
    except (ValueError,TypeError):
        raise ApiError('نگاشت ستون‌ها نامعتبر است')
    return content,file.filename or '',selected,year or None


@router.post('/preview')
def import_preview(db: DbDep,user: UserDep,file: UploadFile=File(...),mapping: str=Form('{}'),year: str=Form('')):
    return service.preview(db,user,*fields(file,mapping,year))


@router.post('/commit')
def import_commit(db: DbDep,user: UserDep,file: UploadFile=File(...),mapping: str=Form('{}'),year: str=Form(''),revision: str=Form(...)):
    return service.apply_import(db,user,*fields(file,mapping,year),revision)


@router.get('/template/{format_}')
def import_template(user: UserDep,format_: str):
    content,media,filename=service.template(format_)
    return Response(content,media_type=media,headers={'Content-Disposition':f'attachment; filename="{filename}"'})
