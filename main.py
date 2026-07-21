import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(
    title="Roman Messenger"
)

# Подключаем папку static
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


# Главная страница
@app.get("/")
async def home():
    return FileResponse("static/index.html")


# Проверка работы сервера
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "message": "Roman Messenger работает"
    }


# Запуск локально
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )