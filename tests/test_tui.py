"""The settings screen loads every setting and saves through the same settings API."""
from pathlib import Path

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from metaform import home, settings, tui


def test_screen_lists_settings_and_saves_a_glued_change(home, tmp_path):
    work = tmp_path / 'work'
    other = tmp_path / 'other'
    work.mkdir(); other.mkdir()
    from metaform import home as h
    h.add_project('work', work)
    h.add_project('other', other)
    with create_pipe_input() as pipe:
        screen = tui.ChassisTUI(tui._Backend(work), input=pipe, output=DummyOutput())
        import asyncio

        async def drive():
            await screen.refresh()
            assert [row['id'] for row in screen.rows][0] == 'chassis'
            keys = [item.key for item in screen.declared_settings]
            assert 'project' in keys
            setting = next(item for item in screen.declared_settings if item.key == 'project')
            screen._save('chassis', setting, 'other')
            screen.pending_pins[('chassis', 'project')] = True
            screen._save_changes()
            await asyncio.sleep(0.2)
        asyncio.run(drive())
    assert settings.value('project', work) == 'other'
    assert settings.state('project', work) == 'glued'


def test_screen_turns_a_module_off_and_on(home, tmp_path):
    import asyncio
    from metaform import loader
    with create_pipe_input() as pipe:
        screen = tui.ChassisTUI(tui._Backend(tmp_path), input=pipe, output=DummyOutput())

        async def drive():
            await screen.refresh()
            ids = [row['id'] for row in screen.rows]
            assert 'template' in ids
            screen.module_index = ids.index('template')
            screen._toggle_module()
            screen._save_changes()
            await asyncio.sleep(0.2)
        asyncio.run(drive())
    loader.reset()
    assert next(item for item in loader.discover() if item.id == 'template').enabled is False
