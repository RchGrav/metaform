"""Prompt files: every prompt an agent reads is authored in an XML file, addressed by name, and never in Python."""
from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from metaform.prompt_files import text as prompt_text

pytestmark = pytest.mark.kind('fixture')

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'metaform'


def prompt_files() -> list[Path]:
    return sorted(SOURCE.glob('**/resources/prompts.xml'))


def prompt(path: Path, name: str) -> ET.Element:
    found = ET.parse(path).getroot().find(name)
    assert found is not None, f'{path} has no prompt {name}'
    return found


@pytest.mark.req('MCP-031')
def test_the_chassis_and_the_modules_that_prompt_agents_keep_their_prompts_in_xml():
    held = {path.relative_to(SOURCE).as_posix() for path in prompt_files()}
    assert {'resources/prompts.xml', 'modules/intake/resources/prompts.xml', 'modules/map/resources/prompts.xml',
            'modules/web/resources/prompts.xml', 'modules/mcp/resources/prompts.xml'} <= held


def literals(path: Path) -> set[str]:
    """Every string a Python file writes, with implicitly joined pieces as one string, as Python reads them."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.add(' '.join(node.value.split()))
    return found


@pytest.mark.req('MCP-031')
def test_no_prompt_text_is_written_in_python():
    python = {path: literals(path) for path in SOURCE.glob('**/*.py') if 'tests' not in path.parts}
    for path in prompt_files():
        for element in ET.parse(path).getroot():
            # Inline fills belong to the same line: a command prefix alone is not duplicated prompt prose.
            body = (element.text or '') + ''.join(ET.tostring(child, encoding='unicode') for child in element)
            for line in body.splitlines():
                line = ' '.join(line.split())
                if len(line) < 25:
                    continue
                holders = [str(source.relative_to(SOURCE)) for source, strings in python.items()
                           if any(line in string for string in strings)]
                assert not holders, f'{path.relative_to(SOURCE)} {element.tag}: "{line}" is in {holders}'


@pytest.mark.req('MCP-031')
def test_the_full_instructions_are_the_instructions_prompt_with_the_surfaced_modules_listed(run, home, tmp_path):
    from metaform.module import module_instructions
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    run('set', '--connect-instructions=full', cwd=folder)
    run('set', '--no-tasks', cwd=folder)  # the task lines are tested below
    element = prompt(SOURCE / 'resources' / 'prompts.xml', 'instructions')
    on = [line.split()[0] for line in run('list', 'modules', cwd=folder).stdout.splitlines() if line.split()[1] == 'on']
    def line(module):  # include state notices, and allow modules with no instructions prompt, MCP-009
        own = (prompt_text(SOURCE / 'modules' / module, 'instructions') or '').strip()
        served = module_instructions(folder, module)
        assert not own or (served is not None and own in served)
        return served
    listed = '\n'.join(filter(None, (line(module) for module in sorted(on))))  # an empty one sends nothing
    assert [child.tag for child in element] == ['surface', 'modules']
    opening = prompt(SOURCE / 'resources' / 'prompts.xml', 'surface_cli').text.strip()  # no server claimed on the CLI
    expected = (element.text or '') + opening + (element[0].tail or '') + listed + (element[1].tail or '')
    assert run('help', 'agents', cwd=folder).stdout.strip() == expected.strip()


INTAKE = (('element', 'code.timer.kitchen', 'role=DE', 'name_length=2', 'name=kitchen timer'),
          ('element', 'code.alarm.audible', 'role=SE', 'name_length=2', 'name=alarm'),
          ('purpose', 'code.timer.kitchen', '["code.alarm.audible"]', 'purpose=Get attention.', 'ef=Rings.',
           'ifd=receives'))


@pytest.mark.req('MCP-029')
@pytest.mark.req('MCP-031')
def test_the_compact_instructions_fit_what_claude_code_keeps_in_every_intake_state(run, home, tmp_path):
    """The MCP startup directive and links fit the host's 2,048-character limit in every intake state. The CLI
    guide serves the full module and state instructions separately, with every shipped module on."""
    from metaform.modules.mcp.server import connect_instructions
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    for module in [line.split()[0] for line in run('list', 'modules', cwd=folder).stdout.splitlines()
                   if line.split()[1] != 'on']:
        run('enable', module, cwd=folder)
    more = prompt(SOURCE / 'resources' / 'prompts.xml', 'more').text.strip()
    def served():
        startup = connect_instructions(folder)
        assert len(startup) <= 2048, len(startup)
        assert startup.splitlines()[0] == prompt_text(SOURCE / 'modules' / 'mcp', 'connect_directive')
        assert {'metaform://rules', 'metaform://metaform', 'metaform://memory', 'metaform://modules',
                'metaform://task/person', 'metaform://proj'} <= set(startup.splitlines())
        text = run('help', 'agents', cwd=folder).stdout
        assert more in text
        return text
    assert prompt_text(SOURCE / 'modules' / 'intake', 'no_intake') in served()
    run('intake', 'start', cwd=folder)
    served()
    for step in INTAKE:
        run('intake', *step, cwd=folder)
    run('intake', 'finish', cwd=folder)
    served()


@pytest.mark.req('MCP-029')
def test_a_module_s_full_instructions_are_read_on_their_own(run, home, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    run('set', '--no-tasks', cwd=folder)
    own = prompt(SOURCE / 'modules' / 'map' / 'resources' / 'prompts.xml', 'instructions').text.strip()
    assert run('help', 'agents', 'map', cwd=folder).stdout.strip() == own
    assert run('instructions', 'map', cwd=folder).stdout.strip() == own
    assert own not in run('help', 'agents', cwd=folder).stdout


@pytest.mark.req('MCP-031')
@pytest.mark.req('MAP-048')
def test_the_kanban_lines_are_served_only_while_tasks_is_on(run, home, tmp_path):
    """Agents assign and track work via Metaform like a kanban; a project that keeps its own board
    turns it off, and then the instructions say nothing of it. On by default. the lines are read on
    demand with the map module's full instructions, never in what every agent is handed at connect, MCP-037."""
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    lines = prompt(SOURCE / 'modules' / 'map' / 'resources' / 'prompts.xml', 'tasks').text.strip()
    assert lines not in run('help', 'agents', cwd=folder).stdout  # no nodes to link work to before an intake
    run('intake', 'start', cwd=folder)
    for step in INTAKE:
        run('intake', *step, cwd=folder)
    run('intake', 'finish', cwd=folder)
    assert lines not in run('help', 'agents', cwd=folder).stdout  # not at connect
    assert lines in run('help', 'agents', 'map', cwd=folder).stdout  # with the module's full instructions
    run('set', '--no-tasks', cwd=folder)
    assert lines not in run('help', 'agents', 'map', cwd=folder).stdout


