#!/usr/bin/env python3
"""Show every action of a test intake, one line each, as the agent takes it.

usage: watch.py <stream.jsonl>            print the actions of a finished run
       watch.py <stream.jsonl> --follow   keep printing as a running agent acts

The file is the transcript that `claude -p --output-format stream-json` writes. Each line
printed is one thing the agent did: text it wrote, a photo it opened, or a command it sent to
the project-map tool, followed by the server's answer.
"""
import json, os, sys, time

def short(text, width=200):
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: width - 1] + "…"

def show(event, pending):
    kind = event.get("type")
    if kind == "assistant":
        for block in (event.get("message") or {}).get("content") or []:
            if block.get("type") == "text" and block.get("text", "").strip():
                print("SAYS   ", short(block["text"], 400))
            elif block.get("type") == "tool_use":
                name, given = block["name"], block.get("input") or {}
                if name == "Read":
                    line = "OPENS   " + os.path.basename(given.get("file_path", ""))
                elif name == "Glob":
                    line = "LISTS   " + str(given.get("pattern", ""))
                else:
                    line = "SENDS   " + short(json.dumps(given, ensure_ascii=False), 600)
                pending[block["id"]] = name
                print(line)
    elif kind == "user":
        for block in (event.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                name = pending.pop(block.get("tool_use_id"), "")
                if name in ("Read", "Glob"):
                    continue
                content = block.get("content")
                text = content if isinstance(content, str) else " ".join(p.get("text", "") for p in content if isinstance(p, dict))
                refused = '"status":"error"' in text
                print(("  REFUSED " if refused else "  ANSWER  ") + short(text, 500))
    elif kind == "result":
        print("DONE    %s s, %s turns, $%.2f" % (round(event.get("duration_ms", 0) / 1000), event.get("num_turns"), event.get("total_cost_usd") or 0))
    sys.stdout.flush()

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path, follow = sys.argv[1], "--follow" in sys.argv[2:]
    pending = {}
    with open(path) as stream:
        while True:
            line = stream.readline()
            if not line:
                if not follow:
                    return
                time.sleep(0.5)
                continue
            try:
                show(json.loads(line), pending)
            except json.JSONDecodeError:
                pass

if __name__ == "__main__":
    main()
