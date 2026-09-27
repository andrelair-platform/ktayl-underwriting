# Multi-stage build for the ktayl-underwriting FastAPI service.
# Non-root at runtime (also enforced by Gatekeeper at deploy time via securityContext).

# ---- builder: install deps into a venv ----
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY pyproject.toml README.md version.txt ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install .

# ---- runtime: minimal, non-root ----
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create an unprivileged user (uid 10001).
RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini version.txt ./

USER 10001

EXPOSE 8000

# uvicorn serves the ASGI app; DATABASE_URL is injected at runtime (env-agnostic image).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
