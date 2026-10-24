"""Historical orchestration records, retained without agent-management behavior."""
from metaform.data import Column, Index, Table, Tables

EPISODES = (
    Table('episodes', key=('episode_id',), columns=(
        Column('episode_id', required=True), Column('created', required=True),
        Column('updated', required=True), Column('session_id'), Column('assignment_id'))),
    Table('episode_work', key=('assignment_id',), columns=(
        Column('assignment_id', required=True), Column('work_id', required=True),
        Column('episode_id', required=True), Column('created', required=True),
        Column('fresh_context', 'bool', default=False)),
        indexes=(Index(('episode_id',)), Index(('work_id',), unique=True))),
    Table('binding_history', key=('session_id', 'assignment_id'), columns=(
        Column('session_id', required=True), Column('assignment_id', required=True),
        Column('episode_id', required=True), Column('runner'),
        Column('created', required=True), Column('updated', required=True)),
        indexes=(Index(('assignment_id',)), Index(('runner',)), Index(('episode_id',)))),
)

ROUTING = Table('routing', key=('work_id',), columns=(
    Column('work_id', required=True), Column('state', required=True), Column('fingerprint'),
    Column('role'), Column('reason'), Column('updated', required=True)), indexes=(Index(('state',)),))

TABLES = Tables(version=6, compatible_from=1, tables=(
    *EPISODES,
    ROUTING,
    Table('assignments', key=('assignment_id',), columns=(
        Column('assignment_id', required=True), Column('work_id', required=True),
        Column('root_work_id', required=True), Column('team_id', required=True),
        Column('gc_assignment_id'), Column('parent_assignment_id'), Column('reviewed_assignment_id'),
        Column('successor_assignment_id'),
        Column('owner_session_id'), Column('authored_role_uri', required=True), Column('role_snapshot', 'json'),
        Column('attempt', 'int', default=1),
        Column('execution_role', required=True, default='worker'), Column('functional_locations', 'json'),
        Column('task', required=True), Column('requested_result', required=True), Column('candidate', 'json'),
        Column('specification', 'json'), Column('plan', 'json'), Column('reviewed_snapshot', 'json'),
        Column('findings', 'json'), Column('mode', required=True), Column('state', required=True),
        Column('return_to', 'json'), Column('pending_direction', 'json'), Column('result', 'json'),
        Column('evidence', 'json'), Column('last_check_in', 'json'), Column('stop', 'json'), Column('stop_history', 'json'),
        Column('findings_filed', 'json'), Column('persons_start', 'bool', default=False),
        Column('created', required=True), Column('updated', required=True)), indexes=(
            Index(('work_id',), unique=True), Index(('owner_session_id',)), Index(('team_id',)),
            Index(('parent_assignment_id',)), Index(('reviewed_assignment_id',)), Index(('state',)))),
    Table('sessions', key=('session_id',), columns=(
        Column('session_id', required=True), Column('assignment_id', required=True), Column('runner'),
        Column('created', required=True)), indexes=(Index(('assignment_id',)), Index(('runner',)))),
    Table('transitions', key=('transition_id',), columns=(
        Column('transition_id', required=True), Column('assignment_id', required=True),
        Column('work_id', required=True), Column('kind', required=True), Column('state', required=True),
        Column('payload', 'json', required=True), Column('delivery', 'json'),
        Column('created', required=True), Column('updated', required=True)),
        indexes=(Index(('state',)), Index(('work_id', 'state')), Index(('assignment_id',)))),
    Table('role_requests', key=('request_id',), columns=(
        Column('request_id', required=True), Column('caller_assignment_id', required=True),
        Column('gc_assignment_id', required=True), Column('role', required=True), Column('purpose', required=True),
        Column('task', required=True), Column('requested_result', required=True), Column('context', 'json'),
        Column('functional_locations', 'json'), Column('creator_assignment_id'), Column('child_assignment_id'),
        Column('state', required=True), Column('source', 'json'), Column('created', required=True)),
        indexes=(Index(('gc_assignment_id',)), Index(('caller_assignment_id',)),
                 Index(('role', 'state')), Index(('creator_assignment_id', 'state')))),
    Table('changes', key=('change_id',), columns=(
        Column('change_id', required=True), Column('assessment_assignment_id', required=True),
        Column('specification', 'json', required=True), Column('previous_revision', required=True),
        Column('current_revision'), Column('before_content', required=True), Column('content', required=True),
        Column('reason', required=True), Column('observed_limitation', required=True),
        Column('affected_work_ids', 'json', required=True), Column('mode_at_publication', required=True),
        Column('source', required=True), Column('user_instruction', 'json'), Column('state', required=True),
        Column('user_message_state', required=True),
        Column('created', required=True), Column('updated', required=True)),
        indexes=(Index(('state',)), Index(('assessment_assignment_id',)),)),
))
