from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    create_or_update_user,
    validate_telegram_init_data,
)
from app.schemas import TelegramAuthRequest
from database import get_database
from models import User


router = APIRouter(
    prefix="/api",
    tags=["users"],
)


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "photo_url": user.photo_url,
        "language_code": user.language_code,
        "messenger_code": user.messenger_code,
    }


@router.post("/auth/telegram")
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
        "user": serialize_user(user),
    }


@router.post("/users")
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
        .order_by(
            User.first_name.asc(),
            User.id.asc(),
        )
        .limit(100)
    ).all()

    return {
        "ok": True,
        "users": [
            serialize_user(user)
            for user in users
        ],
    }