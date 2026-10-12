"""The chassis's own toolbar items and panes in the web GUI's workspace: what belongs to no module.

The chassis owns the settings, the prompt store, search over the map, the map's documents and the build, so it
declares their tools and panes here, as a module declares its own in `Module(toolbar=, panes=)`. They are on the
toolbar while the chassis is on the folder's command surface, CLI-022. `module.contributions` gathers them first.
"""
from __future__ import annotations

from .module import Pane, ToolbarItem, check_workspace

TOOLBAR: tuple[ToolbarItem, ...] = (
    # Finding a node by its words is the fastest way into a map too large to scan.
    ToolbarItem('search', 'Search', 'Find any node of the map by the words it holds, and go to it.', icon='search',
                page='search', order=10, shortcut='/'),
    # Every setting of the folder and its modules in one place, so nothing needs the command line to change.
    ToolbarItem('settings', 'Settings', 'Change any setting of this folder and its modules, and turn modules on or off.',
                icon='gear', pane='settings', order=900),
    # The map as a document to hand to someone, or to an agent with no Metaform; the two formats share one slot.
    ToolbarItem('export-markdown', 'Export Markdown', 'Save the map as a short Markdown document to share or read.',
                icon='download', page='export-markdown', group='export', placement='extra', order=100),
    ToolbarItem('export-xml', 'Export XML', 'Save the map with every field as XML, for another tool to read.',
                icon='download', page='export-xml', group='export', placement='extra', order=110),
    # The project as a file a remote agent or another machine can run.
    ToolbarItem('build', 'Build', 'Build an archive, a wheel for a remote agent, or the installer, to download.',
                icon='archive', page='build', placement='extra', order=200),
    ToolbarItem('shortcuts', 'Keyboard shortcuts', 'See every key the map and the page take.', icon='keyboard',
                page='shortcuts', placement='extra', order=900, shortcut='?'),
)

PANES: tuple[Pane, ...] = (
    # The prompts agents are sent are read and edited beside the node they shape; today the object panel's third tab.
    Pane('prompt', 'Prompt', 'Read and edit the prompts agents are sent, as new versions with their changes shown.',
         icon='pen', page='prompt', area='right', group='node', visible=True, order=30, min_width=320),
    # Settings open as the page's own window, as they always have; the person can dock the pane on the right.
    Pane('settings', 'Settings', 'Change any setting of this folder and its modules, and turn modules on or off.',
         icon='gear', page='settings', area='float', order=90, min_width=360),
)

check_workspace('chassis', (), TOOLBAR, PANES)
