#!/usr/bin/env python3
"""
edge_agent.py — Collibra Edge Server Agent

A Claude API application (claude-opus-4-6, adaptive thinking, streaming) that
manages the core tasks of producing an edge server wrapping Kubernetes and
OpenShift, targeted at CentOS/RHEL 7.7, 7.8, and 7.9, with Collibra edge
compatibility.

Usage:
    python edge_agent.py --task "Generate a complete edge stack for RHEL 7.9"
    python edge_agent.py --task "..." --output-dir ./my-output
    python edge_agent.py   # interactive prompt
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import anthropic

import tools as _tools

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert DevOps and platform engineer specializing in edge server deployments.
You generate production-quality configuration artifacts for:

  - Kubernetes ≤ 1.21 (kubelet / kubeadm / kubectl installed via kubernetes.io RPMs)
  - OpenShift Container Platform 3.11 / OKD 3.11
  - CentOS / RHEL 7.7, 7.8, and 7.9
  - Collibra DGC Edge nodes (Java 11, ports 7080 / 7443)

RHEL 7.x CONSTRAINTS — follow these strictly:
  - Package manager: yum (never dnf)
  - Container runtime: Docker CE (docker-ce RPM, not podman)
  - Python: 3.6 is the system default; use /usr/bin/python3.6 in shebangs
  - Kubernetes API versions: use apps/v1, v1 — never apiVersion >= 1.22 features
  - OpenShift API groups: apps.openshift.io/v1, route.openshift.io/v1, image.openshift.io/v1, security.openshift.io/v1
  - SELinux: enforcing mode; include seLinuxOptions.type = spc_t in pod specs
  - firewalld: always use --permanent flag; always firewall-cmd --reload after changes
  - Java: java-11-openjdk only (Collibra edge requires Java 11)
  - systemd units: use After=network-online.target; include Restart=on-failure

WORKFLOW:
  1. Analyse the task and identify which artifacts are needed.
  2. Generate each artifact using the provided tools.
  3. Write every artifact to disk using write_artifact before summarising.
  4. After all writes, list what was produced and where.
  5. Flag any RHEL 7.x compatibility issues using validate_rhel_compatibility.

GOVERNANCE (Collibra catalog):
  - Every generated config that has governance significance must include a
    collibraId comment/field.  Use an empty string as placeholder if no real
    ID is available — do not omit the field entirely.
"""

# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def run_agent(task: str, output_dir: Path) -> None:
    _tools.set_output_dir(output_dir)

    client = anthropic.Anthropic()

    messages: list[dict] = [{"role": "user", "content": task}]

    print(f"\n[edge-agent] Output directory: {output_dir.resolve()}")
    print(f"[edge-agent] Task: {task}\n")
    print("=" * 72)

    # The beta tool runner handles the agentic loop automatically.
    # We wrap individual API calls in a streaming context to print tokens live,
    # then let the tool runner execute tools and re-enter until end_turn.

    while True:
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=8192,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=_collect_raw_schemas(),
            messages=messages,
        ) as stream:
            response_content = []
            tool_uses = []

            for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "thinking":
                        print("\n[thinking...]", flush=True)
                    elif block.type == "text":
                        pass  # text printed via content_block_delta

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        print(delta.text, end="", flush=True)
                    elif delta.type == "thinking_delta":
                        pass  # suppress thinking tokens; only show text

                elif event.type == "content_block_stop":
                    pass

            final = stream.get_final_message()

        # Collect content for history
        messages.append({"role": "assistant", "content": final.content})

        if final.stop_reason == "end_turn":
            break

        if final.stop_reason != "tool_use":
            print(f"\n[edge-agent] Unexpected stop_reason: {final.stop_reason}", file=sys.stderr)
            break

        # Execute tools
        tool_results = []
        for block in final.content:
            if block.type == "tool_use":
                print(f"\n[tool] {block.name}({_summarise_input(block.input)})", flush=True)
                result = _dispatch_tool(block.name, block.input)
                _print_tool_result(block.name, result)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": _serialise_result(result),
                })

        messages.append({"role": "user", "content": tool_results})

    print("\n" + "=" * 72)
    _list_artifacts(output_dir)


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

