# Agent (ws :8787) and executor. Build context: repo root.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY agent/pyproject.toml agent/uv.lock agent/
RUN uv sync --directory agent --frozen --no-dev --no-install-project
COPY agent agent
RUN uv sync --directory agent --frozen --no-dev

# The bundled Claude Code CLI needs a writable home and doesn't run as root.
RUN useradd --create-home app && chown -R app /app
USER app

ENV BIND_HOST=0.0.0.0
EXPOSE 8787
CMD ["uv", "run", "--directory", "agent", "--no-sync", "agent"]
