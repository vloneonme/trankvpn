FROM python:3.12-slim

WORKDIR /app

COPY web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY web/main.py .

CMD ["python", "main.py"]
