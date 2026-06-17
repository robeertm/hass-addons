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

# Install analyzer from upstream tag. As of v16.41.5 the wheel ships
# templates/static/i18n via pyproject's [tool.setuptools.package-data].
# requirements.txt's pywebview is intentionally NOT installed (headless).
RUN python3 -m pip install --break-system-packages \
        "shelly-energy-analyzer @ git+https://github.com/robeertm/shelly-energy-analyzer.git@v${ANALYZER_VERSION}" \
 && rm -rf ~/.cache/pip

# Build-time guard: fail the build if upstream regresses and stops shipping
# the templates we depend on. Cheaper to surface here than at runtime.
RUN python3 -c "import shelly_analyzer, pathlib; \
print('shelly_analyzer', shelly_analyzer.__version__); \
p = pathlib.Path(shelly_analyzer.__file__).parent / 'web' / 'templates' / 'setup.html'; \
assert p.exists(), f'MISSING TEMPLATE: {p}'; print('templates ok:', p.parent)"

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
