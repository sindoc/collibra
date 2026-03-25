# cdn/Dockerfile — nginx CDN / TLS-terminating reverse proxy
#
# Runs nginx on the CentOS 7 LTS base as an edge CDN layer in front of
# the Collibra edge node (and any other backend services).
#
# Default ports:
#   80   HTTP  (redirects to HTTPS)
#   443  HTTPS (TLS termination, proxies to collibra-edge)
#
# TLS certificates must be mounted at runtime:
#   /opt/edge/cdn/certs/server.crt
#   /opt/edge/cdn/certs/server.key
# (or use Let's Encrypt / cert-manager in Kubernetes)

ARG REGISTRY=localhost
ARG BASE_TAG=latest
FROM sindoc-collibra-edge-base:${BASE_TAG}

LABEL org.opencontainers.image.title="sindoc-collibra-cdn" \
      org.opencontainers.image.description="nginx CDN / TLS proxy on CentOS 7 LTS base" \
      collibra.edge.component="cdn"

# ── Install nginx from EPEL ───────────────────────────────────────────────────
USER root
RUN yum -y install nginx gettext python3 && \
    yum clean all && \
    rm -rf /var/cache/yum && \
    # nginx log/run dirs — owned by edge user so we can run non-root
    mkdir -p /opt/edge/cdn/certs \
             /opt/edge/cdn/cache \
             /opt/edge/cdn/irib3 \
             /opt/edge/cdn/persiangulf \
             /opt/edge/cdn/logs \
             /var/lib/nginx/tmp \
             /run/nginx && \
    chown -R edge:edge \
             /opt/edge/cdn \
             /var/lib/nginx \
             /run/nginx \
             /var/log/nginx \
             /etc/nginx

# ── nginx configuration ───────────────────────────────────────────────────────
COPY nginx.conf       /etc/nginx/nginx.conf
COPY conf.d/          /etc/nginx/conf.d/
COPY irib3/           /opt/edge/cdn/irib3/
COPY persiangulf/     /opt/edge/cdn/persiangulf/
COPY entrypoint.sh    /opt/edge/cdn/entrypoint.sh

RUN chmod +x /opt/edge/cdn/entrypoint.sh

USER edge

EXPOSE 80 443

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost/healthz || exit 1

CMD ["/opt/edge/cdn/entrypoint.sh"]
