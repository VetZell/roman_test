from pydantic import BaseModel, Field


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