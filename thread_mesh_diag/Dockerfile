ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apk add --no-cache python3 py3-pip ca-certificates tzdata \
 && python3 -m pip install --break-system-packages --no-cache-dir \
        websockets requests

COPY rootfs /

RUN chmod a+x /usr/local/bin/thread_mesh_diag.py /run.sh

CMD ["/run.sh"]
