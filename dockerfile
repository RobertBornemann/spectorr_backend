FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    POETRY_HOME=/opt/poetry POETRY_VERSION=1.8.3
ENV PATH="${POETRY_HOME}/bin:${PATH}"

# System deps
RUN apt-get update && apt-get install -y curl build-essential git \
 && rm -rf /var/lib/apt/lists/*

# Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

# Copy only files needed to resolve deps first (layer caching)
COPY pyproject.toml poetry.lock ./
# Install deps (this will fetch spectorr-pipeline from Git)
RUN poetry install --only main --no-interaction --no-ansi

# Now copy the backend source
COPY src ./src

# Data dir for insights & csv (Railway volume will mount here)
RUN mkdir -p /data
ENV SPECTORR_DATA_ROOT=/data

EXPOSE 8000
CMD ["poetry","run","uvicorn","spectorr_backend.app:app","--host","0.0.0.0","--port","8000","--workers","1"]
