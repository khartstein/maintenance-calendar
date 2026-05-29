from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers.auth import router as auth_router
from .routers.calendar import router as calendar_router
from .routers.items import router as items_router
from .routers.settings import router as settings_router

app = FastAPI(title="Maintenance Calendar")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(items_router)
app.include_router(auth_router)
app.include_router(calendar_router)
app.include_router(settings_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
