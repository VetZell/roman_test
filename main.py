
import os

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
)
from app.routers.users import router as users_router
from app.websocket import (
    manager,
    websocket_endpoint,
)
from app.routers.messages import router as messages_router
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from models import Message, User
from database import (
    Base,
    SessionLocal,
    engine,
    get_database,
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Roman Messenger",
    lifespan=lifespan,
)
app.include_router(users_router)
app.include_router(messages_router)
app.websocket("/ws")(websocket_endpoint)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


class TelegramAuthRequest(BaseModel):
    init_data: str

@app.get("/health/database")
def database_health(
    database: Session = Depends(get_database),
):
    database.execute(select(1))

    return {
        "status": "ok",
        "database": "PostgreSQL",
    }

    
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
    )