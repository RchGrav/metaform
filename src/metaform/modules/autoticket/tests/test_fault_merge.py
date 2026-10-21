"""A real main merge closes fault work without a background proof service."""
import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414
from metaform.modules.dispatch.tests.test_merge import git, worked
from metaform.modules.dispatch.tests.test_merge import repo as repo  # noqa: PLC0414

pytestmark = pytest.mark.kind('simulation')


def test_fault_fix_merged_to_main_closes_and_clears_open_condition(dispatch, repo):
    git(repo, 'checkout', '-b', 'main')
    git(repo, 'push', '-qu', 'origin', 'main')
    dispatch.store.edit_work(dispatch.id, {'condition': 'broken', 'kind': 'broken'})
    dispatch.store.prove_work(dispatch.id)
    assert dispatch.ticket().done is None
    [delivered] = worked(dispatch, repo)
    assert delivered['state'] == 'merged' and not delivered['reason']
    assert git(repo, 'rev-parse', 'main') == git(repo, 'rev-parse', 'origin/main')
    assert (repo / 'feature.txt').read_text() == 'ticket feature\n'
    closed = dispatch.ticket()
    assert closed.done and closed.outcome == 'completed'
    assert closed.resolution == 'Feature completed.'
    assert not dispatch.store.work(open=True, condition='broken', limit=0).results
