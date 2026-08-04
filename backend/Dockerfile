# syntax=docker/dockerfile:1
#
# Development image for the FastAPI backend. Single stage on purpose — compose
# bind-mounts the source over /app, so there is nothing to gain from a lean
# runtime stage here.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# The venv lives OUTSIDE /app. Compose mounts ./backend over /app, which would
# otherwise drop the host's Windows .venv on top of this Linux one.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependency layer, cached until pyproject.toml/uv.lock change. `package = false`
# means this single sync is the whole install — there is no project to install
# afterwards. Dev deps stay in so pytest runs in the container.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked

COPY . /app

EXPOSE 8000

# 0.0.0.0, not the 127.0.0.1 default — otherwise the port mapping reaches nothing.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
