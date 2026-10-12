"""The orientation-cost evaluation: what it costs an agent to find its place, with no context, with a generated
AGENTS.md overview, or handed its work by Metaform as dispatch hands a ticket.

    python -m scripts.orientation_eval --dry-run --allow-dirty
    python -m scripts.orientation_eval -k 1 --task mf-unnamed-launcher --task mf-ticket-short-name --allow-dirty

It sits outside the default pytest run: every real run spends tokens. Each task of the declared task set,
scripts/orientation_tasks.json, runs k times in each arm on headless Claude Code (`claude -p`):

  none             the repository and the request, nothing else;
  agents_md        an AGENTS.md overview generated once and cached, which Claude Code reads at the root when there is
                   no CLAUDE.md (code.claude.com/docs/en/memory#agents-md);
  metaform         Metaform as it ships: the MCP server (its connect instructions), the dispatch module on, the request
                   recorded as a ticket at the Address the task names (the oracle node), and the prompt exactly what
                   `metaform dispatch handoff id=<ticket>` prints, the first turn dispatch sends an agent over ACP;
  metaform_chosen  the same, at the node a blind placement pass chose from the request alone, with only the map's
                   tools; the placement's cost is recorded beside the run;
  metaform_warm    arm metaform after the task's seed (another task at the same node) was worked first in the same
                   folder and home, so the task starts from the memories and the ticket the seed left; the seed's cost
                   is recorded apart, as AGENTS.md's is;
  metaform_brief   not run by default: the JSON read of metaform://<Address> followed by the bare request, with the
                   dispatch module off, as the first version of this evaluation did.

The Metaform under test is this repository's working tree, frozen once per invocation as a git commit object through
an index of its own (the working tree, its index and its branches are not touched) and copied from that commit, so
edits made while it runs do not reach it; the commit id is recorded and source.tar.gz is kept beside the results. A
tree that differs from HEAD is refused unless --allow-dirty is given, and one with untracked test modules unless
--allow-dirty-tests is. Before any run, the start state is checked as an agent checking its work would meet it: the
suite's collection errors and the failures of the test modules that import the files the tasks fix; a run whose shell
output showed one of them is marked.

The Metaform arms run on the map the task set names with the code layer the shipped flow adds after an intake (P167),
read by map code-import from tree-sitter, which is installed with uv into the cache, never into the project's
environment (--no-code-layer leaves it out). The results say which map the arms ran on and whether the code layer
holds each task's graded file at its oracle Address. A request that names an Address on the map is refused. On a task of this repository the server, the CLI and
the agent's `metaform` all run from the run's own workspace (PYTHONPATH=<workspace>/src), so the code served is the
code being edited, as the editable install serves it to the person; on another repository they run from the copy.

Every run works in its own copy of the repository under a neutral scratch folder (default /tmp; refused when a folder
above it holds CLAUDE.md or AGENTS.md): no CLAUDE.md, AGENTS.md or .claude folder, the task's setup applied, its own
Metaform home in METAFORM_HOME (an empty one for the arms without Metaform), and a bin folder first on PATH whose
`metaform`, `python` and `python3` run this interpreter on the run's source. With --auth env (the default) it also gets
its own empty HOME, so Claude Code reads no user configuration; the credential comes from ANTHROPIC_API_KEY or
CLAUDE_CODE_OAUTH_TOKEN in this environment, and only this mode is for numbers to be quoted. --auth login uses the
login already on this machine instead, with user settings, hooks, plugins, skills, MCP servers, auto memory and the user
CLAUDE.md turned off by flags; the run shares the person's HOME, so what it leaves there is listed after it: Claude
Code's own per-session state is expected, anything else (a new file at the top of the home, a Metaform or Claude Code
project named for the run's folder) keeps the run out of the summaries.

Writes are found on the file system, not in the commands: a PostToolUse hook given with --settings records the git tree
of the workspace after every tool call. The first write is the first call after which the tree differs from the start;
the first correct edit is the first tree the grader passes on. Recorded per run: input tokens before the first write,
turns to the first correct edit, total tokens, cost, pass or fail on the end state, and how far Metaform's orientation
reached the agent (Metaform tool calls, resource reads, memory reads, ToolSearch queries, permission denials by tool,
prompt bytes), and where the tokens went: each main-thread request in one phase (orientation, work, verification,
bookkeeping, closing), and each tool result's size with the tokens it cost by being carried in by every later request.
Every request's input is split as Claude Code's stream-json reports it: uncached input, cache written and cache read;
the headline numbers are the context the agent carried (all three) and the fresh tokens (uncached plus written), with
list-price USD beside them as a secondary figure. Every block of text Metaform delivered (the connect instructions,
the hand-off prompt, the tool descriptions loaded, each Metaform result) that the agent's context holds more than once
is listed with its size and where each copy came from: a duplicate is a defect to remove at its source.
--remeasure <results folder> measures a finished run's kept transcripts again, spending nothing.
Per task and arm across the k runs: pass@k, pass^k, mean and standard deviation; per task, the paired difference from
arm none. Results are written as results.json and results.md under artifacts/orientation-eval/<UTC time>/.

--dry-run proves each task: its grader fails on the start and passes on the reference; no file but the target holds
the marker, the anchor's text or the setup's original text; and the target file does not rank in the top five files
for a grep of the request's own words, so a request cannot be answered by one grep.

The spend cap bounds the whole invocation: each claude call is given the smaller of --run-budget-usd and what is left
of --spend-cap-usd as its --max-budget-usd, and no call starts once less than --min-run-usd is left. Claude Code's cap
is checked against its own estimate and can be passed by the last call, so the cap holds within one call's overrun.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import itertools
import json
import math
import os
import re
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, cast

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / 'scripts' / 'orientation_tasks.json'
OUT = ROOT / 'artifacts' / 'orientation-eval'
ARMS = ('none', 'agents_md', 'metaform', 'metaform_chosen', 'metaform_warm', 'metaform_brief')
DEFAULT_ARMS = ('none', 'agents_md', 'metaform', 'metaform_chosen', 'metaform_warm')
METAFORM_ARMS = {'metaform', 'metaform_chosen', 'metaform_warm', 'metaform_brief'}
CONTEXT_FILES = ('CLAUDE.md', 'CLAUDE.local.md', 'AGENTS.md', '.claude', '.mcp.json')
# Never copied from this repository: the evaluation itself, which holds every task's answer, and its results.
OWN = ('scripts/orientation_eval.py', 'scripts/orientation_tasks.json', 'artifacts')
# What running code leaves behind is not a write: kept out of every workspace's git by .git/info/exclude.
LEFTOVERS = ('__pycache__/', '*.pyc', '.pytest_cache/', '.ruff_cache/', '.mypy_cache/', '*.egg-info/', '.venv/')
FILE_WRITES = {'Edit', 'Write', 'MultiEdit', 'NotebookEdit'}
# Only when the hook left no record: a Bash command that writes a file (in-place edits, redirection to a file, tee,
# patch, git apply). A heuristic; what a script does inside python -c is not seen.
BASH_WRITE = re.compile(r'\bsed\s+(-\w*\s+)*-i|\bperl\s+-\w*i|\btee\b|\bpatch\b|\bgit\s+apply\b|'
                        r'(?<![-=<>0-9&])>>?\s*(?!/dev/|&)(?!\d+\b)[\w./~-]')
# Only these reach a claude child: the path, locale and terminal, and the documented credentials
# (code.claude.com/docs/en/authentication#authentication-precedence). The parent session's own variables never do.
PASSED = ('PATH', 'LANG', 'LC_ALL', 'TERM', 'USER', 'LOGNAME', 'SHELL', 'TZ')
CREDENTIALS = ('ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL')
# Every arm may check its own work, as the project's own documents tell it to (code.claude.com/docs/en/permissions:
# `:*` is a trailing wildcard, and each part of a compound command must match a rule on its own; tail, head and grep
# are read-only already and need no rule, named here so the list says what a check may pipe through). `uv` is the bin
# folder's shim, which runs the command on this interpreter and answers sync and pip with nothing to do.
CHECKS = ('Bash(python3:*)', 'Bash(python:*)', 'Bash(pytest:*)', 'Bash(uv run:*)', 'Bash(uv sync:*)',
          'Bash(uv pip:*)', 'Bash(tail:*)', 'Bash(head:*)', 'Bash(grep:*)', 'Bash(sort:*)')
# An arm with Metaform may use all of it: its tools, its resources, the deferred-tool search, and its CLI.
METAFORM_TOOLS = ('mcp__metaform', 'ReadMcpResourceTool', 'ListMcpResourcesTool', 'ToolSearch', 'Bash(metaform:*)')
# The placement pass reads the map only.
PLACEMENT_TOOLS = 'ToolSearch,ReadMcpResourceTool,ListMcpResourcesTool'
ADDRESS = re.compile(r'\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+\b')
# The code layer's provider, installed apart from the project's environment into the evaluation's cache and put on the
# Metaform processes' path only (P167: map code-import reads tree-sitter's tags queries).
TREE_SITTER = ('tree-sitter==0.26.0', 'tree-sitter-python==0.25.0')
# Paths every Metaform process of a run imports besides the source under test: the code layer's provider.
EXTRA_PATH: list[Path] = []
# A test module an untracked file would add to every agent's test run.
TEST_MODULE = re.compile(r'(^|/)(test_[^/]*|[^/]*_test|conftest)\.py$')
# Bookkeeping the hand-off asks of an agent once its work is done: its ticket's steps and its memories.
BOOKKEEPING = re.compile(r'^mcp__metaform__(map_work|memory_(create|add|delete)\w*)$')
# Anthropic's list prices in USD per million tokens, as of 2026-10-06 (platform.claude.com pricing): input and output,
# and a cache read. A cache write is 1.25 times input for the 5-minute TTL and 2 times for the 1-hour TTL, which Claude
# Code writes. Claude Haiku 5.5 bills a request whose prompt passes 100K tokens at its long rates. A model not listed
# is costed at none, and its run's USD shows as unknown. The cost is a secondary figure: caching discounts re-sending an
# unchanged prefix, never a duplicate, which is paid in full when sent and then carried for the rest of the session.
PRICES: dict[str, dict[str, float]] = {
    'claude-haiku-5-5': {'input': 0.10, 'output': 0.50, 'read': 0.01, 'long_above': 100_000, 'long_input': 0.50,
                         'long_output': 2.50, 'long_read': 0.05},
    'claude-haiku-4-5': {'input': 1.0, 'output': 5.0, 'read': 0.10},
    'claude-sonnet-5-5': {'input': 2.0, 'output': 10.0, 'read': 0.20},
    'claude-sonnet-5': {'input': 2.0, 'output': 10.0, 'read': 0.20},
    'claude-sonnet-4-6': {'input': 3.0, 'output': 15.0, 'read': 0.30},
    'claude-opus-5-5': {'input': 4.0, 'output': 20.0, 'read': 0.20},
    'claude-opus-5': {'input': 5.0, 'output': 25.0, 'read': 0.50},
    'claude-opus-4-8': {'input': 5.0, 'output': 25.0, 'read': 0.50},
    'claude-opus-4-7': {'input': 5.0, 'output': 25.0, 'read': 0.50},
    'claude-fable-5-1': {'input': 10.0, 'output': 50.0, 'read': 0.25},
}
# A block of delivered text counted for duplicates: a sentence or line of at least this many characters, with a leading
# one-word label (`task:`, `map_work:`) taken off, so the same sentence under two labels is one block.
DUPLICATE_MIN = 30
LABEL = re.compile(r'^[\w.-]{1,32}:\s+')
MEMORY_READS = re.compile(r'^mcp__metaform__memory_(read_graph|search_nodes|open_nodes|note|joins|graph)$')
# What reads like a search for code: the search tools, and a shell search.
SEARCH_COMMAND = re.compile(r'(^|[;&|(]\s*|\bxargs\s+)(grep|rg|ag|find|git\s+(grep|ls-files))\b')
# Claude Code's own per-session state in the person's home, which --auth login leaves (code.claude.com/docs/en/
# claude-directory); anything else a run leaves there breaks its isolation.
SESSION_STATE = ('.claude/session-env', '.claude/todos', '.claude/file-history', '.cache/claude-cli-nodejs',
                 '.claude/shell-snapshots')
STOPWORDS = frozenset((
    'about', 'above', 'after', 'again', 'against', 'also', 'although', 'always', 'another', 'answer', 'anything',
    'around', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'cannot', 'change', 'changed',
    'code', 'could', 'does', 'doing', 'done', 'down', 'during', 'each', 'either', 'else', 'even', 'every', 'find',
    'from', 'function', 'give', 'given', 'gives', 'have', 'having', 'here', 'into', 'just', 'keep', 'kept', 'know',
    'later', 'less', 'like', 'line', 'made', 'make', 'makes', 'many', 'might', 'more', 'most', 'much', 'must',
    'need', 'needs', 'never', 'nothing', 'once', 'only', 'other', 'otherwise', 'over', 'same', 'says', 'should',
    'since', 'some', 'something', 'still', 'such', 'than', 'that', 'their', 'them', 'then', 'there', 'these',
    'they', 'thing', 'things', 'this', 'those', 'though', 'through', 'under', 'until', 'upon', 'used', 'uses',
    'using', 'very', 'want', 'wants', 'were', 'what', 'when', 'where', 'whether', 'which', 'while', 'whom', 'whose',
    'will', 'with', 'within', 'without', 'work', 'works', 'would', 'your', 'yours', 'really', 'reads', 'read',
    'named', 'name'
))
GIT_ID = ('-c', 'user.name=eval', '-c', 'user.email=eval@localhost', '-c', 'core.safecrlf=false')

HOOK = '''\
import json, os, subprocess, sys
folder, log, index = sys.argv[1:4]
try:
    event = json.loads(sys.stdin.read() or '{}')
except ValueError:
    event = {}
env = {**os.environ, 'GIT_INDEX_FILE': index}
tree = ''
try:
    subprocess.run(['git', '-C', folder, 'add', '-A'], env=env, check=True, capture_output=True, timeout=120)
    tree = subprocess.run(['git', '-C', folder, 'write-tree'], env=env, check=True, capture_output=True, text=True,
                          timeout=120).stdout.strip()
except Exception:
    pass
with open(log, 'a', encoding='utf-8') as out:
    out.write(json.dumps({'tool_use_id': event.get('tool_use_id'), 'tool_name': event.get('tool_name'),
                          'event': event.get('hook_event_name'), 'agent_id': event.get('agent_id'),
                          'tree': tree}) + '\\n')
'''


@dataclass
class Options:
    model: str
    k: int
    arms: tuple[str, ...]
    spend_cap: float
    run_budget: float
    min_run: float
    max_turns: int
    timeout: float
    auth: str
    permission_mode: str
    node_bytes: int | None
    intake_model: str
    intake_budget: float
    intake_max_turns: int
    intake_timeout: float
    placement_budget: float
    allow_dirty: bool
    allow_dirty_tests: bool
    code_layer: bool
    grep_rank: int
    dry_run: bool
    keep: bool


@dataclass
class Spend:
    cap: float
    spent: float = 0.0
    calls: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])

    def budget(self, wanted: float, least: float) -> float | None:
        """What the next call may spend, or None when the cap leaves too little for one."""
        left = self.cap - self.spent
        return None if left < least else round(min(wanted, left), 2)

    def add(self, what: str, cost: float | None, budget: float) -> None:
        # A call that ended without saying its cost is counted at its whole budget.
        self.spent += budget if cost is None else cost
        self.calls.append({'what': what, 'cost_usd': cost, 'budget_usd': budget})


class Skip(Exception):
    """A run that cannot be made, with the reason recorded in its place."""


def sha(*parts: str) -> str:
    return hashlib.sha256('\0'.join(parts).encode()).hexdigest()


# ---------------------------------------------------------------------------------------------------------- source


@dataclass
class Source:
    """The Metaform under test: this repository's working tree, frozen once as a git commit object that no branch
    holds, and copied from that commit."""
    tree: Path
    commit: str
    changed: list[str]
    digest: str
    frozen: str = ''
    frozen_tree: str = ''

    @property
    def label(self) -> str:
        return f'{self.commit[:12]}-dirty' if self.changed else self.commit[:12]

    @property
    def ident(self) -> str:
        return f'{self.label}+{self.digest[:12]}'

    def record(self) -> dict[str, Any]:
        return {'commit': self.commit, 'label': self.label, 'changed_files': len(self.changed),
                'changed_sample': self.changed[:20], 'src_sha256': self.digest, 'commit_object': self.frozen,
                'tree_object': self.frozen_tree,
                'restore': f'git archive {self.frozen} | tar -x -C <folder>, or source.tar.gz beside results.json'}


def pathspec(excluded: list[str]) -> list[str]:
    return ['--', '.', *[f':(exclude){pattern}' for pattern in excluded]]


def git_lines(folder: Path, *args: str) -> list[str]:
    done = subprocess.run(['git', '-C', str(folder), *args], check=True, capture_output=True)
    return [line.decode('utf-8', 'surrogateescape') for line in done.stdout.split(b'\0') if line]


def tree_digest(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(folder.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            digest.update(str(path.relative_to(folder)).encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def freeze(paths: list[str], label: str) -> tuple[str, str]:
    """The working tree as it stands, written as a tree and a commit object whose parent is HEAD, through an index of
    its own: the working tree, its index and its branches are not touched. The commit object is held by no ref, so
    git gc may prune it after gc.pruneExpire (two weeks); source.tar.gz in the results keeps it."""
    with tempfile.TemporaryDirectory(prefix='orientation-index-') as held:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(held) / 'index')}
        git = ['git', '-C', str(ROOT), *GIT_ID]
        subprocess.run([*git, 'update-index', '--add', '-z', '--stdin'], env=env, check=True, capture_output=True,
                       input=b''.join(path.encode('utf-8', 'surrogateescape') + b'\0' for path in paths))
        tree = subprocess.run([*git, 'write-tree'], env=env, check=True, capture_output=True,
                              text=True).stdout.strip()
    commit = subprocess.run([*git, 'commit-tree', tree, '-p', 'HEAD', '-m', f'orientation evaluation source {label}'],
                            check=True, capture_output=True, text=True).stdout.strip()
    return commit, tree


def take_worktree(excluded: list[str], target: Path, allow_dirty: bool, allow_dirty_tests: bool) -> Source:
    """A copy of this repository's working tree: tracked and untracked files git does not ignore, and the files git
    ignores under src that the package serves (built views), never bytecode, frozen first as a commit object and
    copied from it. A tree that differs from HEAD is refused unless allowed, and an untracked test module unless that
    too is allowed: it is most often another session's file caught mid-edit, and every agent that runs the tests
    would meet it."""
    spec = pathspec([*excluded, *OWN])
    status = git_lines(ROOT, 'status', '--porcelain', '-z', '--untracked-files=all', *spec)
    changed = sorted({line[3:] for line in status if len(line) > 3})
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], check=True, capture_output=True,
                            text=True).stdout.strip()
    if changed and not allow_dirty:
        raise SystemExit(f'The working tree differs from HEAD {commit[:12]} in {len(changed)} files '
                         f'({", ".join(changed[:5])}, ...). Commit them, or pass --allow-dirty to evaluate the tree as '
                         f'it stands, recorded as {commit[:12]}-dirty and frozen as a commit object.')
    stray = [line[3:] for line in status if line.startswith('??') and TEST_MODULE.search(line[3:])]
    if stray and not allow_dirty_tests:
        raise SystemExit(f'Untracked test modules would join every agent\'s test run: {", ".join(stray[:5])}. '
                         'Commit or remove them, or pass --allow-dirty-tests.')
    built = [path for path in git_lines(ROOT, 'ls-files', '-z', '-oi', '--exclude-standard', '--', 'src',
                                        *[f':(exclude){pattern}' for pattern in [*excluded, *OWN]])
             if '__pycache__' not in path and not path.endswith('.pyc') and '.egg-info' not in path
             and '_cache/' not in path]
    label = f'{commit[:12]}-dirty' if changed else commit[:12]
    files = git_lines(ROOT, 'ls-files', '-z', '-co', '--exclude-standard', *spec)
    present = sorted(path for path in {*files, *built} if (ROOT / path).is_file() or (ROOT / path).is_symlink())
    frozen, frozen_tree = freeze(present, label)
    extract_commit(frozen, target)
    return Source(target, commit, changed, tree_digest(target / 'src' / 'metaform'), frozen, frozen_tree)


def extract_commit(commit: str, into: Path) -> None:
    into.mkdir(parents=True, exist_ok=True)
    archive = into.parent / f'{into.name}.tar'
    subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=tar', f'--output={archive}', commit], check=True)
    with tarfile.open(archive) as held:
        held.extractall(into, filter='fully_trusted')  # this repository's own files, symlinks kept as they are
    archive.unlink()


# ---------------------------------------------------------------------------------------------------------- repos


def is_self(repo: dict[str, Any]) -> bool:
    return repo['source'] == 'local' and (ROOT / repo.get('path', '.')).resolve() == ROOT


def snapshot(name: str, repo: dict[str, Any], work: Path, source: Source) -> tuple[Path, str]:
    """A clean copy of the repository with no agent context files, and the commit it was taken from. This repository
    is the copy of the Metaform under test; another is cloned and archived at its ref."""
    target = work / 'snapshots' / name
    excluded = [*repo.get('exclude', []), *CONTEXT_FILES]
    if is_self(repo):
        shutil.copytree(source.tree, target, symlinks=True,
                        ignore=shutil.ignore_patterns(*CONTEXT_FILES))
        commit = source.label
    else:
        origin = work / 'clones' / name
        if not origin.exists():
            subprocess.run(['git', 'clone', '--quiet', '--filter=blob:none', repo['url'], str(origin)], check=True)
        subprocess.run(['git', '-C', str(origin), 'checkout', '--quiet', repo.get('ref', 'HEAD')], check=True)
        commit = subprocess.run(['git', '-C', str(origin), 'rev-parse', repo.get('ref', 'HEAD')], check=True,
                                capture_output=True, text=True).stdout.strip()
        archive = work / 'snapshots' / f'{name}.tar'
        archive.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', '-C', str(origin), 'archive', '--format=tar', f'--output={archive}', commit,
                        *pathspec(excluded)], check=True)
        target.mkdir(parents=True)
        with tarfile.open(archive) as held:
            held.extractall(target, filter='data')
        archive.unlink()
    for step in repo.get('prepare', []):
        (target / step['write']).write_text(step['text'], encoding='utf-8')
    return target, commit


def workspace(base: Path, into: Path, setup: list[dict[str, str]]) -> Path:
    """A run's own copy of the snapshot with the task's setup applied, committed so its diff is the agent's work."""
    shutil.copytree(base, into, symlinks=True)
    for change in setup:
        path = into / change['file']
        text = path.read_text(encoding='utf-8')
        if text.count(change['find']) != 1:
            raise Skip(f'setup: {change["file"]} holds {text.count(change["find"])} of the text to replace, not one')
        path.write_text(text.replace(change['find'], change['replace']), encoding='utf-8')
    git = ['git', '-C', str(into), *GIT_ID]
    subprocess.run([*git, 'init', '--quiet'], check=True)
    (into / '.git' / 'info').mkdir(parents=True, exist_ok=True)
    (into / '.git' / 'info' / 'exclude').write_text('\n'.join(LEFTOVERS) + '\n', encoding='utf-8')
    subprocess.run([*git, 'add', '-A'], check=True)
    subprocess.run([*git, 'commit', '--quiet', '-m', 'start', '--no-verify'], check=True)
    return into


