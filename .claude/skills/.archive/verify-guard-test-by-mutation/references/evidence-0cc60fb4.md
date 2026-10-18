E       AssertionError: 
E       assert '' == 'Following Cl...de · mushroom'
E         
E         - Following Claude Code · mushroom
/tmp/g46base/src/metaform/modules/web/tests/test_web.py:2080: AssertionError
1 failed, 257 deselected in 19.70s

Run the updated follow test on the unfixed copy: cp src/metaform/modules/web/tests/test_web.py /tmp/g46base/src/metaform/modules/web/tests/test_web.py && ... PYTHONPATH=/tmp/g46base/src timeout 900 .venv/bin/python -m pytest -p no:cacheprovider -q -m browser -n 0 /tmp/g46base/src/metaform/modules/web/tests/test_web.py -k test_the_2d_map_stays_fitted_through_selections_and_frames_the_node_of_the_agent_followed