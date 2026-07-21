import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "В Railway не задана переменная BOT_TOKEN"
    )


app = FastAPI(title="Roman Messenger")

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
    """
    Проверяет подпись Telegram Mini App initData.
    Возвращает подтверждённые данные пользователя.
    """

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
            detail="В данных отсутствует подпись Telegram",
        )

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(parsed_data.items())
    )

    # Telegram:
    # secret_key = HMAC_SHA256(bot_token, key="WebAppData")
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

    if not auth_date_text:
        raise HTTPException(
            status_code=401,
            detail="Отсутствует время авторизации",
        )

    try:
        auth_date = int(auth_date_text)
    except ValueError as error:
        raise HTTPException(
            status_code=401,
            detail="Неверное время авторизации",
        ) from error

    current_time = int(time.time())

    if current_time - auth_date > max_age_seconds:
        raise HTTPException(
            status_code=401,
            detail="Данные авторизации устарели",
        )

    user_json = parsed_data.get("user")

    if not user_json:
        raise HTTPException(
            status_code=401,
            detail="Telegram не передал пользователя",
        )

    try:
        user = json.loads(user_json)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=401,
            detail="Повреждены данные пользователя",
        ) from error

    return {
        "user": user,
        "auth_date": auth_date,
        "query_id": parsed_data.get("query_id"),
        "start_param": parsed_data.get("start_param"),
    }


@app.get("/")
async def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Roman Messenger",
    }


@app.post("/api/auth/telegram")
async def telegram_auth(
    request: TelegramAuthRequest,
):
    validated_data = validate_telegram_init_data(
        request.init_data
    )

    user = validated_data["user"]

    return {
        "ok": True,
        "user": {
            "id": user.get("id"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "username": user.get("username"),
            "language_code": user.get("language_code"),
            "photo_url": user.get("photo_url"),
        },
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
    )