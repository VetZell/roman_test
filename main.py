import hashlib
import hmac
import json
import asyncio
import os
import secrets
import string
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from models import Message, User
from database import Base, engine, get_database
from app.auth import (
    create_or_update_user,
    validate_telegram_init_data,
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "В Railway не задана переменная BOT_TOKEN"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Roman Messenger",
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


class TelegramAuthRequest(BaseModel):
    init_data: str


def validate_telegram_init_data(
    init_data: str,
    max_age_seconds: int = 3600,
) -> dict:
    if not init_data:
        raise HTTPException(
            status_code=401,
            detail="Приложение открыто не из Telegram",
        )

    parsed_data = dict(
        parse_qsl(
            init_data,
            keep_blank_values=True,
        )
    )

    received_hash = parsed_data.pop("hash", None)

    if not received_hash:
        raise HTTPException(
            status_code=401,
            detail="Подпись Telegram отсутствует",
        )

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(parsed_data.items())
    )

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=BOT_TOKEN.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        calculated_hash,
        received_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Подпись Telegram недействительна",
        )

    auth_date_text = parsed_data.get("auth_date")

    try:
        auth_date = int(auth_date_text or "0")
    except ValueError as error:
        raise HTTPException(
            status_code=401,
            detail="Неверное время авторизации",
        ) from error

    if int(time.time()) - auth_date > max_age_seconds:
        raise HTTPException(
            status_code=401,
            detail="Авторизация устарела",
        )

    user_json = parsed_data.get("user")

    if not user_json:
        raise HTTPException(
            status_code=401,
            detail="Пользователь Telegram не найден",
        )

    try:
        user = json.loads(user_json)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=401,
            detail="Повреждены данные пользователя",
        ) from error

    return user


def generate_messenger_code() -> str:
    alphabet = string.ascii_uppercase + string.digits

    return "RM-" + "".join(
        secrets.choice(alphabet)
        for _ in range(6)
    )


def get_unique_messenger_code(
    database: Session,
) -> str:
    while True:
        code = generate_messenger_code()

        existing_user = database.scalar(
            select(User).where(
                User.messenger_code == code
            )
        )

        if existing_user is None:
            return code


def create_or_update_user(
    telegram_user: dict,
    database: Session,
) -> User:
    telegram_id = telegram_user.get("id")

    if not telegram_id:
        raise HTTPException(
            status_code=400,
            detail="Telegram ID отсутствует",
        )

    user = database.scalar(
        select(User).where(
            User.telegram_id == telegram_id
        )
    )

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=telegram_user.get("username"),
            first_name=(
                telegram_user.get("first_name")
                or "Пользователь"
            ),
            last_name=telegram_user.get("last_name"),
            photo_url=telegram_user.get("photo_url"),
            language_code=telegram_user.get(
                "language_code"
            ),
            messenger_code=get_unique_messenger_code(
                database
            ),
        )

        database.add(user)

    else:
        user.username = telegram_user.get("username")
        user.first_name = (
            telegram_user.get("first_name")
            or user.first_name
        )
        user.last_name = telegram_user.get("last_name")
        user.photo_url = telegram_user.get("photo_url")
        user.language_code = telegram_user.get(
            "language_code"
        )

    database.commit()
    database.refresh(user)

    return user

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

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[
            int,
            list[WebSocket],
        ] = {}

    async def connect(
        self,
        user_id: int,
        websocket: WebSocket,
    ):
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = []

        self.active_connections[user_id].append(
            websocket
        )

    def disconnect(
        self,
        user_id: int,
        websocket: WebSocket,
    ):
        connections = self.active_connections.get(
            user_id,
            [],
        )

        if websocket in connections:
            connections.remove(websocket)

        if not connections:
            self.active_connections.pop(
                user_id,
                None,
            )

    async def send_to_user(
        self,
        user_id: int,
        data: dict,
    ):
        connections = self.active_connections.get(
            user_id,
            [],
        )

        disconnected = []

        for connection in connections:
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(
                user_id,
                connection,
            )


manager = ConnectionManager()

@app.get("/")
async def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Roman Messenger",
    }


@app.get("/health/database")
def database_health(
    database: Session = Depends(get_database),
):
    database.execute(select(1))

    return {
        "status": "ok",
        "database": "PostgreSQL",
    }


@app.post("/api/auth/telegram")
def telegram_auth(
    request: TelegramAuthRequest,
    database: Session = Depends(get_database),
):
    telegram_user = validate_telegram_init_data(
        request.init_data
    )

    user = create_or_update_user(
        telegram_user,
        database,
    )

    return {
        "ok": True,
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "photo_url": user.photo_url,
            "language_code": user.language_code,
            "messenger_code": user.messenger_code,
        },
    }

@app.post("/api/users")
def get_users(
    request: TelegramAuthRequest,
    database: Session = Depends(get_database),
):
    telegram_user = validate_telegram_init_data(
        request.init_data
    )

    current_user = create_or_update_user(
        telegram_user,
        database,
    )

    users = database.scalars(
        select(User)
        .where(
            User.id != current_user.id,
            User.is_active.is_(True),
        )
        .order_by(User.first_name.asc())
        .limit(100)
    ).all()

    return {
        "ok": True,
        "users": [
            {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "photo_url": user.photo_url,
                "messenger_code": user.messenger_code,
            }
            for user in users
        ],
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
    
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):
    init_data = websocket.query_params.get(
        "init_data"
    )

    if not init_data:
        await websocket.close(
            code=1008,
            reason="Telegram initData отсутствует",
        )
        return

    database = SessionLocal()

    try:
        telegram_user = validate_telegram_init_data(
            init_data
        )

        current_user = create_or_update_user(
            telegram_user,
            database,
        )

        user_id = current_user.id

        await manager.connect(
            user_id,
            websocket,
        )

        await websocket.send_json(
            {
                "type": "connected",
                "user_id": user_id,
            }
        )

        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30,
                )

                if data == "ping":
                    await websocket.send_text(
                        "pong"
                    )

            except asyncio.TimeoutError:
                await websocket.send_text(
                    "ping"
                )

    except WebSocketDisconnect:
        pass

    except Exception:
        try:
            await websocket.close(
                code=1008,
            )
        except Exception:
            pass

    finally:
        if "user_id" in locals():
            manager.disconnect(
                user_id,
                websocket,
            )

        database.close()
    

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
    )