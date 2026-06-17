ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        python3-dev build-essential \
        libffi-dev libssl-dev \
        ca-certificates curl jq git tzdata \
  && rm -rf /var/lib/apt/lists/*

ARG ANALYZER_VERSION
ENV ANALYZER_VERSION=${ANALYZER_VERSION}

# Install analyzer + Flask runtime from upstream tag (pyproject.toml deps only —
# requirements.txt's pywebview is intentionally NOT installed; this is headless).
RUN python3 -m pip install --break-system-packages \
        "shelly-energy-analyzer @ git+https://github.com/robeertm/shelly-energy-analyzer.git@v${ANALYZER_VERSION}"

# Smoke-test that CLI is importable
RUN python3 -c "import shelly_analyzer; print('shelly_analyzer', shelly_analyzer.__version__)"

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
