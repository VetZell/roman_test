import asyncio

from fastapi import WebSocket, WebSocketDisconnect

from app.auth import create_or_update_user, validate_telegram_init_data
from database import SessionLocal


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(
        self,
        user_id: int,
        websocket: WebSocket,
    ) -> None:
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)

    def disconnect(
        self,
        user_id: int,
        websocket: WebSocket,
    ) -> None:
        connections = self.active_connections.get(user_id, [])

        if websocket in connections:
            connections.remove(websocket)

        if not connections:
            self.active_connections.pop(user_id, None)

    async def send_to_user(
        self,
        user_id: int,
        data: dict,
    ) -> None:
        connections = list(self.active_connections.get(user_id, []))

        for connection in connections:
            try:
                await connection.send_json(data)
            except Exception:
                self.disconnect(user_id, connection)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket) -> None:
    init_data = websocket.query_params.get("init_data")

    if not init_data:
        await websocket.close(
            code=1008,
            reason="Telegram initData отсутствует",
        )
        return

    database = SessionLocal()
    user_id: int | None = None

    try:
        telegram_user = validate_telegram_init_data(init_data)

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
                    await websocket.send_text("pong")

            except asyncio.TimeoutError:
                await websocket.send_text("ping")

            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass

    except Exception:
        try:
            await websocket.close(code=1008)
        except Exception:
            pass

    finally:
        if user_id is not None:
            manager.disconnect(user_id, websocket)

        database.close()