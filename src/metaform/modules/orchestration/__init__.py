"""GC-led delivery using native roles, work records and durable continuations."""
from __future__ import annotations

import json
from typing import Any

from metaform import jev, settings
from metaform.data import functional_context
from metaform.module import AgentRoleDefinition, Context, Module, Noun, Provides, Resource, Subscription, Verb

from .bmad import definitions as bmad_definitions
from .bmad import inspect as bmad_inspect
from .routing import roles_changed
from .specifications import change as publish_change
from .specifications import inspect_change
from .state import ENDED, SERVICE, TABLES, fingerprint, identity, own, requested, row_for, work_changed, work_read

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = True

settings.choice('orchestration_mode', ['adaptive', 'strict'], default='adaptive',
                help='Whether assignments may adapt specifications to serve C(T), or recommend changes.',
                owner='orchestration', scope='folder')

settings.number('orchestration_reviews', 0, min=0, max=10,
                label='Automatic reviews per ticket', category='automation', heading='Verification', person_only=True,
                help='Bound independent reviews of one delivery. Findings reopen that ticket; zero disables automatic reviews.')

ROLE_DUTIES = (
    ('triage', 'The Liaison: interview the person, prepare functional tickets and hand the Planner their intent.',
     'prompt.dispatch:system'),
    ('gc', 'Own a ticket, coordinate its swarm and validate delivery.', 'prompt.orchestration:gc'),
    ('functionality', ('The Harsh Critic: independently assess delivered work and functional quality against C(T); '
                       'approve, or reject with corrective tickets.'), 'prompt.orchestration:functionality'),
    ('investigator', 'Establish behavior, causes, dependencies and implementation entry points.',
     'prompt.orchestration:investigator'),
    ('requirements', 'Express requested outcomes and consequential requirements precisely.', 'prompt.orchestration:requirements'),
    ('planner', 'Build the goal, plan, tickets and implementation order before facilitation.', 'prompt.orchestration:planner'),
    ('implementer', 'Produce the assigned change and establish its effect.', 'prompt.orchestration:implementer'),
    ('verifier', 'Assess whether observed behavior establishes the requested outcome.', 'prompt.orchestration:verifier'),
    ('reviewer', 'Examine requested behavior and implementation quality as separate judgments.', 'prompt.orchestration:reviewer'),
    ('integrator', 'Combine assigned candidates and establish their resulting behavior.', 'prompt.orchestration:integrator'),
    ('architect', 'Design an assigned part and its interfaces within the existing system.', 'prompt.orchestration:architect'),
    ('designer', 'Design clear user journeys, states and recovery behavior.', 'prompt.orchestration:designer'),
    ('researcher', 'Establish attributed findings for an assigned question.', 'prompt.orchestration:researcher'),
    ('synthesizer', 'Reconcile findings into a faithful combined result.', 'prompt.orchestration:synthesizer'),
    ('dogfood', 'Expose user-experience failures by using the actual product.', 'prompt.orchestration:dogfood'),
    ('release', 'Prepare the assigned release candidate and materials.', 'prompt.orchestration:release'),
    ('facilitator', 'Assign specialists to tickets, create or reuse their expertise, and carry the critic\'s corrections.',
     'prompt.orchestration:role_creator'),
    # Retained for already recorded assignments; new commissions use facilitator.
    ('role_creator', 'Publish a reusable specialist duty requested by triage or a worker.', 'prompt.orchestration:role_creator'),
)
ROLES = tuple(AgentRoleDefinition(name, purpose, ('prompt.orchestration:common', prompt), specialist=False)
              for name, purpose, prompt in ROLE_DUTIES)

