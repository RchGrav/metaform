#!/usr/bin/env bash
# Expand one variation of a packet into the work it stands for.
#
#   expand.sh <origin folder> <variation folder> <output folder>
#
# The variation holds changes.diff, a diff of the text that differs from the origin; files/, a whole copy of each
# binary file that differs; and removed.txt, the files the work no longer has. Each part of the diff applies at the
# lines it names or not at all: when the origin is not the one the diff was taken from, this stops and names the
# file. It needs bash, awk and the usual file commands, and nothing else.
set -eu

[ "$#" -eq 3 ] || { echo "Usage: expand.sh <origin folder> <variation folder> <output folder>" >&2; exit 2; }
origin=${1%/} variation=${2%/} output=${3%/}
[ -n "$origin" ] && [ -d "$origin" ] || { echo "No origin folder at $origin." >&2; exit 2; }
[ -n "$variation" ] && [ -d "$variation" ] || { echo "No variation folder at $variation." >&2; exit 2; }
[ -n "$output" ] || { echo "The output folder has no name." >&2; exit 2; }

# A path from the packet stays inside the output folder: it is never absolute and never climbs out.
inside() {
  case "/$1/" in
    //*|*/../*|*/./*) return 1 ;;
  esac
  [ -n "$1" ]
}

mkdir -p "$output"
cp -R "$origin"/. "$output"/

if [ -s "$variation/changes.diff" ]; then
  awk -v origin="$origin" -v output="$output" -v changes="$variation/changes.diff" '
    function fail(path) { printf "%s is not as it was when the diff was taken.\n", path > "/dev/stderr"; exit 1 }
    function quoted(text) { gsub(/\047/, "\047\\\047\047", text); return "\047" text "\047" }
    function outside(path) { return path == "" || substr(path, 1, 1) == "/" || ("/" path "/") ~ /\/\.\.?\// }
    # The lines of a file, and whether its last line has no newline after it.
    function load(file, lines,    text, first, record, count) {
      text = ""; first = 1
      while ((getline record < file) > 0) { text = first ? record : text RS record; first = 0 }
      close(file)
      ended = 1
      if (text == "") return 0
      count = split(text, lines, "\n")
      if (lines[count] == "") count--; else ended = 0
      return count
    }
    BEGIN {
      RS = "\001"
      total = load(changes, diff)
      at = 1
      while (at <= total) {
        if (substr(diff[at], 1, 4) != "--- " || substr(diff[at + 1], 1, 6) != "+++ b/") { at++; continue }
        based = substr(diff[at], 5) != "/dev/null"
        path = substr(diff[at + 1], 7)
        if (outside(path)) { printf "%s is outside the work.\n", path > "/dev/stderr"; exit 1 }
        at += 2
        have = 0; bare = 0
        if (based) {
          have = load(origin "/" path, old)
          bare = have && !ended
        }
        made = 0; from = 1; open = 0
        while (at <= total && substr(diff[at], 1, 4) == "@@ -") {
          split(diff[at], part, " ")
          counts = split(substr(part[2], 2), was, ","); start = was[1] + 0
          need_old = (counts > 1) ? was[2] + 0 : 1
          counts = split(substr(part[3], 2), now, ",")
          need_new = (counts > 1) ? now[2] + 0 : 1
          to = need_old ? start : start + 1
          if (to < from || to > have + 1) fail(path)
          while (from < to) { new[++made] = old[from]; open = (bare && from == have); from++ }
          at++
          while (need_old > 0 || need_new > 0 || diff[at] == "\\ No newline at end of file") {
            line = diff[at]
            if (line == "\\ No newline at end of file") { at++; continue }
            kind = substr(line, 1, 1); text = substr(line, 2)
            unended = (diff[at + 1] == "\\ No newline at end of file")
            if (kind == "+") { new[++made] = text; open = unended; need_new-- }
            else {
              if (from > have || old[from] != text || (bare && from == have) != unended) fail(path)
              if (kind == " ") { new[++made] = text; open = unended; need_new-- }
              from++; need_old--
            }
            at++
          }
        }
        while (from <= have) { new[++made] = old[from]; open = (bare && from == have); from++ }
        target = output "/" path
        folder = target; sub(/\/[^\/]*$/, "", folder)
        system("mkdir -p " quoted(folder))
        printf "" > target
        for (line = 1; line <= made; line++) printf "%s%s", new[line], (line == made && open) ? "" : "\n" > target
        close(target)
      }
    }'
fi

if [ -d "$variation/files" ]; then
  cp -R "$variation/files"/. "$output"/
fi

if [ -f "$variation/removed.txt" ]; then
  while IFS= read -r path || [ -n "$path" ]; do
    [ -n "$path" ] || continue
    inside "$path" || { echo "$path is outside the work." >&2; exit 1; }
    if [ -f "${output:?}/${path:?}" ]; then
      rm -f -- "${output:?}/${path:?}"
    fi
  done < "$variation/removed.txt"
fi
echo "Expanded into $output"
