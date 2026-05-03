FROM python:3.10-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Создание директории для логов
RUN mkdir -p /var/log/bot && chmod 755 /var/log/bot

# Запуск бота
CMD ["python", "bot.py"]