def start_tree(folder: Path) -> str:
    return subprocess.run(['git', '-C', str(folder), 'rev-parse', 'HEAD^{tree}'], check=True, capture_output=True,
                          text=True).stdout.strip()


def extract(folder: Path, tree: str, into: Path) -> Path:
    shutil.rmtree(into, ignore_errors=True)
    into.mkdir(parents=True)
    archive = into.with_suffix('.tar')
    subprocess.run(['git', '-C', str(folder), 'archive', '--format=tar', f'--output={archive}', tree], check=True)
    with tarfile.open(archive) as held:
        held.extractall(into, filter='data')
    archive.unlink()
    return into


# --------------------------------------------------------------------------------------------------------- grading


def python_check(folder: Path, paths: list[str], code: str) -> tuple[bool, str]:
    """Run a check's code against the folder's own source, isolated from this environment's paths (-I), writing
    no bytecode (-B): a reference edit of the same size within the same second would otherwise run the stale cache."""
    prelude = f'import sys\nsys.path[:0] = {[str(folder / path) for path in paths]!r}\n'
    try:
        done = subprocess.run([sys.executable, '-I', '-B', '-c', prelude + code], cwd=tempfile.gettempdir(),
                              capture_output=True, text=True, timeout=120, check=False)
    except subprocess.TimeoutExpired:
        return False, 'the check timed out'
    return done.returncode == 0, (done.stderr.strip().splitlines() or [''])[-1]


def text_files(folder: Path, skip: set[str]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in folder.rglob('*'):
        relative = path.relative_to(folder).as_posix()
        if not path.is_file() or path.is_symlink() or '.git' in path.parts or relative in skip:
            continue
        if path.stat().st_size > 5_000_000:
            continue
        raw = path.read_bytes()
        if b'\0' not in raw[:8192]:
            found.append((relative, raw.decode('utf-8', errors='replace')))
    return found


def marker_check(folder: Path, grade: dict[str, Any]) -> tuple[bool, str]:
    """The marker sits within `within` lines above the anchor, with only blank lines, comments and decorators between,
    and nowhere else in the repository."""
    marker, target = grade['marker'], grade['file']
    elsewhere = [name for name, text in text_files(folder, {target}) if marker in text]
    if elsewhere:
        return False, f'marker also in {", ".join(elsewhere[:3])}'
    path = folder / target
    if not path.exists():
        return False, f'{target} is gone'
    lines = path.read_text(encoding='utf-8').splitlines()
    anchors = [n for n, line in enumerate(lines) if re.search(grade['anchor'], line)]
    marks = [n for n, line in enumerate(lines) if marker in line]
    if not marks:
        return False, 'no marker in the target file'
    for anchor in anchors:
        for mark in marks:
            between = lines[mark + 1:anchor]
            if 0 < anchor - mark <= grade.get('within', 3) and all(
                    not line.strip() or line.strip().startswith(('#', '@')) for line in between):
                return True, ''
    return False, f'marker at line {marks[0] + 1}, not above {grade["anchor"]}'


def grade_folder(folder: Path, task: dict[str, Any], repo: dict[str, Any]) -> tuple[bool, str]:
    grade = task['grade']
    if grade['type'] == 'none':
        return True, 'not graded'
    if grade['type'] == 'marker':
        return marker_check(folder, grade)
    for cache in list(folder.rglob('__pycache__')):  # bytecode the agent's own runs left may be stale
        shutil.rmtree(cache, ignore_errors=True)
    return python_check(folder, repo.get('python_path', ['.']), grade['code'])


def targets(task: dict[str, Any]) -> set[str]:
    """The files a correct edit changes."""
    return {task['grade']['file'], *(change['file'] for change in task.get('setup', []))}


def reference(folder: Path, task: dict[str, Any]) -> None:
    """Apply the task's reference solution: the marker above the anchor, or the setup undone."""
    grade = task['grade']
    if grade['type'] == 'marker':
        path = folder / grade['file']
        lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
        at = next(n for n, line in enumerate(lines) if re.search(grade['anchor'], line))
        indent = re.match(r'\s*', lines[at]).group()  # type: ignore[union-attr]
        lines.insert(at, f'{indent}# {grade["marker"]}\n')
        path.write_text(''.join(lines), encoding='utf-8')
        return
    for change in task.get('setup', []):
        path = folder / change['file']
        path.write_text(path.read_text(encoding='utf-8').replace(change['replace'], change['find']), encoding='utf-8')


def literal(pattern: str) -> str | None:
    """The plain text an anchor pattern matches, when it is plain apart from its start and leading whitespace."""
    text = re.sub(r'^\^', '', pattern)
    text = re.sub(r'^\\s[*+]', '', text)
    text = re.sub(r'\$$', '', text)
    if re.search(r'(?<!\\)[.*+?()\[\]{}|^$]', text):
        return None
    return re.sub(r'\\(.)', r'\1', text)


def leaks(folder: Path, task: dict[str, Any]) -> list[str]:
    """Answers the repository gives away, in any file but the ones the task concerns: the marker, a setup's original
    text, or the anchor's text in a file that also names the target, as a task list would. The anchor's text alone is
    no leak: another function of the same name only means a grep for it finds two."""
    grade = task['grade']
    needles = [change['find'] for change in task.get('setup', [])]
    anchor = None
    if grade['type'] == 'marker':
        needles.append(grade['marker'])
        anchor = literal(grade['anchor'])
    found: list[str] = []
    for name, text in text_files(folder, targets(task)):
        found += [f'{needle!r} in {name}' for needle in needles if needle in text]
        if anchor and anchor in text and grade['file'] in text:
            found.append(f'{anchor!r} with {grade["file"]} in {name}')
    return found


def terms(request: str) -> list[str]:
    """The request's own words as a grep would try them: lower case, four letters or more, no common words, plural
    and verb endings cut; and each pair of neighbouring words joined as an identifier would join them (short_name,
    shortname), which is how an agent turns a description into a search."""
    words = [word.lower() for word in re.findall(r'[A-Za-z][A-Za-z_]+', request)]
    found: list[str] = []
    for word in words:
        if len(word) < 4 or word in STOPWORDS:
            continue
        for ending in ('ing', 'ers', 'es', 'ed', 's'):
            if word.endswith(ending) and len(word) - len(ending) >= 4:
                word = word[:-len(ending)]
                break
        if word not in found:
            found.append(word)
    for first, second in itertools.pairwise(words):
        if len(first) >= 3 and len(second) >= 3 and first not in STOPWORDS - {'name'}:
            found += [joined for joined in (f'{first}_{second}', f'{first}{second}') if joined not in found]
    return found


def grep_rank(folder: Path, request: str, target: str, few: int) -> tuple[int | None, list[str], str | None]:
    """How findable the target is by grepping the repository for the request's words: its rank when each word is
    weighted by how rare it is (log N/df) and each file scored by the words it holds (1 + log of the lines), the top
    five files, and a word that alone finds the target among `few` files or fewer, or names a definition in it among
    `few` files or fewer. It cannot see a search the agent infers, such as ppid for "the program that started it"."""
    files = git_lines(folder, 'ls-files', '-z')
    scores: dict[str, float] = {}
    giveaway: str | None = None
    for term in terms(request):
        done = subprocess.run(['git', '-C', str(folder), 'grep', '-c', '-i', '-F', '-e', term], capture_output=True,
                              text=True, check=False)
        counts = {name: int(count) for name, _, count in
                  (line.rpartition(':') for line in done.stdout.splitlines()) if count.isdigit()}
        if not counts:
            continue
        if giveaway is None and target in counts and len(counts) <= few:
            giveaway = f'{term!r} finds it among {len(counts)} files'
        defined = subprocess.run(['git', '-C', str(folder), 'grep', '-l', '-i', '-E', '-e',
                                  rf'^\s*(async\s+)?(def|class|function)\s+\w*{re.escape(term)}', '--', '*.py',
                                  '*.js', '*.ts'], capture_output=True, text=True, check=False).stdout.split()
        if giveaway is None and target in defined and len(defined) <= few:
            giveaway = f'{term!r} names a definition in it, among {len(defined)} files'
        weight = math.log(len(files) / len(counts))
        for name, count in counts.items():
            scores[name] = scores.get(name, 0.0) + weight * (1 + math.log(count))
    ranked = sorted(scores, key=lambda name: -scores[name])
    return (ranked.index(target) + 1 if target in ranked else None), ranked[:5], giveaway


def check_task(task: dict[str, Any], repo: dict[str, Any], base: Path, scratch: Path, rank_floor: int) -> str | None:
    """None when the task is sound: its setup applies, its grader fails on the start and passes on the reference, the
    repository gives no answer away, and one grep of the request's words does not find the target, unless the task is
    declared a control: in a repository this small any fair request is found by grep, so such a task shows what each
    arm's context costs when orientation is free, and is reported apart."""
    folder = scratch / f'check-{task["id"]}'
    try:
        workspace(base, folder, task.get('setup', []))
        leaked = leaks(folder, task)
        if leaked:
            return f'the repository gives the answer away: {"; ".join(leaked[:3])}'
        rank, top, giveaway = grep_rank(folder, task['request'], task['grade']['file'], rank_floor)
        findable = (f'a grep of the request finds the target at rank {rank} (top: {", ".join(top)})'
                    if rank is not None and rank <= rank_floor else
                    f'one grep of the request finds the target: {giveaway}' if giveaway else None)
        if findable and not task.get('control'):
            return findable
        if findable:
            print(f'    a control task, findable by grep: {findable}')
        failed, _ = grade_folder(folder, task, repo)
        if failed:
            return 'the grader passes on the starting state'
        reference(folder, task)
        passed, why = grade_folder(folder, task, repo)
        if not passed:
            return f'the grader fails on the reference solution: {why}'
        print(f'    grep rank of the target: {rank or "unranked"}')
        return None
    except Skip as skip:
        return str(skip)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def module_of(path: str, python_path: list[str]) -> str | None:
    """The dotted module a repository path is imported as, through the repository's python_path."""
    for root in python_path:
        prefix = '' if root in ('', '.') else root.rstrip('/') + '/'
        if path.startswith(prefix) and path.endswith('.py'):
            return path[len(prefix):-3].replace('/', '.').removesuffix('.__init__')
    return None


def related_tests(folder: Path, modules: dict[str, set[str]]) -> list[str]:
    """The test modules that import one of the modules, or a public name one defines through the module or a package
    above it (`from metaform.data import short_name`): what an agent checking its fix would run first."""
    patterns: list[re.Pattern[str]] = []
    for module, names in modules.items():
        patterns.append(re.compile(rf'\b{re.escape(module)}\b'))
        parts = module.split('.')
        for depth in range(1, len(parts)):
            above = re.escape('.'.join(parts[:depth]))
            wanted = '|'.join(re.escape(name) for name in sorted({*names, parts[depth]}))
            patterns.append(re.compile(rf'from\s+{above}\s+import\s[^\n]*\b({wanted})\b'))
    found: list[str] = []
    for path in sorted(folder.rglob('*.py')):
        relative = path.relative_to(folder).as_posix()
        if TEST_MODULE.search(relative) and not relative.endswith('conftest.py') and any(
                pattern.search(path.read_text(encoding='utf-8', errors='replace')) for pattern in patterns):
            found.append(relative)
    return found


def public_names(path: Path) -> set[str]:
    text = path.read_text(encoding='utf-8', errors='replace') if path.exists() else ''
    return {name for name in re.findall(r'^(?:async\s+)?(?:def|class)\s+([A-Za-z]\w*)', text, re.MULTILINE)}


def start_failures(base: Path, repo: dict[str, Any], tasks: list[dict[str, Any]], scratch: Path) -> dict[str, Any]:
    """What an agent that checks its work meets before it has changed anything: the test suite's collection errors,
    and the failures of the test modules that import the files the tasks fix, run on the snapshot as the repository
    configures pytest, writing no bytecode and no cache into it."""
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join(str(base / path) for path in repo.get('python_path', ['.'])),
           'METAFORM_HOME': str(scratch / 'mfhome-baseline'), 'PYTHONDONTWRITEBYTECODE': '1'}
    started = time.monotonic()

    def pytest(*args: str, timeout: float) -> tuple[str, str]:
        try:
            done = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider', *args], cwd=base,
                                  env=env, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return '', f'timed out after {timeout:.0f}s'
        lines = done.stdout.strip().splitlines()
        return done.stdout, (lines[-1] if lines else done.stderr.strip()[-200:])

    collected, collect_note = pytest('--co', '-q', timeout=600)
    errors = sorted({line.split(' ', 1)[1].split(' - ')[0] for line in collected.splitlines()
                     if line.startswith('ERROR ')})
    modules = {module: public_names(base / task['grade']['file']) for task in tasks
               if task['grade']['type'] == 'python' and not task.get('control')
               if (module := module_of(task['grade']['file'], repo.get('python_path', ['.']))) is not None}
    files = related_tests(base, modules) if modules else []
    failed: list[str] = []
    note = 'no test module imports the files the tasks fix'
    if files:
        ran, note = pytest('-q', '-rfE', *files, timeout=1800)
        failed = sorted({line.split(' ', 1)[1].split(' - ')[0] for line in ran.splitlines()
                         if line.startswith(('FAILED ', 'ERROR '))})
    return {'collection_errors': errors, 'collection': collect_note, 'tests': files, 'failed': failed,
            'tests_summary': note, 'seconds': round(time.monotonic() - started, 1)}


