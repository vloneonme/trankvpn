FROM python:3.12-slim

WORKDIR /app

COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY bot/bot.py .

RUN mkdir -p /var/log/bot

CMD ["python", "bot.py"]
