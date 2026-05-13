FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y libgomp1 && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8080
CMD uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8080}
