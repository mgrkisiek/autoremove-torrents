#!/bin/sh
# Runs autoremove-torrents every INTERVAL seconds.
# Arguments, if given, are passed to autoremove-torrents for a single run instead
# (e.g. `docker compose run --rm autoremove-torrents --view`).
set -e

RENDERED=/tmp/config.yml

run() {
    python /app/docker/render_config.py "$CONFIG_FILE" "$RENDERED" || return 1
    # shellcheck disable=SC2086
    autoremove-torrents --conf="$RENDERED" --log="$LOG_DIR" $EXTRA_ARGS "$@"
}

if [ "$#" -gt 0 ]; then
    run "$@"
    exit $?
fi

echo "Running autoremove-torrents every ${INTERVAL}s with $CONFIG_FILE"
while true; do
    run || echo "Run failed, retrying in ${INTERVAL}s" >&2
    sleep "$INTERVAL"
done