# -------------------------------------------------------------------------------------------------------- metaform


def served_path(src: Path) -> str:
    """The import path of every Metaform process of a run: the source under test, then the code layer's provider."""
    return os.pathsep.join(str(path) for path in (src, *EXTRA_PATH))


def metaform_env(home: Path, src: Path) -> dict[str, str]:
    return {**os.environ, 'METAFORM_HOME': str(home), 'PYTHONPATH': served_path(src)}


def code_provider(cache: Path) -> tuple[Path | None, str]:
    """tree-sitter and its Python grammar, installed once with uv into the evaluation's cache, never into the
    project's environment; None with the reason when it cannot be."""
    tag = sha(*TREE_SITTER, sys.version)[:12]
    folder = cache / 'code-provider' / f'tree-sitter-{tag}'
    if (folder / 'tree_sitter').is_dir():
        return folder, ' '.join(TREE_SITTER)
    uv = shutil.which('uv')
    if uv is None:
        return None, 'uv is not on PATH to install tree-sitter with'
    held = folder.with_name(folder.name + '.partial')
    shutil.rmtree(held, ignore_errors=True)
    done = subprocess.run([uv, 'pip', 'install', '--quiet', '--python', sys.executable, '--target', str(held),
                           *TREE_SITTER], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        return None, f'uv pip install {" ".join(TREE_SITTER)}: {done.stderr.strip()[-200:]}'
    held.rename(folder)
    return folder, ' '.join(TREE_SITTER)


def code_layer(folder: Path, home: Path, src: Path) -> dict[str, Any]:
    """The code layer as the shipped flow builds it after an intake (P167): map code-import, here from tree-sitter."""
    started = time.monotonic()
    said = metaform(['map', 'code-import', 'from=tree-sitter'], home=home, src=src, cwd=folder)
    found: dict[str, Any] = {'seconds': round(time.monotonic() - started, 1)}
    for line in said.splitlines():
        key, _, value = line.partition(': ')
        if key in ('provider', 'symbols', 'files', 'edges', 'linked'):
            try:
                found[key] = json.loads(value)
            except ValueError:
                found[key] = value
    return found


def metaform(args: list[str], *, home: Path, src: Path, cwd: Path, check: bool = True) -> str:
    done = subprocess.run([sys.executable, '-m', 'metaform', *args], cwd=cwd, env=metaform_env(home, src),
                          capture_output=True, text=True, timeout=300, check=False)
    if check and done.returncode != 0:
        raise Skip(f'metaform {" ".join(args)[:80]}: {(done.stderr.strip() or done.stdout.strip())[-300:]}')
    return done.stdout


def metaform_home(folder: Path, home: Path, project: str, exported: Path | None, node_bytes: int | None, src: Path,
                  *, dispatch: bool, code: bool = False) -> dict[str, Any] | None:
    """A fresh Metaform home with the folder registered, its map imported, its code layer read when asked, dispatch
    on when asked, and Claude Code recorded as provisioned, as metaform install leaves it, so no first-run notice
    reaches the agent. Returns what the code import said."""
    home.mkdir(parents=True)
    metaform(['add', 'project', project, str(folder)], home=home, src=src, cwd=folder)
    if exported is not None:
        metaform(['import', str(exported), project], home=home, src=src, cwd=folder)
    if node_bytes is not None:
        metaform(['set', '--node-summary-bytes', str(node_bytes)], home=home, src=src, cwd=folder)
    if dispatch:
        metaform(['enable', 'dispatch'], home=home, src=src, cwd=folder)
    claude = shutil.which('claude')
    if claude:
        provisioned = 'import sys\nfrom metaform import harness\nharness.done(sys.argv[1])\n'
        subprocess.run([sys.executable, '-c', provisioned, claude], env=metaform_env(home, src), check=True)
    return code_layer(folder, home, src) if code and exported is not None else None


def brief(folder: Path, home: Path, src: Path, address: str | None) -> str:
    """The text an agent reads at metaform://<address>, from the MCP server's own read; with no address, the map's
    entry as map where gives it."""
    if not address:
        return metaform(['map', 'where'], home=home, src=src, cwd=folder).strip()
    code = ('import sys\nfrom pathlib import Path\nfrom metaform.modules.mcp.server import brief\n'
            'print(brief(Path(sys.argv[1]), sys.argv[2]))\n')
    done = subprocess.run([sys.executable, '-c', code, str(folder), address], cwd=folder, capture_output=True,
                          text=True, env=metaform_env(home, src), timeout=120, check=False)
    if done.returncode != 0:
        raise Skip(f'no brief for {address}: {(done.stderr.strip().splitlines() or ["?"])[-1]}')
    return done.stdout.strip()


def ticket(folder: Path, home: Path, src: Path, address: str, task: str) -> tuple[str, str]:
    """Record the request as a work record at the address and return its id and the hand-off dispatch sends."""
    made = metaform(['map', 'work', 'op=add', f'address={address}', 'title=orientation task', f'task={task}'],
                    home=home, src=src, cwd=folder)
    found = re.search(r'^id: (\w+)', made, re.MULTILINE)
    if found is None:
        raise Skip(f'map work op=add gave no id: {made[:200]}')
    return found.group(1), metaform(['dispatch', 'handoff', f'id={found.group(1)}'], home=home, src=src,
                                    cwd=folder).rstrip()


def mcp_config(home: Path, src: Path, into: Path) -> Path:
    """The metaform stdio server as metaform install registers it, run from the source under test, given to this run
    alone with --mcp-config."""
    entry = {'type': 'stdio', 'command': sys.executable, 'args': ['-m', 'metaform', 'mcp', 'serve'],
             'env': {'METAFORM_HOME': str(home), 'PYTHONPATH': served_path(src)}}
    into.write_text(json.dumps({'mcpServers': {'metaform': entry}}), encoding='utf-8')
    return into


def server_surface(folder: Path, home: Path, src: Path) -> dict[str, Any]:
    """What the server gives a client before any call, from one initialize, tools/list and resources/list over
    stdio, the calls metaform mcp serve answers a host: the instructions, the tool count and the bytes of the list."""
    env = metaform_env(home, src)
    where = subprocess.run([sys.executable, '-c', 'import metaform; print(metaform.__file__)'], cwd=folder, env=env,
                           capture_output=True, text=True, check=False).stdout.strip()
    if not where.startswith(str(src)):
        raise Skip(f'metaform imports from {where or "nowhere"}, not from {src}')
    with tempfile.TemporaryFile('w+', encoding='utf-8') as errors:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'mcp', 'serve'], cwd=folder, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True,
                                   encoding='utf-8')
        killer = threading.Timer(90, process.kill)
        killer.start()
        given, read = cast(IO[str], process.stdin), cast(IO[str], process.stdout)

        def send(message: dict[str, Any]) -> None:
            given.write(json.dumps({'jsonrpc': '2.0', **message}) + '\n')
            given.flush()

        def ask(ident: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
            send({'id': ident, 'method': method, 'params': params})
            while True:
                line = read.readline()
                if not line:
                    errors.seek(0)
                    raise Skip(f'the MCP server ended before answering {method}: '
                               f'{(errors.read().strip().splitlines() or ["?"])[-1][:300]}')
                try:
                    message = cast(dict[str, Any], json.loads(line))
                except ValueError:
                    continue
                if message.get('id') == ident:
                    if 'error' in message:
                        raise Skip(f'{method}: {message["error"]}')
                    return cast(dict[str, Any], message.get('result') or {})

        try:
            started = ask(1, 'initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                            'clientInfo': {'name': 'claude-code', 'version': '0'}})
            send({'method': 'notifications/initialized'})
            listed: dict[str, list[dict[str, Any]]] = {'tools': [], 'resources': []}
            sizes = {'tools': 0, 'resources': 0}
            ident = 2
            for kind in listed:
                cursor: str | None = None
                while True:
                    page = ask(ident, f'{kind}/list', {'cursor': cursor} if cursor else {})
                    ident += 1
                    sizes[kind] += len(json.dumps(page).encode())
                    listed[kind] += cast(list[dict[str, Any]], page.get(kind) or [])
                    cursor = cast(str | None, page.get('nextCursor'))
                    if not cursor:
                        break
        finally:
            killer.cancel()
            process.kill()
            process.wait()
    instructions = str(started.get('instructions') or '')
    names = [str(tool.get('name')) for tool in listed['tools']]
    return {'served_from': where, 'protocol': started.get('protocolVersion'), 'instructions': instructions,
            'instructions_chars': len(instructions), 'tools': len(names), 'tools_list_bytes': sizes['tools'],
            'dispatch_tools': sum(name.startswith('dispatch_') for name in names),
            'resources': len(listed['resources']),
            'tool_descriptions': {str(tool.get('name')): str(tool.get('description') or '') for tool in listed['tools']}}


# ---------------------------------------------------------------------------------------------------------- claude


def claude_command(options: Options, budget: float, *, model: str, mcp: Path | None, settings: dict[str, Any],
                   allowed: list[str], max_turns: int, tools: str | None = None) -> list[str]:
    command = ['claude', '-p', '--output-format', 'stream-json', '--verbose', '--model', model,
               '--max-budget-usd', f'{budget:.2f}', '--max-turns', str(max_turns),
               '--permission-mode', options.permission_mode, '--permission-prompts', 'none',
               '--no-session-persistence', '--disallowedTools', 'WebFetch', 'WebSearch', '--strict-mcp-config']
    if tools is not None:
        command += ['--tools', tools]
    if mcp is not None:
        command += ['--mcp-config', str(mcp)]
    if allowed:
        command += ['--allowedTools', *allowed]
    settings = dict(settings)
    if options.auth == 'login':
        user = Path.home()
        settings['claudeMdExcludes'] = [str(user / '.claude' / 'CLAUDE.md'), str(user / '.claude' / 'rules' / '**')]
        command += ['--setting-sources', 'project,local', '--disable-slash-commands']
    if settings:
        command += ['--settings', json.dumps(settings)]
    return command


def hook_settings(here: Path, folder: Path, scratch: Path) -> tuple[dict[str, Any], Path]:
    """The PostToolUse and PostToolUseFailure hook that records the workspace's tree after every tool call, with a git
    index of its own so the agent's index is never touched (code.claude.com/docs/en/hooks)."""
    script = scratch / 'tree_hook.py'
    if not script.exists():
        script.write_text(HOOK, encoding='utf-8')
    log, index = here / 'trees.jsonl', here / 'hook-index'
    shutil.copyfile(folder / '.git' / 'index', index)
    command = ' '.join(shlex.quote(part) for part in (sys.executable, '-I', str(script), str(folder), str(log),
                                                      str(index)))
    entry = [{'matcher': '*', 'hooks': [{'type': 'command', 'command': command, 'timeout': 180}]}]
    return {'hooks': {'PostToolUse': entry, 'PostToolUseFailure': entry}}, log


UV_SHIM = '''case "$1" in
  run)
    shift
    while [ $# -gt 0 ]; do
      case "$1" in
        --) shift; break ;;
        --with|--extra|--group|--python|-p|--project|--directory|--package|--env-file|--index|--only-group) shift 2 ;;
        -*) shift ;;
        *) break ;;
      esac
    done
    PATH="{path}" exec "$@" ;;
  sync|pip|lock|venv)
    echo "uv $1: the environment is provided by the evaluation; nothing to do." >&2
    exit 0 ;;
  *)
    echo "uv $1 is not available in this evaluation; use uv run <command>." >&2
    exit 2 ;;
esac'''


def bin_folder(here: Path, home: Path, src: Path) -> Path:
    """Commands the agent's shell finds first: metaform on the run's own home and source; python, python3 and pytest
    on this interpreter, which has the dependencies; and uv, whose run runs the command with this folder and the
    interpreter's own scripts (ruff, pyright) first on PATH, and whose sync and pip have nothing to do."""
    folder = here / 'bin'
    folder.mkdir(parents=True, exist_ok=True)
    python = shlex.quote(sys.executable)
    scripts = Path(sys.executable).parent
    shims = {'metaform': (f'METAFORM_HOME={shlex.quote(str(home))} PYTHONPATH={shlex.quote(served_path(src))} '
                          f'exec {python} -m metaform "$@"'),
             'python': f'exec {python} "$@"', 'python3': f'exec {python} "$@"',
             'pytest': f'exec {python} -m pytest "$@"',
             'uv': UV_SHIM.replace('{path}', f'{folder}:{scripts}:$PATH')}
    for name, line in shims.items():
        path = folder / name
        path.write_text(f'#!/bin/sh\n{line}\n', encoding='utf-8')
        path.chmod(0o755)
    return folder


def claude_env(options: Options, home: Path, *, metaform_home: Path, bin_dir: Path | None,
               python_path: list[Path]) -> dict[str, str]:
    env = {name: os.environ[name] for name in PASSED if name in os.environ}
    env.update(CLAUDE_CODE_DISABLE_AUTO_MEMORY='1', DISABLE_AUTOUPDATER='1', METAFORM_HOME=str(metaform_home))
    if bin_dir is not None:
        env['PATH'] = os.pathsep.join([str(bin_dir), env.get('PATH', '')])
    if python_path:
        env['PYTHONPATH'] = os.pathsep.join(str(path) for path in python_path)
    if options.auth == 'env':
        env.update({name: os.environ[name] for name in CREDENTIALS if name in os.environ})
        env['HOME'] = str(home)
        home.mkdir(parents=True, exist_ok=True)
    else:
        env['HOME'] = str(Path.home())
    return env


def run_claude(command: list[str], prompt: str, cwd: Path, env: dict[str, str], timeout: float,
               stream: Path) -> tuple[list[dict[str, Any]], str, float]:
    """Run one claude call to its end or its timeout, keeping every stream event, and its wall time."""
    started = time.monotonic()
    # The prompt goes in on standard input: after a variadic flag such as --allowedTools, an argument would be read
    # as one more tool name.
    with stream.open('w', encoding='utf-8') as out, tempfile.TemporaryFile('w+') as err, \
            tempfile.TemporaryFile('w+', encoding='utf-8') as given:
        given.write(prompt)
        given.seek(0)
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=err, stdin=given,
                                   start_new_session=True, text=True)
        try:
            process.wait(timeout=timeout)
            reason = '' if process.returncode == 0 else f'exit {process.returncode}'
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            reason = f'timed out after {timeout:.0f}s'
        err.seek(0)
        errors = err.read().strip()
    events: list[dict[str, Any]] = []
    for line in stream.read_text(encoding='utf-8').splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if errors:
        reason = (reason + ': ' if reason else '') + errors.splitlines()[-1][:300]
    return events, reason, time.monotonic() - started


def result_of(events: list[dict[str, Any]]) -> dict[str, Any]:
    none: dict[str, Any] = {}
    return next((event for event in reversed(events) if event.get('type') == 'result'), none)


def init_of(events: list[dict[str, Any]]) -> dict[str, Any]:
    none: dict[str, Any] = {}
    return next((event for event in events if event.get('type') == 'system' and event.get('subtype') == 'init'), none)


def context_tokens(usage: dict[str, Any]) -> int:
    """Everything a turn's request carried in: new input and the cache written and read."""
    return int(usage.get('input_tokens') or 0) + int(usage.get('cache_creation_input_tokens') or 0) + int(
        usage.get('cache_read_input_tokens') or 0)


def split_tokens(usage: dict[str, Any]) -> dict[str, int]:
    """A request's tokens by kind, as Claude Code's stream-json reports them: uncached input, the cache written (and
    of it, what was written for an hour), the cache read, and output. Fresh is uncached plus written: what was new to
    the context in that request; read is the prefix carried again."""
    written = int(usage.get('cache_creation_input_tokens') or 0)
    return {'uncached': int(usage.get('input_tokens') or 0), 'written': written,
            'written_1h': min(written, int(usage.get('cache_creation.ephemeral_1h_input_tokens') or 0)),
            'read': int(usage.get('cache_read_input_tokens') or 0), 'output': int(usage.get('output_tokens') or 0)}


def price_of(model: str) -> dict[str, float] | None:
    return next((held for name, held in PRICES.items() if model == name or model.startswith(f'{name}-2')), None)


def request_usd(model: str, usage: dict[str, Any]) -> float | None:
    """One request at list prices: uncached input at the input rate, the cache written at 1.25 times it (2 times for
    the hour), the cache read at the read rate, and output; None for a model with no price here."""
    price = price_of(model)
    if price is None:
        return None
    held = split_tokens(usage)
    long = 'long_above' in price and held['uncached'] + held['written'] + held['read'] > price['long_above']
    rate, read, out = ((price['long_input'], price['long_read'], price['long_output']) if long
                       else (price['input'], price['read'], price['output']))
    return (held['uncached'] * rate + (held['written'] - held['written_1h']) * rate * 1.25
            + held['written_1h'] * rate * 2 + held['read'] * read + held['output'] * out) / 1e6


def models_of(events: list[dict[str, Any]]) -> dict[str, str]:
    """Each assistant message's model, by message id."""
    found: dict[str, str] = {}
    for event in events:
        if event.get('type') == 'assistant':
            message = cast(dict[str, Any], event.get('message') or {})
            found.setdefault(str(message.get('id')), str(message.get('model') or ''))
    return found


def text_blocks(text: str) -> list[str]:
    """The blocks of a delivered text, for finding what was said twice: each sentence or line of DUPLICATE_MIN
    characters or more, whitespace folded and a leading one-word label taken off; a JSON result is read for its
    strings, and a string that is itself JSON, such as a resource read's text, is read again."""
    strings: list[str] = []

    def walk(held: Any) -> None:
        if isinstance(held, str):
            stripped = held.strip()
            if stripped[:1] in ('{', '['):
                try:
                    walk(json.loads(stripped))
                    return
                except ValueError:
                    pass
            strings.append(held)
        elif isinstance(held, dict):
            for value in cast(dict[str, Any], held).values():
                walk(value)
        elif isinstance(held, list):
            for value in cast(list[Any], held):
                walk(value)

    walk(text)
    found: list[str] = []
    for one in strings:
        for line in one.splitlines():
            for sentence in re.split(r'(?<=[.!?])\s+', line.strip()):
                block = ' '.join(LABEL.sub('', sentence.strip()).split())
                if len(block) >= DUPLICATE_MIN:
                    found.append(block)
    return found


def delivered(events: list[dict[str, Any]], prompt: str | None, instructions: str | None,
              descriptions: dict[str, str] | None) -> list[tuple[str, str]]:
    """What Metaform put in the agent's context, in order, each with where it came from: the connect instructions,
    the hand-off prompt, the descriptions of the Metaform tools a ToolSearch select loaded (when the surface recorded
    them), and the result of every Metaform tool call, resource read and metaform command."""
    held: list[tuple[str, str]] = []
    if instructions:
        held.append(('connect instructions', instructions))
    if prompt:
        held.append(('hand-off prompt', prompt))
    texts = result_texts(events)
    for call in calls_and_usage(events)[2]:
        if call.name == 'ToolSearch':
            for name in re.findall(r'mcp__metaform__([\w-]+)', str(call.input.get('query') or '')):
                if descriptions and name in descriptions:
                    held.append((f'{name} description', descriptions[name]))
        elif is_metaform(call) and call.ident in texts:
            held.append((f'{result_key(call).removeprefix("mcp__metaform__")} result', texts[call.ident]))
    return held


def duplicates(sources: list[tuple[str, str]]) -> dict[str, Any]:
    """Every block of what Metaform delivered that the agent's context holds more than once, MCP's defect to remove at
    its source: per run the blocks, the characters of their extra copies, and, grouped by where the copies came from,
    how many blocks and characters; with the largest blocks as examples."""
    seen: dict[str, list[str]] = {}
    for label, text in sources:
        for block in text_blocks(text):
            seen.setdefault(block, []).append(label)
    grouped: dict[str, dict[str, int]] = {}
    examples: list[dict[str, Any]] = []
    for block, where in seen.items():
        if len(where) < 2:
            continue
        counts: dict[str, int] = {}
        for label in where:
            counts[label] = counts.get(label, 0) + 1
        key = ' + '.join(f'{label} ×{n}' if n > 1 else label for label, n in sorted(counts.items()))
        row = grouped.setdefault(key, {'blocks': 0, 'chars': 0})
        row['blocks'] += 1
        row['chars'] += len(block) * (len(where) - 1)
        examples.append({'text': block[:100], 'chars': len(block), 'copies': len(where), 'from': key})
    return {'delivered_chars': sum(len(text) for _, text in sources),
            'duplicate_blocks': sum(row['blocks'] for row in grouped.values()),
            'duplicate_chars': sum(row['chars'] for row in grouped.values()),
            'duplicates_by_source': [{'from': key, **row} for key, row in
                                     sorted(grouped.items(), key=lambda item: -item[1]['chars'])][:12],
            'duplicate_examples': sorted(examples, key=lambda one: -one['chars'] * (one['copies'] - 1))[:6]}


def totals(events: list[dict[str, Any]], usage: dict[str, dict[str, int]]) -> tuple[int, int]:
    """Input and output tokens of the whole run, from the result's per-model usage, which counts every model the run
    used, subagents and Claude Code's own small calls included; the stream's sums stand in when there is no result."""
    models = cast(dict[str, dict[str, Any]], result_of(events).get('modelUsage') or {})
    if models:
        return (sum(int(each.get('inputTokens') or 0) + int(each.get('cacheReadInputTokens') or 0)
                    + int(each.get('cacheCreationInputTokens') or 0) for each in models.values()),
                sum(int(each.get('outputTokens') or 0) for each in models.values()))
    return (sum(context_tokens(each) for each in usage.values()),
            sum(int(each.get('output_tokens') or 0) for each in usage.values()))


@dataclass
class Call:
    message: str
    turn: int  # the main thread's turns up to and including this call's
    name: str
    input: dict[str, Any]
    ident: str


def calls_and_usage(events: list[dict[str, Any]]) -> tuple[list[str], dict[str, dict[str, int]], list[Call], int]:
    """The assistant messages in order with each one's usage, the tool calls with the turn that made them, and the
    main thread's turn count. A message streamed in several events is counted once, with the largest usage seen."""
    order: list[str] = []
    usage: dict[str, dict[str, int]] = {}
    calls: list[Call] = []
    turns = 0
    for event in events:
        if event.get('type') != 'assistant':
            continue
        message = cast(dict[str, Any], event.get('message') or {})
        ident = str(message.get('id') or len(order))
        if ident not in usage:
            order.append(ident)
            usage[ident] = {}
            if event.get('parent_tool_use_id') is None:
                turns += 1
        for key, value in cast(dict[str, Any], message.get('usage') or {}).items():
            if isinstance(value, int):
                usage[ident][key] = max(usage[ident].get(key, 0), value)
            elif key == 'cache_creation' and isinstance(value, dict):  # the cache written, by its TTL
                for ttl, count in cast(dict[str, Any], value).items():
                    if isinstance(count, int):
                        usage[ident][f'cache_creation.{ttl}'] = max(usage[ident].get(f'cache_creation.{ttl}', 0),
                                                                    count)
        for block in cast(list[dict[str, Any]], message.get('content') or []):
            if block.get('type') == 'tool_use':
                calls.append(Call(ident, turns, str(block.get('name')), cast(dict[str, Any], block.get('input') or {}),
                                  str(block.get('id'))))
    return order, usage, calls, turns


def result_texts(events: list[dict[str, Any]]) -> dict[str, str]:
    """Each tool call's result as the model was given it, by tool_use_id: its text blocks joined."""
    found: dict[str, str] = {}
    for event in events:
        if event.get('type') != 'user':
            continue
        content = cast(dict[str, Any], event.get('message') or {}).get('content')
        for block in cast(list[dict[str, Any]], content if isinstance(content, list) else []):
            if block.get('type') != 'tool_result':
                continue
            held = block.get('content')
            parts = cast(list[Any], held or [])
            text = held if isinstance(held, str) else '\n'.join(
                str(cast(dict[str, Any], part).get('text') or '') for part in parts if isinstance(part, dict))
            found[str(block.get('tool_use_id'))] = text
    return found


def metaform_cli(call: Call) -> bool:
    return call.name == 'Bash' and bool(re.search(r'(^|[;&|]\s*)metaform\b', str(call.input.get('command', ''))))


def is_metaform(call: Call) -> bool:
    """A call of Metaform's own surface: its tools, its resources, the deferred-tool search that loads them, or its
    CLI."""
    return (call.name.startswith('mcp__metaform__') or call.name in ('ReadMcpResourceTool', 'ListMcpResourcesTool',
                                                                      'ToolSearch') or metaform_cli(call))


def result_key(call: Call) -> str:
    if call.name == 'ReadMcpResourceTool':
        return f'read {call.input.get("uri") or call.input.get("file_path") or "?"}'
    if call.name == 'Bash':
        return 'Bash (metaform)' if metaform_cli(call) else 'Bash'
    return call.name


def decompose(events: list[dict[str, Any]], write_turn: int | None, correct_turn: int | None) -> dict[str, Any]:
    """Where a run's tokens went. Each main-thread request is counted whole (all it carried in, and what it wrote)
    in one phase: orientation up to and including the request that made the first write; work up to the first
    correct edit; then each later request by the calls it made, bookkeeping when they are all the ticket's and the
    memory's writes the hand-off asks for, verification when one is a shell command that is not Metaform's, closing
    otherwise. Subagents and Claude Code's own small calls are apart. Each tool result is sized in characters, about
    four to a token, and carried: its tokens times the main-thread requests that carried it in, up to the first write
    and to the end."""
    order, usage, calls, _ = calls_and_usage(events)
    main = {str(cast(dict[str, Any], event.get('message') or {}).get('id')) for event in events
            if event.get('type') == 'assistant' and event.get('parent_tool_use_id') is None}
    by_message: dict[str, list[Call]] = {}
    for call in calls:
        by_message.setdefault(call.message, []).append(call)
    phases = {name: 0 for name in ('orientation', 'work', 'verification', 'bookkeeping', 'closing', 'subagents')}
    kinds = {name: {'fresh': 0, 'read': 0, 'output': 0, 'usd': 0.0} for name in phases}
    models = models_of(events)
    priced = True
    turns: list[int] = []
    metaform_only = {'requests': 0, 'tokens': 0}
    context: dict[str, int] = {'at_end': 0, 'peak': 0}
    turn = 0
    for ident in order:
        spent = context_tokens(usage[ident]) + int(usage[ident].get('output_tokens') or 0)
        held, usd = split_tokens(usage[ident]), request_usd(models.get(ident, ''), usage[ident])
        priced = priced and usd is not None
        if ident not in main:
            phases['subagents'] += spent
            for name, value in (('fresh', held['uncached'] + held['written']), ('read', held['read']),
                                ('output', held['output']), ('usd', usd or 0.0)):
                kinds['subagents'][name] += value
            continue
        turn += 1
        turns.append(turn)
        context['at_end'] = context_tokens(usage[ident])
        context['peak'] = max(context['peak'], context['at_end'])
        if write_turn is not None and turn == write_turn:
            context['at_first_write'] = context['at_end']  # left out when no write was made
        made = by_message.get(ident, [])
        if write_turn is None or turn <= write_turn:
            phase = 'orientation'
            if made and all(is_metaform(call) for call in made):
                metaform_only['requests'] += 1
                metaform_only['tokens'] += spent
        elif correct_turn is None or turn <= correct_turn:
            phase = 'work'
        elif made and all(BOOKKEEPING.match(call.name) for call in made):
            phase = 'bookkeeping'
        elif any(call.name == 'Bash' and not metaform_cli(call) for call in made):
            phase = 'verification'
        else:
            phase = 'closing'
        phases[phase] += spent
        for name, value in (('fresh', held['uncached'] + held['written']), ('read', held['read']),
                            ('output', held['output']), ('usd', usd or 0.0)):
            kinds[phase][name] += value
    total_in, total_out = totals(events, usage)
    phases['other'] = max(0, total_in + total_out - sum(phases.values()))
    reported = result_of(events).get('total_cost_usd')
    used = cast(dict[str, dict[str, Any]], result_of(events).get('modelUsage') or {}).values()
    whole = {'fresh': sum(int(one.get('inputTokens') or 0) + int(one.get('cacheCreationInputTokens') or 0)
                          for one in used),
             'read': sum(int(one.get('cacheReadInputTokens') or 0) for one in used),
             'output': sum(int(one.get('outputTokens') or 0) for one in used)}
    kinds['other'] = {**{name: max(0, whole[name] - sum(int(one[name]) for one in kinds.values()))
                         if whole['fresh'] + whole['read'] else 0 for name in ('fresh', 'read', 'output')},
                      'usd': max(0.0, float(reported) - sum(one['usd'] for one in kinds.values()))
                      if isinstance(reported, (int, float)) and priced else 0.0}
    texts = result_texts(events)
    sized: dict[str, dict[str, int]] = {}
    for call in calls:
        if call.ident not in texts:
            continue
        chars = len(texts[call.ident])
        tokens = math.ceil(chars / 4)
        later = [one for one in turns if one > call.turn]
        held = sized.setdefault(result_key(call), {'calls': 0, 'chars': 0, 'tokens_est': 0,
                                                   'carried_to_first_write': 0, 'carried_to_end': 0})
        held['calls'] += 1
        held['chars'] += chars
        held['tokens_est'] += tokens
        held['carried_to_first_write'] += tokens * sum(1 for one in later if write_turn is None or one <= write_turn)
        held['carried_to_end'] += tokens * len(later)
    return {'phases': phases, 'kinds': kinds, 'priced': priced, 'context': context,
            'metaform_only_before_first_write': metaform_only,
            'results': dict(sorted(sized.items(), key=lambda item: -item[1]['carried_to_end']))}


def met_failures(events: list[dict[str, Any]], known: set[str]) -> list[str]:
    """The start state's failing tests and collection errors that a shell command's output showed the agent."""
    if not known:
        return []
    texts = result_texts(events)
    _, _, calls, _ = calls_and_usage(events)
    shown = '\n'.join(texts.get(call.ident, '') for call in calls if call.name == 'Bash')
    return sorted(one for one in known if one in shown)


PYTEST_SUMMARY = re.compile(r'^[^\n]*\b\d+ (?:passed|failed|errors?)\b[^\n]* in [\d.]+s\b[^\n]*$', re.MULTILINE)


def failures_seen(events: list[dict[str, Any]], after_turn: int | None) -> int | None:
    """The most failing and erroring tests a pytest summary showed the agent after its first correct edit, whatever
    their cause: a run that passed the grader and still saw failures checked against a suite that was not green.
    None when no shell output after that edit held a pytest summary."""
    if after_turn is None:
        return None
    texts = result_texts(events)
    _, _, calls, _ = calls_and_usage(events)
    seen: int | None = None
    for call in calls:
        if call.name != 'Bash' or call.turn <= after_turn:
            continue
        for found in PYTEST_SUMMARY.finditer(texts.get(call.ident, '')):
            count = sum(int(number) for number in re.findall(r'(\d+) (?:failed|errors?)\b', found.group()))
            seen = count if seen is None else max(seen, count)
    return seen


def first_search_and_target(calls: list[Call], target: str) -> dict[str, Any]:
    """Whether the agent opened the target file before it searched: the turn of its first search (Grep, Glob, a shell
    grep or find, Metaform's code search) and of its first read of the target."""
    searched = next((call.turn for call in calls if call.name in ('Grep', 'Glob', 'mcp__metaform__map_code-search')
                     or (call.name == 'Bash' and SEARCH_COMMAND.search(str(call.input.get('command', ''))))), None)
    opened = next((call.turn for call in calls if target and (
        (call.name == 'Read' and str(call.input.get('file_path', '')).endswith(target))
        or (call.name == 'Bash' and target in str(call.input.get('command', ''))
            and not SEARCH_COMMAND.search(str(call.input.get('command', '')))))), None)
    return {'first_search_turn': searched, 'target_opened_turn': opened,
            'opened_target_before_search': None if opened is None else (searched is None or opened <= searched)}


def folder_slug(folder: Path) -> str:
    """The name Claude Code and Metaform give a folder in the home: its path with every other character a dash."""
    return re.sub(r'[^A-Za-z0-9]', '-', str(folder))


def leftover(user: Path, parent: str, name: str, session: str) -> bool:
    """Whether a folder a run left in the home is Claude Code's own per-session state: one of its session folders, or
    a project folder holding only the session's spilled large tool results (<session>/tool-results)."""
    if parent in SESSION_STATE:
        return True
    if parent == '.claude/projects' and session:
        held = [path.relative_to(user / parent / name).parts for path in (user / parent / name).rglob('*')
                if path.is_file()]
        return all(len(parts) >= 3 and parts[0] == session and parts[1] == 'tool-results' for parts in held)
    return False


def home_changes(user: Path, marker: float, session: str, slug: str) -> dict[str, list[str]]:
    """What a --auth login run left in the person's home: Claude Code's own per-session state, found by the run's
    session id or its folder's name, is expected; a file at the top of the home written since the run began, or any
    other folder named for the run's folder (a Metaform project, a Claude Code project holding more than spilled tool
    results), is not. Other sessions on the machine write the home at the same time, so only what is the run's by
    name, or new at the top, is looked at; a full walk would take minutes and find their writes too."""
    expected: list[str] = []
    unexpected: list[str] = []
    for name in sorted(os.listdir(user)):
        path = user / name
        try:
            if path.is_file() and not path.is_symlink() and path.stat().st_mtime > marker and \
                    not name.startswith('.claude.json'):
                unexpected.append(f'~/{name}')
        except OSError:
            continue
    for parent in ('.claude', '.cache', '.metaform', '.metaform/projects', '.claude/projects', *SESSION_STATE):
        folder = user / parent
        if not folder.is_dir():
            continue
        for name in os.listdir(folder):
            if (session and session in name) or name == slug or name.startswith(f'{slug}-'):
                (expected if leftover(user, parent, name, session) else unexpected).append(f'~/{parent}/{name}')
    return {'expected': sorted(set(expected)), 'unexpected': sorted(set(unexpected))}


def written(call: Call, folder: Path) -> tuple[bool, str | None]:
    """Fallback only: whether a tool call writes a file, and the repository path it writes when that is known."""
    if call.name in FILE_WRITES:
        raw = str(call.input.get('file_path') or call.input.get('notebook_path') or '')
        path = Path(raw) if Path(raw).is_absolute() else folder / raw
        try:
            return True, str(path.resolve().relative_to(folder.resolve()))
        except ValueError:
            return True, raw
    if call.name == 'Bash' and BASH_WRITE.search(str(call.input.get('command', ''))):
        return True, None
    return False, None


def replay(call: Call, folder: Path, relative: str) -> bool:
    """Fallback only: apply one file tool call to the replay copy; False when it cannot be applied as the tool would."""
    path = folder / relative
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    if call.name == 'Write':
        path.write_text(str(call.input.get('content', '')), encoding='utf-8')
        return True
    edits = cast(list[dict[str, Any]], call.input.get('edits') or [call.input])
    for edit in edits:
        old, new = str(edit.get('old_string', '')), str(edit.get('new_string', ''))
        if not old or old not in text:
            return False
        text = text.replace(old, new) if edit.get('replace_all') else text.replace(old, new, 1)
    path.write_text(text, encoding='utf-8')
    return True


def by_trees(trail: list[dict[str, Any]], calls: dict[str, Call], folder: Path, start: str, task: dict[str, Any],
             repo: dict[str, Any], scratch: Path) -> dict[str, Any]:
    """The first write and the first correct edit from the trees the hook recorded: the first call after which the
    tree differs from the start, and the first new tree the grader passes on."""
    first_write: dict[str, Any] | None = None
    first_correct: dict[str, Any] | None = None
    previous = start
    for entry in trail:
        tree = str(entry.get('tree') or '')
        if not tree or tree == previous:
            continue
        previous = tree
        call = calls.get(str(entry.get('tool_use_id')))
        found = {'call': call, 'tool': entry.get('tool_name'), 'tree': tree}
        if first_write is None:
            changed = subprocess.run(['git', '-C', str(folder), 'diff-tree', '-r', '--name-only', start, tree],
                                     capture_output=True, text=True, check=False).stdout.split()
            first_write = {**found, 'paths': changed}
        if task['grade']['type'] != 'none' and grade_folder(extract(folder, tree, scratch / 'tree'), task, repo)[0]:
            first_correct = found
            break
    shutil.rmtree(scratch / 'tree', ignore_errors=True)
    return {'first_write': first_write, 'first_correct': first_correct}


def by_replay(calls: list[Call], folder: Path, task: dict[str, Any], repo: dict[str, Any],
              scratch: Path) -> dict[str, Any]:
    """When the hook left no record: writes read from the commands, and the agent's file edits replayed on the start
    and graded after each; a target written by Bash ends the replay, since what it wrote is not known."""
    start = extract(folder, start_tree(folder), scratch / 'replay')
    wanted = targets(task)
    first_write: dict[str, Any] | None = None
    first_correct: dict[str, Any] | None = None
    replayable = True
    for call in calls:
        writes, relative = written(call, folder)
        if not writes:
            continue
        first_write = first_write or {'call': call, 'tool': call.name, 'paths': [relative] if relative else []}
        if relative is None:
            command = str(call.input.get('command', ''))
            if any(target in command or Path(target).name in command for target in wanted):
                replayable = False
            continue
        if relative in wanted and replayable and first_correct is None:
            replayable = replay(call, start, relative)
            if replayable and task['grade']['type'] != 'none' and grade_folder(start, task, repo)[0]:
                first_correct = {'call': call, 'tool': call.name}
    shutil.rmtree(start, ignore_errors=True)
    return {'first_write': first_write, 'first_correct': first_correct, 'replay_complete': replayable}


def reach(calls: list[Call], events: list[dict[str, Any]]) -> dict[str, Any]:
    """How far Metaform reached the agent: its tools listed and called, resources read, deferred-tool searches, and
    what the permission system refused, by tool."""
    init = init_of(events)
    listed = [str(name) for name in cast(list[Any], init.get('tools') or [])]
    denials: dict[str, int] = {}
    for denial in cast(list[dict[str, Any]], result_of(events).get('permission_denials') or []):
        name = str(denial.get('tool_name'))
        denials[name] = denials.get(name, 0) + 1
    used = [call.name for call in calls if call.name.startswith('mcp__metaform__')]
    return {
        'model_resolved': init.get('model'),
        'metaform_tools_listed': sum(name.startswith('mcp__metaform__') for name in listed),
        'dispatch_tools_listed': sum(name.startswith('mcp__metaform__dispatch_') for name in listed),
        'metaform_calls': len(used),
        'metaform_tools_used': sorted(set(used)),
        'metaform_cli_calls': sum(metaform_cli(call) for call in calls),
        'memory_reads': sum(bool(MEMORY_READS.match(call.name)) for call in calls),
        'memory_writes': sum(call.name.startswith('mcp__metaform__memory_') and not MEMORY_READS.match(call.name)
                             for call in calls),
        'resource_reads': [str(call.input.get('uri') or json.dumps(call.input)) for call in calls
                           if call.name == 'ReadMcpResourceTool'],
        'tool_searches': [str(call.input.get('query')) for call in calls if call.name == 'ToolSearch'],
        'denials': denials,
    }


def measure(events: list[dict[str, Any]], folder: Path, task: dict[str, Any], repo: dict[str, Any],
            trail_log: Path, scratch: Path, known_failures: set[str]) -> dict[str, Any]:
    order, usage, calls, turns = calls_and_usage(events)
    trail = [cast(dict[str, Any], json.loads(line)) for line in
             (trail_log.read_text(encoding='utf-8').splitlines() if trail_log.exists() else []) if line.strip()]
    if trail:
        found = by_trees(trail, {call.ident: call for call in calls}, folder, start_tree(folder), task, repo, scratch)
        found['write_detection'] = 'hook'
    else:
        found = by_replay(calls, folder, task, repo, scratch)
        found['write_detection'] = 'command text (no hook record)'

    def call_of(key: str) -> Call | None:
        held = cast(dict[str, Any] | None, found.get(key))
        return cast(Call | None, held.get('call')) if held else None

    def before(call: Call | None) -> int | None:
        if call is None or call.message not in order:
            return None
        return sum(context_tokens(usage[ident]) for ident in order[:order.index(call.message) + 1])

    write, correct = call_of('first_write'), call_of('first_correct')
    held_write = cast(dict[str, Any] | None, found.get('first_write'))
    total_in, total_out = totals(events, usage)
    tools: dict[str, int] = {}
    for call in calls:
        tools[call.name] = tools.get(call.name, 0) + 1
    result = result_of(events)
    reached = reach(calls, events)
    return {
        'turns': turns,
        'num_turns': result.get('num_turns'),
        'write_detection': found['write_detection'],
        'first_write_tool': held_write.get('tool') if held_write else None,
        'first_write_paths': held_write.get('paths') if held_write else None,
        'input_tokens_before_first_write': before(write),
        'turns_before_first_write': write.turn if write else None,
        'turns_to_first_correct_edit': correct.turn if correct else None,
        'input_tokens_before_first_correct_edit': before(correct),
        'replay_complete': found.get('replay_complete'),
        'input_tokens': total_in,
        'output_tokens': total_out,
        'total_tokens': total_in + total_out,
        'cost_usd': result.get('total_cost_usd'),
        'result_subtype': result.get('subtype'),
        'is_error': result.get('is_error'),
        'tools': tools,
        **reached,
        **spent_on(events, write.turn if write else None, correct.turn if correct else None, turns, reached),
        **first_search_and_target(calls, task['grade'].get('file', '')),
        'met_start_failures': met_failures(events, known_failures),
        'failures_seen_after_fix': failures_seen(events, correct.turn if correct else None),
        'session_id': init_of(events).get('session_id'),
        'mcp_servers': init_of(events).get('mcp_servers'),
        'claude_code_version': init_of(events).get('claude_code_version'),
    }


def spent_on(events: list[dict[str, Any]], write_turn: int | None, correct_turn: int | None, turns: int,
             reached: dict[str, Any]) -> dict[str, Any]:
    """The decomposition, flattened into the run's record so the summaries can pair it."""
    split = decompose(events, write_turn, correct_turn)
    denied = sum(cast(dict[str, int], reached.get('denials') or {}).values())
    kinds = cast(dict[str, dict[str, float]], split['kinds'])
    context = cast(dict[str, int], split['context'])
    fresh_before = int(kinds['orientation']['fresh'])
    return {**{f'tokens_{name}': value for name, value in split['phases'].items()},
            **{f'fresh_{name}': int(held['fresh']) for name, held in kinds.items()},
            **{f'read_{name}': int(held['read']) for name, held in kinds.items()},
            **{f'usd_{name}': round(held['usd'], 6) if split['priced'] else None for name, held in kinds.items()},
            'fresh_tokens': sum(int(held['fresh']) for held in kinds.values()),
            'read_tokens': sum(int(held['read']) for held in kinds.values()),
            'usd_list': round(sum(held['usd'] for held in kinds.values()), 6) if split['priced'] else None,
            'fresh_before_first_write': fresh_before if write_turn is not None else None,
            'context_at_first_write': context.get('at_first_write'), 'context_at_end': context['at_end'],
            'context_peak': context['peak'],
            'metaform_only_requests_before_first_write': split['metaform_only_before_first_write']['requests'],
            'metaform_only_tokens_before_first_write': split['metaform_only_before_first_write']['tokens'],
            'results_carried': split['results'], 'denial_share': round(denied / turns, 3) if turns else None}


# -------------------------------------------------------------------------------------------------------- the runs


@dataclass
class Prepared:
    repo: dict[str, Any]
    base: Path
    commit: str
    agents_md: Path | None = None
    map_export: Path | None = None
    prep: dict[str, Any] = field(default_factory=dict[str, Any])
    surface: dict[str, Any] | None = None
    surface_error: str | None = None
    surface_home: Path | None = None
    surface_folder: Path | None = None
    code: dict[str, Any] | None = None  # what map code-import said on the surface home; None when it was not run
    code_error: str | None = None
    oracle: dict[str, dict[str, Any]] = field(default_factory=dict[str, dict[str, Any]])
    start: dict[str, Any] | None = None  # the start state's test failures

    @property
    def map_label(self) -> str:
        """How the Metaform arms' map stands, said beside every number they give."""
        if self.code is None:
            return 'map without code layer'
        linked = cast(dict[str, Any], self.code.get('linked') or {})
        return 'map with code layer' if linked.get('nodes') else 'map with code layer, no code linked to its nodes'


def served_src(prepared: Prepared, folder: Path, source: Source) -> Path:
    """Where the Metaform under test is imported from: this repository's run workspace when the task is on it, so the
    server is the code being edited; otherwise the copy."""
    return folder / 'src' if is_self(prepared.repo) else source.tree / 'src'


def kept(cache: Path, kind: str, name: str, key: str, suffix: str) -> tuple[Path, Path]:
    path = cache / kind / f'{name}-{key[:16]}{suffix}'
    return path, path.with_suffix(path.suffix + '.json')


def sidecar(events: list[dict[str, Any]], options: Options, started: str, model: str, key: str) -> dict[str, Any]:
    init = init_of(events)
    return {'cost_usd': result_of(events).get('total_cost_usd'), 'run': started, 'model': model,
            'model_resolved': init.get('model'), 'claude_code_version': init.get('claude_code_version'),
            'auth': options.auth, 'key': key}


def prepare_agents_md(name: str, prepared: Prepared, plan: dict[str, Any], options: Options, spend: Spend,
                      cache: Path, scratch: Path, log: Path, started: str, source: Source) -> None:
    """The AGENTS.md overview of the repository, generated once per prompt, model and repository state and cached,
    with a sidecar of what it cost."""
    prompt = plan['agents_md_prompt']
    key = sha(prompt, options.model, prepared.commit, source.ident if is_self(prepared.repo) else '')
    path, side = kept(cache, 'agents-md', name, key, '.md')
    print(f'  AGENTS.md cache key {key[:16]} (prompt {sha(prompt)[:12]}, model {options.model})')
    if path.exists():
        prepared.agents_md = path
        prepared.prep['agents_md'] = {**(json.loads(side.read_text()) if side.exists() else {}), 'cached': True,
                                      'bytes': path.stat().st_size}
        return
    if options.dry_run:
        print(f'  would generate AGENTS.md for {name} into {path}')
        return
    budget = spend.budget(options.run_budget, options.min_run)
    if budget is None:
        raise Skip('the spend cap leaves nothing to generate AGENTS.md with')
    folder = workspace(prepared.base, scratch / f'agents-md-{name}', [])
    empty = scratch / f'mfhome-empty-am-{name}'
    events, reason, _ = run_claude(
        claude_command(options, budget, model=options.model, mcp=None, settings={}, allowed=[],
                       max_turns=options.max_turns),
        prompt, folder, claude_env(options, scratch / f'home-am-{name}', metaform_home=empty, bin_dir=None,
                                   python_path=[]), options.timeout, log / f'prepare-agents-md-{name}.jsonl')
    spend.add(f'AGENTS.md for {name}', result_of(events).get('total_cost_usd'), budget)
    made = next((folder / file for file in ('AGENTS.md', 'CLAUDE.md') if (folder / file).exists()), None)
    if made is None:
        raise Skip(f'the AGENTS.md generation wrote no file ({reason or result_of(events).get("subtype")})')
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(made, path)
    note = sidecar(events, options, started, options.model, key)
    side.write_text(json.dumps(note, indent=2), encoding='utf-8')
    prepared.agents_md = path
    prepared.prep['agents_md'] = {**note, 'cached': False, 'bytes': path.stat().st_size}


def prepare_map(name: str, prepared: Prepared, options: Options, spend: Spend, cache: Path, scratch: Path,
                log: Path, started: str, source: Source) -> None:
    """The map the Metaform arms import: an export in the repository or named by file, or one an intake run
    recorded, cached by the intake prompt, model, Metaform and repository state. Then the server's surface, read once
    from a home like the arms', which also proves the source under test starts."""
    declared = prepared.repo.get('map', {})
    if 'import' in declared or 'export_file' in declared:
        prepared.map_export = (prepared.base / declared['import'] if 'import' in declared
                               else Path(declared['export_file']).expanduser())
        prepared.prep['map'] = {'how': f'imported {declared.get("import") or declared["export_file"]}',
                                'cost_usd': None, 'model': None,
                                'note': 'made outside this evaluation; its preparation cost is not known'}
    else:
        folder = workspace(prepared.base, scratch / f'intake-{name}', [])
        home = scratch / f'mfhome-intake-{name}'
        src = served_src(prepared, folder, source)
        metaform_home(folder, home, name, None, options.node_bytes, src, dispatch=False)
        prompt = metaform(['intake', 'prompt'], home=home, src=src, cwd=folder)
        key = sha(prompt, options.intake_model, source.ident, prepared.commit)
        path, side = kept(cache, 'maps', name, key, '.json')
        print(f'  map cache key {key[:16]} (intake prompt {sha(prompt)[:12]}, model {options.intake_model}, '
              f'metaform {source.label})')
        if path.exists():
            prepared.map_export = path
            prepared.prep['map'] = {**(json.loads(side.read_text()) if side.exists() else {}), 'cached': True,
                                    'how': f'intake kept at {path.relative_to(cache.parent)}'}
        elif options.dry_run:
            print(f'  would run the intake for {name} with {options.intake_model}, at most '
                  f'${options.intake_budget:.2f} and {options.intake_max_turns} turns')
        else:
            budget = spend.budget(options.intake_budget, options.min_run)
            if budget is None:
                raise Skip('the spend cap leaves nothing for the intake')
            command = claude_command(options, budget, model=options.intake_model,
                                     mcp=mcp_config(home, src, scratch / 'intake.json'), settings={},
                                     allowed=[*METAFORM_TOOLS], max_turns=options.intake_max_turns)
            events, reason, _ = run_claude(command, prompt, folder, claude_env(
                options, scratch / f'home-intake-{name}', metaform_home=home, bin_dir=bin_folder(
                    scratch / f'intake-bin-{name}', home, src), python_path=[]), options.intake_timeout,
                log / f'prepare-intake-{name}.jsonl')
            spend.add(f'intake for {name}', result_of(events).get('total_cost_usd'), budget)
            status = metaform(['intake', 'status'], home=home, src=src, cwd=folder, check=False).strip()
            exported = scratch / f'intake-{name}.json'
            metaform(['export', name, f'file={exported}'], home=home, src=src, cwd=folder)
            document = json.loads(exported.read_text(encoding='utf-8'))
            for entry in document.get('projects', []):
                if not entry.get('active_base'):
                    raise Skip(f'the intake left no active map ({reason or status})')
                # As the release map does: the folder it was recorded in belongs to that run.
                entry['project'].update(path='', target_value='')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(document), encoding='utf-8')
            note = sidecar(events, options, started, options.intake_model, key)
            side.write_text(json.dumps(note, indent=2), encoding='utf-8')
            prepared.map_export = path
            prepared.prep['map'] = {**note, 'cached': False, 'how': f'intake by {options.intake_model}'}
    if prepared.map_export is None:
        return
    folder = workspace(prepared.base, scratch / f'surface-{name}', [])
    home = scratch / f'mfhome-surface-{name}'
    src = served_src(prepared, folder, source)
    prepared.surface_home, prepared.surface_folder = home, folder
    try:
        prepared.code = metaform_home(folder, home, name, prepared.map_export, options.node_bytes, src, dispatch=True,
                                      code=options.code_layer and bool(EXTRA_PATH))
        prepared.surface = server_surface(folder, home, src)
    except Skip as skip:
        prepared.surface_error = str(skip)
        raise