OBJECT = {'type': 'object', 'additionalProperties': True}
ARRAY = {'type': 'array', 'items': OBJECT}
ASSIGNMENT = Noun('assignment', 'Recorded assignment; omitted uses the calling agent.', required=False)
ROLE = Noun('role', 'Registered specialist role name or URI.')
RESULT = Noun('result', 'Requested contribution returned to the immediate caller.', required=False)
AT = Noun('at', 'Existing functional element address; absent inherits the parent location.', required=False)
KEY = Noun('key', 'Stable call or result identity used when retrying the same operation.', required=False)
WAIT = Noun('wait', 'Suspend the parent while its delegated contribution runs.', 'bool', required=False)
SPEC = Noun('specification', 'Existing operative file reference or stored workflow address/layer/name and revision.',
            'json', required=False, schema=OBJECT)
CANDIDATE = Noun('candidate', 'Exact candidate under examination.', 'json', required=False, schema=OBJECT)
EVIDENCE = Noun('evidence', 'Candidate-specific observations and verification results.', 'json', required=False,
                schema={'type': 'array', 'items': {}})


def inspect(ctx: Context) -> Any:
    return SERVICE.assignment(ctx, assignment_id=ctx.nouns.get('assignment'), work_id=ctx.nouns.get('work'))


def team(ctx: Context) -> Any:
    assignment = SERVICE.assignment(ctx)
    team_id = ctx.nouns.get('team') or (assignment or {}).get('team_id')
    if team_id:
        return {'team_id': team_id, 'members': SERVICE.members(ctx, str(team_id)),
                **SERVICE.related(ctx, str(team_id))}
    with own(ctx).tables(write=False) as tx:
        return {'assignments': list(tx.rows('assignments', limit=0).results)}


def assess(ctx: Context) -> Any:
    assignment = requested(ctx, ctx.nouns.get('assignment'))
    with own(ctx).tables(write=False) as tx:
        team = row_for(tx, assignment_id=assignment['team_id']) or assignment
        if team.get('reviewed_assignment_id'):
            # An assessment, or a specialist it called, is already the assessment of that work; it returns its
            # findings through check-in, so it never queues another assessment of the same work.
            return {**team, 'queued': False, 'said': 'This is the assessment of that work; nothing was queued. '
                    'Return its result and findings with orchestration_check-in state=returned.'}
        gc = row_for(tx, assignment_id=assignment.get('gc_assignment_id')) or assignment
        if gc['state'] in ENDED:
            # A delivered result was queued its assessment once, at delivery.
            prior = tx.rows('assignments', {'reviewed_assignment_id': gc['assignment_id']}, limit=0).results
            if prior:
                return {**max(prior, key=lambda one: str(one['created'])), 'queued': False,
                        'said': 'The delivered result already has its assessment; nothing was queued.'}
    report = {name: ctx.nouns.get(name) for name in ('summary', 'candidate', 'evidence')}
    asked = ctx.nouns.get('key') or fingerprint(json.dumps(report, sort_keys=True, default=str))
    key = identity(assignment['assignment_id'], 'assessment_request', str(asked))
    return SERVICE.assessment(ctx, gc, report, key)


def role_requests(ctx: Context) -> Any:
    with own(ctx).tables(write=False) as tx:
        if ctx.nouns.get('request'):
            return tx.get('role_requests', {'request_id': str(ctx.nouns['request'])})
        return list(tx.rows('role_requests', limit=0).results)


def publish_role(ctx: Context) -> Any:
    published = SERVICE.publish_role(ctx)
    role = published['role']
    assignment = published['assignment']
    return {'role': {key: role.get(key) for key in ('name', 'uri', 'version_id')},
            'source': published.get('source'), 'match_reason': published.get('match_reason'),
            'assignment': {key: assignment[key] for key in ('assignment_id', 'work_id', 'state')}
                if assignment else None,
            'board_placement': published['board_placement'],
            'continued': len(published['assignments'])}


def change(ctx: Context) -> Any:
    return publish_change(ctx, SERVICE)


def claim(ctx: Context) -> dict[str, Any]:
    assigned = SERVICE.claim(ctx)
    return {key: assigned[key] for key in ('assignment_id', 'state')}


