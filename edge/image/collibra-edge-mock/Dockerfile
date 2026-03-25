# collibra-edge-mock/Dockerfile — Collibra DGC Edge mock for local development
#
# Replaces the real collibra-edge service when collibra-edge.jar is not available.
# Responds to /rest/2.0/ping and other DGC REST surface endpoints so the
# stack health checks and CDN routing pass cleanly.
#
# Uses python:3.11-slim (arm64-native) instead of the CentOS 7 base so that
# this mock runs without QEMU emulation on Apple Silicon.

FROM python:3.11-slim

LABEL org.opencontainers.image.title="sindoc-collibra-edge-mock" \
      org.opencontainers.image.description="Collibra DGC Edge mock for local development — not for production use" \
      collibra.edge.component="dgc-edge-mock"

ENV COLLIBRA_HTTP_PORT=7080

RUN useradd -u 10000 -s /sbin/nologin -d /opt/mock mock && \
    mkdir -p /opt/mock && chown mock:mock /opt/mock

COPY --chown=mock:mock mock_dgc.py /opt/mock/mock_dgc.py

USER mock
WORKDIR /opt/mock

EXPOSE 7080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:7080/rest/2.0/ping')" || exit 1

CMD ["python3", "/opt/mock/mock_dgc.py"]
