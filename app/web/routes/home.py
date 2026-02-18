from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.core import constants

router = APIRouter(
    prefix="/web/chat",
    tags=["frontend"]
)

BASE_DIR = Path(__file__).resolve().parent.parent

templates = Jinja2Templates(directory=constants.WEB_DIR / "templates")

@router.get("/", response_class=HTMLResponse)
async def render_home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request}
    )
