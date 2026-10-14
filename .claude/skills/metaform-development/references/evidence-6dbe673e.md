patch -R -p1 < /tmp/a08-mine.patch && grep -n "opened(payload" src/metaform/modules/web/page/app/figures/attention.js
PYTHONPATH=/tmp/a08-old/src /home/rich/metaform/.venv/bin/python -c "import metaform; print(metaform.__file__)"
/tmp/a08-old/src/metaform/__init__.py
3 failed, 240 deselected in 67.16s (0:01:07)