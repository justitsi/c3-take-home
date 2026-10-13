# Development runner only; the submitted fixer image is built from ../fixer.
FROM --platform=linux/amd64 python:3.12.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# The runner talks to the host daemon; it never starts a nested Docker daemon.
RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io \
    && apt-get clean \
    && python3 -m pip install --no-cache-dir PyYAML==6.0.2 pytest==8.3.5

COPY entrypoint.sh /opt/c3-dev/entrypoint.sh
COPY runner_paths.sh /opt/c3-dev/runner_paths.sh
ENTRYPOINT ["/bin/bash", "/opt/c3-dev/entrypoint.sh"]
