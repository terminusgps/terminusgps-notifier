FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /usr/local/terminusgps-notifier
ENV DJANGO_SETTINGS_MODULE="src.settings.prod"
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE="copy"
ENV UV_NO_SYNC=1

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . /usr/local/terminusgps-notifier
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --all-groups --locked

ENV PATH="/usr/local/terminusgps-notifier/.venv/bin:$PATH"

ENTRYPOINT []

CMD ["uv", "run", "uvicorn", "--workers", "4", "--host", "0.0.0.0", "--port", "8000", "src.asgi:application"]

EXPOSE 8000
