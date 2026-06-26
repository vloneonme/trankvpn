"""
TrankVPN Web — лендинг + прокси подписок Marzban
Подписки отдаются через наш домен, скрывая адрес Marzban-сервера
"""

import os
import re
import base64
import logging
import httpx
from urllib.parse import quote
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trankvpn-web")

app = FastAPI(title="TrankVPN Web")

BOT_USERNAME = os.getenv('BOT_USERNAME', 'TrankVPNbot')
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', 'support')
MARZBAN_URL = os.getenv('MARZBAN_URL', '').rstrip('/')


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
        .features { list-style: none; margin-bottom: 36px; text-align: left; }
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
        .footer { margin-top: 24px; color: #555570; font-size: 13px; }
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
        <a class="btn" href="https://t.me/{bot_username}">✈️ Открыть в Telegram</a>
        <div class="footer">
            Поддержка: <a href="https://t.me/{support}">@{support}</a>
        </div>
    </div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    html = LANDING_HTML \
        .replace('{bot_username}', BOT_USERNAME) \
        .replace('{support}', SUPPORT_USERNAME)
    return HTMLResponse(content=html)


@app.get("/sub/{token}")
async def proxy_subscription(token: str):
    """
    Проксирует подписку с Marzban через наш домен.
    Клиент видит только наш домен — адрес Marzban скрыт.
    """
    if not MARZBAN_URL:
        raise HTTPException(status_code=503, detail="VPN service unavailable")

    # Токен должен быть безопасной строкой (буквы, цифры, дефис, подчёркивание)
    if not re.match(r'^[a-zA-Z0-9_\-]{8,128}$', token):
        raise HTTPException(status_code=400, detail="Invalid token")

    try:
        # Marzban отдаёт HTTPS с самоподписанным сертификатом — проверку отключаем
        # (так же, как в shared/marzban.py)
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(
                f"{MARZBAN_URL}/sub/{token}",
                headers={"User-Agent": "TrankVPN-Proxy/1.0"},
                follow_redirects=True,
            )
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Subscription not found")
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "text/plain; charset=utf-8")
            return Response(content=resp.content, media_type=content_type)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Subscription upstream error for token %s: %r", token, e)
        raise HTTPException(status_code=502, detail="Upstream error")


# Шаблоны deep-link'ов VPN-приложений. {url} — подписка (url-encoded),
# {raw} — подписка как есть, {b64} — подписка в base64 (для Shadowrocket).
APP_DEEPLINKS = {
    'happ':         'happ://add/{raw}',
    'v2rayng':      'v2rayng://install-config?url={url}',
    'hiddify':      'hiddify://import/{url}',
    'nekobox':      'sn://subscription?url={url}',
    'streisand':    'streisand://import/{url}',
    'singbox':      'sing-box://import-remote-profile?url={url}',
    'shadowrocket': 'shadowrocket://add/sub?url={b64}',
}


@app.get("/import/{app_id}")
async def import_redirect(app_id: str, url: str):
    """
    Редирект на deep-link VPN-приложения.

    Telegram запрещает кастомные URL-схемы (v2rayng://, hiddify:// и т.п.)
    на inline-кнопках, поэтому кнопка ведёт на этот https-эндпоинт,
    а он уже редиректит на схему приложения.
    """
    template = APP_DEEPLINKS.get(app_id)
    if not template:
        raise HTTPException(status_code=404, detail="Unknown app")

    # Принимаем только наши же ссылки на подписку
    if not re.match(r'^https?://[\w.\-]+/sub/[a-zA-Z0-9_\-]{8,128}$', url):
        raise HTTPException(status_code=400, detail="Invalid subscription url")

    deep_link = template.format(
        url=quote(url, safe=''),
        raw=url,
        b64=base64.b64encode(url.encode()).decode(),
    )
    return RedirectResponse(deep_link, status_code=302)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8080)