def delegate(ctx: Context) -> Any:
    return SERVICE.delegate(ctx)


def specialist_call(ctx: Context) -> Any:
    return SERVICE.delegate(ctx, waiting=True)


def route(ctx: Context) -> Any:
    return SERVICE.route(ctx, str(ctx.nouns['work']), refresh=bool(ctx.nouns.get('refresh')))


def credits(ctx: Context) -> Any:
    refresh = bool(ctx.nouns.get('refresh'))
    result = jev.openrouter_credits(refresh=refresh, fetch=refresh)
    if refresh and result['status'] == 'available':
        roles_changed({'project': ctx.project}, ctx)
    return result


def functionality(ctx: Context) -> Any:
    store = ctx.require_store()
    return functional_context(store, store.ticket(str(ctx.nouns['work'])).work)


CALL_NOUNS = (ROLE, Noun('task', 'The specialist contribution and relevant context.'), ASSIGNMENT, AT, RESULT,
              WAIT, KEY, CANDIDATE,
              Noun('purpose', 'Purpose of a requested new specialty.', required=False),
              Noun('contribution', 'What the new specialist must contribute.', required=False),
              Noun('context', 'Context for a missing-role request.', 'json', required=False, schema=OBJECT))

MODULE = Module(
    id='orchestration', summary='Specialist assignments, specialist calls and functional change orders.',
    purpose='Preserves user intent in functionally located work, delivery ownership and durable agent returns.',
    tables=TABLES, work_read=work_read,
    provides=(Provides('agent.roles', ROLES), Provides('agent.roles', bmad_definitions),
              Provides('orchestration', SERVICE)),
    subscriptions=(Subscription('map.changed', work_changed), Subscription('agent.role.changed', roles_changed)),
    resources=(Resource('metaform://orchestration/assignment/{assignment}', 'Assignment',
                        'Current owner, role, mode, specification and return destination.', 'inspect'),
               Resource('metaform://orchestration/bmad', 'Installed BMAD roles',
                        'Actual installed entry points, versions, menus and managed role calls.', 'bmad')),
    verbs=(
        Verb('functionality', functionality, 'Read a ticket’s local requirements and dependents as a named graph and Markdown.',
             effect='read', nouns=(Noun('work', 'Ticket id.'),)),
        Verb('route', route, 'Select specialist expertise or automatically commission the Facilitator.',
             nouns=(Noun('work', 'Ticket id.'),
                    Noun('refresh', 'Retry an unresolved selection after provider or credit recovery.', 'bool', required=False))),
        Verb('credits', credits, 'Read OpenRouter credit and observation time; refresh explicitly on demand.',
             effect='read', nouns=(Noun('refresh', 'Fetch the current account balance.', 'bool', required=False),)),
        Verb('claim', claim, 'Assign a ticket directly to a specialist, creating a missing role first.',
             nouns=(Noun('work', 'Existing root work id.'),
                    Noun('role', 'Reusable specialist name or URI; omitted uses the selected specialist. Missing roles are created.', required=False),
                    Noun('create', 'Have the Facilitator name and publish missing expertise before this ticket starts.',
                         'bool', required=False),
                    RESULT, SPEC, CANDIDATE,
                    Noun('mode', 'Adaptive or strict; absent uses the project default.', required=False),
                    Noun('session', 'Session binding for a local user-issued claim.', required=False),
                    Noun('pm_session', 'PM session following this ticket.', required=False))),
        Verb('inspect', inspect, 'Read assignment ownership, operative state and recorded return route.',
             effect='read', nouns=(ASSIGNMENT, Noun('work', 'Work id.', required=False))),
        Verb('team', team, 'Read GC team membership, descendants and independent assessments.',
             effect='read', nouns=(Noun('team', 'GC team id; absent lists the caller team or project.', required=False),)),
        Verb('bmad', bmad_inspect, 'Inspect optional installed BMAD roles, sources and menu invocation.',
             effect='read'),
        Verb('delegate', delegate, 'Assign an existing specialist a child contribution through dispatch capacity.',
             nouns=CALL_NOUNS),
        Verb('call', specialist_call, 'Call a specialist and suspend until its contribution returns.',
             nouns=CALL_NOUNS),
        Verb('handoff', SERVICE.handoff, 'Transfer the defined responsibility to a recorded successor.',
             nouns=CALL_NOUNS),
        Verb('role_requests', role_requests, 'Read specialist-role contributions awaiting their GC commission.',
             effect='read', nouns=(Noun('request', 'Role request id.', required=False),)),
        Verb('commission', SERVICE.commission, 'Commission the Facilitator for a worker\'s requested specialty.',
             nouns=(Noun('request', 'Recorded worker role request.'), ASSIGNMENT, WAIT)),
        Verb('publish_role', publish_role, 'Publish or reuse expertise and continue the original ticket; return its identity.',
             nouns=(Noun('request', 'Recorded GC commission.'),
                    Noun('duty', 'Reusable XML system prompt; omit to reuse an existing specialist.', required=False),
                    Noun('role', 'Reusable specialist name or URI; required when the commission has no name.', required=False),
                    Noun('match_reason', 'Brief reason this expertise fits the ticket.', required=False),
                    Noun('column', 'Pending board column: todo by default, or backlog when explicitly requested.', required=False),
                    ASSIGNMENT,
                    Noun('purpose', 'Specialist purpose; absent retains the requested purpose.', required=False))),
        Verb('check-in', SERVICE.check_in, 'Record progress, a blocker, result or delivery and route its continuation.',
             nouns=(Noun('state', 'running, waiting, blocked, returned, delivered or failed.'),
                    Noun('summary', 'Observed progress, result or blocker.'), ASSIGNMENT, EVIDENCE, CANDIDATE, KEY,
                    Noun('work_so_far', 'Retained work and recovery context.', required=False),
                    Noun('findings', 'Functional findings requiring corrective GC work.', 'json', required=False,
                         schema=ARRAY))),
        Verb('assess', assess, 'Deliver GC validation or a functional concern to an independent FQC assessment.',
             nouns=(Noun('summary', 'Observed outcome or functional concern.'),
                                          ASSIGNMENT, EVIDENCE, CANDIDATE, KEY)),
        Verb('change', change, 'Publish an adaptive operative revision or record a strict-mode recommendation.',
             nouns=(Noun('content', 'With section: that one record, heading first. Without: '
                                                'the whole new file, replacing every line of it.'),
                    Noun('reason', 'Connection to C(T) and the full design.'), ASSIGNMENT, SPEC, KEY,
                    Noun('section', 'Record id or heading of the one file record to replace or, if absent, add '
                                    'after the last record of its level; every other record stays.', required=False),
                    Noun('removing', 'Headings or record ids a whole-file content removes; a write dropping any '
                                     'record not named is refused.', 'json', required=False,
                         schema={'type': 'array', 'items': {'type': 'string'}}),
                    Noun('assessment', 'Responsible assessment assignment; absent uses caller.', required=False),
                    Noun('base', 'Reviewed revision; intervening changes must be reconciled.', required=False),
                    Noun('observed_limitation', 'Observed limitation of the previous approach.', required=False),
                    Noun('affected_work_ids', 'Affected root tickets.', 'json', required=False,
                         schema={'type': 'array', 'items': {'type': 'string'}}),
                    Noun('user_instruction', 'New user direction supplied by a user call.', required=False))),
        Verb('changes', inspect_change, 'Inspect committed revisions, recommendations and delivery state.',
             effect='read', nouns=(Noun('change', 'Change id.', required=False),)),
        Verb('mode', SERVICE.mode, 'Select adaptive or strict behavior for a ticket and its descendants.',
             nouns=(Noun('assignment', 'Assignment selecting the ticket/team.'),
                                          Noun('mode', 'adaptive or strict.'))),
    ),
)
