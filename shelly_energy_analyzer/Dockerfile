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
# Workaround for upstream: pyproject.toml doesn't ship package_data (templates,
# static, i18n .json files) — we clone the source and overlay it onto the
# installed package directory so HTML/CSS/JS/JSON resources are present.
RUN git clone --depth 1 --branch "v${ANALYZER_VERSION}" \
        https://github.com/robeertm/shelly-energy-analyzer.git /tmp/sea \
 && cd /tmp/sea \
 && python3 -m pip install --break-system-packages . \
 && SP="$(python3 -c 'import shelly_analyzer, os; print(os.path.dirname(shelly_analyzer.__file__))')" \
 && echo "Overlaying resources onto $SP" \
 && cp -rT /tmp/sea/src/shelly_analyzer "$SP" \
 && rm -rf /tmp/sea ~/.cache/pip

# Smoke-test that CLI is importable AND templates are reachable
RUN python3 -c "import shelly_analyzer, pathlib; print('shelly_analyzer', shelly_analyzer.__version__); \
p = pathlib.Path(shelly_analyzer.__file__).parent / 'web' / 'templates' / 'setup.html'; \
assert p.exists(), f'MISSING TEMPLATE: {p}'; print('templates ok:', p.parent)"

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
