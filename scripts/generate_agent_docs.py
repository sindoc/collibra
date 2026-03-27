#!/usr/bin/env python3
"""Generate agent markdown files from the shared Singine XML contract."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_XML = REPO_ROOT / "docs" / "xml" / "singine-agent-contract.xml"


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


def render_agent(common, agent):
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
    return "\n".join(lines)


def main() -> int:
    tree = ET.parse(INPUT_XML)
    root = tree.getroot()
    agents = root.find("agents")
    if agents is None:
        raise SystemExit("No <agents> section found")

    for agent in agents.findall("agent"):
        output = agent.get("output")
        if not output:
            continue
        target = REPO_ROOT / output
        target.write_text(render_agent(tree, agent), encoding="utf-8")
        print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
