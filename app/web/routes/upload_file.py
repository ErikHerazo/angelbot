from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.core import constants

router = APIRouter(
    prefix="/upload",
    tags=["upload"]
)

templates = Jinja2Templates(directory=constants.WEB_DIR / "templates")

@router.get("/file", response_class=HTMLResponse)
async def render_home(request: Request):
    return templates.TemplateResponse(
        "blob_upload.html",
        {"request": request}
    )
