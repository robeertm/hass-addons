ARG BUILD_FROM=ghcr.io/matter-js/matterjs-server:1.1.1
FROM ${BUILD_FROM}

# matter.js image is debian-bookworm based and runs as 'node' user.
# Need root to install tools and write our run.sh.
USER root

# Install bashio (HAOS config helper) + jq + dbus tools for BlueZ access verification
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        bash jq curl ca-certificates dbus iproute2 bluez \
 && curl -L -o /tmp/bashio.tar.gz \
        https://github.com/hassio-addons/bashio/archive/refs/tags/v0.16.2.tar.gz \
 && tar -xzf /tmp/bashio.tar.gz -C /tmp \
 && mv /tmp/bashio-0.16.2/lib /usr/lib/bashio \
 && ln -s /usr/lib/bashio/bashio /usr/bin/bashio \
 && rm -rf /tmp/bashio* /var/lib/apt/lists/*

WORKDIR /

COPY rootfs/run.sh /run.sh
RUN chmod a+x /run.sh \
 && ls -la /run.sh \
 && head -1 /run.sh

# Override upstream image's ENTRYPOINT (node MatterServer.js) — our run.sh
# constructs the argv with options from /data/options.json and exec's matter.js.
ENTRYPOINT []
CMD ["/run.sh"]
