# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-20
# GitHub Packages / GHCR image for IoTAiTech/MC-GPT.
# The source label is required so the image appears on the repository Packages tab.

FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

LABEL org.opencontainers.image.source="https://github.com/IoTAiTech/MC-GPT" \
      org.opencontainers.image.url="https://github.com/IoTAiTech/MC-GPT" \
      org.opencontainers.image.documentation="https://iotaitech.github.io/MC-GPT/" \
      org.opencontainers.image.licenses="PolyForm-Noncommercial-1.0.0" \
      org.opencontainers.image.title="MC-GPT / IOT-AI Coder Suite" \
      org.opencontainers.image.description="Natural-language governed multi-agent coding control plane"

RUN useradd --create-home --home-dir /var/lib/iotai --uid 10001 --shell /usr/sbin/nologin iotai

WORKDIR /src
COPY pyproject.toml LICENSE LICENSE-COMMERCIAL.md LICENSE_POLICY.json NOTICE README.md MANIFEST.in ./
COPY src ./src
COPY skills ./skills

RUN pip install --no-cache-dir . \
    && rm -rf /src/src /src/build /src/*.egg-info

USER 10001
WORKDIR /var/lib/iotai
ENTRYPOINT ["iot-ai"]
CMD ["help"]
