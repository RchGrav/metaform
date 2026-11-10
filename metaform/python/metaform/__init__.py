"""Metaform, the Python form: the `project-map` tool over stdio MCP, on a SQLite store laid out
as a structure of arrays. The design is `metaform/docs/designs/sqlite-forms.md`. Each module
names the Rust module it ports.
"""

# The version the server reports. It is the Rust form's, because an agent must not be able to
# tell the forms apart.
VERSION = "0.1.0"