def check_on_map(prepared: Prepared, tasks: list[dict[str, Any]], source: Source) -> dict[str, str]:
    """What the map says of each task: a request that names an Address on the map is no blind placement and is
    refused (a control is only told); and whether the code layer holds the graded file at the oracle Address, so the
    oracle is the map's answer and not only its author's guess."""
    home, folder = prepared.surface_home, prepared.surface_folder
    if home is None or folder is None or prepared.surface is None:
        return {}
    src = served_src(prepared, folder, source)
    refused: dict[str, str] = {}
    for task in tasks:
        named = [one for one in ADDRESS.findall(task['request'])
                 if subprocess.run([sys.executable, '-m', 'metaform', 'map', 'where', one], cwd=folder,
                                   env=metaform_env(home, src), capture_output=True, check=False).returncode == 0]
        if named and not task.get('control'):
            refused[task['id']] = f'the request names map Address {named[0]}'
        held: list[str] = []
        if prepared.code is not None and task['grade'].get('file'):
            said = metaform(['map', 'code-context', f'file={task["grade"]["file"]}', 'limit=1'], home=home, src=src,
                            cwd=folder, check=False)
            line = next((one for one in said.splitlines() if one.startswith('address: ')), 'address: []')
            try:
                held = [str(one) for one in cast(list[Any], json.loads(line.partition(': ')[2]))]
            except ValueError:
                held = []
        prepared.oracle[task['id']] = {
            'address': task.get('address'), 'addresses_holding_file': held,
            'confirmed': (task.get('address') in held) if task.get('address') and prepared.code is not None and
                         cast(dict[str, Any], prepared.code.get('linked') or {}).get('nodes') else None,
            'request_names': named}
    return refused


