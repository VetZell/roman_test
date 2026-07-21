import hashlib
import hmac
import json
import os
import secrets
import string
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from models import Message, User

from database import Base, engine, get_database


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

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
    )