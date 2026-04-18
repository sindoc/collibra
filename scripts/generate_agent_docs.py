#!/usr/bin/env python3
"""Generate agent markdown files from the shared Singine XML contract."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_XML = REPO_ROOT / "docs" / "xml" / "singine-agent-contract.xml"
WORKSPACE_TOKEN = "ws"
CLAUDE_BASENAME = "CLAUDE.md"
AGENTS_BASENAME = "AGENTS.md"


def bullets(parent, tag):
    node = parent.find(tag)
    if node is None:
        return []
    return [child.text.strip() for child in node.findall("rule") if child.text and child.text.strip()]


def source_lines(parent):
    node = parent.find("documentation-sources")
    if node is None:
        return []
    items = []
    for child in node.findall("source"):
        path = child.get("path", "").strip()
        label = (child.text or "").strip()
        if path and label:
            items.append(f"- `{path}`: {label}")
    return items


def find_workspace_root(start: Path, token: str = WORKSPACE_TOKEN) -> Path | None:
    """Return the nearest ancestor named like the workspace root, usually `ws`."""
    current = Path(start).expanduser().resolve()
    for candidate in (current, *current.parents):
        if candidate.name == token:
            return candidate
    return None


def discover_claude_roots(start: Path, workspace_root: Path | None = None) -> list[Path]:
    """Return ancestor directories that define `CLAUDE.md`, from nearest to farthest."""
    current = Path(start).expanduser().resolve()
    stop = Path(workspace_root).expanduser().resolve() if workspace_root else None
    roots: list[Path] = []
    for candidate in (current, *current.parents):
        if (candidate / CLAUDE_BASENAME).exists():
            roots.append(candidate)
        if stop is not None and candidate == stop:
            break
    return roots


def agents_targets(start: Path, workspace_root: Path | None = None) -> list[Path]:
    """Map ancestor `CLAUDE.md` locations to their sibling `AGENTS.md` paths."""
    return [root / AGENTS_BASENAME for root in discover_claude_roots(start, workspace_root)]


def workspace_suffix(path_text: str) -> str | None:
    """Return the path suffix that follows the workspace root (`.../ws/`)."""
    normalised = path_text.replace("\\", "/")
    marker = f"/{WORKSPACE_TOKEN}/"
    if normalised.startswith(f"~/{WORKSPACE_TOKEN}/"):
        return normalised.split(f"~/{WORKSPACE_TOKEN}/", 1)[1]
    if marker in normalised:
        return normalised.split(marker, 1)[1]
    if normalised.endswith(f"/{WORKSPACE_TOKEN}"):
        return ""
    return None


def render_workspace_path(suffix: str, workspace_root: str) -> str:
    """Join a workspace-relative suffix onto a caller-provided workspace root text."""
    root = workspace_root.rstrip("/\\")
    if not suffix:
        return root
    separator = "\\" if "\\" in root and "/" not in root else "/"
    cleaned_suffix = suffix.replace("\\", separator).replace("/", separator)
    return f"{root}{separator}{cleaned_suffix}"


def rewrite_workspace_paths(text: str, workspace_root: str | None) -> str:
    """Rewrite embedded workspace paths to the requested workspace root."""
    if not workspace_root:
        return text
    rewritten: list[str] = []
    for token in text.split():
        suffix = workspace_suffix(token.strip("`()[]{}<>,;:'\""))
        if suffix is None:
            rewritten.append(token)
            continue
        rebuilt = render_workspace_path(suffix, workspace_root)
        rewritten.append(token.replace(token.strip("`()[]{}<>,;:'\""), rebuilt))
    return " ".join(rewritten)


def adapt_lines(lines: Iterable[str], workspace_root: str | None) -> list[str]:
    return [rewrite_workspace_paths(line, workspace_root) for line in lines]


def render_agent(common, agent, workspace_root: str | None = None):
    title = agent.findtext("title", default="Agent Contract").strip()
    intro = agent.findtext("intro", default="").strip()
    shared_ratio = common.getroot().get("shared_ratio", "80")
    specific_ratio = common.getroot().get("specific_ratio", "20")

    boundary = bullets(common.find("common"), "boundary")
    change_policy = bullets(common.find("common"), "change-policy")
    metamodel_policy = bullets(common.find("common"), "metamodel-policy")
    verification = bullets(common.find("common"), "verification")
    specific = [child.text.strip() for child in agent.find("specific").findall("rule") if child.text and child.text.strip()]
    sources = source_lines(common.find("common"))
    summary = common.find("common").findtext("summary", default="").strip()

    lines = [
        f"# {title}",
        "",
        "<!-- Generated from docs/xml/singine-agent-contract.xml. -->",
        "",
        summary,
        "",
        f"This file follows the shared-agent split of approximately {shared_ratio}% common policy and {specific_ratio}% agent-specific guidance.",
        "",
    ]
    if intro:
        lines.extend([intro, ""])

    lines.extend(["## Repository Boundary", ""])
    lines.extend(f"- {item}" for item in boundary)
    lines.append("")

    lines.extend(["## Change Policy", ""])
    lines.extend(f"- {item}" for item in change_policy)
    lines.append("")

    lines.extend(["## Metamodel Alignment", ""])
    lines.extend(f"- {item}" for item in metamodel_policy)
    lines.append("")

    lines.extend(["## Documentation Sources", ""])
    lines.extend(sources)
    lines.append("")

    lines.extend(["## Verification", ""])
    lines.extend(f"- {item}" for item in verification)
    lines.append("")

    lines.extend(["## Agent-Specific Additions", ""])
    lines.extend(f"- {item}" for item in specific)
    lines.append("")
    return "\n".join(adapt_lines(lines, workspace_root))


def load_contract_tree(repo_root: Path) -> ET.ElementTree:
    input_xml = Path(repo_root).expanduser().resolve() / "docs" / "xml" / "singine-agent-contract.xml"
    return ET.parse(input_xml)


def render_agent_files(tree: ET.ElementTree, workspace_root: str | None = None) -> dict[str, str]:
    root = tree.getroot()
    agents = root.find("agents")
    if agents is None:
        raise SystemExit("No <agents> section found")

    rendered: dict[str, str] = {}
    for agent in agents.findall("agent"):
        output = agent.get("output")
        if not output:
            continue
        rendered[output] = render_agent(tree, agent, workspace_root=workspace_root)
    return rendered


def write_agent_files(repo_root: Path, rendered: dict[str, str]) -> list[Path]:
    repo_root = Path(repo_root).expanduser().resolve()
    written: list[Path] = []
    for output, content in rendered.items():
        target = repo_root / output
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=os.environ.get("AGENT_DOCS_REPO_ROOT", str(REPO_ROOT)),
        help="Repository root containing docs/xml/singine-agent-contract.xml",
    )
    parser.add_argument(
        "--workspace-root",
        default=os.environ.get("AGENT_DOCS_WORKSPACE_ROOT"),
        help="Optional workspace-root text used to rewrite embedded ~/ws-style paths",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()
    tree = load_contract_tree(repo_root)
    rendered = render_agent_files(tree, workspace_root=args.workspace_root)
    for target in write_agent_files(repo_root, rendered):
        print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
