"""Punto de entrada de la aplicación FastAPI."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.notificaciones import advertir_si_falta_configuracion



@asynccontextmanager
async def lifespan(app: FastAPI):
    advertir_si_falta_configuracion()
    yield


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

# Permite que el frontend (otro origen/puerto) llame a la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"app_name": settings.APP_NAME})
