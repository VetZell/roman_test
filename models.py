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
def send_message(
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

    return {
        "ok": True,
        "message": {
            "id": message.id,
            "sender_id": message.sender_id,
            "receiver_id": message.receiver_id,
            "text": message.text,
            "created_at": message.created_at.isoformat(),
        },
    }