def place(task: dict[str, Any], plan: dict[str, Any], folder: Path, home: Path, src: Path, here: Path,
          options: Options, spend: Spend, log: Path, tag: str) -> dict[str, Any]:
    """The blind placement: an agent with only the map's tools reads the request and names the Address it belongs
    at, as the person's system agent places a ticket. Its cost is recorded beside the run, not in it."""
    budget = spend.budget(options.placement_budget, options.min_run)
    if budget is None:
        raise Skip('spend cap reached before placement')
    command = claude_command(options, budget, model=options.model, mcp=mcp_config(home, src, here / 'place.json'),
                             settings={}, allowed=[*METAFORM_TOOLS], max_turns=options.max_turns,
                             tools=PLACEMENT_TOOLS)
    events, reason, _ = run_claude(command, plan['placement_prompt'].replace('{request}', task['request']), folder,
                                   claude_env(options, here / 'home-place', metaform_home=home, bin_dir=None,
                                              python_path=[]), options.timeout, log / f'{tag}.placement.jsonl')
    result = result_of(events)
    spend.add(f'{tag} placement', result.get('total_cost_usd'), budget)
    _, usage, calls, turns = calls_and_usage(events)
    total_in, total_out = totals(events, usage)
    said = str(result.get('result') or '')
    named = ADDRESS.findall(said.strip().splitlines()[-1] if said.strip() else '')
    address = named[-1] if named else None
    if address and subprocess.run([sys.executable, '-m', 'metaform', 'map', 'where', address], cwd=folder,
                                  env=metaform_env(home, src), capture_output=True, check=False).returncode != 0:
        address = None
    return {'placement_address': address, 'placement_said': said[-300:], 'placement_turns': turns,
            'placement_tokens': total_in + total_out, 'placement_cost_usd': result.get('total_cost_usd'),
            'placement_metaform_calls': sum(call.name.startswith('mcp__metaform__') for call in calls),
            'placement_ended': reason or None,
            'placement_matches_oracle': address == task.get('address') if task.get('address') else None}


