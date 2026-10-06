#!/usr/bin/env python3
"""Standalone MCP server serving the same libs and skills as the knowledge module, for a host that is not
running metaform yet. stdio transport. Needs: pip install "mcp>=2".

Register (Claude Code):  claude mcp add --transport stdio --scope user knowledge -- python /path/to/server.py
Tools:   lib(name)  skill(name)  scan(workflow, task)  libs()  skills()
Prompts: one per skill, so a person can run /knowledge:<skill> (MCP prompts; in Claude Code the colon form).
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from mcp.server.mcpserver import MCPServer

HERE = Path(__file__).resolve().parent
PROMPTS = ET.parse(HERE / "module" / "knowledge" / "resources" / "prompts.xml").getroot()
LIBS = ("lib_axiom", "lib_metaform", "lib_workflow", "lib_quality")
SKILLS = ("scan", "write_workflow", "import_workflow", "workflow_efficiency", "prompt_efficiency")
REQUIRES = {
    "scan": (), "write_workflow": ("lib_axiom", "lib_metaform", "lib_workflow"),
    "import_workflow": ("lib_axiom", "lib_metaform", "lib_workflow"),
    "workflow_efficiency": ("lib_axiom", "lib_metaform", "lib_workflow", "lib_quality"),
    "prompt_efficiency": ("lib_axiom", "lib_quality"),
}


def _text(name: str) -> str:
    el = PROMPTS.find(name)
    if el is None:
        raise ValueError(f"no prompt element {name}")
    return (el.text or "").strip("\n")


server = MCPServer(
    "knowledge",
    instructions=_text("instructions"),
)


@server.tool()
def lib(name: str) -> str:
    """One reference lib, verbatim. Load it once per agent; skip it if its marker line is already in your context. Names: lib_axiom, lib_metaform, lib_workflow, lib_quality."""
    if name not in LIBS:
        return f"Error: no lib named {name}.\nNext: call libs"
    return _text(name)


@server.tool()
def libs() -> str:
    """The lib names with each one's first line."""
    return "\n".join(f"{n}: {_text(n).splitlines()[0]}" for n in LIBS)


@server.tool()
def skill(name: str) -> str:
    """A task skill's Axiom, to follow now. Its `# requires:` line names the libs to have loaded. Names: scan, write_workflow, import_workflow, workflow_efficiency, prompt_efficiency."""
    if name not in SKILLS:
        return f"Error: no skill named {name}.\nNext: call skills"
    return _text(name)


@server.tool()
def skills() -> str:
    """The skills and the libs each requires."""
    return "\n".join(f"{n}: requires {', '.join(REQUIRES[n]) or 'nothing'}" for n in SKILLS)


@server.tool()
def scan(workflow: str, task: str = "other") -> str:
    """Which libs a workflow or prompt needs for a task (write | import | workflow_efficiency | prompt_efficiency | other). Returns the scan skill with the text bound as data."""
    return _text("scan") + f"\n\n<<DATA: Workflow>>\n{workflow}\n<<END DATA>>\nTask := {task}\n"


def _make_prompt(name: str):
    def _p() -> str:
        libs_ = ", ".join(REQUIRES[name]) or "nothing"
        return (f"Follow this skill now. It requires: {libs_}. Call the `lib` tool only for a lib whose marker "
                f"is not already in your context.\n\n{_text(name)}")
    _p.__name__ = name
    _p.__doc__ = f"Run the {name} skill."
    return _p


for _n in SKILLS:
    server.prompt(name=_n)(_make_prompt(_n))

if __name__ == "__main__":
    server.run("stdio")
