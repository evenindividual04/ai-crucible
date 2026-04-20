FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt /app/backend-requirements.txt
RUN pip install --no-cache-dir -r /app/backend-requirements.txt

COPY pyproject.toml README.md /app/
COPY src /app/src
RUN pip install --no-cache-dir -e /app

COPY backend/src /app/backend/src

EXPOSE 8000

CMD ["uvicorn", "backend.src.server:app", "--host", "0.0.0.0", "--port", "8000"]