def request_of(task: dict[str, Any], plan: dict[str, Any]) -> str:
    return f'{task["request"]}\n\n{plan["instructions"].get(task["kind"], "")}'.strip()


def one_run(task: dict[str, Any], arm: str, trial: int, prepared: Prepared, plan: dict[str, Any], options: Options,
            spend: Spend, scratch: Path, log: Path, source: Source,
            by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tag = f'{task["id"]}.{arm}.{trial}'
    record: dict[str, Any] = {'task': task['id'], 'arm': arm, 'trial': trial, 'kind': task['kind'],
                              'repo': task['repo'], 'commit': prepared.commit, 'control': bool(task.get('control'))}
    here = scratch / tag
    here.mkdir(parents=True)
    folder, home = here / 'repo', here / 'metaform-home'
    request = request_of(task, plan)
    prompt, mcp, allowed = request, None, [*CHECKS]
    code = options.code_layer and bool(EXTRA_PATH)
    if arm in METAFORM_ARMS:
        if prepared.map_export is None or prepared.surface is None:
            raise Skip(f'no map or no server for {task["repo"]}: {prepared.surface_error or "see preparation"}')
        record['map'] = prepared.map_label
        mcp, allowed = mcp_config(home, served_src(prepared, folder, source), here / 'mcp.json'), \
            [*CHECKS, *METAFORM_TOOLS]
    if arm == 'metaform_warm':
        seed = by_id.get(str(task.get('seed') or ''))
        if seed is None or seed['repo'] != task['repo'] or not seed.get('address') or not task.get('address'):
            raise Skip('the task names no seed task with an Address on the same repository')
        if options.dry_run:
            raise Skip('a warm run spends on its seed first; not run in a dry run')
        # The seed works a ticket at its node first, in the same folder and home, as an earlier ticket there would;
        # then the folder is set back to the task's start and the task is handed over at its own node.
        workspace(prepared.base, folder, seed.get('setup', []))
        src = served_src(prepared, folder, source)
        record['code_layer'] = metaform_home(folder, home, task['repo'], prepared.map_export, options.node_bytes, src,
                                             dispatch=True, code=code)
        _, told = ticket(folder, home, src, seed['address'], request_of(seed, plan))
        seeded, events = agent_run(seed, 'metaform', told, folder, home, src, here / 'seed', prepared, options, spend,
                                   log, f'{tag}.seed', mcp, allowed)
        names = sorted({str(entity.get('name')) for call in calls_and_usage(events)[2]
                        if call.name == 'mcp__metaform__memory_create_entities'
                        for entity in cast(list[dict[str, Any]], call.input.get('entities') or [])})
        record['seed'] = {'task': seed['id'], 'address': seed['address'], 'passed': seeded.get('passed'),
                          'total_tokens': seeded.get('total_tokens'), 'cost_usd': seeded.get('cost_usd'),
                          'memory_writes': seeded.get('memory_writes'), 'memory_names': names}
        shutil.rmtree(folder)
        workspace(prepared.base, folder, task.get('setup', []))
        record['address'] = task['address']
        record['work_id'], prompt = ticket(folder, home, src, task['address'], request)
        record['prompt_context_bytes'] = len(prompt.encode()) - len(request.encode())
        record['prompt_names_seed_memory'] = [name for name in names if name in prompt]
        record.update(agent_run(task, arm, prompt, folder, home, src, here, prepared, options, spend, log, tag, mcp,
                                allowed)[0])
        return record
    workspace(prepared.base, folder, task.get('setup', []))
    src = served_src(prepared, folder, source)
    if arm == 'agents_md':
        if prepared.agents_md is None:
            raise Skip('no AGENTS.md for this repository')
        shutil.copyfile(prepared.agents_md, folder / 'AGENTS.md')
        record['prompt_context_bytes'] = (folder / 'AGENTS.md').stat().st_size
    if arm in METAFORM_ARMS:
        record['code_layer'] = metaform_home(folder, home, task['repo'], prepared.map_export, options.node_bytes, src,
                                             dispatch=arm != 'metaform_brief', code=code)
        if arm == 'metaform_brief':
            told = brief(folder, home, src, task.get('address'))
            prompt = f'{told}\n\n{request}'
            record['address'] = task.get('address')
            record['prompt_context_bytes'] = len(told.encode())
        else:
            if arm == 'metaform':
                address = task.get('address')
                if not address:
                    raise Skip('the task names no Address, so there is no oracle node')
            else:
                if options.dry_run:
                    raise Skip('placement spends tokens; not run in a dry run')
                record.update(place(task, plan, folder, home, src, here, options, spend, log, tag))
                address = record['placement_address']
                if not address:
                    raise Skip(f'the placement named no element on the map: {record["placement_said"][-120:]!r}')
            record['address'] = address
            record['work_id'], prompt = ticket(folder, home, src, address, request)
            record['prompt_context_bytes'] = len(prompt.encode()) - len(request.encode())
    else:
        home.mkdir(parents=True)  # an empty home, so a metaform call never reaches the person's own
    record.update(agent_run(task, arm, prompt, folder, home, src, here, prepared, options, spend, log, tag, mcp,
                            allowed)[0])
    if 'placement_tokens' in record and record.get('total_tokens') is not None:
        record['total_tokens_with_placement'] = record['total_tokens'] + record['placement_tokens']
    return record


def agent_run(task: dict[str, Any], arm: str, prompt: str, folder: Path, home: Path, src: Path, here: Path,
              prepared: Prepared, options: Options, spend: Spend, log: Path, tag: str, mcp: Path | None,
              allowed: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """One agent's run on a prepared folder: what the arm put there committed as the start, the claude call with the
    tree hook, and the run measured, graded and checked for what it left in the person's home."""
    record: dict[str, Any] = {}
    here.mkdir(parents=True, exist_ok=True)
    # What the arm put in the workspace (the overview, anything Metaform's setup wrote there) is part of the start.
    record['arm_setup_paths'] = [line[3:] for line in subprocess.run(
        ['git', '-C', str(folder), 'status', '--porcelain', '--untracked-files=all'], check=True, capture_output=True,
        text=True).stdout.splitlines()]
    subprocess.run(['git', '-C', str(folder), 'add', '-A'], check=True)
    subprocess.run(['git', '-C', str(folder), *GIT_ID, 'commit', '--quiet', '--no-verify', '--allow-empty', '-m',
                    f'arm {arm}'], check=True)
    record['prompt_bytes'] = len(prompt.encode())
    (log / f'{tag}.prompt.txt').write_text(prompt, encoding='utf-8')
    budget = spend.budget(options.run_budget, options.min_run)
    if budget is None:
        raise Skip('spend cap reached')
    if options.dry_run:
        record['planned_budget_usd'] = budget
        return record, []
    settings, trail = hook_settings(here, folder, here)
    command = claude_command(options, budget, model=options.model, mcp=mcp, settings=settings, allowed=allowed,
                             max_turns=options.max_turns)
    python_path = [folder / path for path in prepared.repo.get('python_path', ['.'])]
    env = claude_env(options, here / 'home', metaform_home=home, bin_dir=bin_folder(here, home, src),
                     python_path=python_path)
    began = time.time() - 1  # the file system's times are coarser than the clock on some systems
    events, reason, seconds = run_claude(command, prompt, folder, env, options.timeout, log / f'{tag}.jsonl')
    start = prepared.start or {}
    known = {*cast(list[str], start.get('failed') or []), *cast(list[str], start.get('collection_errors') or [])}
    record.update(measure(events, folder, task, prepared.repo, trail, here, known))
    if arm in METAFORM_ARMS:
        surface = prepared.surface or {}
        record.update(duplicates(delivered(events, prompt, surface.get('instructions'),
                                           surface.get('tool_descriptions'))))
    if trail.exists():
        shutil.copyfile(trail, log / f'{tag}.trees.jsonl')
    spend.add(tag, record['cost_usd'], budget)
    record['passed'], record['grade_note'] = grade_folder(folder, task, prepared.repo)
    record['seconds'] = round(seconds, 1)
    record['ended'] = reason or None
    diff = subprocess.run(['git', '-C', str(folder), 'diff'], capture_output=True, text=True, check=False).stdout
    (log / f'{tag}.diff').write_text(diff, encoding='utf-8')
    record['changed_files'] = subprocess.run(['git', '-C', str(folder), 'diff', '--name-only'], capture_output=True,
                                             text=True, check=False).stdout.split()
    if options.auth == 'login':
        left = home_changes(Path.home(), began, str(record.get('session_id') or ''), folder_slug(folder))
        record['home_changes'] = left
        record['isolation_breach'] = bool(left['unexpected'])
    return record, events


# --------------------------------------------------------------------------------------------------------- results


PHASES = ('orientation', 'work', 'verification', 'bookkeeping', 'closing', 'subagents', 'other')
METRICS = ('input_tokens_before_first_write', 'turns_to_first_correct_edit', 'input_tokens_before_first_correct_edit',
           'total_tokens', 'cost_usd', 'denial_share', 'metaform_only_requests_before_first_write',
           'metaform_only_tokens_before_first_write', *(f'tokens_{phase}' for phase in PHASES),
           'context_at_first_write', 'context_at_end', 'context_peak', 'fresh_tokens', 'fresh_before_first_write',
           'read_tokens', 'usd_list', 'delivered_chars', 'duplicate_blocks', 'duplicate_chars',
           *(f'fresh_{phase}' for phase in PHASES), *(f'usd_{phase}' for phase in PHASES))
PAIRED = ('input_tokens_before_first_write', 'turns_to_first_correct_edit', 'total_tokens', 'tokens_orientation',
          'tokens_work', 'tokens_verification', 'tokens_bookkeeping', 'context_at_end', 'fresh_tokens',
          'fresh_before_first_write', 'usd_list')


def spread(values: list[Any]) -> dict[str, Any]:
    known = [float(value) for value in values if value is not None]
    if not known:
        return {'n': 0, 'mean': None, 'stdev': None, 'min': None, 'max': None}
    return {'n': len(known), 'mean': statistics.fmean(known),
            'stdev': statistics.stdev(known) if len(known) > 1 else 0.0, 'min': min(known), 'max': max(known)}


def groups(records: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    held: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        if 'passed' in record and not record.get('isolation_breach'):
            held.setdefault((record['task'], record['arm']), []).append(record)
    return held


def summarise(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per task and arm across the k runs: pass@k (any passed), pass^k (all passed), each metric's spread across the
    runs, and how far Metaform reached the agent."""
    rows: list[dict[str, Any]] = []
    for (task, arm), held in groups(records).items():
        denials: dict[str, int] = {}
        for record in held:
            for name, count in cast(dict[str, int], record.get('denials') or {}).items():
                denials[name] = denials.get(name, 0) + count
        rows.append({'task': task, 'arm': arm, 'control': bool(held[0].get('control')), 'k': len(held),
                     'passed': sum(bool(r['passed']) for r in held),
                     'pass_at_k': any(r['passed'] for r in held), 'pass_hat_k': all(r['passed'] for r in held),
                     **{metric: spread([r.get(metric) for r in held]) for metric in METRICS},
                     'prompt_bytes': spread([r.get('prompt_bytes') for r in held]),
                     'metaform_calls': sum(int(r.get('metaform_calls') or 0) for r in held),
                     'metaform_cli_calls': sum(int(r.get('metaform_cli_calls') or 0) for r in held),
                     'resource_reads': sum(len(r.get('resource_reads') or []) for r in held),
                     'tool_searches': sum(len(r.get('tool_searches') or []) for r in held),
                     'memory_reads': sum(int(r.get('memory_reads') or 0) for r in held),
                     'met_start_failures': (sum(bool(r.get('met_start_failures')) for r in held)
                                            if any('met_start_failures' in r for r in held) else None),
                     'failures_seen_after_fix': [r.get('failures_seen_after_fix') for r in held],
                     'map': sorted({str(r['map']) for r in held if r.get('map')}),
                     'denials': denials, 'addresses': sorted({str(r.get('address')) for r in held if r.get('address')}),
                     'model_resolved': sorted({str(r.get('model_resolved')) for r in held if r.get('model_resolved')})})
    return rows


def paired(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Each arm against arm none on the same task and trial: per task, the differences' spread across trials; per arm,
    the per-task means with their range across tasks, never a pooled spread."""
    base = {(r['task'], r['trial']): r for r in records if r['arm'] == 'none' and 'passed' in r}
    rows: list[dict[str, Any]] = []
    for (task, arm), held in groups(records).items():
        if arm == 'none':
            continue
        row: dict[str, Any] = {'task': task, 'arm': arm, 'control': bool(held[0].get('control'))}
        for metric in PAIRED:
            diffs = [r[metric] - base[(task, r['trial'])][metric] for r in held
                     if (task, r['trial']) in base and r.get(metric) is not None
                     and base[(task, r['trial'])].get(metric) is not None]
            row[metric] = spread(diffs)
        row['total_tokens_with_placement'] = spread([
            r['total_tokens_with_placement'] - base[(task, r['trial'])]['total_tokens'] for r in held
            if r.get('total_tokens_with_placement') is not None and (task, r['trial']) in base
            and base[(task, r['trial'])].get('total_tokens') is not None])
        if any(row[metric]['n'] for metric in PAIRED):
            rows.append(row)
    arms: list[dict[str, Any]] = []
    for arm in ARMS[1:]:
        held = [row for row in rows if row['arm'] == arm and not row['control']]
        if held:
            arms.append({'arm': arm, 'tasks': len(held),
                         **{metric: spread([row[metric]['mean'] for row in held])
                            for metric in (*PAIRED, 'total_tokens_with_placement')}})
    return rows, arms


def shown(cell: dict[str, Any], digits: int = 0, signed: bool = False) -> str:
    if cell['mean'] is None:
        return '–'
    form = f'{{:+,.{digits}f}}' if signed else f'{{:,.{digits}f}}'
    mean = form.format(cell['mean'])
    return mean if cell['n'] < 2 else f'{mean} ± {cell["stdev"]:,.{digits}f}'


def ranged(cell: dict[str, Any], digits: int = 0) -> str:
    if cell['mean'] is None:
        return '–'
    form = f'{{:+,.{digits}f}}'
    mean = form.format(cell['mean'])
    return mean if cell['n'] < 2 else f'{mean} ({form.format(cell["min"])} to {form.format(cell["max"])})'


def table(head: list[str], rows: list[list[str]]) -> list[str]:
    return ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head), *['| ' + ' | '.join(row) + ' |' for row in rows]]


def carried_rows(report: dict[str, Any], limit: int = 3) -> list[list[str]]:
    """Per run, the tool results that cost the most by being carried in: size and carried tokens."""
    rows: list[list[str]] = []
    for run in report['runs']:
        held = cast(dict[str, dict[str, int]], run.get('results_carried') or {})
        for key, size in list(held.items())[:limit]:
            rows.append([run['task'], run['arm'], key, str(size['calls']), f'{size["chars"]:,}',
                         f'{size["tokens_est"]:,}', f'{size["carried_to_first_write"]:,}',
                         f'{size["carried_to_end"]:,}'])
    return rows


def markdown(report: dict[str, Any]) -> str:
    setup, spent = report['setup'], report['spend']
    source = cast(dict[str, Any], setup.get('metaform_source') or {'label': 'not recorded', 'changed_files': '?',
                                                                     'src_sha256': '?'})
    models = sorted({model for row in report['summary'] for model in row['model_resolved']})
    lines = [
        '# Orientation-cost evaluation', '',
        (f'Run {report["started"]} on Claude Code {setup.get("claude_code_version") or "?"}, model `{setup["model"]}` '
         f'(resolved: {", ".join(f"`{m}`" for m in models) or "?"}), k={setup["k"]}, auth `{setup["auth"]}`, '
         f'permission mode `{setup["permission_mode"]}`, node_summary_bytes {setup["node_bytes"] or "default"}. '
         f'Metaform under test: `{source["label"]}` ({source["changed_files"]} files differ from HEAD; '
         f'src/metaform sha256 `{source["src_sha256"][:16]}`), '
         + (f'frozen as commit object `{source["commit_object"][:12]}`' if source.get('commit_object')
            else 'copied before the source was frozen, so it cannot be restored')
         + (', kept as source.tar.gz' if report.get('source_archive') else '') + '. '
         f'Spent ${spent["spent_usd"]:.3f} of a ${spent["cap_usd"]:.2f} cap.'), '',
    ]
    if setup['auth'] == 'login':
        lines += [('Auth `login` runs on this machine\'s own login with the person\'s HOME; only auth `env` gives each '
                   'run a HOME of its own, and is the mode for numbers to be quoted.'), '']
    lines += ['## Repositories and preparation', '']
    rows: list[list[str]] = []
    for name, held in report['repos'].items():
        prep = held['prepared']
        overview = cast(dict[str, Any], prep.get('agents_md') or {})
        made = cast(dict[str, Any], prep.get('map') or {})
        code = cast(dict[str, Any] | None, held.get('code'))
        rows.append([name, f'`{held["commit"][:20]}`',
                     (f'{overview.get("bytes", "?")} bytes by {overview.get("model_resolved") or overview.get("model")}'
                      f', ${overview["cost_usd"]:.3f}' if overview.get('cost_usd') is not None else '–'),
                     f'{made.get("how", "–")}' + (f', ${made["cost_usd"]:.3f}' if made.get('cost_usd') is not None
                                                 else (', cost not known' if made else '')),
                     (f'{code.get("provider")}: {code.get("symbols")} symbols, '
                      f'{cast(dict[str, Any], code.get("linked") or {}).get("nodes", 0)} nodes linked, '
                      f'{code.get("seconds")} s' if code else (held.get('code_error') or 'none')),
                     str(held.get('map_label') or '–')])
    lines += table(['Repository', 'Commit', 'AGENTS.md (arm agents_md)', 'Map (Metaform arms)', 'Code layer',
                    'The Metaform arms ran on'], rows)
    starts = [(name, held['start']) for name, held in report['repos'].items() if held.get('start')]
    if starts:
        lines += ['', ('What an agent checking its work meets before changing anything: the suite\'s collection '
                       'errors, and failures in the test modules that import the files the tasks fix:'), '']
        lines += table(['Repository', 'Collection', 'Collection errors', 'Test modules run', 'Failing at the start'],
                       [[name, start['collection'], ', '.join(start['collection_errors'][:5]) or '0',
                         str(len(start['tests'])), ', '.join(start['failed'][:5]) or '0'] for name, start in starts])
    oracles = [(task, held) for repo in report['repos'].values()
               for task, held in cast(dict[str, dict[str, Any]], repo.get('oracle') or {}).items()]
    if oracles:
        lines += ['', 'Each task\'s oracle Address against the code layer: the Addresses whose code holds the graded file.',
                  '']
        lines += table(['Task', 'Oracle', 'Addresses holding the file', 'Confirmed'],
                       [[task, str(held.get('address') or '–'), ', '.join(held['addresses_holding_file']) or 'none',
                         {True: 'yes', False: 'no', None: '–'}[held.get('confirmed')]] for task, held in oracles])
    surfaces = [(name, held['surface']) for name, held in report['repos'].items() if held.get('surface')]
    if surfaces:
        lines += ['', ('What the Metaform server gives a client before any call (initialize, tools/list, '
                       'resources/list over stdio):'), '']
        lines += table(['Repository', 'Instructions (chars)', 'Tools', 'tools/list bytes', 'Dispatch tools',
                        'Resources'],
                       [[name, str(s['instructions_chars']), str(s['tools']), f'{s["tools_list_bytes"]:,}',
                         str(s['dispatch_tools']), str(s['resources'])] for name, s in surfaces])
    lines += ['', '## Per task and arm', '']
    lines += table(['Task', 'Arm', 'Node', 'Passed', 'Input tokens before first write', 'Turns to first correct edit',
                    'Input tokens to first correct edit', 'Total tokens', 'Cost USD', 'Prompt bytes',
                    'Metaform calls (MCP / CLI)', 'Resource reads', 'Memory reads', 'ToolSearch', 'Denials',
                    'Denials per turn', 'Met start failures', 'Failing tests seen after the fix'],
                   [[row['task'] + (' (control)' if row['control'] else ''),
                     row['arm'] + (f' ({"; ".join(row["map"])})' if row['map'] else ''),
                     ', '.join(row['addresses']) or '–', f'{row["passed"]}/{row["k"]}',
                     shown(row['input_tokens_before_first_write']), shown(row['turns_to_first_correct_edit'], 1),
                     shown(row['input_tokens_before_first_correct_edit']), shown(row['total_tokens']),
                     shown(row['cost_usd'], 3), shown(row['prompt_bytes']),
                     f'{row["metaform_calls"]} / {row["metaform_cli_calls"]}', str(row['resource_reads']),
                     str(row['memory_reads']), str(row['tool_searches']),
                     ', '.join(f'{name} {count}' for name, count in row['denials'].items()) or '0',
                     shown(row['denial_share'], 2),
                     '–' if row['met_start_failures'] is None else f'{row["met_start_failures"]}/{row["k"]}',
                     ', '.join('–' if seen is None else str(seen) for seen in row['failures_seen_after_fix'])]
                    for row in report['summary']])
    lines += ['', '## Context and fresh tokens', '', ('The headline numbers. Context is what the agent\'s window '
              'held at a request (everything it carried in); fresh is what was new to it (uncached input and cache '
              'written), each new token once; read is the prefix carried again. List USD is secondary: caching '
              'discounts re-sending a prefix, never what was said twice.'), '']
    lines += table(['Task', 'Arm', 'Context at first write', 'Context at end', 'Fresh before first write',
                    'Fresh total', 'Read total', 'List USD', 'Claude Code USD'],
                   [[row['task'], row['arm'], shown(row['context_at_first_write']), shown(row['context_at_end']),
                     shown(row['fresh_before_first_write']), shown(row['fresh_tokens']), shown(row['read_tokens']),
                     shown(row['usd_list'], 4), shown(row['cost_usd'], 4)] for row in report['summary']])
    lines += ['', 'Fresh tokens by phase, with list USD in brackets:', '']
    lines += table(['Task', 'Arm', *[phase.capitalize() for phase in PHASES]],
                   [[row['task'], row['arm'], *[f'{shown(row[f"fresh_{phase}"])} (${shown(row[f"usd_{phase}"], 4)})'
                                                for phase in PHASES]] for row in report['summary']])
    doubled = [r for r in report['runs'] if r.get('delivered_chars') is not None]
    if doubled:
        lines += ['', '## Said twice', '', ('Every block (a sentence or line of 30 characters or more) of what Metaform '
                  'delivered that the agent\'s context holds more than once, grouped by where its copies came from. '
                  'Each is a defect to remove at its source: a copy is paid in full when it is sent and carried to '
                  'the end, cached or not. Chars count the extra copies only.'), '']
        lines += table(['Task', 'Arm', 'Delivered chars', 'Blocks said twice', 'Extra chars', 'From'],
                       [[r['task'], r['arm'], f'{r["delivered_chars"]:,}', str(r['duplicate_blocks']),
                         f'{r["duplicate_chars"]:,}',
                         '; '.join(f'{one["from"]}: {one["blocks"]} blocks, {one["chars"]:,} chars'
                                   for one in r['duplicates_by_source'][:4]) or '–'] for r in doubled])
    lines += ['', '## Where the tokens went', '', ('Each main-thread request counted whole in one phase (see Reading '
              'the numbers); other is the rest of the run\'s total, Claude Code\'s own small calls.'), '']
    lines += table(['Task', 'Arm', *[phase.capitalize() for phase in PHASES], 'Total',
                    'Of orientation: requests making only Metaform calls'],
                   [[row['task'], row['arm'], *[shown(row[f'tokens_{phase}']) for phase in PHASES],
                     shown(row['total_tokens']),
                     (f'{shown(row["metaform_only_requests_before_first_write"])} requests, '
                      f'{shown(row["metaform_only_tokens_before_first_write"])} tokens')] for row in report['summary']])
    carried = carried_rows(report)
    if carried:
        lines += ['', ('The tool results that cost most by being carried: each result\'s tokens (about four '
                       'characters to one) times the main-thread requests that carried it in after it came back.'), '']
        lines += table(['Task', 'Arm', 'Result', 'Calls', 'Chars', '≈ Tokens', 'Carried to first write',
                        'Carried to end'], carried)
    if report['paired']:
        lines += ['', '## Against arm none, paired by task and trial', '']
        lines += table(['Task', 'Arm', 'Δ input tokens before first write', 'Δ turns to first correct edit',
                        'Δ total tokens', 'Δ total incl. placement', 'Δ orientation', 'Δ work', 'Δ verification',
                        'Δ bookkeeping'],
                       [[row['task'] + (' (control)' if row['control'] else ''), row['arm'],
                         shown(row['input_tokens_before_first_write'], signed=True),
                         shown(row['turns_to_first_correct_edit'], 1, signed=True),
                         shown(row['total_tokens'], signed=True), shown(row['total_tokens_with_placement'], signed=True),
                         *[shown(row[f'tokens_{phase}'], signed=True)
                           for phase in ('orientation', 'work', 'verification', 'bookkeeping')]]
                        for row in report['paired']])
        lines += ['', 'Per arm, the mean of the per-task differences, with their range across tasks, controls left out:',
                  '']
        lines += table(['Arm', 'Tasks', 'Δ input tokens before first write', 'Δ turns to first correct edit',
                        'Δ total tokens', 'Δ total incl. placement', 'Δ orientation', 'Δ verification',
                        'Δ bookkeeping'],
                       [[row['arm'], str(row['tasks']), ranged(row['input_tokens_before_first_write']),
                         ranged(row['turns_to_first_correct_edit'], 1), ranged(row['total_tokens']),
                         ranged(row['total_tokens_with_placement']), ranged(row['tokens_orientation']),
                         ranged(row['tokens_verification']), ranged(row['tokens_bookkeeping'])]
                        for row in report['paired_arms']])
        lines += ['', 'The same, by the headline numbers, with list USD last:', '']
        lines += table(['Arm', 'Tasks', 'Δ context at end', 'Δ fresh before first write', 'Δ fresh total',
                        'Δ list USD'],
                       [[row['arm'], str(row['tasks']), ranged(row['context_at_end']),
                         ranged(row['fresh_before_first_write']), ranged(row['fresh_tokens']),
                         ranged(row['usd_list'], 4)] for row in report['paired_arms']])
    placed = [r for r in report['runs'] if 'placement_tokens' in r]
    if placed:
        lines += ['', '## Placement for arm metaform_chosen', '']
        lines += table(['Task', 'Trial', 'Chosen', 'Oracle', 'Same', 'Tokens', 'Cost USD', 'Map calls'],
                       [[r['task'], str(r['trial']), r.get('placement_address') or 'none',
                         str(r.get('oracle_address') or '–'),
                         {True: 'yes', False: 'no', None: '–'}[r.get('placement_matches_oracle')],
                         f'{r["placement_tokens"]:,}', f'{r["placement_cost_usd"] or 0:.3f}',
                         str(r['placement_metaform_calls'])] for r in placed])
    warm = [r for r in report['runs'] if r.get('seed')]
    if warm:
        lines += ['', '## Arm metaform_warm: the seed ticket worked first at the same node', '']
        lines += table(['Task', 'Trial', 'Seed', 'Seed passed', 'Seed tokens', 'Seed cost USD', 'Memories written',
                        'Hand-off names a seed memory', 'Memory reads', 'Opened the target before searching'],
                       [[r['task'], str(r['trial']), r['seed']['task'], str(r['seed'].get('passed')),
                         f'{r["seed"].get("total_tokens") or 0:,}', f'{r["seed"].get("cost_usd") or 0:.3f}',
                         str(len(r['seed'].get('memory_names') or [])),
                         'yes' if r.get('prompt_names_seed_memory') else 'no', str(r.get('memory_reads', '–')),
                         {True: 'yes', False: 'no', None: '–'}[r.get('opened_target_before_search')]]
                        for r in warm])
    breached = [r for r in report['runs'] if r.get('isolation_breach')]
    if breached:
        lines += ['', '## Not counted: runs that left files in the person\'s home', '',
                  *[f'- {r["task"]} / {r["arm"]} / {r["trial"]}: {", ".join(r["home_changes"]["unexpected"][:5])}'
                    for r in breached]]
    skipped = [r for r in report['runs'] if 'skipped' in r]
    if skipped:
        lines += ['', '## Not run', '', *[f'- {r["task"]} / {r["arm"]} / {r["trial"]}: {r["skipped"]}' for r in skipped]]
    lines += ['', '## Reading the numbers', '', *NOTES]
    return '\n'.join(lines) + '\n'


NOTES = (
    ('- Input tokens count everything each request carried in (new input, cache written and cache read), summed over '
     'the requests up to and including the one that made the first write.'),
    ('- A write is any tool call after which the workspace\'s git tree differs from the start, recorded by a '
     'PostToolUse hook, so Bash edits count and read-only commands never do; first_write_paths in results.json names '
     'what changed. The first correct edit is the first such tree the grader passes on; – means none did.'),
    "- Turns count the main thread's model requests; subagent requests count toward tokens, not turns.",
    ('- Arm metaform is handed the node the task author chose (an oracle); arm metaform_chosen the node a blind '
     'placement pass chose from the request with only the map, whose tokens and cost are listed apart. Arm agents_md '
     'and an intake are prepared once per repository; their cost and model are listed under preparation. A map '
     'imported from an export was made outside this evaluation and its cost is not known.'),
    ('- Metaform calls count the agent\'s calls of the metaform MCP tools and of the metaform CLI; Denials are the '
     'permission system\'s refusals by tool.'),
    ('- Phases: orientation is every main-thread request up to and including the one that made the first write; '
     'work runs to the first correct edit; after it, a request whose calls are all the ticket\'s steps and memory '
     'writes the hand-off asks for is bookkeeping, one with a shell command that is not Metaform\'s is verification, '
     'the rest closing. Each request counts what it carried in and what it wrote, so a large result read early is '
     'paid again by every later request; the carried table shows by how much.'),
    ('- Met start failures counts runs whose shell output showed a test that fails, or a module that does not collect, '
     'before any change: verification there chases failures that are not the task\'s.'),
    ('- Arm metaform_warm works a seed ticket at the same node in the same folder and home first, then the task: its '
     'memories and its ticket stay, as they would for the next agent there. The seed\'s cost is listed apart, as '
     'AGENTS.md\'s is.'),
    ('- The Metaform arms run on the map the preparation names, with the code layer map code-import reads from '
     'tree-sitter. A map with no sources layer links no code to its nodes, so code search finds symbols and files '
     'but names no Address for them, and an oracle Address is then its task author\'s choice, not the map\'s.'),
    ('- Differences against arm none pair runs of the same task and trial. With k=1 there is one pair per task, and '
     'the range across tasks shows how tasks differ, not run noise.'),
    ('- Fresh tokens are uncached input plus cache written, read tokens the cache read, from each request\'s usage in '
     'Claude Code\'s stream-json (input_tokens, cache_creation_input_tokens with its 5-minute and 1-hour split, '
     'cache_read_input_tokens). Context at a request is all three inputs together. Other holds what the run\'s '
     'modelUsage counts beyond the stream\'s requests.'),
    ('- List USD prices each request at Anthropic\'s list prices (PRICES in the script): a cache read at a tenth of '
     'input, a write at 1.25 times for five minutes and 2 times for an hour; Claude Code USD is its own total.'),
    ('- Said twice counts sentences and lines of the connect instructions, the hand-off prompt, the Metaform tool '
     'descriptions a ToolSearch select loaded (when the surface recorded them) and every Metaform result. The '
     'instructions sit in the system prompt and are counted once.'),
    '- With k this small the numbers show the harness works and where the tokens go, not which arm is better.',
)


# ------------------------------------------------------------------------------------------------------------ main


def neutral_scratch(root: Path) -> Path:
    """A scratch folder no agent context reaches: Claude Code reads CLAUDE.md and AGENTS.md in the folders above the
    one it starts in."""
    root = root.resolve()
    for folder in (root, *root.parents):
        held = [name for name in ('CLAUDE.md', 'CLAUDE.local.md', 'AGENTS.md') if (folder / name).exists()]
        if held:
            raise SystemExit(f'{folder} holds {", ".join(held)}, which every run under {root} would read; '
                             f'choose another --scratch-dir.')
    return Path(tempfile.mkdtemp(prefix='orientation-', dir=root))


def parse(argv: list[str] | None) -> tuple[argparse.Namespace, Options]:
    parser = argparse.ArgumentParser(prog='python -m scripts.orientation_eval',
                                     description=(__doc__ or '').split('\n\n')[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tasks', type=Path, default=TASKS, help='the task set (default: %(default)s)')
    parser.add_argument('--task', action='append', default=[], help='run only this task id; repeatable')
    parser.add_argument('--arm', action='append', choices=ARMS, default=[],
                        help=f'run only this arm; repeatable (default: {", ".join(DEFAULT_ARMS)})')
    parser.add_argument('-k', type=int, default=1, help='runs per task and arm (default: %(default)s)')
    parser.add_argument('--model', default='haiku', help='the agents\' model (default: %(default)s)')
    parser.add_argument('--spend-cap-usd', type=float, default=2.0, help='the most this invocation may spend, '
                        'preparation included (default: %(default)s)')
    parser.add_argument('--run-budget-usd', type=float, default=0.5, help='the most one run may spend '
                        '(default: %(default)s)')
    parser.add_argument('--placement-budget-usd', type=float, default=0.2, help='the most one placement pass may '
                        'spend (default: %(default)s)')
    parser.add_argument('--min-run-usd', type=float, default=0.05, help='start no call with less than this left '
                        '(default: %(default)s)')
    parser.add_argument('--max-turns', type=int, default=40, help='turns one run may take (default: %(default)s)')
    parser.add_argument('--timeout', type=float, default=600, help='seconds one run may take (default: %(default)s)')
    parser.add_argument('--auth', choices=('env', 'login'), default='env', help='env: an empty HOME per run and a '
                        'credential from the environment; login: this machine\'s login, user configuration turned '
                        'off by flags (default: %(default)s)')
    parser.add_argument('--permission-mode', default='acceptEdits', help='(default: %(default)s)')
    parser.add_argument('--node-bytes', type=int, help='the map setting node_summary_bytes for the Metaform arms')
    parser.add_argument('--intake-model', help='the model of an intake run (default: --model)')
    parser.add_argument('--intake-budget-usd', type=float, default=1.0, help='(default: %(default)s)')
    parser.add_argument('--intake-max-turns', type=int, default=400, help='(default: %(default)s)')
    parser.add_argument('--intake-timeout', type=float, default=3600, help='seconds (default: %(default)s)')
    parser.add_argument('--allow-dirty', action='store_true', help='evaluate the working tree although it differs '
                        'from HEAD; it is recorded as <commit>-dirty with a sha256 of src/metaform')
    parser.add_argument('--allow-dirty-tests', action='store_true', help='evaluate a tree that holds untracked test '
                        'modules (test_*.py, *_test.py, conftest.py)')
    parser.add_argument('--no-code-layer', action='store_true', help='run the Metaform arms on the map alone, without '
                        'the code layer map code-import reads from tree-sitter')
    parser.add_argument('--remeasure', type=Path, help='measure a finished run\'s kept transcripts again (a results '
                        'folder holding results.json) and rewrite its results; spends nothing')
    parser.add_argument('--grep-rank', type=int, default=5, help='a task fails its check when a grep of its request '
                        'ranks the target file this high or higher (default: %(default)s)')
    parser.add_argument('--probe', help='run this request instead of the task set, ungraded, to see what an arm '
                        'can do (for example read a resource or run a command)')
    parser.add_argument('--probe-repo', default='metaform', help='(default: %(default)s)')
    parser.add_argument('--probe-address', help='the node the probe\'s ticket is at, for arm metaform')
    parser.add_argument('--out', type=Path, default=OUT, help='the results folder (default: %(default)s)')
    parser.add_argument('--scratch-dir', type=Path, default=Path('/tmp') if Path('/tmp').is_dir() else None,
                        help='where the run folders go; no folder above it may hold CLAUDE.md or AGENTS.md '
                        '(default: %(default)s)')
    parser.add_argument('--dry-run', action='store_true', help='prepare and check everything, spend nothing')
    parser.add_argument('--keep', action='store_true', help='keep the run folders')
    args = parser.parse_args(argv)
    options = Options(model=args.model, k=args.k, arms=tuple(args.arm) or DEFAULT_ARMS, spend_cap=args.spend_cap_usd,
                      run_budget=args.run_budget_usd, min_run=args.min_run_usd, max_turns=args.max_turns,
                      timeout=args.timeout, auth=args.auth, permission_mode=args.permission_mode,
                      node_bytes=args.node_bytes, intake_model=args.intake_model or args.model,
                      intake_budget=args.intake_budget_usd, intake_max_turns=args.intake_max_turns,
                      intake_timeout=args.intake_timeout, placement_budget=args.placement_budget_usd,
                      allow_dirty=args.allow_dirty, allow_dirty_tests=args.allow_dirty_tests,
                      code_layer=not args.no_code_layer, grep_rank=args.grep_rank, dry_run=args.dry_run, keep=args.keep)
    return args, options


def remeasure(folder: Path) -> int:
    """A finished run measured again from its kept stream-json, with the first write and first correct edit it
    recorded (the workspaces are gone, so the trees are not graded again): the decomposition, the reach and the
    summaries are rewritten."""
    report = cast(dict[str, Any], json.loads((folder / 'results.json').read_text(encoding='utf-8')))
    named = Path(str(report['setup'].get('tasks_file') or TASKS))
    plan = json.loads((named if named.exists() else TASKS).read_text(encoding='utf-8'))
    files = {str(task['id']): str(task['grade'].get('file') or '') for task in plan['tasks']}
    for run in cast(list[dict[str, Any]], report['runs']):
        stream = folder / f'{run["task"]}.{run["arm"]}.{run["trial"]}.jsonl'
        if 'passed' not in run or not stream.exists():
            continue
        events = [cast(dict[str, Any], json.loads(line)) for line in stream.read_text(encoding='utf-8').splitlines()
                  if line.strip()]
        _, _, calls, turns = calls_and_usage(events)
        reached = reach(calls, events)
        run.update(reached)
        run.update(spent_on(events, run.get('turns_before_first_write'), run.get('turns_to_first_correct_edit'),
                            turns, reached))
        run.update(first_search_and_target(calls, files.get(str(run['task']), '')))
        run['failures_seen_after_fix'] = failures_seen(events, run.get('turns_to_first_correct_edit'))
        if run['arm'] in METAFORM_ARMS:
            surface = cast(dict[str, Any], cast(dict[str, Any], report['repos'].get(run.get('repo')) or {}).get(
                'surface') or {})
            told = folder / f'{run["task"]}.{run["arm"]}.{run["trial"]}.prompt.txt'
            run.update(duplicates(delivered(events, told.read_text(encoding='utf-8') if told.exists() else None,
                                            surface.get('instructions'), surface.get('tool_descriptions'))))
        if 'placement_tokens' in run and run.get('total_tokens') is not None:
            run['total_tokens_with_placement'] = run['total_tokens'] + run['placement_tokens']
        changes = cast(dict[str, list[str]] | None, run.get('home_changes'))
        if changes is not None:
            # Kept to what is the run's own by its folder's name or its session, as home_changes now finds them.
            slug = folder_slug(Path(str(report['setup']['scratch'])) / f'{run["task"]}.{run["arm"]}.{run["trial"]}'
                               / 'repo')
            session = str(run.get('session_id') or '')
            left: dict[str, list[str]] = {'expected': [], 'unexpected': []}
            for shown in (*changes['expected'], *changes['unexpected']):
                parent, _, name = shown.removeprefix('~/').rpartition('/')
                if not parent:
                    left['unexpected'].append(shown)
                elif (session and session in name) or name == slug or name.startswith(f'{slug}-'):
                    left['expected' if leftover(Path.home(), parent, name, session) else 'unexpected'].append(shown)
            run['home_changes'] = left
            run['isolation_breach'] = bool(left['unexpected'])
        run.setdefault('map', 'map without code layer' if run['arm'] in METAFORM_ARMS else None)
        if run['map'] is None:
            del run['map']
    for held in cast(dict[str, dict[str, Any]], report['repos']).values():
        held.setdefault('map_label', 'map without code layer')
        code = cast(dict[str, Any], held.get('code') or {})
        if not cast(dict[str, Any], code.get('linked') or {}).get('nodes'):
            for oracle in cast(dict[str, dict[str, Any]], held.get('oracle') or {}).values():
                oracle['confirmed'] = None  # no code is linked to any node, so the layer cannot confirm an Address
    report['summary'] = summarise(report['runs'])
    report['paired'], report['paired_arms'] = paired(report['runs'])
    report['remeasured'] = datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')
    (folder / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (folder / 'results.md').write_text(markdown(report), encoding='utf-8')
    print(f'Results: {folder / "results.md"}')
    return 0


def main(argv: list[str] | None = None) -> int:
    args, options = parse(argv)
    if args.remeasure:
        return remeasure(args.remeasure)
    plan = json.loads(args.tasks.read_text(encoding='utf-8'))
    tasks: list[dict[str, Any]]
    if args.probe:
        tasks = [{'id': 'probe', 'repo': args.probe_repo, 'kind': 'probe', 'address': args.probe_address,
                  'request': args.probe, 'grade': {'type': 'none', 'file': ''}}]
    else:
        tasks = [task for task in plan['tasks'] if not args.task or task['id'] in args.task]
        unknown = set(args.task) - {task['id'] for task in plan['tasks']}
        if unknown:
            print(f'No such task: {", ".join(sorted(unknown))}', file=sys.stderr)
            return 2
    if not options.dry_run and shutil.which('claude') is None:
        print('claude is not on PATH.', file=sys.stderr)
        return 2
    if not options.dry_run and options.auth == 'env' and not any(name in os.environ for name in CREDENTIALS[:3]):
        print('--auth env needs ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN (claude setup-token) in the environment; '
              'or use --auth login.', file=sys.stderr)
        return 2
    started = datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')
    scratch = neutral_scratch(args.scratch_dir or Path(tempfile.gettempdir()))
    log = args.out / started if not options.dry_run else scratch / 'log'
    log.mkdir(parents=True, exist_ok=True)
    cache = args.out / 'cache'
    spend = Spend(options.spend_cap)
    records: list[dict[str, Any]] = []
    repos: dict[str, Prepared] = {}
    broken: list[str] = []
    declared = cast(dict[str, dict[str, Any]], plan['repos'])
    nothing: dict[str, Any] = {'exclude': []}
    local = next((repo for repo in declared.values() if is_self(repo)), nothing)
    by_id = {str(task['id']): task for task in plan['tasks']}
    try:
        source = take_worktree([*local.get('exclude', []), *CONTEXT_FILES], scratch / 'metaform-source',
                               options.allow_dirty, options.allow_dirty_tests)
        print(f'metaform source: {source.label} ({len(source.changed)} files differ from HEAD; '
              f'src/metaform sha256 {source.digest[:16]}; frozen as {source.frozen[:12]})')
        if not options.dry_run:
            archive = log / 'source.tar.gz'
            subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=tar.gz', f'--output={archive}',
                            source.frozen], check=True)
        code_error = None
        if options.code_layer and METAFORM_ARMS & set(options.arms):
            provider, said = code_provider(cache)
            if provider is None:
                code_error = said
                print(f'code layer: none, {said}; the Metaform arms run on a map without one')
            else:
                EXTRA_PATH[:] = [provider]
                print(f'code layer provider: {said}')
        for name in sorted({str(task['repo']) for task in tasks}):
            repo = declared[name]
            base, commit = snapshot(name, repo, scratch, source)
            prepared = repos[name] = Prepared(repo, base, commit)
            prepared.code_error = code_error
            print(f'{name} at {commit}')
            for task in (task for task in tasks if task['repo'] == name and task['kind'] != 'probe'):
                problem = check_task(task, repo, base, scratch, options.grep_rank)
                print(f'  task {task["id"]}: {problem or "proven"}')
                if problem:
                    broken.append(task['id'])
            mine = [task for task in tasks if task['repo'] == name and task['kind'] != 'probe']
            prepared.start = start_failures(base, repo, mine, scratch)
            start = prepared.start
            print(f'  start state: collection {start["collection"]!r}, {len(start["collection_errors"])} collection '
                  f'errors; {len(start["tests"])} related test modules, {len(start["failed"])} failing '
                  f'({start["tests_summary"]!r}, {start["seconds"]} s)')
            try:
                if 'agents_md' in options.arms:
                    prepare_agents_md(name, prepared, plan, options, spend, cache, scratch, log, started, source)
                if METAFORM_ARMS & set(options.arms):
                    prepare_map(name, prepared, options, spend, cache, scratch, log, started, source)
                    if prepared.surface:
                        surface = prepared.surface
                        print(f'  server: {surface["instructions_chars"]} characters of instructions, '
                              f'{surface["tools"]} tools in {surface["tools_list_bytes"]:,} bytes '
                              f'({surface["dispatch_tools"]} dispatch), {surface["resources"]} resources')
                        code = prepared.code or {}
                        print(f'  code layer: {code.get("provider") or "none"}, {code.get("symbols", 0)} symbols, '
                              f'{cast(dict[str, Any], code.get("linked") or {}).get("nodes", 0)} nodes linked, '
                              f'{code.get("seconds", 0)} s: {prepared.map_label}')
                        for task_id, problem in check_on_map(prepared, mine, source).items():
                            print(f'  task {task_id}: {problem}')
                            broken.append(task_id)
                        for task_id, held in prepared.oracle.items():
                            if held.get('address'):
                                print(f'  task {task_id}: oracle {held["address"]}, code layer holds the file at '
                                      f'{", ".join(held["addresses_holding_file"]) or "no Address"}')
            except Skip as skip:
                print(f'  preparation: {skip}')
        for trial in range(1, options.k + 1):
            for task in tasks:
                for arm in options.arms:
                    try:
                        if task['id'] in broken:
                            raise Skip('the task failed its check')
                        record = one_run(task, arm, trial, repos[task['repo']], plan, options, spend, scratch, log,
                                         source, by_id)
                    except Skip as skip:
                        record = {'task': task['id'], 'arm': arm, 'trial': trial, 'skipped': str(skip)}
                    record['oracle_address'] = task.get('address')
                    records.append(record)
                    print('  ' + json.dumps({key: record.get(key) for key in (
                        'task', 'arm', 'trial', 'address', 'passed', 'turns_to_first_correct_edit',
                        'input_tokens_before_first_write', 'total_tokens', 'cost_usd', 'prompt_bytes',
                        'metaform_calls', 'resource_reads', 'memory_reads', 'tokens_orientation',
                        'tokens_verification', 'tokens_bookkeeping', 'met_start_failures', 'isolation_breach',
                        'denials', 'planned_budget_usd', 'skipped', 'ended')
                        if record.get(key) not in (None, [], {})}))
    finally:
        if not options.keep:
            shutil.rmtree(scratch, ignore_errors=True)
    if options.dry_run:
        print('Dry run: nothing spent.' + (f' Broken tasks: {broken}' if broken else '')
              + (f' Run folders kept in {scratch}.' if options.keep else ''))
        return 1 if broken else 0
    version = next((r.get('claude_code_version') for r in records if r.get('claude_code_version')), None)
    pairs, pair_arms = paired(records)
    report = {
        'started': started,
        'setup': {'model': options.model, 'k': options.k, 'arms': list(options.arms), 'auth': options.auth,
                  'node_bytes': options.node_bytes, 'max_turns': options.max_turns, 'run_budget_usd': options.run_budget,
                  'permission_mode': options.permission_mode, 'claude_code_version': version,
                  'tasks_file': str(args.tasks), 'probe': args.probe, 'metaform_source': source.record(),
                  'scratch': str(scratch)},
        'repos': {name: {'commit': held.commit, 'source': held.repo.get('url') or 'this repository',
                         'prepared': held.prep, 'surface': held.surface, 'surface_error': held.surface_error,
                         'agents_md': str(held.agents_md) if held.agents_md else None, 'code': held.code,
                         'code_error': held.code_error, 'map_label': held.map_label, 'oracle': held.oracle,
                         'start': held.start}
                  for name, held in repos.items()},
        'source_archive': 'source.tar.gz',
        'spend': {'cap_usd': options.spend_cap, 'spent_usd': round(spend.spent, 4), 'calls': spend.calls},
        'summary': summarise(records),
        'paired': pairs,
        'paired_arms': pair_arms,
        'runs': records,
    }
    (log / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (log / 'results.md').write_text(markdown(report), encoding='utf-8')
    print(f'Results: {log / "results.md"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
