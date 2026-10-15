FAILED src/metaform/modules/mcp/tests/test_mcp.py::test_every_verb_that_reaches_the_network_or_writes_declares_it_in_its_annotation
E       AssertionError: dispatch_spend declared read, writes: metaform_module_system_dispatch.spend_read > metaform_module_system_dispatch.spend_rows > metaform_module_system_dispatch.carry_spend > own_store(store).tables()
Only `dispatch_spend` remains in the guard. Confirming it isn't mine:
b3d942e work: RULE FROM RICH: never open a visible browser window on Rich'