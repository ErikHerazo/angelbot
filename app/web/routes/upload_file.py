from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent

templates = Jinja2Templates(directory="templates")

@router.get("/upload-file", response_class=HTMLResponse)
async def render_home(request: Request):
    return templates.TemplateResponse(
        "upload.html",
        {"request": request}
    )
