E           ValueError: The source placement run's base no longer exists in this project.

src/metaform/modules/source_placement/pipeline.py:58: ValueError
FAILED src/metaform/modules/source_placement/tests/test_source_placement.py::test_a_start_in_one_home_leaves_a_shared_project_folders_runs_resumable_from_another
# Each home's bases have ids of their own; the run was prepared in home B, so it names B's base.
    base_b = metaform_home.add_base('proj', 'original').id