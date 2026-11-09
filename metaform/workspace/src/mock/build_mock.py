#!/usr/bin/env python3
"""Build the graph workspace mock data from the project's real maps.

Output: workspace.json beside this script. Every project is stored as its raw dump, the nested JSON that
`{".": {}}` returns (R-5.34). The mock GraphSource derives `map`, `goto` and layer reads from
that dump, so the mock cannot drift from the read forms.

Sources (read only):
- metaform/metaform-canonical.json: the Metaform map from the earlier system.
- roundtable/metaform.json: the Roundtable map.
- metaform/intake-example.json: the small `mashtrac` intake example.

Adjustments, each so that the dump matches the current specification:
- Old role codes become role names: DE is Definitive, SE is Supportive, NE is Notable (R-3.13).
  CQU is not a role (R-3.15), so it is dropped.
- Only intake fields (technical_name, name, role, uri, status), wants and the layers named
  below are kept. Older fields such as `references` and `investigations` are dropped (R-6.13).
- Wants that name an address missing from the map are dropped.
- `layer.document.specification` is added with the definition the server seeds (R-6.24).
- Specification, memory and skills records are sample data, marked "mock" in their text.

Run: python3 metaform/workspace/src/mock/build_mock.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # the repository root
OUT = Path(__file__).with_name("workspace.json")

INTAKE = ["technical_name", "name", "role", "uri", "status"]
ROLES = {"DE": "Definitive", "SE": "Supportive", "NE": "Notable",
         "Definitive": "Definitive", "Supportive": "Supportive",
         "Notable": "Notable", "Divergent": "Divergent"}
OLD_WANT = {"goal": "why", "function": "how", "intent": "direction"}
SCOPES = ["code", "document", "media", "data", "collection", "upstream", "downstream", "layer"]

SPEC_DEFINITION = {
    "technical_name": "specification document layer",
    "name": "Specification",
    "role": "Supportive",
    "description": "Prose that the skeleton leaves out on purpose: what each element does, "
                   "how it behaves and why, as blocks with Markdown heading levels.",
    "template": "{title}: {text}",
    "format": "markdown_blocks",
    "instruction": "(mock) The server seeds this definition; the real instruction is "
                   "metaform_core::specification::INSTRUCTION.",
}


def children(node):
    # Field values are strings or arrays; `wants` is the one dictionary that is not a child.
    return {k: v for k, v in node.items() if isinstance(v, dict) and k != "wants"}


def addresses(node, prefix=()):
    for key, child in children(node).items():
        path = prefix + (key,)
        yield ".".join(path), child
        yield from addresses(child, path)


def clean(node, known):
    """Return a copy of `node` in the current dump form."""
    out = {}
    for field in INTAKE:
        value = node.get(field)
        if field == "role" and isinstance(value, str):
            value = ROLES.get(value)
        if isinstance(value, str) and value:
            out[field] = value
    raw = node.get("wants") or {}
    if isinstance(raw, list):
        # Older maps (roundtable/metaform.json) hold wants as a list of one-key dictionaries
        # with the earlier field names goal, function and intent.
        raw = {k: v for item in raw if isinstance(item, dict) for k, v in item.items()}
    wants = {}
    for other, record in raw.items():
        if other in known and isinstance(record, dict):
            record = {OLD_WANT.get(k, k): v for k, v in record.items()}
            wants[other] = {k: record[k] for k in ("why", "how", "direction") if k in record}
    if wants:
        out["wants"] = wants
    for key, child in children(node).items():
        out[key] = clean(child, known)
    return out


def load(path, key):
    tree = json.loads((ROOT / path).read_text())[key]
    tree = {k: v for k, v in tree.items() if k in SCOPES}
    known = {address for address, _ in addresses(tree)}
    return {scope: clean(node, known) for scope, node in tree.items()}


def at(tree, address):
    node = tree
    for segment in address.split("."):
        node = node.setdefault(segment, {})
    return node


def link(project, address):
    # The mock uses the project name as its id. Real ids are opaque (dev/graph_workspace_seam.md).
    return f"metaform://map/project/{project}/main#{address}"


def spec(title, text):
    return [{"level": 1, "title": title, "text": f"(mock) {text}"}]


def memory(name, *observations):
    # Memory records follow the MCP sample memory server's entity form (R-6.15).
    return {"name": name, "entityType": "fact", "observations": [f"(mock) {o}" for o in observations]}


def skill(name, description):
    return {"frontmatter": {"name": name, "description": f"(mock) {description}"},
            "uri": f"skill://{name}"}


def canonical(node):
    """The order metaform-core's `Map::to_tree` writes (JD-011): intake fields in R-6.15 order,
    the other fields by name, then `wants` by address (each want: why, how, direction, then the
    rest by name), then child elements by segment."""
    fields = {k: v for k, v in node.items() if not isinstance(v, dict)}
    out = {k: fields[k] for k in INTAKE if k in fields}
    out.update({k: fields[k] for k in sorted(fields) if k not in INTAKE})
    if isinstance(node.get("wants"), dict) and node["wants"]:
        out["wants"] = {
            other: {**{k: w[k] for k in ("why", "how", "direction") if k in w},
                    **{k: w[k] for k in sorted(w) if k not in ("why", "how", "direction")}}
            for other, w in sorted(node["wants"].items())}
    for key in sorted(children(node)):
        out[key] = canonical(node[key])
    return out


def project(name, tree, records):
    at(tree, "layer.document.specification").update(SPEC_DEFINITION)
    for address, layer, value in records:
        if address in {a for a, _ in addresses(tree)}:
            at(tree, address).setdefault(layer, []).append(value)
    return {"id": name, "name": name, "folder": f"~/{name}", "dump": canonical(tree)}


def main():
    metaform = load("metaform/metaform-canonical.json", "metaform")
    roundtable = load("roundtable/metaform.json", "roundtable")
    mashtrac = load("metaform/intake-example.json", "mashtrac")

    # Cross-project links. Linking an upstream element to another registered project is not
    # specified (owner gap 3 in the seam document, dev/graph_workspace_seam.md). The mock follows that document's
    # option a: `uri` is the other map's resource URI, and the fragment names the element there.
    at(roundtable, "upstream.service.metaform").update({
        "technical_name": "functional map server", "name": "Metaform", "role": "Supportive",
        "uri": link("metaform", "code.server.tool")})
    at(metaform, "downstream.coordinator.roundtable").update({
        "technical_name": "roundtable coordinator", "name": "Roundtable", "role": "Notable",
        "uri": link("roundtable", "code.adapter.agent")})
    at(mashtrac, "upstream.service.metaform").update({
        "technical_name": "functional map server", "name": "Metaform", "role": "Supportive",
        "uri": link("metaform", "code.server.tool")})

    # A chained map (R-4.15, D-16): an element can hold its own functional map for reference.
    # Seen from the parent map, the held map sits under `upstream` at the holder's address: the
    # upstream project's Definitive element is upstream.code.engine.workflow, placed inside our
    # code.engine.workflow, with the rest of its map beneath. No want links the two. The
    # Definitive element's `uri` names the upstream repository. SIMULATED: a small reference map;
    # the uri uses the reserved .invalid domain (RFC 2606), so it can never name a real one.
    chained = "upstream.code.engine.workflow"
    reference = {
        "": ("workflow engine reference map", "workflow (mock)", "Definitive"),
        "code.interpreter.flow": ("control flow interpreter", "Interpreter", "Supportive"),
        "code.transport.call": ("procedure call transport", "Call transport", "Supportive"),
        "code.store.frame": ("call frame store", "Frames", "Supportive"),
        "code.verifier.step": ("step result verifier", "Verifier", "Notable"),
        "code.policy.retry": ("retry policy", "Retry", "Notable"),
        "document.procedure": ("authored procedure", "Procedures", "Supportive"),
    }
    for suffix, (technical, label, role) in reference.items():
        at(metaform, f"{chained}.{suffix}" if suffix else chained).update(
            {"technical_name": technical, "name": label, "role": role})
    for holder, wanted, why, how, direction in [
        ("code.interpreter.flow", "document.procedure", "(mock) Interpret the authored control flow.", "(mock) Reads each procedure's steps in order.", "inbound"),
        ("code.interpreter.flow", "code.transport.call", "(mock) Run each step as a call.", "(mock) Sends one call per step and waits for its result.", "outbound"),
        ("code.transport.call", "code.store.frame", "(mock) Resume interrupted calls.", "(mock) Saves and restores call frames.", "two-way"),
        ("code.interpreter.flow", "code.verifier.step", "(mock) Accept only checked results.", "(mock) Passes each result through the verifier.", "outbound"),
        ("code.verifier.step", "code.policy.retry", "(mock) Recover from a failed check.", "(mock) Asks the retry policy whether to run the step again.", "outbound"),
    ]:
        at(metaform, f"{chained}.{holder}").setdefault("wants", {})[f"{chained}.{wanted}"] = {
            "why": why, "how": how, "direction": direction}
    at(metaform, chained)["uri"] = "https://example.invalid/mock/workflow-engine"

    projects = {
        "metaform": project("metaform", metaform, [
            ("code.server.tool", "specification", spec("Project map tool", "One MCP tool, project-map, carries every map command.")),
            ("code.server.tool", "memory", memory("project-map", "goto keeps record counts, not records.")),
            ("code.store.memory", "specification", spec("Memory store", "Durable facts kept at the address they come from.")),
            ("code.service.decision", "memory", memory("Jev", "The decision service in the earlier system.")),
            ("code.interface.graphical", "specification", spec("Graph workspace", "The web interface for the map.")),
            ("code.interface.graphical", "skills", skill("graph-workspace", "How to work on the graph workspace.")),
        ]),
        "roundtable": project("roundtable", roundtable, [
            ("code.adapter.agent", "specification", spec("Agent adapter", "Runs a model as an ACP participant.")),
            ("code.adapter.agent", "memory", memory("adapter", "Two routes exist; the first to build is not decided.")),
        ]),
        "mashtrac": project("mashtrac", mashtrac, []),
    }

    # Agent presence has no backend source yet (the agents module is not specified, SPEC
    # section 11). These agents are simulated.
    agents = [
        {"id": "ida", "name": "Ida", "project": "metaform", "at": "code.store.memory", "activity": "writing specification"},
        {"id": "marcus", "name": "Marcus", "project": "metaform", "at": "code.server.tool", "activity": "reading goto"},
        {"id": "jorge", "name": "Jorge", "project": "roundtable", "at": "code.adapter.agent", "activity": "idle"},
    ]

    # Simulated updates. Each is applied to the mock dump; then the mock emits "map changed"
    # for the project, which is what the real server sends (notifications/resources/updated).
    events = [
        {"after_s": 6, "agent": "ida", "project": "metaform", "address": "code.store.memory",
         "write": {"layer": "specification", "record": {"level": 2, "title": "Recall", "text": "(mock) Facts are read by presence."}}},
        {"after_s": 14, "agent": "marcus", "project": "metaform", "address": "code.server.tool",
         "move": "code.server.hosting"},
        {"after_s": 22, "agent": "jorge", "project": "roundtable", "address": "code.adapter.agent",
         "write": {"layer": "memory", "record": memory("adapter", "Pi + pi-acp is the existing route.")}},
    ]

    out = {"simulated": True, "projects": projects, "agents": agents, "events": events}
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    for name, p in projects.items():
        n = sum(1 for _ in addresses(p["dump"]))
        w = sum(len(e.get("wants", {})) for _, e in addresses(p["dump"]))
        print(f"{name}: {n} addresses, {w} wants")


if __name__ == "__main__":
    main()
