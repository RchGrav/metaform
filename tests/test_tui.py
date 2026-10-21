"""The settings screen edits the same settings as set and unset, and turns modules on and off."""
import asyncio

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from metaform import home as metaform_home
from metaform import loader, settings, tui

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('CLI-026')]


def _screen(folder):
    pipe = create_pipe_input()
    return pipe, tui.ChassisTUI(tui._Backend(folder), input=pipe, output=DummyOutput())


def test_screen_shows_every_setting_in_the_schema(home, tmp_path):
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            await screen.refresh()
            shown = set()
            for index, row in enumerate(screen.rows):
                screen.module_index = index
                shown |= {item.key for item in screen.declared_settings}
            return shown
        shown = asyncio.run(drive())
    # Every setting of the chassis and of each loaded module; a disabled module another test imported in this process
    # has settings in the schema that the screen rightly does not show.
    loaded = {'chassis'} | {item.id for item in loader.discover() if item.module is not None}
    assert shown == {key for key, item in settings.SCHEMA.items() if item.owner in loaded and not item.per_call}


def test_help_key_on_a_setting_shows_its_details(home, tmp_path):
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            await screen.refresh()
            screen._focus('settings')
            screen.setting_index = next(index for index, item in enumerate(screen.declared_settings) if item.details)
            screen._module_help()  # F2
            return screen.declared_settings[screen.setting_index], screen.module_help_text.text
        setting, shown = asyncio.run(drive())
    assert setting.details in shown and shown.startswith(setting.switch)


def test_screen_edits_and_glues_through_its_own_keys(home, tmp_path):
    work, other = tmp_path / 'work', tmp_path / 'other'
    work.mkdir(); other.mkdir()
    metaform_home.add_project('work', work)
    metaform_home.add_project('other', other)
    pipe, screen = _screen(work)
    with pipe:
        async def drive():
            await screen.refresh()
            screen._focus('settings')
            screen.setting_index = [item.key for item in screen.declared_settings].index('project')
            screen._edit()  # a choice setting opens the picker on its choices
            screen.pick_index = screen.pick_choices.index('other')
            screen._pick_apply()
            screen._toggle_glue()
            screen._save_changes()
            await screen.last_task
        asyncio.run(drive())
    assert settings.value('project', work) == 'other'
    assert settings.state('project', work) == 'glued'


def test_screen_turns_a_module_off_and_on(home, tmp_path):
    def toggle():
        pipe, screen = _screen(tmp_path)
        with pipe:
            async def drive():
                await screen.refresh()
                screen.module_index = [row.id for row in screen.rows].index('template')
                screen._toggle_module()
                screen._save_changes()
                await screen.last_task
            asyncio.run(drive())
        loader.reset()
        return next(item for item in loader.discover() if item.id == 'template').enabled
    first = toggle()
    assert toggle() is not first


@pytest.mark.req('CLI-031')
def test_screen_rows_read_as_config_show_rows(home, tmp_path, capsys):
    from metaform import cli
    settings.assign('debug', True, tmp_path)
    settings.assign('connect_instructions', 'full', tmp_path, glue=True)  # report, removed 2026-10-15, was here
    assert cli.main(['config', '--show', f'folder={tmp_path}']) == 0
    expected = {line.split(':')[0].lstrip('* '): line for line in capsys.readouterr().out.splitlines() if ': ' in line}
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            await screen.refresh()
            screen.module_index = [row.id for row in screen.rows].index('chassis')
            return [text for _, text in screen._setting_lines()]
        rows = asyncio.run(drive())
    for key in ('debug', 'connect_instructions', 'layers', 'modules'):
        assert any(row.rstrip('\n').endswith(expected[key]) for row in rows), (key, expected[key], rows)



@pytest.mark.req('BASE-037')
@pytest.mark.req('BASE-018')
def test_refreshing_the_screen_starts_no_module_again(home, tmp_path, user_module):
    marks = tmp_path / 'starts.txt'
    user_module('counted', f'''
        from pathlib import Path
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        def start(ctx):
            with Path({str(marks)!r}).open('a') as out:
                out.write('start\\n')
        MODULE = Module(id='counted', summary='Counts.', purpose='Counts. Details: metaform help counted.',
                        start=start)
    ''')
    loader.reset()
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            for _ in range(3):
                await screen.refresh()
        asyncio.run(drive())
    assert marks.read_text().splitlines() == ['start']


