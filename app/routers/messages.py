from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.auth import (
    create_or_update_user,
    validate_telegram_init_data,
)
from app.schemas import (
    MessagesRequest,
    SendMessageRequest,
)
from app.websocket import manager
from database import get_database
from models import Message, User


router = APIRouter(
    prefix="/api",
    tags=["messages"],
)


def serialize_message(message: Message) -> dict:
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "receiver_id": message.receiver_id,
        "text": message.text,
        "created_at": message.created_at.isoformat(),
    }


@router.post("/messages")
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

    if not other_user.is_active:
        raise HTTPException(
            status_code=404,
            detail="Пользователь недоступен",
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
            serialize_message(message)
            for message in messages
        ],
    }


@router.post("/messages/send")
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

    if not receiver.is_active:
        raise HTTPException(
            status_code=400,
            detail="Получатель недоступен",
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

    try:
        database.add(message)
        database.commit()
        database.refresh(message)
    except Exception:
        database.rollback()

        raise HTTPException(
            status_code=500,
            detail="Не удалось сохранить сообщение",
        )

    message_data = serialize_message(message)

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