#!/bin/bash
set -euo pipefail

RUNNER_SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
ASSESSMENT_DIR=$(CDPATH= cd -- "$RUNNER_SCRIPT_DIR/.." && pwd -P)
DEV_IMAGE=${C3_DEV_IMAGE:-c3-fixer-dev:prototype}
PROXY_STATE_VOLUME=${C3_DEV_PROXY_VOLUME:-c3-prototype-proxy-state}
RUN_IDENTIFIER="$(date -u +%Y%m%dT%H%M%SZ)-$$"

if [[ $# -eq 0 ]]; then
    echo "Usage: solution/grade-docker.sh --fixer IMAGE [--cases practice/A2] [grader options]" >&2
    exit 2
fi
if [[ ! -f "$ASSESSMENT_DIR/.env" ]]; then
    echo "Docker grader: add the supplied OPENROUTER_API_KEY to $ASSESSMENT_DIR/.env first." >&2
    exit 2
fi

docker build --platform linux/amd64 -t "$DEV_IMAGE" "$RUNNER_SCRIPT_DIR/dev"
docker volume create "$PROXY_STATE_VOLUME" >/dev/null
PROXY_VOLUME_PATH=$(docker volume inspect "$PROXY_STATE_VOLUME" --format '{{.Mountpoint}}')
if [[ "$PROXY_VOLUME_PATH" != /* ]]; then
    echo "Docker grader: expected an absolute Docker volume mountpoint." >&2
    exit 2
fi

# Docker Desktop cannot forward a Unix socket through a macOS directory bind.
# Put proxy state in a Linux named volume and mount it at Docker's own absolute
# path, so the original grader's nested sidecar bind resolves to the same socket.
exec docker run --rm --init --platform linux/amd64 \
    --mount "type=bind,source=$ASSESSMENT_DIR,target=$ASSESSMENT_DIR" \
    --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock \
    --mount "type=volume,source=$PROXY_STATE_VOLUME,target=$PROXY_VOLUME_PATH" \
    --workdir "$ASSESSMENT_DIR" \
    -e "C3_ASSESSMENT_ROOT=$ASSESSMENT_DIR" \
    -e "C3_PROXY_STATE=$PROXY_VOLUME_PATH/$RUN_IDENTIFIER" \
    -e "C3_RUNNER_LOG_DIR=$ASSESSMENT_DIR/results/.runner/$RUN_IDENTIFIER" \
    "$DEV_IMAGE" "$@"
