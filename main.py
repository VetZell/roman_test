import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >
        <title>Roman Messenger</title>

        <style>
            body {
                margin: 0;
                font-family: -apple-system, sans-serif;
                background: #10141c;
                color: white;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                text-align: center;
            }

            .card {
                padding: 30px;
            }

            h1 {
                font-size: 32px;
            }

            p {
                opacity: 0.7;
            }
        </style>
    </head>

    <body>
        <div class="card">
            <h1>💬 Roman Messenger</h1>
            <p>Telegram Mini App работает!</p>
        </div>
    </body>
    </html>
    """


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
    )