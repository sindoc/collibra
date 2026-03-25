# base/Dockerfile — CentOS 7 LTS edge base image
#
# Provides the common foundation for all edge images:
#   - CentOS 7 (matches RHEL 7.7–7.9 binary compatibility)
#   - Java 11 (required by Collibra DGC edge)
#   - EPEL + common tools
#   - Non-root 'edge' user
#   - Standard directories

FROM centos:7

LABEL org.opencontainers.image.title="sindoc-collibra-edge-base" \
      org.opencontainers.image.description="CentOS 7 LTS base for Collibra edge and CDN images" \
      org.opencontainers.image.vendor="sindoc" \
      collibra.edge.platform="rhel7-compat"

# ── System update + EPEL ──────────────────────────────────────────────────────
# Use CentOS vault mirrors — CentOS 7 reached EOL June 2024, official mirrors
# may no longer serve packages; the vault always has the full CentOS 7 tree.
RUN sed -i \
      's|^mirrorlist=|#mirrorlist=|g; s|^#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' \
      /etc/yum.repos.d/CentOS-*.repo && \
    yum -y update && \
    yum -y install epel-release && \
    yum -y install \
        java-11-openjdk-headless \
        curl \
        wget \
        unzip \
        net-tools \
        bind-utils \
        iproute \
        which \
        tzdata \
        ca-certificates \
        openssl && \
    yum clean all && \
    rm -rf /var/cache/yum

# ── Java environment ──────────────────────────────────────────────────────────
ENV JAVA_HOME=/usr/lib/jvm/jre-11-openjdk \
    PATH="/usr/lib/jvm/jre-11-openjdk/bin:${PATH}"

# ── Non-root edge user ────────────────────────────────────────────────────────
RUN groupadd -g 10000 edge && \
    useradd  -u 10000 -g edge -s /sbin/nologin -d /opt/edge -m edge

# ── Standard runtime directories ─────────────────────────────────────────────
RUN mkdir -p /opt/edge/config /opt/edge/data /opt/edge/logs && \
    chown -R edge:edge /opt/edge

WORKDIR /opt/edge
USER edge

# Healthcheck baseline — override in derived images
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD java -version 2>&1 | grep -q "11\." || exit 1
