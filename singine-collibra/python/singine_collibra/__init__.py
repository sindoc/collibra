"""singine_collibra — core Python implementation of singine collibra subcommands.

This package lives under ``collibra/singine-collibra/python/`` and is
dynamically imported by the singine CLI when ``singine collibra id``,
``singine collibra contract``, ``singine collibra io``,
``singine collibra query``, ``singine collibra quantum``, or
``singine collibra server`` subcommands are invoked.

The collibra repo is the system-of-record for Collibra-specific implementations.
Singine provides the secure CLI/runtime front-end; this package provides the
Collibra-aware core logic. Transformation-heavy XML/RDF/XSLT/XPath work should
prefer SilkPage when feasible.
"""
