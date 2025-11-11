# ---- base
FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl build-essential git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry but install deps into the *system* env (simpler for Docker)
RUN curl -sSL https://install.python-poetry.org | python3 - \
 && /root/.local/bin/poetry config virtualenvs.create false

WORKDIR /app

# Copy project metadata first
COPY pyproject.toml poetry.lock ./

# Install runtime deps (no project code yet)
RUN pip install --no-cache-dir --upgrade pip \
 && /root/.local/bin/poetry install --only main --no-interaction --no-ansi --no-root

# Now copy source so the package is present
COPY src ./src

# Make sure Python can see /app/src
ENV PYTHONPATH=/app/src

# Expose and start (shell form so $PORT expands on Railway)
ENV PORT=8000
CMD sh -c 'uvicorn spectorr_backend.app:app --host 0.0.0.0 --port ${PORT:-8000}'