@pytest.mark.req('BASE-009')
@pytest.mark.req('BASE-018')
def test_the_screen_loads_and_turns_off_a_module_whose_start_and_stop_are_async(home, tmp_path, user_module):
    marks = tmp_path / 'marks.txt'
    user_module('asyncer', f'''
        from pathlib import Path
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        async def start(ctx):
            with Path({str(marks)!r}).open('a') as out:
                out.write('start\\n')
        async def stop(ctx):
            with Path({str(marks)!r}).open('a') as out:
                out.write('stop\\n')
        MODULE = Module(id='asyncer', summary='Async.', purpose='Async. Details: metaform help asyncer.',
                        start=start, stop=stop)
    ''')
    loader.reset()
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            await screen.refresh()
            assert 'asyncer' not in screen.backend.load_errors
            screen.module_index = [row.id for row in screen.rows].index('asyncer')
            screen._toggle_module()
            screen._save_changes()
            await screen.last_task
        asyncio.run(drive())
    assert marks.read_text().splitlines() == ['start', 'stop']
    assert next(item for item in loader.discover() if item.id == 'asyncer').problem == ''


@pytest.mark.req('CLI-031')
def test_choices_are_picked_from_a_list_and_stepped_with_left_and_right(home, tmp_path):
    work, other = tmp_path / 'work', tmp_path / 'other'
    work.mkdir(); other.mkdir()
    metaform_home.add_project('work', work)
    metaform_home.add_project('other', other)
    pipe, screen = _screen(work)
    with pipe:
        async def drive():
            await screen.refresh()
            screen._focus('settings')
            keys = [item.key for item in screen.declared_settings]
            screen.setting_index = keys.index('modules')
            screen._edit()  # the modules setting opens as a checklist of every group, all checked while empty
            assert screen.picking and 'map' in screen.pick_choices and screen.pick_checked == set(screen.pick_choices)
            screen._pick_check(everything=True)
            screen.pick_index = screen.pick_choices.index('map')
            screen._pick_check()
            screen._pick_apply()
            screen.setting_index = keys.index('project')
            screen._side(1)  # → steps a choice setting instead of switching panels
            assert screen.panel == 'settings'
            screen._save_changes()
            await screen.last_task
        asyncio.run(drive())
    assert settings.value('modules', work) == ['map']
    assert settings.value('project', work) == 'other'


@pytest.mark.req('CLI-019')
def test_a_list_of_one_value_per_name_unchecks_the_others_of_a_name_when_one_is_checked(home, tmp_path):
    pipe, screen = _screen(tmp_path)
    with pipe:
        listed = settings.Setting(key='probe_options', kind='list', exclusive='=')
        screen.pick_target = ('probe', listed)
        screen.pick_choices = ['claude.model=small', 'claude.model=large', 'codex.model=small']
        screen.pick_checked = {'claude.model=small', 'codex.model=small'}
        screen.pick_index = 1
        screen._pick_check()
        assert screen.pick_checked == {'claude.model=large', 'codex.model=small'}
        screen._pick_check()
        assert screen.pick_checked == {'codex.model=small'}, 'unchecking leaves the name with none'


def test_a_section_opens_as_a_menu_of_its_settings_and_lists_are_alphabetical(home, tmp_path):
    loader.set_enabled('dispatch', True)  # off in a new home
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            await screen.refresh()
            ids = [row.id for row in screen.rows]
            assert ids == ['chassis', *sorted(ids[1:], key=str.casefold)]
            screen.module_index = ids.index('dispatch')
            screen._focus('settings')
            top = screen.entries
            assert 'Agent options' in top and 'dispatch_claude_mode' not in [getattr(one, 'key', one) for one in top]
            screen.setting_index = top.index('Agent options')
            screen._edit()  # Enter opens the section: the agents
            assert screen.entries == ['Claude Code', 'Codex', 'Google Antigravity']
            screen._side(1)  # → opens the agent's options, each by its label
            assert [one.label for one in screen.entries] == ['Agent', 'Effort', 'Fast mode', 'Mode', 'Model']
            screen.setting_index = 3
            screen._edit()  # the option's values, default the one in force
            assert screen.picking and screen.pick_choices[0] == 'default' and screen.pick_checked == {'default'}
            assert 'Claude Code' in screen._pick_about()
            screen._back(); screen._back()  # the picker closes, then back out to the agents
            return screen.section, screen.entries[screen.setting_index]
        assert asyncio.run(drive()) == (('Agent options',), 'Claude Code')


@pytest.mark.req('CLI-027')
def test_a_list_whose_items_hold_commas_is_saved_from_the_screen_as_it_reads(home, tmp_path):
    loader.set_enabled('dispatch', True)  # off in a new home
    loader.set_enabled('hello', True)  # its friends setting is a list with no choices
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            await screen.refresh()
            setting = settings.SCHEMA['friends']
            edited = ['Ada', 'Hopper, Grace']
            screen._stage('hello', setting, edited)
            screen._save_changes()
            await screen.last_task
            return edited, screen.error
        edited, failed = asyncio.run(drive())
    assert not failed
    assert settings.value('friends', tmp_path) == edited


