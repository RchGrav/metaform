"""knowledge: reference libs and task skills, served once per agent.

Written to the module contract as BASE-035 / BASE-015 / BASE-050 describe it (Module, Verb, Noun,
Stop, Context; metaform.prompt_files; metaform.nonce). Check the signatures against the records
before merging; the chassis is the authority, this file is the sketch.
"""
from __future__ import annotations

from metaform.module import Context, Module, Noun, Stop, Verb
from metaform import nonce, prompt_files

SUPPORTED_OS = ("linux", "macos", "windows")   # BASE-015: top-level literals, read with ast
DEPENDENCIES = ()
SHIPS_DISABLED = False

LIBS = ("lib_axiom", "lib_metaform", "lib_workflow", "lib_quality")
SKILLS = ("scan", "write_workflow", "import_workflow", "workflow_efficiency", "prompt_efficiency")
REQUIRES = {   # what each skill names in its `# requires:` line; the server does not pre-load them
    "scan": (),
    "write_workflow": ("lib_axiom", "lib_metaform", "lib_workflow"),
    "import_workflow": ("lib_axiom", "lib_metaform", "lib_workflow"),
    "workflow_efficiency": ("lib_axiom", "lib_metaform", "lib_workflow", "lib_quality"),
    "prompt_efficiency": ("lib_axiom", "lib_quality"),
}


def _prompt(name: str) -> str:
    return prompt_files.text(__name__, name)      # reads resources/prompts.xml by element name (MCP-031)


def lib(ctx: Context) -> str:
    """knowledge lib <name>: one reference lib, verbatim. Load it once; its first line is its marker."""
    name = ctx.nouns["name"]
    if name not in LIBS:
        raise Stop(f"No lib named {name}.", "knowledge libs")
    return _prompt(name)


def libs(ctx: Context) -> str:
    """knowledge libs: the lib names, one per line, with the first line of each."""
    return "\n".join(f"{n}: {_prompt(n).splitlines()[0]}" for n in LIBS)


def skill(ctx: Context) -> str:
    """knowledge skill <name>: the skill's Axiom, to follow now. It names the libs it requires."""
    name = ctx.nouns["name"]
    if name not in SKILLS:
        raise Stop(f"No skill named {name}.", "knowledge skills")
    return _prompt(name)


def skills(ctx: Context) -> str:
    """knowledge skills: the skill names and the libs each requires."""
    return "\n".join(f"{n}: requires {', '.join(REQUIRES[n]) or 'nothing'}" for n in SKILLS)


def scan(ctx: Context) -> str:
    """knowledge scan <workflow> [task=...]: serves the scan skill with the workflow bound as data."""
    text = ctx.nouns["workflow"]
    task = ctx.nouns.get("task") or "other"
    return _prompt("scan") + f"\n\n<<DATA: Workflow>>\n{text}\n<<END DATA>>\nTask := {task}\n"


def assign(ctx: Context) -> str:
    """knowledge assign <skill> [input=...]: hands a skill to a fresh agent as a task, by nonce (BASE-050).

    The fresh agent runs `metaform <nonce>` and receives the skill, the libs it requires, and the input,
    with nothing else in its context. That is how a skill is called system-wide, in any host.
    """
    name = ctx.nouns["skill"]
    if name not in SKILLS:
        raise Stop(f"No skill named {name}.", "knowledge skills")
    reached = nonce.reached()
    if reached is None:
        n = nonce.request("knowledge", "assign", value={"skill": name, "input": ctx.nouns.get("input")})
        return f"metaform {n}"
    value = nonce.read(reached)["value"]
    parts = [_prompt(l) for l in REQUIRES[value["skill"]]] + [_prompt(value["skill"])]
    if value.get("input"):
        parts.append(f"<<DATA: Input>>\n{value['input']}\n<<END DATA>>")
    parts.append("When your YIELD is complete, run: metaform <this nonce> complete")
    return "\n\n".join(parts)


def complete(ctx: Context) -> str:
    """knowledge complete: closes the nonce of the assignment the agent came through."""
    n = nonce.current()
    nonce.close(n)
    return "Assignment closed."


MODULE = Module(
    id="knowledge",
    summary="Reference libs and task skills, loaded once per agent.",
    purpose=("Serves the Axiom, metaform, workflow and quality reference libs and five task skills. "
             "Load a lib once and skip it when its marker is already in your context. metaform help knowledge"),
    verbs=(
        Verb("lib", lib, "One reference lib, verbatim.", nouns=(Noun("name", "lib name"),)),
        Verb("libs", libs, "List the libs."),
        Verb("skill", skill, "A task skill's Axiom.", nouns=(Noun("name", "skill name"),)),
        Verb("skills", skills, "List the skills and what each requires."),
        Verb("scan", scan, "Which libs a workflow needs.",
             nouns=(Noun("workflow", "workflow text or address"), Noun("task", "write|import|workflow_efficiency|prompt_efficiency", required=False))),
        Verb("assign", assign, "Hand a skill to a fresh agent by nonce.",
             nouns=(Noun("skill", "skill name"), Noun("input", "the skill's input text", required=False))),
        Verb("complete", complete, "Close this assignment's nonce."),
    ),
)
