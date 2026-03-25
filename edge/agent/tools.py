"""
tools.py — Edge Server Agent Tool Definitions

Six @beta_tool functions for generating Kubernetes manifests, OpenShift resources,
RHEL 7.x compatibility validation, Collibra edge configuration, and file I/O.

Target platform: CentOS/RHEL 7.7, 7.8, 7.9
  - Kubernetes ≤ 1.21 (kubelet/kubeadm/kubectl RPMs)
  - OpenShift 3.11 (apps.openshift.io/v1, route.openshift.io/v1)
  - Docker CE (not podman)
  - SELinux enforcing
  - yum package manager
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from anthropic import beta_tool

try:
    import yaml as _yaml
    _HAS_YAML = True
except ImportError:
    _yaml = None  # type: ignore[assignment]
    _HAS_YAML = False

# Resolved at runtime from edge_agent.py; tools reference this via closure.
_output_dir: Path = Path("output")


def set_output_dir(path: Path) -> None:
    global _output_dir
    _output_dir = path
    _output_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. generate_kubernetes_manifest
# ---------------------------------------------------------------------------

@beta_tool
def generate_kubernetes_manifest(
    component: str,
    image: str,
    replicas: int = 1,
    port: int = 8080,
    resource_kind: str = "Deployment",
    namespace: str = "collibra-edge",
    extra_labels: Optional[str] = None,
) -> dict:
    """Generate a Kubernetes YAML manifest for an edge server component.

    Produces one of: Deployment, Service, ConfigMap, or PersistentVolumeClaim.
    All manifests are compatible with Kubernetes ≤ 1.21 and include SELinux
    context annotations required for RHEL 7.x nodes.

    Args:
        component:     Short name of the component (e.g. 'collibra-edge', 'nginx-proxy').
        image:         Container image reference (e.g. 'collibra/dgc-edge:2023.11').
        replicas:      Desired replica count for Deployment kind (default 1).
        port:          Container port to expose (default 8080).
        resource_kind: One of Deployment | Service | ConfigMap | PersistentVolumeClaim.
        namespace:     Kubernetes namespace (default 'collibra-edge').
        extra_labels:  JSON string of additional key=value labels to merge (optional).
    """
    labels = {"app": component, "tier": "edge", "platform": "rhel7"}
    if extra_labels:
        try:
            labels.update(json.loads(extra_labels))
        except json.JSONDecodeError:
            pass

    kind = resource_kind.strip()
    name = component.lower().replace(" ", "-").replace("_", "-")

    if kind == "Deployment":
        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {
                "replicas": replicas,
                "selector": {"matchLabels": {"app": component}},
                "template": {
                    "metadata": {"labels": labels},
                    "spec": {
                        "securityContext": {
                            "seLinuxOptions": {"type": "spc_t"},
                        },
                        "containers": [
                            {
                                "name": name,
                                "image": image,
                                "ports": [{"containerPort": port}],
                                "resources": {
                                    "requests": {"memory": "512Mi", "cpu": "250m"},
                                    "limits": {"memory": "2Gi", "cpu": "1000m"},
                                },
                                "securityContext": {
                                    "allowPrivilegeEscalation": False,
                                    "readOnlyRootFilesystem": False,
                                },
                            }
                        ],
                    },
                },
            },
        }

    elif kind == "Service":
        manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {
                "selector": {"app": component},
                "ports": [{"protocol": "TCP", "port": port, "targetPort": port}],
                "type": "ClusterIP",
            },
        }

    elif kind == "ConfigMap":
        manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": f"{name}-config", "namespace": namespace},
            "data": {
                "PLATFORM": "rhel7",
                "COMPONENT": component,
                "PORT": str(port),
            },
        }

    elif kind == "PersistentVolumeClaim":
        manifest = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": f"{name}-pvc", "namespace": namespace},
            "spec": {
                "accessModes": ["ReadWriteOnce"],
                "resources": {"requests": {"storage": "10Gi"}},
            },
        }

    else:
        return {"error": f"Unsupported resource_kind: {kind}"}

    if _HAS_YAML:
        content = _yaml.dump(manifest, default_flow_style=False, sort_keys=False)
        fmt = "yaml"
    else:
        content = json.dumps(manifest, indent=2)
        fmt = "json"

    return {"kind": kind, "component": component, "format": fmt, "manifest": content}


# ---------------------------------------------------------------------------
# 2. generate_openshift_resource
# ---------------------------------------------------------------------------

@beta_tool
def generate_openshift_resource(
    component: str,
    resource_kind: str = "Route",
    hostname: str = "",
    namespace: str = "collibra-edge",
    image: str = "",
    port: int = 8080,
) -> dict:
    """Generate an OpenShift 3.11 resource definition.

    Supports: Route | DeploymentConfig | ImageStream | SecurityContextConstraints.
    Uses OpenShift 3.11 API groups: apps.openshift.io/v1, route.openshift.io/v1.

    Args:
        component:     Component name (e.g. 'collibra-edge').
        resource_kind: One of Route | DeploymentConfig | ImageStream | SecurityContextConstraints.
        hostname:      External hostname for Route (e.g. 'collibra.apps.example.com').
        namespace:     OpenShift project/namespace (default 'collibra-edge').
        image:         Image reference (for DeploymentConfig / ImageStream).
        port:          Port for Route service target (default 8080).
    """
    name = component.lower().replace(" ", "-").replace("_", "-")
    kind = resource_kind.strip()

    if kind == "Route":
        manifest = {
            "apiVersion": "route.openshift.io/v1",
            "kind": "Route",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "host": hostname or f"{name}.apps.example.com",
                "to": {"kind": "Service", "name": name, "weight": 100},
                "port": {"targetPort": port},
                "tls": {"termination": "edge", "insecureEdgeTerminationPolicy": "Redirect"},
            },
        }

    elif kind == "DeploymentConfig":
        manifest = {
            "apiVersion": "apps.openshift.io/v1",
            "kind": "DeploymentConfig",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "replicas": 1,
                "selector": {"app": name},
                "template": {
                    "metadata": {"labels": {"app": name}},
                    "spec": {
                        "containers": [
                            {
                                "name": name,
                                "image": image or f"{name}:latest",
                                "ports": [{"containerPort": port}],
                            }
                        ]
                    },
                },
                "triggers": [{"type": "ConfigChange"}],
            },
        }

    elif kind == "ImageStream":
        manifest = {
            "apiVersion": "image.openshift.io/v1",
            "kind": "ImageStream",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "tags": [
                    {
                        "name": "latest",
                        "from": {"kind": "DockerImage", "name": image or f"{name}:latest"},
                    }
                ]
            },
        }

    elif kind == "SecurityContextConstraints":
        manifest = {
            "apiVersion": "security.openshift.io/v1",
            "kind": "SecurityContextConstraints",
            "metadata": {"name": f"{name}-scc"},
            "allowPrivilegedContainer": False,
            "allowHostNetwork": False,
            "allowHostPorts": False,
            "seLinuxContext": {"type": "MustRunAs"},
            "runAsUser": {"type": "MustRunAsRange"},
            "fsGroup": {"type": "MustRunAs"},
            "supplementalGroups": {"type": "RunAsAny"},
            "volumes": ["configMap", "emptyDir", "persistentVolumeClaim", "secret"],
        }

    else:
        return {"error": f"Unsupported resource_kind: {kind}"}

    if _HAS_YAML:
        content = _yaml.dump(manifest, default_flow_style=False, sort_keys=False)
        fmt = "yaml"
    else:
        content = json.dumps(manifest, indent=2)
        fmt = "json"

    return {"kind": kind, "component": component, "format": fmt, "manifest": content}


# ---------------------------------------------------------------------------
# 3. validate_rhel_compatibility
# ---------------------------------------------------------------------------

@beta_tool
def validate_rhel_compatibility(
    rhel_version: str,
    packages: Optional[str] = None,
    config_snippet: Optional[str] = None,
) -> dict:
    """Check a package list or configuration snippet for RHEL 7.x compatibility.

    Args:
        rhel_version:    Target version string: '7.7', '7.8', or '7.9'.
        packages:        JSON array string of RPM package names to check (optional).
        config_snippet:  A short configuration text to scan for known incompatibilities (optional).
    """
    supported = {"7.7", "7.8", "7.9"}
    if rhel_version not in supported:
        return {
            "ok": False,
            "issues": [f"rhel_version must be one of {sorted(supported)}, got '{rhel_version}'"],
        }

    issues: list[str] = []
    warnings: list[str] = []

    # Known incompatible or renamed packages on RHEL 7
    dnf_only = {"dnf", "dnf-plugins-core", "dnf-automatic"}
    podman_warning = {"podman", "buildah", "skopeo"}
    k8s_too_new = {"kubernetes-1.22", "kubernetes-1.23", "kubernetes-1.24", "kubernetes-1.25"}
    java_bad = {"java-1.8.0-openjdk", "java-1.7.0-openjdk"}  # Collibra edge needs Java 11

    if packages:
        try:
            pkg_list: list[str] = json.loads(packages)
        except json.JSONDecodeError:
            pkg_list = [p.strip() for p in packages.split(",") if p.strip()]

        for pkg in pkg_list:
            pkg_lower = pkg.lower()
            if any(d in pkg_lower for d in dnf_only):
                issues.append(f"'{pkg}' is dnf-only; use yum on RHEL 7")
            if any(p in pkg_lower for p in podman_warning):
                warnings.append(
                    f"'{pkg}' is available on RHEL 7.6+ but Docker CE is the recommended "
                    "container runtime for Kubernetes on RHEL 7.7–7.9"
                )
            if any(k in pkg_lower for k in k8s_too_new):
                issues.append(
                    f"'{pkg}' exceeds Kubernetes ≤1.21 requirement for RHEL 7"
                )
            if any(j in pkg_lower for j in java_bad) and rhel_version in {"7.7", "7.8", "7.9"}:
                warnings.append(
                    f"'{pkg}' — Collibra edge requires Java 11 (java-11-openjdk), not Java 8/7"
                )

    if config_snippet:
        snippet = config_snippet.lower()
        if "python3.8" in snippet or "python3.9" in snippet or "python3.10" in snippet:
            warnings.append(
                "Python 3.8+ is not in the base RHEL 7 repos; "
                "requires EPEL or Software Collections (scl)"
            )
        if "dnf install" in snippet:
            issues.append("'dnf install' found; replace with 'yum install' for RHEL 7")
        if "systemctl --now" in snippet:
            warnings.append(
                "'systemctl --now' requires systemd 219+; verify version on target RHEL 7.x host"
            )
        if "firewall-cmd" in snippet and "--permanent" not in snippet:
            warnings.append(
                "firewall-cmd rules without --permanent will not survive reboots"
            )

    return {
        "ok": len(issues) == 0,
        "rhel_version": rhel_version,
        "issues": issues,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 4. generate_collibra_edge_config
# ---------------------------------------------------------------------------

@beta_tool
def generate_collibra_edge_config(
    hostname: str,
    dgc_url: str,
    java_heap_gb: int = 4,
    http_port: int = 7080,
    https_port: int = 7443,
    collibra_id: str = "",
) -> dict:
    """Generate Collibra DGC Edge node configuration artifacts.

    Produces:
      - Java startup options (JAVA_OPTS)
      - firewalld zone XML fragment for required ports
      - systemd unit file for the Collibra edge service
      - Collibra edge properties snippet

    Args:
        hostname:       FQDN of the edge node (e.g. 'edge01.example.com').
        dgc_url:        URL of the central Collibra DGC instance (e.g. 'https://dgc.example.com').
        java_heap_gb:   Java heap size in GB (Xms and Xmx, default 4).
        http_port:      Collibra edge HTTP port (default 7080).
        https_port:     Collibra edge HTTPS port (default 7443).
        collibra_id:    Collibra asset ID for governance tracking (empty = placeholder).
    """
    java_opts = (
        f"-Xms{java_heap_gb}g -Xmx{java_heap_gb}g "
        "-XX:+UseG1GC -XX:MaxGCPauseMillis=200 "
        "-Djava.awt.headless=true "
        f"-Dcollibra.edge.hostname={hostname} "
        f"-Dcollibra.dgc.url={dgc_url}"
    )

    firewalld_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<zone>
  <short>collibra-edge</short>
  <description>Firewalld zone for Collibra Edge on RHEL 7</description>
  <!-- Collibra edge HTTP/HTTPS -->
  <port protocol="tcp" port="{http_port}"/>
  <port protocol="tcp" port="{https_port}"/>
  <!-- Kubernetes API server -->
  <port protocol="tcp" port="6443"/>
  <!-- Kubelet -->
  <port protocol="tcp" port="10250"/>
  <port protocol="tcp" port="10255"/>
  <!-- etcd (single-node edge) -->
  <port protocol="tcp" port="2379"/>
  <port protocol="tcp" port="2380"/>
</zone>
"""

    systemd_unit = f"""[Unit]
Description=Collibra DGC Edge Node
Documentation=https://documentation.collibra.com
After=network-online.target docker.service
Requires=network-online.target
Wants=docker.service

[Service]
Type=simple
User=collibra
Group=collibra
Environment="JAVA_HOME=/usr/lib/jvm/java-11-openjdk"
Environment="JAVA_OPTS={java_opts}"
WorkingDirectory=/opt/collibra/edge
ExecStart=/usr/lib/jvm/java-11-openjdk/bin/java $JAVA_OPTS -jar /opt/collibra/edge/collibra-edge.jar
ExecStop=/bin/kill -SIGTERM $MAINPID
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=collibra-edge

# SELinux / security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""

    edge_properties = f"""# Collibra Edge Node Properties