@pytest.mark.req('VIEW-039')
def test_a_risky_choice_is_never_stepped_onto_and_is_stored_only_when_confirmed(home, tmp_path):
    from metaform import cli
    loader.set_enabled('dispatch', True)
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            await screen.refresh()
            screen.module_index = [row.id for row in screen.rows].index('dispatch')
            screen._focus('settings')
            screen.setting_index = [getattr(one, 'key', None) for one in screen.entries].index('dispatch_prompts')
            setting = screen.current
            stepped = []
            for amount in (1, -1, -1):  # from ask_all, wrapping onto approve-all is refused; then approve-reads; then
                # approve-all is refused again
                screen._side(amount)
                stepped.append(screen._value('dispatch', setting))
            screen._edit()  # picked from the list, it waits for the person's yes
            screen.pick_index = screen.pick_choices.index('approve-all')
            screen._pick_apply()
            asked = screen.confirm_open, screen._value('dispatch', setting)
            screen._confirm(False)
            refused = screen._value('dispatch', setting)
            screen._edit()
            screen.pick_index = screen.pick_choices.index('approve-all')
            screen._pick_apply()
            screen._confirm(True)
            return stepped, asked, refused, screen._value('dispatch', setting)
        stepped, asked, refused, confirmed = asyncio.run(drive())
    assert stepped == ['ask_all', 'approve-reads', 'approve-reads']
    assert asked == (True, 'approve-reads') and refused == 'approve-reads' and confirmed == 'approve-all'
    assert cli.main(['set', '--dispatch-prompts', 'approve-all', f'folder={tmp_path}']) == 2
    assert settings.value('dispatch_prompts', tmp_path) == 'ask_all'
    assert cli.main(['set', '--dispatch-prompts', 'approve-all', '--confirm', f'folder={tmp_path}']) == 0
    assert settings.value('dispatch_prompts', tmp_path) == 'approve-all'


def test_one_read_describes_every_group_and_a_filter_finds_settings_in_any_group(home, tmp_path, monkeypatch):
    loader.set_enabled('dispatch', True)
    described = []
    real = settings.describe
    monkeypatch.setattr(settings, 'describe', lambda *args, **kwargs: described.append(kwargs) or real(*args, **kwargs))
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            await screen.refresh()
            screen.module_index = [row.id for row in screen.rows].index('chassis')
            screen._filter_settings()
            screen.editor.text = 'prompts'
            screen._apply_edit()
            found = [(one.owner, one.key) for one in screen.entries]
            rows = [text for _, text in screen._setting_lines()]
            screen._filter_settings()  # opened again, typing goes at the end of the filter
            return found, rows, screen.editor.buffer.cursor_position
        found, rows, cursor = asyncio.run(drive())
    assert described == [{'choices': False}], 'one description of the folder serves every group, without choices'
    assert ('dispatch', 'dispatch_prompts') in found and any('dispatch  dispatch_prompts: ' in row for row in rows)
    assert cursor == len('prompts')


@pytest.mark.req('CLI-019')
def test_a_value_outside_its_choices_is_refused_with_them_and_a_staged_row_is_marked(home, tmp_path):
    loader.set_enabled('dispatch', True)
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            await screen.refresh()
            kinds = settings.SCHEMA['code_kinds']
            screen._stage('map', kinds, ['Functon'])
            refused = screen.message, dict(screen.pending_settings)
            screen._stage('map', kinds, ['Function'])
            screen.module_index = [row.id for row in screen.rows].index('map')
            screen._focus('settings')
            rows = [text for _, text in screen._setting_lines()]
            model = settings.SCHEMA['dispatch_claude_model']
            screen._open_pick('dispatch', model, 'default')  # no catalog yet: the picker offers to read it
            return refused, rows, screen.pick_choices, screen.pick_reader
        (message, pending), rows, choices, reader = asyncio.run(drive())
    assert "--code-kinds has no choice 'Functon'. Choices: Function, Method" in message and not pending
    staged = next(row for row in rows if 'code_kinds' in row)
    assert '  ~ code_kinds: Function  (staged)' in staged, staged
    assert choices == ['default'] and reader == 'metaform dispatch options agent=claude prime=true'
    with pytest.raises(settings.SettingError) as refusal:
        settings.checked('dispatch_claude_model', 'opus', tmp_path, typed=True)
    assert refusal.value.next_step == reader
