# Amsterdam Concert Tracker — run 24/7 in a container
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Data and DB live here so they persist when using a volume
ENV DATABASE_PATH=/data/bot.db
RUN mkdir -p /data

CMD ["python", "main.py"]
