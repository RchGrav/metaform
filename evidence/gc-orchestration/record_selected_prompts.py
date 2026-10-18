"""Reproduce isolated selected-source migration and actual MCP role-resource receipt evidence.

Run from the candidate checkout with .venv/bin/python evidence/gc-orchestration/record_selected_prompts.py.
It creates a temporary Metaform home and project, never reads the user's selected prompt store, and records
the prompt source hashes so this evidence can be matched to a subsequently named implementation candidate.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def main() -> None:
    repository = Path(__file__).resolve().parents[2]
    destination = Path(__file__).with_name('selected-prompt-versions.json')
    with tempfile.TemporaryDirectory(prefix='metaform-selected-evidence-') as temporary:
        root = Path(temporary)
        os.environ['METAFORM_HOME'] = str(root / 'home')
        for key in ('METAFORM_SESSION', 'METAFORM_ROLE', 'METAFORM_WORK', 'METAFORM_AUTHORED_ROLE'):
            os.environ.pop(key, None)
        project = root / 'project'
        project.mkdir()

        def command(*words: str) -> None:
            subprocess.run([sys.executable, '-m', 'metaform', *words], cwd=project, check=True,
                           capture_output=True, text=True)

        command('add', 'project', 'prompt-evidence', str(project))
        command('enable', 'orchestration')
        command('enable', 'dispatch')
        from metaform import module, prompt_files, skills
        from metaform.data import prompts
        from metaform.modules.mcp.server import read_resource_text

        module.refresh_modules()
        updates = prompt_files.prompt_updates()
        migrations = []
        for name, update in updates.items():
            owner, colon, component = name.partition(':')
            if owner == 'skill':
                current, format_ = skills.procedure(component), 'text'
            elif not colon:
                source = prompt_files.shipped('skills', name)
                assert source is not None
                current, format_ = prompt_files.rendered(source), 'text'
            else:
                source = prompt_files.shipped(owner, component)
                assert source is not None
                current, format_ = prompt_files.plain(source), 'xml'
            baseline = current
            for edit in reversed(update['edits']):
                assert baseline.count(edit['new']) == 1, (name, edit)
                baseline = baseline.replace(edit['new'], edit['old'], 1)
            register = f'User-authored fixture register retained for {name}.'
            before = baseline + '\n\n' + register
            declared = re.findall(r'<([\w.-]+)\s*/>', baseline)
            original = prompts.shipped(name, format_, prompt_files.encode(baseline, declared)
                                       if format_ == 'xml' else baseline)
            selected = prompts.save_prompt(name, prompt_files.encode(before, declared)
                                            if format_ == 'xml' else before, format=format_)
            resolved = prompt_files.resolve_text(name, current) if format_ == 'text' else prompt_files.resolve(name)
            actual = prompts.prompt_version(name)
            assert actual.number == 3 and actual.parent_id == selected.version_id
            assert actual.prompt_id == original.prompt_id == selected.prompt_id
            assert register in resolved['text']
            migrations.append({'name': name, 'format': format_, 'source': update['source'],
                'source_component': update.get('source_component', name),
                'prompt_id': actual.prompt_id, 'shipped_before_version_id': original.version_id,
                'selected_before_version_id': selected.version_id, 'selected_before_number': selected.number,
                'selected_before_text': selected.text, 'actual_version_id': actual.version_id,
                'actual_number': actual.number, 'actual_parent_id': actual.parent_id,
                'rendered_text': resolved['text'], 'rendered_fingerprint': resolved['rendered_fingerprint'],
                'user_register_preserved': True, 'migration': prompts.prompt_merges(name)[0]})

        def verb(identifier: str, name: str, **nouns):
            owner = next(one for one in module.surface(project) if one.id == identifier)
            declared = next(one for one in owner.verbs if one.name == name)
            return module.call(declared.run, module.context(identifier, project, project='prompt-evidence', nouns=nouns))

        native = []
        for definition in verb('agents', 'roles')['authored']:
            if definition['provider'] != 'orchestration' or definition['role'].startswith('bmad.'):
                continue
            session = f'evidence-{definition["role"]}'
            resolved = module.resolve_agent_role(project, definition['role'], project='prompt-evidence')
            assert not resolved['problems']
            response = asyncio.run(read_resource_text(project, definition['uri'], session=session))
            assert response is not None
            receipts = verb('agents', 'receipts', session=session)
            assert {one['name'] for one in receipts['receipts']} == {one['name'] for one in resolved['components']}
            native.append({**definition, 'session': session, 'resource_mime': response[1],
                'resource_text': response[0], 'resource_fingerprint': digest(response[0]),
                'context_epoch': receipts['epoch'], 'components': [
                    {key: one[key] for key in ('name', 'actual_version_id', 'selected_version_id',
                                              'rendered_fingerprint', 'number', 'origin')}
                    for one in resolved['components']],
                'receipts': [{key: one[key] for key in ('session_id', 'epoch', 'name', 'fingerprint',
                    'actual_version_id', 'selected_version_id', 'channel', 'at')} for one in receipts['receipts']]})
        assert len(native) == 17
        source_files = {update['source'] for update in updates.values()} | {
            'src/metaform/modules/orchestration/resources/prompts.xml',
            'src/metaform/resources/prompt_updates.json',
            'src/metaform/prompt_files.py', 'src/metaform/skills.py', 'src/metaform/data/prompts.py'}
        output = {'recorded_at': datetime.now(UTC).isoformat(),
            'base_checkout': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip(),
            'reviewed_baseline': next(iter(updates.values()))['reviewed_baseline'],
            'source_baseline': next(iter(updates.values()))['baseline'],
            'scope': 'Isolated fixtures using the current source. No live user prompt store was inspected or changed.',
            'selection_fixture': 'Each requested source anchor is reversed to its documented prior text, then a '
                'distinct user register is appended as selected version 2. The exact merge appends version 3.',
            'delivery_boundary': 'Native role resources were actually returned by the MCP resource handler and '
                'acknowledged in its shared ledger. ACP turn handoff and integrated ownership evidence are recorded separately.',
            'source_sha256': {path: hashlib.sha256((repository / path).read_bytes()).hexdigest()
                              for path in sorted(source_files)},
            'migrations': migrations, 'native_roles': native,
            'summary': {'selected_migrations': len(migrations), 'native_role_resources': len(native),
                        'identity_and_register_preserved': True, 'user_home_touched': False}}
        destination.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'output': str(destination), **output['summary']}))


if __name__ == '__main__':
    main()
