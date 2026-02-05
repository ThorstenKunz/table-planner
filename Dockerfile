FROM python:3.12-slim AS test

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1

WORKDIR /app

COPY requirements.txt ./
RUN if [ -f "requirements.txt" ]; then \
        pip install --no-cache-dir --requirement requirements.txt; \
    fi

COPY . .

RUN pytest


FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1

WORKDIR /app

ARG APP_UID=1000
ARG APP_GID=1000
RUN addgroup --system --gid "$APP_GID" app && \
    adduser --system --uid "$APP_UID" --gid "$APP_GID" app

COPY requirements-prod.txt ./
RUN if [ -f "requirements-prod.txt" ]; then \
        pip install --no-cache-dir --requirement requirements-prod.txt; \
    fi

COPY . .

RUN mkdir -p /app/data && \
    chown -R "$APP_UID":"$APP_GID" /app

USER app

VOLUME ["/app/data"]

CMD ["python", "main.py"]
