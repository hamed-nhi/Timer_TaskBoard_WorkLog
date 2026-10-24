from typing import Annotated

from fastapi import Depends

from .auth import current_user, require_admin
from .db import Db, get_db

DbDep = Annotated[Db, Depends(get_db)]
UserDep = Annotated[dict, Depends(current_user)]
AdminDep = Annotated[dict, Depends(require_admin)]
