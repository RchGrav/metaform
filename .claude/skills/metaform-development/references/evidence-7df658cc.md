def holds(store: Store, work_ids: list[str]) -> set[str]:
    """Those of these tickets the person holds, `map_work hold=true`, kept in the map module's own table: a hold keeps agents and automatic starts off a ticket as the Backlog's held mark does. Read by key; none without the map module."""
    if not work_ids:
        return set()
    try:
        with Store(store.project_id, module='map').tables(write=False) as tx:
            found = [tx.get('ticket_settings', {'work_id': work_id}) for work_id in work_ids]
    except StoreError:
        return set()
    return {str(row['work_id']) for row in found if row is not None and row['hold']}