"""
TrankVPN Web — лендинг и информационные страницы сервиса
"""

import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="TrankVPN Web")

BOT_USERNAME = os.getenv('BOT_USERNAME', 'TrankVPNbot')
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', 'support')


LANDING_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrankVPN — Быстрый и безопасный VPN</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f13;
            color: #e8e8f0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }
        .card {
            background: #1a1a24;
            border: 1px solid #2a2a3a;
            border-radius: 20px;
            padding: 48px 40px;
            max-width: 480px;
            width: 100%;
            text-align: center;
        }
        .logo { font-size: 56px; margin-bottom: 8px; }
        h1 { font-size: 28px; font-weight: 700; color: #fff; margin-bottom: 8px; }
        .tagline { color: #8888aa; font-size: 16px; margin-bottom: 36px; }
        .features {
            list-style: none;
            margin-bottom: 36px;
            text-align: left;
        }
        .features li {
            padding: 8px 0;
            color: #c0c0d8;
            font-size: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .features li::before { content: '✓'; color: #5e9aff; font-weight: 700; }
        .btn {
            display: inline-block;
            background: #3390ec;
            color: #fff;
            text-decoration: none;
            padding: 16px 40px;
            border-radius: 12px;
            font-size: 17px;
            font-weight: 600;
            transition: background 0.2s;
            width: 100%;
        }
        .btn:hover { background: #2979d9; }
        .footer {
            margin-top: 24px;
            color: #555570;
            font-size: 13px;
        }
        .footer a { color: #5e9aff; text-decoration: none; }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">🔒</div>
        <h1>TrankVPN</h1>
        <p class="tagline">Быстрый · Безопасный · Надёжный</p>

        <ul class="features">
            <li>Работает во всех странах</li>
            <li>Android, iOS, Windows, Mac</li>
            <li>Безлимитный трафик</li>
            <li>Мгновенная активация</li>
            <li>Оплата в USDT / TON</li>
        </ul>

        <a class="btn" href="https://t.me/{bot_username}">
            ✈️ Открыть в Telegram
        </a>

        <div class="footer">
            Поддержка: <a href="https://t.me/{support}">@{support}</a>
        </div>
    </div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    html = LANDING_HTML.replace('{bot_username}', BOT_USERNAME).replace('{support}', SUPPORT_USERNAME)
    return HTMLResponse(content=html)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8080)