@pytest.mark.req('MCP-031')
def test_the_trouble_report_and_debug_prompts_are_served_only_while_debug_is_on(run, home, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    chassis = SOURCE / 'resources' / 'prompts.xml'
    lines = [prompt(chassis, name).text.strip() for name in ('stop', 'debug')]
    served = run('help', 'agents', cwd=folder).stdout
    assert not any(line in served for line in lines)
    run('set', '--debug', cwd=folder)
    assert run('help', 'agents', cwd=folder).stdout.rstrip().endswith('\n\n'.join(lines))


def test_a_served_prompt_comes_from_the_prompt_store_and_an_edit_there_is_sent_in_its_place(home, tmp_path,
                                                                                           monkeypatch):
    from metaform import prompt_files
    from metaform.data import prompts
    folder = tmp_path / 'mine'
    (folder / 'resources').mkdir(parents=True)
    (folder / 'resources' / 'prompts.xml').write_text(
        '<prompts><greet>Hello <who/> &amp; welcome.</greet></prompts>', encoding='utf-8')
    sent = prompt_files.collect()
    try:
        assert prompt_files.served(folder, 'greet', who='Ada') == 'Hello Ada & welcome.'
        assert prompts.prompt_version('prompt.mine:greet').text == 'Hello <who /> &amp; welcome.'
        prompts.save_prompt('prompt.mine:greet', 'Hi <who/>.')
        assert prompt_files.served(folder, 'greet', who='Ada') == 'Hi Ada.'
        prompts.save_prompt('prompt.mine:greet', 'Hi <who>.')  # not well formed: the shipped text is sent
        assert prompt_files.served(folder, 'greet', who='Ada') == 'Hello Ada & welcome.'
        trial = tmp_path / 'trial.xml'
        trial.write_text('<prompts><greet>Trial <who/>.</greet></prompts>', encoding='utf-8')
        monkeypatch.setenv(prompt_files.TRIAL, str(trial))
        assert prompt_files.served(folder, 'greet', who='Ada') == 'Trial Ada.'
    finally:
        prompt_files.release(sent)
    assert [(one.name, one.number, one.origin) for one in sent] == [
        ('prompt.mine:greet', 1, 'shipped'), ('prompt.mine:greet', 2, 'edited'), ('prompt.mine:greet', 1, 'shipped'),
        ('prompt.mine:greet', None, 'trial')]
    assert sent[2].selected_version_id != sent[2].version_id
    assert sent[2].problems and sent[2].rendered_fingerprint == sent[0].rendered_fingerprint
    assert prompts.prompt_version('prompt.mine:greet').number == 3
    with pytest.raises(LookupError):
        prompt_files.served(folder, 'nothing')


def test_a_prompt_written_wrong_in_its_file_is_named_with_its_line_and_the_others_still_serve(home, tmp_path):
    """UX review round 2, prompt-authoring F1: a bare & is the character it is; a bare < in one prompt names the file,
    the line and the prompt, and leaves every other prompt, the rules with them, read, so the module still loads, and
    the broken prompt is sent as its last shipped version."""
    from metaform import prompt_files
    folder = tmp_path / 'mine'
    (folder / 'resources').mkdir(parents=True)
    path = folder / 'resources' / 'prompts.xml'
    path.write_text('<prompts>\n<rules><rule why="So it is kept.">Keep it.</rule></rules>\n'
                    '<greet>Hello <who/>.</greet>\n<other>Plans & tickets.</other>\n</prompts>\n', encoding='utf-8')
    assert prompt_files.problems(folder) == []
    assert prompt_files.text(folder, 'other') == 'Plans & tickets.'
    assert prompt_files.served(folder, 'greet', who='Ada') == 'Hello Ada.'  # its shipped text is now in the store
    path.write_text('<prompts>\n<rules><rule why="So it is kept.">Keep it.</rule></rules>\n'
                    '<greet>Write <address>: <task>, <who/>.</greet>\n<other>Plans & tickets.</other>\n</prompts>\n',
                    encoding='utf-8')
    [said] = prompt_files.problems(folder)
    assert said.startswith(f'{path}: line 3, column 14, in <greet>: <address> starts a tag that is never closed')
    assert prompt_files.rules(folder) == [('Keep it.', 'So it is kept.')]  # what the loader reads: no refusal
    assert prompt_files.text(folder, 'other') == 'Plans & tickets.'
    assert prompt_files.served(folder, 'greet', who='Ada') == 'Hello Ada.'
    path.write_text('<prompts>\n<fresh>New <x/>.</fresh>\n<broken>a < b</broken>\n</prompts>\n', encoding='utf-8')
    with pytest.raises(LookupError, match='line 3, column .*, in <broken>'):  # nothing earlier to serve in its place
        prompt_files.required(folder, 'broken')


def test_an_edit_is_written_as_plain_text_and_sent_exactly_as_written(home, tmp_path):
    """UX review round 2, prompt-authoring F2 and F3: the gate every surface saves through encodes the person's text,
    so &, < and > are sent as written, a declared fill place stays one, and what is saved is what is sent; reads give
    it back as written. The Canonical Intake stays fixed while other whole files remain editable."""
    from metaform import prompt_files
    from metaform.data import prompts
    folder = tmp_path / 'mine'
    (folder / 'resources').mkdir(parents=True)
    (folder / 'resources' / 'prompts.xml').write_text(
        '<prompts><greet>Hello <who/> &amp; welcome.</greet></prompts>', encoding='utf-8')
    shipped = 'Hello <who /> &amp; welcome.'  # as a version holds the file's element
    assert prompt_files.plain(shipped) == 'Hello <who /> & welcome.'
    version, said = prompt_files.save_edit('prompt.mine:greet', 'Write <address>: <task> & cite <ref/>, <who/>.',
                                           shipped_text=shipped)
    assert version.text == 'Write &lt;address&gt;: &lt;task&gt; &amp; cite &lt;ref/&gt;, <who />.'
    assert said == [('<ref/> is sent as written, for no fill place of prompt.mine:greet is written so; its fill places are '
                     '<who/>.')]
    assert prompt_files.served(folder, 'greet', who='Ada') == 'Write <address>: <task> & cite <ref/>, Ada.'
    assert prompt_files.plain(prompts.prompt_version('prompt.mine:greet').text) == \
        'Write <address>: <task> & cite <ref/>, <who />.'
    assert prompts.prompt_version('prompt.mine:greet', 1).origin == 'shipped'  # the edit's parent is the shipped text
    with pytest.raises(ValueError, match='Canonical Intake'):
        prompt_files.save_edit('prompt.intake:intake.axiom', 'x')
    intake_text = '# A different intake\n\nUse these words directly.\n<unclosed & literal < >'
    edited, notices = prompt_files.save_edit('prompt.intake:intake.xml', intake_text)
    assert edited.text == intake_text and notices == []
    selected = prompt_files.resolve_text('prompt.intake:intake.xml', 'The shipped file has different words.')
    assert selected['text'] == intake_text
    assert selected['actual_version_id'] == selected['selected_version_id'] == edited.version_id
    assert selected['problems'] == []


def test_prompt_save_on_the_command_line_goes_through_the_gate(run, home):
    """prompt-authoring F2: `metaform prompt save` of a prompt a module ships stores what is sent and reads it back
    as written. A save of the fixed Canonical Intake is refused. Other whole files accept arbitrary text."""
    from metaform import prompt_files
    from metaform.data import prompts
    run('prompt', 'save', 'prompt.chassis:work_reminder', 'Hand work on & name its node <here/>.')
    assert prompt_files.chassis('work_reminder') == 'Hand work on & name its node <here/>.'  # what is sent
    stored = prompts.prompt_version('prompt.chassis:work_reminder')
    assert stored.format == 'xml' and stored.text == 'Hand work on &amp; name its node &lt;here/&gt;.'
    assert run('prompt', 'prompt.chassis:work_reminder').stdout == 'Hand work on & name its node <here/>.'
    refused = run('prompt', 'save', 'prompt.intake:intake.axiom', 'x', ok=False)
    assert refused.returncode == 2 and 'never be sent' in refused.stderr
    intake_text = '# Replacement\n\n[unfinished Markdown]( & <unclosed>\nNo former sections are required.'
    run('prompt', 'save', 'prompt.intake:intake.xml', intake_text)
    selected = prompts.prompt_version('prompt.intake:intake.xml')
    assert selected.text == intake_text
    assert run('prompt', 'prompt.intake:intake.xml').stdout == intake_text
    assert prompt_files.resolve_text('prompt.intake:intake.xml', 'Original prompt.')['text'] == intake_text


def test_intake_schema_instructions_are_editable_like_other_whole_files(home):
    from metaform import prompt_files
    from metaform.data import prompts

    name = 'prompt.intake:metaform.xml'
    text = 'Choose any source. A < b & <unclosed need no prescribed markup.'
    selected, notices = prompt_files.save_edit(name, text)

    assert notices == []
    assert prompt_files.readable(selected) == text
    assert prompts.prompt_version(name).version_id == selected.version_id
    assert prompt_files.resolve_text(name, 'Original schema instructions.')['text'] == text


@pytest.mark.parametrize('name', ['prompt.intake:intake.axiom', 'prompt.intake:schema_pointer'])
def test_canonical_intake_and_its_schema_pointer_stay_fixed(home, name):
    from metaform import prompt_files

    with pytest.raises(ValueError, match='never be sent'):
        prompt_files.save_edit(name, 'An edit must not replace the served Canonical Intake.')


@pytest.mark.parametrize('format', ['text', 'markdown', 'xml'])
def test_whole_file_resolution_serves_selected_edits_literally_regardless_of_stored_format(home, format):
    from metaform import prompt_files
    from metaform.data import prompts

    name = 'prompt.intake:intake.xml'
    source = '<old_layout><old_tag>Original content.</old_tag></old_layout>'
    prompts.shipped(name, format, source)
    text = '  # Any replacement\n\n<unknown &amp; <unclosed>\nNo old tags.\n  '
    edited, notices = prompt_files.save_edit(name, text)

    resolved = prompt_files.resolve_text(name, source)

    assert notices == []
    assert edited.format == format
    assert resolved['text'] == text
    assert resolved['actual_version_id'] == resolved['selected_version_id'] == edited.version_id
    assert (resolved['number'], resolved['origin']) == (edited.number, 'edited')
    assert resolved['source']['kind'] == 'selected_edit'
    assert resolved['source']['path'] is None
    assert resolved['bindings'] == {}
    assert resolved['problems'] == resolved['notices'] == []
    assert prompts.prompt_version(name, 1).text == source


def test_whole_file_resolution_applies_only_explicit_literal_bindings_and_preserves_source_metadata(home):
    from metaform import prompt_files

    name = 'prompt.intake:intake.xml'
    source = '# Arbitrary words\n{project}\n<unclosed &amp; {task}\n{unknown}\n<who/>\n'
    before = prompt_files.resolve_text(name, source)
    text = source + '\nAn edited ending without any required section.'
    selected, notices = prompt_files.save_edit(name, text)
    unfilled = prompt_files.resolve_text(name, source)
    bindings = {'{project}': 'A & <B>', '{task}': 'Keep <raw/> &amp; literal.', 'who': 'Unapplied'}

    resolved = prompt_files.resolve_text(name, source, **bindings)

    assert notices == []
    assert before['text'] == source
    assert resolved['text'] == text.replace('{project}', 'A & <B>').replace(
        '{task}', 'Keep <raw/> &amp; literal.')
    assert '{unknown}' in resolved['text'] and '<who/>' in resolved['text']
    assert resolved['bindings'] == bindings
    assert resolved['actual_version_id'] == resolved['selected_version_id'] == selected.version_id
    assert resolved['source'] == unfilled['source']
    assert resolved['number'] == unfilled['number'] == selected.number
    assert resolved['origin'] == unfilled['origin'] == 'edited'
    assert resolved['problems'] == resolved['notices'] == []
    assert resolved['rendered_fingerprint'] != unfilled['rendered_fingerprint']