# Generated for RHEL 7 — do not edit manually; regenerate via edge-agent

collibra.edge.hostname={hostname}
collibra.dgc.url={dgc_url}
collibra.edge.http.port={http_port}
collibra.edge.https.port={https_port}

# Java
java.home=/usr/lib/jvm/java-11-openjdk

# Collibra asset identity (Collibra catalog governance reference)
# collibraId: {collibra_id if collibra_id else "(placeholder — populate from Collibra catalog)"}
"""

    return {
        "hostname": hostname,
        "dgc_url": dgc_url,
        "collibra_id": collibra_id,
        "java_opts": java_opts,
        "firewalld_xml": firewalld_xml,
        "systemd_unit": systemd_unit,
        "edge_properties": edge_properties,
    }


# ---------------------------------------------------------------------------
# 5. write_artifact
# ---------------------------------------------------------------------------

@beta_tool
def write_artifact(name: str, content: str, extension: str = "yaml") -> dict:
    """Write a text artifact (YAML, XML, properties, service unit) to the output directory.

    Args:
        name:      Base filename without extension (e.g. 'collibra-edge-deployment').
        content:   Text content to write.
        extension: File extension without dot (default 'yaml').
    """
    safe_name = Path(name).name  # strip any directory traversal
    filename = f"{safe_name}.{extension}"
    dest = _output_dir / filename
    dest.write_text(content, encoding="utf-8")
    return {"path": str(dest), "bytes": len(content), "filename": filename}


# ---------------------------------------------------------------------------
# 6. read_artifact
# ---------------------------------------------------------------------------

@beta_tool
def read_artifact(name: str, extension: str = "yaml") -> dict:
    """Read a previously written artifact from the output directory.

    Args:
        name:      Base filename without extension.
        extension: File extension without dot (default 'yaml').
    """
    safe_name = Path(name).name
    filename = f"{safe_name}.{extension}"
    dest = _output_dir / filename
    if not dest.exists():
        return {"error": f"Artifact not found: {filename}", "path": str(dest)}
    content = dest.read_text(encoding="utf-8")
    return {"path": str(dest), "bytes": len(content), "content": content}


# ---------------------------------------------------------------------------
# All tools exported for tool runner
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    generate_kubernetes_manifest,
    generate_openshift_resource,
    validate_rhel_compatibility,
    generate_collibra_edge_config,
    write_artifact,
    read_artifact,
]
