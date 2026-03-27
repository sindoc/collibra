# AGENTS.md - Cross-Agent Contract

<!-- Generated from docs/xml/singine-agent-contract.xml. -->

This repository is the system of record for Collibra-specific code,
      metamodel abstractions, operating-model import/export workflows, Edge
      integrations, and the implementation behind the `singine collibra ...`
      command family.

This file follows the shared-agent split of approximately 80% common policy and 20% agent-specific guidance.

This file is the generic entry point for agents and LLM-based tools that
        do not have their own dedicated repository instruction file yet.

## Repository Boundary

- Implement Collibra REST, SDK, CLI, MCP, operating-model, Edge, and tenant-specific governance logic here.
- Expose Collibra-aware logic to Singine through `singine-collibra/python/singine_collibra/` rather than duplicating it in Singine.
- Keep Singine focused on execution, privileges, orchestration, and general runtime publication concerns.
- Prefer SilkPage for transformation-heavy XML/XSLT/XPath/RDF/TTL/SPARQL/SQL/GraphQL pipelines when that work is not intrinsically Collibra-specific.
- Treat the Collibra metamodel and its governed identifiers as a canonical alignment contract across repositories and agents.

## Change Policy

- Default to adding or updating tests for every functional change.
- Prefer Singine-level tests and MCP-interface tests when the feature is exposed through `singine collibra ...`.
- Update documentation in parallel with code changes: XML model/command docs, OpenAPI descriptions when applicable, man pages, and Markdown pages.
- If tests or documentation are intentionally omitted, explain that explicitly in the final response.
- When a change introduces or modifies a CLI surface, keep command registration, docs/xml, man pages, and Markdown usage examples aligned.

## Metamodel Alignment

- New features should explain how they map to the Collibra metamodel, operating model, assignments, views, or governed identifiers.
- Prefer loading the exported operating-model package from `~/ws/today/metamodel/` when available, and use hand-written fallbacks only as secondary sources.
- Metamodel visualisation, import, and export features should preserve interchangeability with Singine-friendly in-memory opmodel projections.

## Documentation Sources

- `docs/xml/singine-collibra-model.xml`: Canonical model narrative
- `docs/xml/singine-collibra-commands.xml`: Canonical command narrative
- `docs/man/`: Generated and maintained man pages
- `README.md`: Human-oriented repository overview
- `BACKLOG.md`: Open implementation gaps and risks

## Verification

- Run the smallest meaningful verification for the change, and prefer executable checks over pure inspection.
- For Python changes, at minimum run syntax validation and targeted execution paths when possible.
- For command-surface changes, verify the parser wiring or command output path directly.

## Agent-Specific Additions

- Assume the shared 80% contract is mandatory and keep system-specific behavior in a thin compatibility layer.
- New agent integrations should extend the XML contract rather than forking repository policy into unrelated markdown files.
