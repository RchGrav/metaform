"""What a built wheel needs to know about the chassis package it was built from, BASE-041.

`CHASSIS_DEPENDENCIES` is the `[project].dependencies` array of the chassis
`pyproject.toml`, copied here because an installed package has no
`pyproject.toml`; a repository test fails when the two differ.
"""
CHASSIS_DEPENDENCIES = ('prompt_toolkit>=3.0', 'networkx>=3.3', 'grand-cypher>=0.12')
REQUIRES_PYTHON = '>=3.11'
