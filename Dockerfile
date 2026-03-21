FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /usr/sbin/nologin dailyder

COPY pyproject.toml README.md /app/
COPY dailyder_bot /app/dailyder_bot

RUN pip install --no-cache-dir .
RUN apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip

USER dailyder

CMD ["python", "-m", "dailyder_bot"]
