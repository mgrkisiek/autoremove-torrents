FROM python:3.12-slim

LABEL org.opencontainers.image.title="autoremove-torrents" \
      org.opencontainers.image.description="Automatically remove torrents according to your strategies, on a schedule" \
      org.opencontainers.image.source="https://github.com/mgrkisiek/autoremove-torrents" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app
COPY pyproject.toml README.rst LICENSE ./
COPY autoremovetorrents ./autoremovetorrents
COPY docker ./docker
RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /config /logs \
    && chown app:app /logs \
    && chmod +x /app/docker/entrypoint.sh

USER app

# Every INTERVAL seconds, render /config/config.yml (${VAR} placeholders are
# replaced from the environment) and run autoremove-torrents
ENV INTERVAL=300 \
    CONFIG_FILE=/config/config.yml \
    LOG_DIR=/logs \
    EXTRA_ARGS=""

VOLUME ["/logs"]
# Log files go to the working directory when --log is not given
WORKDIR /logs
ENTRYPOINT ["/app/docker/entrypoint.sh"]
