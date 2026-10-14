E                   AttributeError: 'Project' object has no attribute 'id'
1 failed, 7 deselected in 1.31s
RESTORED

(second mutant, the in-place rename plus a copy left in home A)
>       assert home_a_folder is not None and not (home_a_folder / 'source_placement' / run_id).exists()
1 failed, 7 deselected in 1.90s
RESTORED