def _dispatch_tool(name: str, input_data: dict):
    import json as _json

    dispatch = {
        "generate_kubernetes_manifest": _tools.generate_kubernetes_manifest,
        "generate_openshift_resource": _tools.generate_openshift_resource,
        "validate_rhel_compatibility": _tools.validate_rhel_compatibility,
        "generate_collibra_edge_config": _tools.generate_collibra_edge_config,
        "write_artifact": _tools.write_artifact,
        "read_artifact": _tools.read_artifact,
    }
    fn = dispatch.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}

    # @beta_tool functions are called with keyword arguments
    try:
        return fn(**input_data)
    except Exception as exc:
        return {"error": str(exc)}


def _collect_raw_schemas() -> list[dict]:
    """Extract raw JSON-schema tool definitions from @beta_tool wrappers."""
    schemas = []
    for fn in _tools.ALL_TOOLS:
        if hasattr(fn, "to_dict"):
            schemas.append(fn.to_dict())
    return schemas


def _serialise_result(result) -> str:
    import json as _json
    if isinstance(result, str):
        return result
    return _json.dumps(result, ensure_ascii=False, indent=2)


def _summarise_input(input_data: dict) -> str:
    parts = []
    for k, v in list(input_data.items())[:3]:
        v_str = str(v)
        parts.append(f"{k}={v_str[:40]!r}" if len(v_str) > 40 else f"{k}={v_str!r}")
    suffix = ", ..." if len(input_data) > 3 else ""
    return ", ".join(parts) + suffix


def _print_tool_result(name: str, result: dict) -> None:
    if isinstance(result, dict):
        if "error" in result:
            print(f"  ERROR: {result['error']}", file=sys.stderr)
        elif name == "write_artifact":
            print(f"  -> wrote {result.get('filename')} ({result.get('bytes')} bytes)")
        elif name == "validate_rhel_compatibility":
            ok = result.get("ok", True)
            status = "OK" if ok else "ISSUES FOUND"
            print(f"  -> {status}: {len(result.get('issues', []))} issues, {len(result.get('warnings', []))} warnings")
        else:
            keys = [k for k in result if k not in ("manifest", "content", "systemd_unit",
                                                     "firewalld_xml", "edge_properties", "java_opts")]
            print(f"  -> {', '.join(f'{k}={result[k]!r}' for k in keys[:4])}")


def _list_artifacts(output_dir: Path) -> None:
    artifacts = sorted(output_dir.glob("*")) if output_dir.exists() else []
    if not artifacts:
        print("\n[edge-agent] No artifacts written.")
        return
    print(f"\n[edge-agent] Artifacts in {output_dir.resolve()}:")
    for p in artifacts:
        size = p.stat().st_size
        print(f"  {p.name:45s}  {size:>8,} bytes")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Edge Server Agent — generate Kubernetes / OpenShift / Collibra edge artifacts for RHEL 7.7-7.9",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python edge_agent.py --task "Generate a Collibra edge Deployment and Route for RHEL 7.9"
  python edge_agent.py --task "Generate firewalld rules and systemd unit for Collibra edge on RHEL 7.8"
  python edge_agent.py --output-dir /tmp/edge-stack
""",
    )
    parser.add_argument(
        "--task",
        default="",
        help="Natural-language task description. If omitted, reads from stdin.",
    )
    parser.add_argument(
        "--output-dir",
        default="./output",
        metavar="PATH",
        help="Directory to write generated artifacts (default: ./output).",
    )
    args = parser.parse_args()

    task = args.task.strip()
    if not task:
        if sys.stdin.isatty():
            print("Enter task (Ctrl-D to submit): ", end="", flush=True)
        task = sys.stdin.read().strip()
    if not task:
        parser.error("No task provided. Use --task or pipe a task via stdin.")

    output_dir = Path(args.output_dir)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "[edge-agent] ERROR: ANTHROPIC_API_KEY is not set.\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        sys.exit(1)

    run_agent(task, output_dir)


if __name__ == "__main__":
    main()
