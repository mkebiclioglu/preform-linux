# syntax=docker/dockerfile:1
# Formlabs PreFormServer on Linux: Ubuntu 24.04 + WineHQ + Xvfb.
#
# The image contains no Formlabs software. PreFormServer is downloaded from
# downloads.formlabs.com and signature-checked on first start (into the /data
# volume), or at build time with --build-arg BUNDLE=1 for a private image.

FROM ubuntu:24.04 AS shim
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc-mingw-w64-x86-64 make \
 && rm -rf /var/lib/apt/lists/*
COPY shim /src/shim
RUN make -C /src/shim dnsapi.dll check

FROM ubuntu:24.04
ARG WINE_BRANCH=devel
ARG WINE_VERSION=11.17~noble-1
ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture i386 \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip xvfb xauth osslsigncode openssl \
      libgl1 libglx-mesa0 libgl1-mesa-dri fonts-dejavu-core tini procps iproute2 \
 && mkdir -pm755 /etc/apt/keyrings \
 && curl -fsSL https://dl.winehq.org/wine-builds/winehq.key -o /etc/apt/keyrings/winehq-archive.key \
 && curl -fsSL https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources -o /etc/apt/sources.list.d/winehq-noble.sources \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      "winehq-${WINE_BRANCH}=${WINE_VERSION}" "wine-${WINE_BRANCH}=${WINE_VERSION}" \
      "wine-${WINE_BRANCH}-amd64=${WINE_VERSION}" "wine-${WINE_BRANCH}-i386:i386=${WINE_VERSION}" \
 && rm -rf /var/lib/apt/lists/* \
 && wine --version

RUN userdel -r ubuntu 2>/dev/null || true \
 && useradd -m -u 1000 -s /bin/bash preform \
 && mkdir -p /data /jobs \
 && chown preform:preform /data /jobs

COPY bin /opt/preform-linux/bin
COPY certs /opt/preform-linux/certs
COPY docker/entrypoint.sh docker/healthcheck.sh /opt/preform-linux/docker/
COPY --from=shim /src/shim/dnsapi.dll /opt/preform-linux/shim/dnsapi.dll

ENV PATH=/opt/preform-linux/bin:$PATH \
    HOME=/home/preform \
    PREFORM_LINUX_HOME=/data \
    PREFORM_SHIM_DLL=/opt/preform-linux/shim/dnsapi.dll \
    PREFORM_PORT=44388

ARG PREFORM_VERSION=latest
ENV PREFORM_VERSION=$PREFORM_VERSION
ARG BUNDLE=0

USER preform
WORKDIR /jobs
RUN if [ "$BUNDLE" = "1" ]; then preform-linux install; fi

VOLUME ["/data", "/jobs"]
EXPOSE 44388
HEALTHCHECK --interval=15s --timeout=5s --start-period=600s --retries=3 CMD ["/opt/preform-linux/docker/healthcheck.sh"]
ENTRYPOINT ["tini", "--", "/opt/preform-linux/docker/entrypoint.sh"]
CMD ["run"]
