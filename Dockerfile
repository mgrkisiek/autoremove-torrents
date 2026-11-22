FROM python:3.12-slim

WORKDIR /app
COPY . /app
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

ENTRYPOINT ["/app/docker/entrypoint.sh"]
