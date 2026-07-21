import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.routers.messages import router as messages_router
from app.routers.users import router as users_router
from app.websocket import websocket_endpoint
from database import Base, engine, get_database


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def migrate_message_receipts() -> None:
    statements = [
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_delivered BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP NULL",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_read BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_at TIMESTAMP NULL",
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_message_receipts()
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
