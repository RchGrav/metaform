$ C=/tmp/t45/copy; ... cp -r src conftest.py pyproject.toml $C/; python3 - <<'EOF' ... (reverts only the threadRows lines in the copy)
...
E           AssertionError: assert 2 == 1
+  where 2 = evaluate('window.heldAtOnce')
1 failed, 242 deselected in 35.50s