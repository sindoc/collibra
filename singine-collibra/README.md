# singine-collibra

Collibra-specific implementation home for the `singine collibra ...` command
family.

Layout:

- `python/singine_collibra/` contains the importable Python package used by
  Singine
- top-level names prefer hyphens, hence `singine-collibra/`
- the Python package keeps the underscore because Python import names do not
  support hyphens

Integration principle:

- the Collibra metamodel and its four-letter codes are a canonical integration
  contract across Collibra, Singine, SilkPage, and Edge-facing workflows
