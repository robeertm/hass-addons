ARG BUILD_FROM=ghcr.io/matter-js/matterjs-server:1.1.1
FROM ${BUILD_FROM}

# Upstream image runs as 'node' user and has /app/node_modules/matter-server.
# We need root to install jq and write /run.sh.
USER root

# jq for parsing /data/options.json. Skip bashio: base is plain Debian, not
# HAOS s6-overlay, so /usr/bin/with-contenv isn't available.
RUN apt-get update \
 && apt-get install -y --no-install-recommends jq ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /

COPY run.sh /run.sh
RUN chmod a+x /run.sh \
 && ls -la /run.sh \
 && head -3 /run.sh

# Override upstream image's ENTRYPOINT (node MatterServer.js).
ENTRYPOINT []
CMD ["/run.sh"]
