"""Historical hold-review records retained without automatic review or execution policy."""
from metaform.data import Column, Index, Table

HOLD_REVIEW_TABLES = (
    Table('hold_reviews', place='project', key=('base_id', 'work_id'),
          columns=(Column('base_id', required=True), Column('work_id', required=True),
                   Column('deadline', 'real', required=True), Column('reason', required=True),
                   Column('board', required=True), Column('signal_key')),
          indexes=(Index(('deadline',)), Index(('signal_key',)))),
    Table('hold_review_state', place='project', key=('name',),
          columns=(Column('name', required=True), Column('initialized', 'int', required=True), Column('signal_key'))),
)
