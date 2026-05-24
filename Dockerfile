# syntax=docker/dockerfile:1.7
#
# Multi-stage build for the storage exporter.
#
# Runtime image is python:3.13-slim + coreutils (for the `du`, `nice`,
# `ionice` binaries the collectors shell out to). Slim is only ~70 MB
# and already has libc6 and the kubernetes service-account token path
# available, so there's nothing else to add.
#
# Built and pushed by .github/workflows/release.yaml for linux/amd64
# and linux/arm64 on every git tag.

FROM python:3.13-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir hatchling
COPY pyproject.toml README.md ./
COPY exporter ./exporter
RUN pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.13-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends coreutils util-linux \
 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /wheels/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl pyyaml \
 && rm /tmp/*.whl
EXPOSE 9101
# Intentionally NO ENV defaults for INTERVAL_SECONDS / LISTEN_PORT /
# METRIC_PREFIX / DU_TIMEOUT_SECONDS: env vars take precedence over
# the YAML config, so baking them here would silently override
# user-supplied config.yaml values. The defaults are owned by
# /etc/storage-exporter/defaults.yaml inside the package.
#
# NODE_NAME is the one exception — pod templates set it via the
# downward API, so we don't need a default.
ENTRYPOINT ["python", "-m", "exporter"]
