# Build from the repository root:
# docker build --platform linux/amd64 -t c3-fixer-prototype:v1-final solution/fixer
FROM --platform=linux/amd64 python:3.12.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Runtime case tests and the deterministic simulator use these packages.
# All dependencies are installed at build time; runtime has proxy-only network.
RUN python3 -m pip install --no-cache-dir PyYAML==6.0.2 pytest==8.3.5

COPY . /fixer/
WORKDIR /workspace

ENTRYPOINT ["/bin/sh", "/fixer/run.sh"]
