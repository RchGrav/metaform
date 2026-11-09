"""Measure operation-specific slices of the intake document.

Blocks are character offsets into the owner's file. No intake wording is stored
here; the script stops if the file's hash differs from the one in blocks.json.

usage: slice.py [--write DIR]
"""
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
TERMS = {
    "c.aue": r"\bAUEs?\b", "c.re": r"\bREs?\b", "c.op": r"\bOPs?\b", "c.ef": r"\bEFs?\b",
    "c.pe": r"\bPEs?\b", "c.cqu": r"\bCQUs?\b", "c.at": r"\bATs?\b", "c.ne": r"\bNEs?\b",
    "c.de": r"\bDEs?\b", "c.se": r"\bSEs?\b", "c.ifd": r"\bifd\b|\bIFD\b", "c.ns": r"\bNS\b",
    "c.ice": r"\bICE\b", "c.parametric": r"(?i)\bparametric", "c.purpose": r"\bpurpose record",
    "c.entity": r"(?i)\bentit(y|ies)\b", "c.element": r"(?i)\belements?\b",
}


def tokens(text):
    return len(text.encode()) // 4


def main():
    spec = json.loads((HERE / "blocks.json").read_text())
    raw = pathlib.Path(spec["source"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec["sha256"]:
        sys.exit("source changed: re-check every offset before measuring")
    src = raw.decode()
    text = {b: src[s:e] for b, (s, e) in spec["blocks"].items()}

    spans = sorted(spec["blocks"].values())
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        sys.exit("blocks overlap")
    gaps = [src[a[1]:b[0]] for a, b in zip([[0, 0]] + spans, spans + [[len(src), 0]])]
    left = re.sub(r"<[^>]*>|\s+", "", "".join(gaps))
    print(f"source {len(raw)} bytes, ~{tokens(src)} tokens; {len(text)} blocks; unassigned text: {left!r}")

    def close(ids):
        have, todo = set(ids), list(ids)
        while todo:
            body = text[todo.pop()]
            for c, pat in TERMS.items():
                if c not in have and re.search(pat, body):
                    have.add(c)
                    todo.append(c)
        return have

    def size(ids):
        return sum(tokens(text[b]) for b in ids)

    usable = [b for b in text if b not in spec["retired"]]
    full = size(usable)
    print(f"retired: ~{size(spec['retired'])} tokens; usable: ~{full}")
    print(f"\n{'operation':26}{'blocks':>7}{'+terms':>7}{'tokens':>8}{'% of usable':>13}")
    for op, ids in spec["operations"].items():
        c = close(ids)
        print(f"{op:26}{len(ids):7}{len(c) - len(ids):7}{size(c):8}{100 * size(c) // full:12}%")
        if "--write" in sys.argv:
            out = pathlib.Path(sys.argv[sys.argv.index("--write") + 1])
            out.mkdir(parents=True, exist_ok=True)
            order = [b for b in spec["blocks"] if b in c]
            (out / f"{op}.txt").write_text("\n".join(text[b] for b in order))

    print(f"\nall concepts: ~{sum(tokens(t) for b, t in text.items() if b.startswith('c.'))} tokens")
    print(f"examples: ~{sum(tokens(t) for b, t in text.items() if b.startswith('x.'))} tokens")
    saved = size(spec["omit_candidates"])
    print(f"omit candidates: ~{saved} tokens, {100 * saved / full:.1f}% of usable")
    print(f"duplicate groups: {len(spec['duplicates'])}, across {sum(len(v) for v in spec['duplicates'].values())} blocks")


main()
