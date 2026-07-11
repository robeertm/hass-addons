ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG=C.UTF-8 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# jq for run.sh option parsing; libmaxminddb (+ build deps) for geoip2/maxminddb
RUN apk add --no-cache jq libmaxminddb gcc musl-dev libmaxminddb-dev

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY collector.py /app/collector.py
COPY geoip /app/geoip
COPY run.sh /run.sh
RUN chmod a+x /run.sh

EXPOSE 2055/udp
EXPOSE 3002/tcp
CMD ["/run.sh"]
