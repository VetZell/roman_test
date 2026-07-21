
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

class MessagesRequest(BaseModel):
    init_data: str
    user_id: int


class SendMessageRequest(BaseModel):
    init_data: str
    receiver_id: int

    text: str = Field(
        min_length=1,
        max_length=4000,
    )


@app.get("/health/database")
def database_health(
    database: Session = Depends(get_database),
):
    database.execute(select(1))

    return {
        "status": "ok",
        "database": "PostgreSQL",
    }



@app.post("/api/messages")
def get_messages(
    request: MessagesRequest,
    database: Session = Depends(get_database),
):
    telegram_user = validate_telegram_init_data(
        request.init_data
    )

    current_user = create_or_update_user(
        telegram_user,
        database,
    )

    other_user = database.get(
        User,
        request.user_id,
    )

    if other_user is None:
        raise HTTPException(
            status_code=404,
            detail="Пользователь не найден",
        )

    messages = database.scalars(
        select(Message)
        .where(
            or_(
                and_(
                    Message.sender_id == current_user.id,
                    Message.receiver_id == other_user.id,
                ),
                and_(
                    Message.sender_id == other_user.id,
                    Message.receiver_id == current_user.id,
                ),
            )
        )
        .order_by(
            Message.created_at.asc(),
            Message.id.asc(),
        )
        .limit(500)
    ).all()

    return {
        "ok": True,
        "messages": [
            {
                "id": message.id,
                "sender_id": message.sender_id,
                "receiver_id": message.receiver_id,
                "text": message.text,
                "created_at": message.created_at.isoformat(),
            }
            for message in messages
        ],
    }


@app.post("/api/messages/send")
async def send_message(
    request: SendMessageRequest,
    database: Session = Depends(get_database),
):
    telegram_user = validate_telegram_init_data(
        request.init_data
    )

    current_user = create_or_update_user(
        telegram_user,
        database,
    )

    receiver = database.get(
        User,
        request.receiver_id,
    )

    if receiver is None:
        raise HTTPException(
            status_code=404,
            detail="Получатель не найден",
        )

    if receiver.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Нельзя отправить сообщение самому себе",
        )

    clean_text = request.text.strip()

    if not clean_text:
        raise HTTPException(
            status_code=400,
            detail="Сообщение не может быть пустым",
        )

    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver.id,
        text=clean_text,
    )

    database.add(message)
    database.commit()
    database.refresh(message)

    message_data = {
        "id": message.id,
        "sender_id": message.sender_id,
        "receiver_id": message.receiver_id,
        "text": message.text,
        "created_at": message.created_at.isoformat(),
    }

    await manager.send_to_user(
        receiver.id,
        {
            "type": "new_message",
            "message": message_data,
        },
    )

    return {
        "ok": True,
        "message": message_data,
    }
    
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
    )