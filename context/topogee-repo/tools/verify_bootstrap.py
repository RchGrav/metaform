"""Check portable docs, preserved source bytes and embedded current contracts."""
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    manifest = json.loads((ROOT / 'source-register.json').read_text())
    for entry in manifest['sources']:
        path = ROOT / entry['path']
        if not path.is_file():
            errors.append('Missing preserved source: ' + entry['path'])
        elif sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            errors.append('Changed preserved source: ' + entry['path'])

    # Historical references keep their original bytes/links. Current root docs
    # must be portable and cannot depend on the assistant's old workspace.
    for path in [*ROOT.glob('*.md'), *ROOT.glob('metaform/*.md')]:
        text = path.read_text()
        for raw in re.findall(r'\]\(([^\n]+?)\)', text):
            target = raw.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                continue
            target = target.split('#', 1)[0]
            if target.startswith('/') or not (path.parent / target).exists():
                errors.append(f'{path.relative_to(ROOT)}: nonportable or broken link {target}')

    schema = json.loads((ROOT / 'metaform/metaform.schema.json').read_text())
    doc = (ROOT / 'metaform/SPECIFICATION.md').read_text()
    blocks = [json.loads(block) for block in re.findall(r'```json\n(.*?)\n```', doc, re.S)]
    if schema not in blocks:
        errors.append('Specification appendix does not contain the exact current schema')
    registry = json.loads((ROOT / 'metaform/mcp-tools.proposed.json').read_text())
    if len(registry['tools']) != 1:
        errors.append('The current Metaform contract must declare exactly one tool')
    documented_tools = [block for block in blocks
                        if 'name' in block and 'inputSchema' in block]

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
    config = tomllib.loads((ROOT / '.codex/config.toml').read_text())
    if config.get('mcp_servers', {}).get('boat-docs', {}).get('url') != 'https://docs.boat.dev/mcp':
        errors.append('Boat docs MCP URL differs from the owner request')
    for required in ('README.md', 'AGENTS.md', 'DECISIONS.md', 'DEVELOPMENT.md',
                     'metaform/requirements-dev.txt', '.github/workflows/validate.yml',
                     'metaform/Intake.xml', 'metaform/intake.mmd', 'metaform/docs/mcp-query-source.md'):
        if not (ROOT / required).is_file():
            errors.append('Missing bootstrap file: ' + required)
    if errors:
        print('FAIL:\n' + '\n'.join(errors))
        return 1
    print(f"PASS: {len(manifest['sources'])} preserved source hashes; portable current links; exact schema/tool/skill appendices; project intake files; MCP docs configuration.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
