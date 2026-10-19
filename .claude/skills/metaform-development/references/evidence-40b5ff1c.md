cat > /tmp/fqc24/identity_settled.py <<'EOF'
import pytest

@pytest.fixture(autouse=True)
def _identity_settled(monkeypatch):
    from metaform.modules.memory import citations, delivery
    monkeypatch.setattr(citations, 'settled', lambda why: why)
    monkeypatch.setattr(delivery, 'settled', lambda why: why)
EOF
cd /home/rich/metaform && PYTHONPATH=/tmp/fqc24 timeout 300 uv run pytest -n 0 -q -p identity_settled src/metaform/modules/memory/tests/test_delivery.py -k moves_again 2>&1 | grep -E "assert|passed|failed|Error" | head -8

        assert 'stale' not in mcp_read(project)['entities'][0]
        assert (entry['receiver'], entry['unread'], entry['updated']) == (A, 1, 1)
        assert mcp_read(project)['entities'][0]['stale'] == ['route.py:2: line 2 changed; the cited text is now at line 3']
>       assert delivery.notices(ctx)['entries'] == [] and node_count(ctx, (A,))[0].at[A][1] == 0
E       AssertionError: assert ([{'receiver':...ead': 1, ...}] == []
src/metaform/modules/memory/tests/test_delivery.py:326: AssertionError
1 failed, 13 deselected in 1.77s