FROM python:3.12-slim

WORKDIR /app

COPY requirements_api.txt .
RUN pip install --no-cache-dir -r requirements_api.txt

COPY api/ ./api/

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
