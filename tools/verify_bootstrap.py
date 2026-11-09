"""Check preserved evidence, portable links and embedded current contracts.

Ported on 2026-11-08 from the original `~/topogee/tools/verify_bootstrap.py`
(kept unchanged in `context/topogee-repo/tools/`) for this folder's layout:

- The preserved-source register and the files it hashes now live under
  `context/topogee-repo/`, at their original repository paths.
- Documents in `metaform/` still name repository files such as `DECISIONS.md`
  by their old paths. A link that resolves under `context/topogee-repo/` at the
  same relative path counts as relocated, not broken.
- `context/` is read-only evidence: every file there must still match the
  checksum recorded in `MANIFEST.sha256` at preparation time.
"""
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / 'context' / 'topogee-repo'


def check_register(errors):
    manifest = json.loads((REPO / 'source-register.json').read_text())
    for entry in manifest['sources']:
        candidates = [REPO / entry['path'], ROOT / entry['path']]
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            errors.append('Missing preserved source: ' + entry['path'])
        elif sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            errors.append('Changed preserved source: ' + entry['path'])
    return len(manifest['sources'])


def check_context_unchanged(errors):
    count = 0
    for line in (ROOT / 'MANIFEST.sha256').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.lstrip('*')
        if not name.startswith('./context/'):
            continue
        count += 1
        path = ROOT / name
        if not path.is_file():
            errors.append('Missing context file: ' + name)
        elif sha256(path.read_bytes()).hexdigest() != digest:
            errors.append('Changed context file: ' + name)
    return count


def check_links(errors):
    relocated = 0
    for path in [*ROOT.glob('*.md'), *ROOT.glob('metaform/*.md')]:
        text = path.read_text()
        for raw in re.findall(r'\]\(([^\n]+?)\)', text):
            target = raw.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                continue
            target = target.split('#', 1)[0]
            if target.startswith('/'):
                errors.append(f'{path.relative_to(ROOT)}: nonportable link {target}')
                continue
            if (path.parent / target).exists():
                continue
            # The same link, read as if the file still sat in the original repository.
            mirror = (REPO / path.parent.relative_to(ROOT) / target).resolve()
            if mirror.exists() and mirror.is_relative_to(REPO.resolve()):
                relocated += 1
                continue
            errors.append(f'{path.relative_to(ROOT)}: broken link {target}')
    return relocated


def check_appendices(errors):
    schema = json.loads((ROOT / 'metaform/metaform.schema.json').read_text())
    doc = (ROOT / 'metaform/SPECIFICATION.md').read_text()
    blocks = [json.loads(block) for block in re.findall(r'```json\n(.*?)\n```', doc, re.S)]
    if schema not in blocks:
        errors.append('Specification appendix does not contain the exact current schema')
    registry = json.loads((ROOT / 'metaform/mcp-tools.proposed.json').read_text())
    if len(registry['tools']) != 1:
        errors.append('The current Metaform contract must declare exactly one tool')
    documented_tools = [block for block in blocks if 'name' in block and 'inputSchema' in block]

    def localize_refs(value):
        if isinstance(value, dict):
            return {key: (item.replace('metaform.schema.json#/', '#/', 1)
                          if key == '$ref' and item.startswith('metaform.schema.json#/')
                          else localize_refs(item)) for key, item in value.items()}
        if isinstance(value, list):
            return [localize_refs(item) for item in value]
        return value

    for index, tool in enumerate(documented_tools):
        tool = localize_refs(tool)
        for kind in ('inputSchema', 'outputSchema'):
            if kind in tool:
                tool[kind].setdefault('$defs', {}).update(schema['$defs'])
        documented_tools[index] = tool
    if documented_tools != registry['tools']:
        errors.append('Specification tool appendix differs from the current single-tool registry')
    skill = (ROOT / 'metaform/SKILL.proposed.md').read_text()
    if skill not in doc:
        errors.append('Specification appendix does not contain the current proposed skill')


def check_config(errors):
    config = tomllib.loads((ROOT / '.codex/config.toml').read_text())
    if config.get('mcp_servers', {}).get('boat-docs', {}).get('url') != 'https://docs.boat.dev/mcp':
        errors.append('Boat docs MCP URL differs from the owner request')
    servers = json.loads((ROOT / '.mcp.json').read_text()).get('mcpServers', {})
    if 'metaform' not in servers:
        errors.append('.mcp.json does not declare the metaform server')
    for required in ('START_HERE.md', 'PROJECT_CONTEXT.md', 'OWNER_REVIEW_SPEC.md',
                     'CLAUDE.md', 'TASTE.md', 'EXPECTATIONS.md',
                     'metaform/requirements-dev.txt', '.github/workflows/validate.yml',
                     'metaform/Intake.md', 'metaform/Intake.xml', 'metaform/intake.mmd',
                     'metaform/docs/mcp-query-source.md'):
        if not (ROOT / required).is_file():
            errors.append('Missing bootstrap file: ' + required)


def main():
    errors = []
    sources = check_register(errors)
    context = check_context_unchanged(errors)
    relocated = check_links(errors)
    check_appendices(errors)
    check_config(errors)
    if errors:
        print('FAIL:\n' + '\n'.join(errors))
        return 1
    print(f'PASS: {sources} preserved source hashes; {context} context files unchanged; '
          f'portable links ({relocated} resolved under context/topogee-repo/); '
          'exact schema/tool/skill appendices; project intake files; MCP configuration.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
