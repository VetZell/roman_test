import asyncio
import json

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

        self.active_connections.setdefault(
            user_id,
            [],
        ).append(websocket)

    def disconnect(
        self,
        user_id: int,
        websocket: WebSocket,
    ) -> None:
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

    def is_online(
        self,
        user_id: int,
    ) -> bool:
        return bool(
            self.active_connections.get(user_id)
        )

    async def send_to_user(
        self,
        user_id: int,
        data: dict,
    ) -> None:
        connections = list(
            self.active_connections.get(
                user_id,
                [],
            )
        )

        for connection in connections:
            try:
                await connection.send_json(data)
            except Exception:
                self.disconnect(
                    user_id,
                    connection,
                )

    async def broadcast(
        self,
        data: dict,
    ) -> None:
        disconnected_connections: list[
            tuple[int, WebSocket]
        ] = []

        for user_id, connections in list(
            self.active_connections.items()
        ):
            for connection in list(connections):
                try:
                    await connection.send_json(data)
                except Exception:
                    disconnected_connections.append(
                        (
                            user_id,
                            connection,
                        )
                    )

        for user_id, connection in disconnected_connections:
            self.disconnect(
                user_id,
                connection,
            )


manager = ConnectionManager()


async def websocket_endpoint(
    websocket: WebSocket,
) -> None:
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
    user_id: int | None = None

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

        await manager.broadcast(
            {
                "type": "user_status",
                "user_id": user_id,
                "is_online": True,
            }
        )

        while True:
            try:
                raw_data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30,
                )

                if raw_data == "ping":
                    await websocket.send_text("pong")
                    continue

                if raw_data == "pong":
                    continue

                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    continue

                if data.get("type") != "typing":
                    continue

                receiver_id = data.get("receiver_id")
                is_typing = bool(data.get("is_typing"))

                try:
                    receiver_id = int(receiver_id)
                except (TypeError, ValueError):
                    continue

                if receiver_id == user_id:
                    continue

                await manager.send_to_user(
                    receiver_id,
                    {
                        "type": "typing",
                        "user_id": user_id,
                        "is_typing": is_typing,
                    },
                )

            except asyncio.TimeoutError:
                await websocket.send_text("ping")

            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass

    except Exception:
        try:
            await websocket.close(
                code=1008
            )
        except Exception:
            pass

    finally:
        if user_id is not None:
            manager.disconnect(
                user_id,
                websocket,
            )

            if not manager.is_online(user_id):
                await manager.broadcast(
                    {
                        "type": "user_status",
                        "user_id": user_id,
                        "is_online": False,
                    }
                )

        database.close()
