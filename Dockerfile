FROM python:3.11-slim

LABEL org.opencontainers.image.title="OmniOps" \
      org.opencontainers.image.description="OmniOps Factory IT Suite" \
      org.opencontainers.image.vendor="OmniOps" \
      org.opencontainers.image.source="https://github.com/slhkrt-tech/OmniOps"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_NAME=OmniOps

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    postgresql-client \
    iputils-ping \
    tcpdump \
    libpcap-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/media /app/staticfiles /app/logs

EXPOSE 8000

CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]