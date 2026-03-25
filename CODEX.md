# CODEX.md - Collibra Repository Boundary

This repository is the system of record for Collibra-specific code.

Rules:

1. Implement Collibra REST, SDK, CLI, and Edge logic here.
2. Expose that logic to Singine through `singine_collibra/` and `COLLIBRA_DIR`
   discovery rather than duplicating Collibra-aware code in `singine/`.
3. Keep Singine focused on secure execution, identity, privileges, JVM
   orchestration, and docs/runtime publication.
4. Route XML/XSLT/XPath/RDF/TTL/SPARQL/SQL/GraphQL transformation-heavy work
   toward SilkPage where possible.

Practical test:

- If the code depends on Collibra semantics, it belongs here.
- If the code is generic execution/runtime infrastructure, it belongs in
  Singine.
- If the code is primarily cross-format transformation, it belongs in
  SilkPage.
