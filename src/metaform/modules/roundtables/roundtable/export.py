"""The structured record of a table, as JSON: the discussion, its seats with the model each really was, every
submission with its outcome, Jev's four nouls and the questions it fell below the bar on, what each turn used of the
prompt cache and what it cost, and a summary. Read at any time as `roundtable://discussion<N>/export`, and written
beside the report as `<N>-<subject>.json` when the table ends.

Every judgment Jev made, or the code made for it as a repeat, is in `judgments`, with the request as sent and the raw
answer. A Roundtable 2 table's export also holds its topics in order, each with why its discussion ended and everything its
stages gave: the synthesis and its ideas, every seat's raw ranking (with the answer a repair was asked about), its
top-three and bottom-three explanations, the host's summary, and a Borda count over the rankings, labeled derived.

Every seat's availability is in it with its slots, `taken`, apart from its submissions, and the table's operational
events. `mechanical` is the report written from the record alone, by no model, so a table always has one.
"""
from __future__ import annotations

import re
from typing import Any, cast

from . import render, stages, store
from .prompts import said
from .store import NOULS

USE = ('prompt_tokens', 'cached_tokens', 'cache_write_tokens', 'cost')


def veto_reason(row: dict[str, Any]) -> str:
    """Explain only failed recorded checks, without generating a rationale or exposing passing ratings."""
    if row.get('repeat_of') is not None:
        return 'Repeated material already submitted.'
    held = render.captured(store.discussion(int(row['discussion'])))
    bars = render.floors(held)
    labels = {'new_context': 'New information', 'on_topic': 'Topic relevance', 'new': 'Novelty',
              'valuable': 'Value', 'relevant': 'Relevance', 'keep': 'Worth retaining'}
    return ' '.join(f'{labels.get(name, name)} scored {float(row[name])}, '
                    f'below the required {bars[name]}.' for name in render.failed(row)) \
        or 'No veto reason was recorded.'


def jev_cost(number: int, rows: list[dict[str, Any]]) -> float:
    """What Jev cost the table: its judgments' costs, those of rounds and failed calls among them; for a table made
    before judgments were recorded, what its submissions say."""
    judged = store.judgments(number)
    if judged:
        return round(sum(float(one['cost'] or 0) for one in judged), 6)
    return round(sum(float(row['jev_cost'] or 0) for row in rows), 6)


def build(number: int) -> dict[str, Any]:
    found = store.discussion(number)
    unjudged = store.pending(number) if found['state'] in ('ending', 'ended') else None
    rows = [*store.submissions(number), *([unjudged] if unjudged else [])]
    seated = store.seats(number)
    turns = [{
        'number': row['number'], 'turn': row.get('message_id') or render.turn(int(row['number'])),
        **({'message_id': row['message_id']} if row.get('message_id') else {}), 'round': row['round'],
        **({'topic': int(row['topic']) + 1} if row.get('topic') is not None else {}), 'seat': row['seat'], 'name': render.who(row), 'kind': row['kind'], 'outcome': render.outcome(row),
        'short': render.short(row), 'text': row['text'],
        **({'truncated': True, 'original': row['original']} if row['truncated'] else {}),
        **({'reason': row['reason']} if row['reason'] else {}),
        **({'label': row['label']} if row.get('label') else {}),
        **({'repeat_of': row['repeat_of']} if row.get('repeat_of') is not None else {}),
        'nouls': {name: row[name] for name in store.noul_names(row)} if store.nouls(row) is not None else None,
        'failed': render.failed(row),
        'link': None if row.get('unjudged') else render.link(number, int(row['number'])),
        'model': row['model'], **{key: row[key] for key in USE}, 'jev_cost': row['jev_cost'],
        'created': row['created']} for row in rows]

    def latest_model(seat: dict[str, Any]) -> str | None:
        if seat['reported']:
            return seat['reported']
        used = [row['model'] for row in rows if row['position'] == seat['position'] and row['model']]
        return used[-1] if used else None

    seats_out: list[dict[str, Any]] = []
    for seat in seated:
        own = [row for row in rows if row['position'] == seat['position']]
        seats_out.append({
            'position': seat['position'], 'seat': seat['id'], 'name': seat['name'], 'kind': seat['kind'],
            'agent': seat['agent'], 'model': seat['model'], 'reported_model': latest_model(seat),
            'session': seat['session'], 'kept': seat['kept'], 'taken': seat['taken'],
            'submitted': seat['submitted'], 'gone': seat['gone'], 'availability': availability(seat),
            'cost': round(sum(float(row['cost'] or 0) for row in own), 6),
            'prompt_tokens': sum(int(row['prompt_tokens'] or 0) for row in own),
            'cached_tokens': sum(int(row['cached_tokens'] or 0) for row in own)})
    outcomes = [render.outcome(row) for row in rows]
    kinds = {int(seat['position']): seat['kind'] for seat in seated}

    def used(kind: str) -> dict[str, Any]:
        """What one kind of seat used: OpenRouter's usage, whose prompt tokens include the cached ones; or what the
        ACP agents reported, as each adapter counts it, its cost notional on the person's subscription."""
        own = [row for row in rows if row['position'] is not None and kinds.get(int(row['position'])) == kind]
        prompt = sum(int(row['prompt_tokens'] or 0) for row in own)
        cached = sum(int(row['cached_tokens'] or 0) for row in own)
        return {'cost': round(sum(float(row['cost'] or 0) for row in own), 6), 'prompt_tokens': prompt,
                'cached_tokens': cached,
                'cache_write_tokens': sum(int(row['cache_write_tokens'] or 0) for row in own),
                **({'cached_share': round(cached / prompt, 3) if prompt else None} if kind == 'openrouter' else {})}

    return {
        'discussion': {key: found[key] for key in ('number', 'subject', 'opening', 'folder', 'state', 'reason',
                                                  'rounds', 'spend', 'reporter', 'report', 'report_error',
                                                  'created', 'ended')}
        | {'round': found['round'], 'spent': round(float(found['spent'] or 0), 6),
           **({'stage': found['stage'], 'topic': int(found['topic']) + 1, 'host': found['host'],
               'synthesizer': found['synthesizer']} if found.get('stage') else {}),
           'keep': render.captured(found).get('keep'), 'snapshot': found.get('snapshot'),
           'rules': render.rules([str(seat['name']) for seat in seated], found),
           'continuation': found.get('continuation')},
        'seats': seats_out,
        **({'topics': topics_of(number)} if found.get('stage') else {}),
        'submissions': turns,
        'judgments': store.judgments(number),
        'events': store.events(number),
        **({'mechanical_report': found['mechanical']} if found.get('mechanical') else {}),
        'summary': {
            'turns': sum(1 for one in outcomes if one != 'comment'),
            **{one: outcomes.count(one) for one in ('kept', 'vetoed', 'none', 'comment', 'unjudged')},
            **({'over512': outcomes.count('over512')} if 'over512' in outcomes else {}),
            **({'pass': outcomes.count('pass')} if 'pass' in outcomes else {}),
            'truncated': sum(1 for row in rows if row['truncated']),
            'rounds_run': found['round'], 'spent': round(float(found['spent'] or 0), 6),
            'jev_cost': jev_cost(number, rows),
            'openrouter': used('openrouter'), 'acp': used('acp')},
        **({'not_recorded': limitations(found)} if limitations(found) else {})}


def safe_shared(native: dict[str, Any]) -> dict[str, Any]:
    """Whitelist participant-readable material from an owner export, without consulting or changing its store.

    Accepted prose is preserved. Audit identities, unsuccessful attempts, original replies, judgments, prompts and
    operational records never enter this projection. Historical accepted messages retain their cited T labels.
    """
    discussion = cast(dict[str, Any], native.get('discussion') or {})
    public_ids = bool(cast(dict[str, Any], discussion.get('snapshot') or {}).get('message_ids'))
    seats = cast(list[dict[str, Any]], native.get('seats') or [])
    roles = [cast(dict[str, Any], discussion[key]) for key in ('host', 'synthesizer')
             if isinstance(discussion.get(key), dict)]
    identities = {str(row[key]) for row in [*seats, *roles]
                  for key in ('seat', 'id', 'agent', 'model', 'reported_model', 'profile_key') if row.get(key)}
    aliases: dict[str, str] = {}

    def named(row: dict[str, Any], fallback: str, *, roster: bool = False) -> str:
        source = str(row.get('seat') or row.get('id') or '')
        if source in aliases:
            return aliases[source]
        name = str(row.get('name') or '').strip()
        if not name or (not roster and name not in aliases.values()) or \
                any(re.search(r'(?<!\w)' + re.escape(value) + r'(?!\w)', name, re.IGNORECASE)
                    for value in identities):
            name = fallback
        if source:
            aliases[source] = name
        return name

    public_seats = [{'name': named(row, f'Participant {at}', roster=True)} for at, row in enumerate(seats, 1)]
    for role, fallback in zip(roles, ('Host', 'Synthesizer'), strict=False):
        named(role, fallback, roster=True)

    def reason(text: Any) -> str:
        result = str(text or '')
        for value in sorted(identities, key=lambda value: (len(value), value), reverse=True):
            result = re.sub(r'(?<!\w)' + re.escape(value) + r'(?!\w)',
                            lambda _match, value=value: aliases.get(value, 'a participant'), result, flags=re.IGNORECASE)
        return result

    messages: list[dict[str, Any]] = []
    for row in cast(list[dict[str, Any]], native.get('submissions', native.get('turns')) or []):
        if row.get('outcome') not in ('kept', 'comment') or row.get('accepted') is False:
            continue
        public_id = str(row.get('message_id') or '')
        if not re.fullmatch(r'R\d+-\d+', public_id):
            if public_ids:
                continue  # phase directives and private attempt numbers are not public contributions
            legacy = str(row.get('turn') or '')
            public_id = legacy if re.fullmatch(r'(?:R\d+-\d+|T\d+)', legacy) else \
                f'T{row.get("number", row.get("n", len(messages) + 1))}'
        chair = row.get('outcome') == 'comment'
        messages.append({'message_id': public_id, 'turn': public_id,
                         **({'topic': row['topic']} if isinstance(row.get('topic'), int) else {}),
                         'name': 'Chair' if chair else named(row, 'Participant'),
                         'kind': 'chair' if chair else 'seat', 'text': str(row.get('text') or '')})

    def stage(row: Any, fallback: str) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        item = cast(dict[str, Any], row)
        if item.get('error'):
            return None
        return {'name': named(item, fallback), 'text': str(item.get('text') or '')}

    topics: list[dict[str, Any]] = []
    for topic in cast(list[dict[str, Any]], native.get('topics') or []):
        synthesis = stage(topic.get('synthesis'), 'Synthesizer')
        original_synthesis = cast(dict[str, Any], topic.get('synthesis') or {})
        ideas = [{key: str(idea.get(key) or '') for key in ('id', 'name', 'summary')}
                 for idea in cast(list[dict[str, Any]], original_synthesis.get('ideas') or [])] \
            if synthesis is not None else []
        if synthesis is not None:
            synthesis['ideas'] = ideas
        ids = [one['id'] for one in ideas]
        rankings: list[dict[str, Any]] = []
        for row in cast(list[dict[str, Any]], topic.get('rankings') or []):
            raw_ranking = row.get('ranking')
            ranking = cast(list[str], raw_ranking) if isinstance(raw_ranking, list) and \
                all(isinstance(one, str) for one in cast(list[Any], raw_ranking)) else None
            public = stage(row, 'Participant')
            if public is not None and ranking is not None and set(ranking) == set(ids) and len(ranking) == len(ids):
                rankings.append({**public, 'ranking': list(ranking)})
        counted = cast(dict[str, Any], topic.get('borda') or {})
        points = cast(dict[str, Any], counted.get('points') or {})
        topics.append({**{key: topic[key] for key in ('number', 'name', 'title', 'text') if key in topic},
                       'why': reason(topic.get('why')), 'synthesis': synthesis, 'rankings': rankings,
                       **{key: [public for row in cast(list[dict[str, Any]], topic.get(key) or [])
                                if (public := stage(row, 'Participant')) is not None]
                          for key in ('top_three', 'bottom_three')},
                       'host_summary': stage(topic.get('host_summary'), 'Host'),
                       'borda': {'derived': True, 'points': {key: points[key] for key in ids
                                                           if isinstance(points.get(key), (int, float))},
                                 'order': [key for key in counted.get('order', []) if key in ids]}
                       if counted and ids else None})
    return {'discussion': {**{key: discussion[key] for key in ('subject', 'opening', 'state') if key in discussion},
                           'reason': reason(discussion.get('reason'))},
            'seats': public_seats, 'submissions': messages, 'topics': topics,
            'summary': {'messages': len(messages)}}


def shared_mechanical(shared: dict[str, Any]) -> str:
    """The participant-readable Markdown record, from the same safe projection as its JSON companion."""
    discussion = cast(dict[str, Any], shared['discussion'])
    lines = [f'# {discussion.get("subject") or "Roundtable record"}']
    if discussion.get('reason'):
        lines.append(f'Ended: {discussion["reason"]}')
    if discussion.get('opening'):
        lines.append(f'## Opening\n\n{discussion["opening"]}')
    if shared['seats']:
        lines.append('## Participants\n\n' + '\n'.join(f'- {one["name"]}' for one in shared['seats']))
    if shared['submissions']:
        lines.append('## Discussion')
        lines.extend(f'### {one["message_id"]} · {one["name"]}\n\n{one["text"]}' for one in shared['submissions'])
    for topic in shared['topics']:
        lines.append(f'## Topic {topic.get("number", "")}: {topic.get("title") or "Discussion"}')
        if topic.get('text'):
            lines.append(str(topic['text']))
        if topic.get('why'):
            lines.append(f'Discussion ended: {topic["why"]}')
        synthesis = topic.get('synthesis')
        if synthesis:
            lines.append(f'### Ideas · {synthesis["name"]}\n\n' + '\n'.join(
                f'- **{idea["id"]}: {idea["name"]}**: {idea["summary"]}' for idea in synthesis['ideas']))
        if topic.get('borda'):
            counted = topic['borda']
            lines.append('### Borda result\n\n' + '\n'.join(
                f'- {key}: {counted["points"].get(key, 0)} points' for key in counted['order']))
        for key, title in (('rankings', 'Rankings'), ('top_three', 'Top three'), ('bottom_three', 'Bottom three')):
            if topic.get(key):
                lines.append(f'### {title}\n\n' + '\n\n'.join(
                    f'**{one["name"]}**\n\n{one["text"]}' for one in topic[key]))
        host = topic.get('host_summary')
        if host:
            lines.append(f'### Host summary · {host["name"]}\n\n{host["text"]}')
    return '\n\n'.join(lines) + '\n'


def availability(seat: dict[str, Any]) -> dict[str, Any]:
    """A seat's availability as the record gives it: its state, and when it is not active, why, since when, its
    failures in a row by kind and when it is probed next."""
    state = str(seat.get('availability') or 'active')
    if state == 'active':
        return {'state': state}
    return {'state': state, 'reason': seat['reason'], 'since': seat['since'], 'failures': seat['failures'],
            'failing': seat['failing'], 'retry_at': seat['retry_at']}


def mechanical(number: int) -> str:
    """The report written from the record alone, by no model, so a table always has one: why it ended, the opening,
    each seat's slots, submissions, kept turns and availability; then for each topic its ideas as synthesized, every
    seat's ranking with the derived Borda count, the top-three and bottom-three explanations and the host's summary;
    for a table without topics, what entered its discussion."""
    found = store.discussion(number)
    seated = store.seats(number)
    lines = [said('mechanical_title', discussion=number, subject=found['subject']),
             said('mechanical_intro', reason=found['reason'] or ''),
             said('record_opening', opening=found['opening']),
             said('mechanical_seats', seats='\n'.join(
                 said('mechanical_seat', seat=seat['name'], id=seat['id'], slots=seat['taken'],
                      submitted=seat['submitted'], kept=seat['kept'],
                      state=f'left: {seat["gone"]}' if seat['gone'] else str(seat['availability']))
                 for seat in seated))]
    if not found.get('stage'):
        entered = [render.entry(row) for row in store.submissions(number) if render.entered(row)]
        lines.append(said('mechanical_turns', turns='\n\n'.join(entered) or said('mechanical_nothing')))
        return '\n\n'.join(lines) + '\n'
    staged = store.staged(number)
    for topic in store.topics(number):
        own = [one for one in staged if int(one['topic']) == int(topic['topic'])]
        lines.append(said('mechanical_topic', number=int(topic['topic']) + 1, title=topic['title']))
        synthesis = next((one for one in reversed(own) if one['stage'] == 'synthesis' and one['ideas']), None)
        listed = cast(list[dict[str, Any]], synthesis['ideas']) if synthesis else []
        lines.append(said('mechanical_ideas', seat=synthesis['name'], ideas=render.idea_lines(listed)) if synthesis
                     else said('mechanical_no_ideas'))
        if any(one['stage'] == 'ranking' for one in own):
            lines.append(said('mechanical_rankings', rankings=render.stage_lines(own, 'ranking')))
            if listed:
                counted = stages.borda(listed, [one['ranking'] for one in own if one['stage'] == 'ranking'])
                titles = {str(one['id']): str(one['name']) for one in listed}
                lines.append(said('mechanical_borda', label=counted['label'], order='\n'.join(
                    said('mechanical_borda_line', id=one, title=titles[one], points=counted['points'][one])
                    for one in counted['order'])))
        if any(one['stage'] == 'top_three' for one in own):
            lines.append(said('mechanical_tops', text=render.stage_lines(own, 'top_three')))
        if any(one['stage'] == 'bottom_three' for one in own):
            lines.append(said('mechanical_bottoms', text=render.stage_lines(own, 'bottom_three')))
        host = next((one for one in reversed(own) if one['stage'] == 'host_summary' and one['text']), None)
        if host:
            lines.append(said('mechanical_host', seat=host['name'], text=host['text']))
    return '\n\n'.join(lines) + '\n'


STAGE_USE = ('model', *USE)


def stage_of(row: dict[str, Any]) -> dict[str, Any]:
    """One answer of a stage: who gave it, its text whole, its original when cut, and what it used."""
    return {'seat': row['seat'], 'name': row['name'], 'text': row['text'],
            **({'truncated': True, 'original': row['original']} if row['truncated'] else {}),
            **({'error': row['error']} if row['error'] else {}),
            **{key: row[key] for key in STAGE_USE if row.get(key) is not None}, 'created': row['created']}


def topics_of(number: int) -> list[dict[str, Any]]:
    """Every topic of a Roundtable 2 table, in order, with everything its stages gave and the Borda count derived
    from its rankings."""
    found: list[dict[str, Any]] = []
    staged = store.staged(number)
    for topic in store.topics(number):
        own = [one for one in staged if int(one['topic']) == int(topic['topic'])]
        synthesis = next((one for one in reversed(own) if one['stage'] == 'synthesis'), None)
        listed: list[dict[str, Any]] = cast(list[dict[str, Any]], synthesis['ideas'] or []) if synthesis else []
        host = next((one for one in reversed(own) if one['stage'] == 'host_summary'), None)
        rankings = [{**stage_of(one), 'ranking': one['ranking'],
                     **({'repair_asked_about': one['repair']} if one['repair'] else {})}
                    for one in own if one['stage'] == 'ranking']
        found.append({
            'number': int(topic['topic']) + 1, 'name': topic['name'], 'title': topic['title'], 'text': topic['text'],
            **{key: topic[key] for key in ('opened', 'discussed', 'closed')},
            'advanced_by': topic['advanced_by'], 'why': topic['why'],
            'sufficiency': [{'round': one['round'], **one['nouls'], 'settled': one['decision'] == 'settled',
                             'cost': one['cost']} for one in store.judgments(number, int(topic['topic']))
                            if one['kind'] == 'sufficiency' and one['nouls'] is not None],
            'synthesis': {**stage_of(synthesis), 'ideas': listed} if synthesis else None,
            'rankings': rankings,
            'top_three': [stage_of(one) for one in own if one['stage'] == 'top_three'],
            'bottom_three': [stage_of(one) for one in own if one['stage'] == 'bottom_three'],
            'host_summary': stage_of(host) if host else None,
            'borda': stages.borda(listed, [one['ranking'] for one in rankings]) if listed else None})
    return found


# ----------------------------------------------------------------------------------------------- the self-contained files
#
# Three files a person downloads, as table 1's record was laid out: the discussion (the table, its legend, its summary
# and every turn), one file per seat (its result and every turn it took, what it received and what it replied), and
# all of it in one. The four questions are written once, in the legend; every entry gives only its scores array.

OUTCOMES = ('kept', 'vetoed', 'none', 'pass', 'comment', 'unjudged', 'over512')


def rows_of(number: int) -> list[dict[str, Any]]:
    """Every submission, with the one Jev never judged after them once the table is ending or has ended."""
    found = store.discussion(number)
    unjudged = store.pending(number) if found['state'] in ('ending', 'ended') else None
    return [*store.submissions(number), *([unjudged] if unjudged else [])]


def imported_of(found: dict[str, Any]) -> dict[str, Any]:
    given: Any = found.get('imported')
    return cast(dict[str, Any], given) if isinstance(given, dict) else {}


def limitations(found: dict[str, Any]) -> list[str]:
    """Preserve source capture limits and disclose missing historical judgment settings."""
    own: Any = imported_of(found).get('not_recorded')
    missing = [str(item) for item in cast(list[Any], own)] if isinstance(own, list) else ([str(own)] if own else [])
    if not render.captured(found):
        missing.append('Discussion-time rules, criterion definitions and threshold were not recorded. '
                       'Failed criterion lists are unknown and exclusion counts are null.')
    return missing


def exclusions(found: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, int | None]:
    held = render.captured(found)
    repeats = 'repeat' in (held.get('failed') or {}) or any(row.get('repeat_of') is not None for row in rows)
    criteria = cast(dict[str, Any], held.get('criteria') or {})
    names = [*criteria, *(['repeat'] if repeats else [])] if held else NOULS
    failed = [name for row in rows if render.outcome(row) == 'vetoed' for name in render.failed(row)]
    return {name: failed.count(name) if held else None for name in names}


def legend(found: dict[str, Any]) -> dict[str, str]:
    """What every entry's fields mean, said once. An imported table keeps the legend its record came with."""
    own = imported_of(found).get('legend')
    if isinstance(own, dict):
        return {str(key): str(value) for key, value in cast(dict[str, Any], own).items()}
    held = render.captured(found)
    criteria = cast(dict[str, Any], held.get('criteria') or {})
    questions = ' '.join(f'({name}) {question["instructions"]}' for name, question in criteria.items())
    threshold = (', '.join(f'{name} {bar:.2f}' for name, bar in render.floors(held).items()) if held.get('floors')
                 else f"{held['keep']:.2f}" if held.get('keep') is not None else 'no novelty threshold')
    named = ', '.join(criteria) or ', '.join(NOULS)
    return {
        'scores': f"Every score array is [{named}]: Jev's probability that each of its questions is true of the "
                  f'turn. {questions} A turn entered the discussion only at {threshold} or above on every one; one '
                  'that repeated an earlier submission was vetoed as a repeat before Jev was asked.',
        'failed': ('The questions a vetoed turn fell below the bar on: ' + ', '.join(criteria) + '.'
                   if held else 'Discussion-time criteria and threshold were not recorded; failed lists are unknown.'),
        'outcome': 'kept (Jev kept it and it entered) | vetoed (it fell below the bar on at least one question) | '
                   'none (the seat made no submission; reason says why) | comment (the chair\'s, never judged) | '
                   'unjudged (the table ended before Jev judged it)',
        'use': 'prompt_tokens, cached_tokens and cache_write_tokens per turn: for an OpenRouter seat as OpenRouter '
               'counts them, its prompt tokens including the cached ones; for an ACP seat as its agent reports them '
               '(Claude Code counts input tokens without its cache reads and writes). cost in US dollars; an ACP '
               "seat's is the agent's notional figure on the person's subscription. jev_cost is Jev's judgment.",
        'roles': "'received' is what the roundtable sent the seat: the rules and the opening first, then the turns "
                 "since its last reply, a vetoed one as its short line. 'replied' is what the seat answered.",
        'exact_text': 'Every text received or replied is exactly as sent and stored, unaltered.'}


def scored(row: dict[str, Any]) -> dict[str, Any]:
    """One turn as an entry of the discussion: its number, round, seat by name, outcome, scores and text."""
    return {'n': row['number'], 'turn': row.get('message_id') or render.turn(int(row['number'])),
            **({'message_id': row['message_id']} if row.get('message_id') else {}),
            **({'topic': int(row['topic']) + 1} if row.get('topic') is not None else {}),
            'round': row['round'], 'seat': render.who(row), 'outcome': render.outcome(row),
            **({'scores': store.nouls(row)} if store.nouls(row) is not None else {}),
            **({'failed': render.failed(row), 'veto_reason': veto_reason(row)}
               if render.outcome(row) == 'vetoed' else {}),
            **({'text': row['text']} if row['text'] else {}),
            **({'truncated': True, 'original': row['original']} if row['truncated'] else {}),
            **({'reason': row['reason']} if row['reason'] else {}),
            **{key: row[key] for key in ('model', *USE, 'jev_cost') if row.get(key) is not None},
            **({'created': row['created']} if row.get('created') else {})}


def seat_stats(seat: dict[str, Any], rows: list[dict[str, Any]], imported: dict[str, Any]) -> dict[str, Any]:
    """One seat's result: kept against taken, its outcomes, which questions excluded its turns, what it used and
    cost, and the model it really ran."""
    own = [row for row in rows if row['position'] == seat['position']]
    outcomes = [render.outcome(row) for row in own]
    prompt = sum(int(row['prompt_tokens'] or 0) for row in own)
    cached = sum(int(row['cached_tokens'] or 0) for row in own)
    ran = sorted({str(row['model']) for row in own if row.get('model')} | ({str(seat['reported'])}
                                                                           if seat['reported'] else set()))
    session: Any = cast(dict[str, Any], imported.get('sessions') or {}).get(str(seat['position']))
    return {'position': seat['position'], 'name': seat['name'], 'seat': seat['id'], 'kind': seat['kind'],
            'asked': seat['model'] or seat['id'], 'ran': ran, 'kept': seat['kept'], 'taken': seat['taken'],
            'outcomes': {one: outcomes.count(one) for one in OUTCOMES if one in outcomes},
            'excluded_by': exclusions(store.discussion(int(seat['discussion'])), own),
            'prompt_tokens': prompt, 'cached_tokens': cached,
            'cache_write_tokens': sum(int(row['cache_write_tokens'] or 0) for row in own),
            'cache_hits': sum(1 for row in own if int(row['cached_tokens'] or 0) > 0),
            'turns_with_use': sum(1 for row in own if row.get('prompt_tokens') is not None),
            **({'cached_share': round(cached / prompt, 3) if prompt else None} if seat['kind'] == 'openrouter' else {}),
            'cost': round(sum(float(row['cost'] or 0) for row in own), 6),
            'jev_cost': round(sum(float(row['jev_cost'] or 0) for row in own), 6),
            **({'gone': seat['gone']} if seat['gone'] else {}),
            'submitted': seat['submitted'], 'availability': availability(seat),
            **({'session': seat['session']} if seat['session'] else {}),
            **({'session_reported': session} if isinstance(session, dict) else {})}


def stats(number: int) -> dict[str, Any]:
    """A table's stats and each seat's, and what each turn used."""
    found = store.discussion(number)
    rows = rows_of(number)
    imported = imported_of(found)
    seated = [seat_stats(seat, rows, imported) for seat in store.seats(number)]
    outcomes = [render.outcome(row) for row in rows]
    return {'discussion': number, 'turns': sum(1 for one in outcomes if one != 'comment'),
            'outcomes': {one: outcomes.count(one) for one in OUTCOMES if one in outcomes},
            'excluded_by': exclusions(found, rows),
            'spent': round(float(found['spent'] or 0), 6),
            'jev_cost': jev_cost(number, rows),
            'cost': round(sum(float(row['cost'] or 0) for row in rows), 6),
            'prompt_tokens': sum(int(row['prompt_tokens'] or 0) for row in rows),
            'cached_tokens': sum(int(row['cached_tokens'] or 0) for row in rows),
            'cache_write_tokens': sum(int(row['cache_write_tokens'] or 0) for row in rows),
            'cache_hits': sum(1 for row in rows if int(row['cached_tokens'] or 0) > 0),
            'seats': seated,
            'per_turn': [{'n': row['number'], 'round': row['round'], 'seat': render.who(row),
                          **({'message_id': row['message_id']} if row.get('message_id') else {}),
                          'outcome': render.outcome(row), **{key: row.get(key) for key in ('model', *USE, 'jev_cost')}}
                         for row in rows if row['kind'] != 'chair'],
            **({'not_recorded': limitations(found)} if limitations(found) else {})}


def context(number: int, position: int) -> list[dict[str, Any]]:
    """A seat's context as it arrived: every message the table sent it and what it replied, in order, each reply
    with the turn it became, its outcome and scores. A reply is matched to the seat's next submission whose text,
    or full original, it is; one that matches none (the report, or a reply the first version refused) stands alone."""
    seat = next((one for one in store.seats(number) if one['position'] == position), None)
    if seat is None:
        raise store.Missing(f'No seat {position} at roundtable {number}.')
    own = [row for row in rows_of(number) if row['position'] == position and row['kind'] == 'seat']
    turns: list[dict[str, Any]] = []
    at = 0
    for message in cast(list[dict[str, Any]], seat['messages'] or []):
        content = message.get('content')
        text = content if isinstance(content, str) else ''.join(
            str(part.get('text') or '') for part in cast(list[dict[str, Any]], content or []))
        if message.get('role') != 'assistant':
            turns.append({'received': text})
            continue
        entry: dict[str, Any] = {'replied': text}
        match = next((index for index in range(at, len(own))
                      if text.strip() in (str(own[index]['text']).strip(), str(own[index]['original'] or '').strip())),
                     None)
        if match is not None:
            row, at = own[match], match + 1
            entry.update({'n': row['number'], 'turn': row.get('message_id') or render.turn(int(row['number'])),
                          **({'message_id': row['message_id']} if row.get('message_id') else {}),
                          'round': row['round'], 'outcome': render.outcome(row),
                          **({'scores': store.nouls(row)} if store.nouls(row) is not None else {}),
                          **({'failed': render.failed(row)} if render.outcome(row) == 'vetoed' else {})})
        if turns and 'replied' not in turns[-1]:
            turns[-1].update(entry)
        else:
            turns.append(entry)
    return turns


def table_of(found: dict[str, Any], seated: list[dict[str, Any]]) -> dict[str, Any]:
    return {**{key: found[key] for key in ('number', 'subject', 'opening', 'state', 'reason', 'round', 'rounds',
                                           'spend', 'reporter', 'report_error', 'created', 'ended')},
            'spent': round(float(found['spent'] or 0), 6), 'snapshot': found.get('snapshot'),
            **({'stage': found['stage'], 'topic': int(found['topic']) + 1} if found.get('stage') else {}),
            **({'not_recorded': limitations(found)} if limitations(found) else {}),
            'seats_in_order': [str(seat['name']) for seat in seated],
            **({'imported': {key: value for key, value in imported_of(found).items()
                             if key not in ('legend', 'sessions', 'session_logs')}} if imported_of(found) else {})}


def discussion_file(number: int) -> dict[str, Any]:
    """The discussion: the table, the legend, the summary and every turn."""
    found = store.discussion(number)
    seated = store.seats(number)
    counted = stats(number)
    return {'table': table_of(found, seated), 'legend': legend(found),
            'rules': render.rules([str(seat['name']) for seat in seated], found),
           'continuation': found.get('continuation'),
            'summary': {key: counted[key] for key in counted if key not in ('seats', 'per_turn', 'discussion')}
            | {'by_seat': {seat['name']: {'kept': seat['kept'], 'taken': seat['taken'], 'outcomes': seat['outcomes'],
                                          'excluded_by': seat['excluded_by']} for seat in counted['seats']}},
            'transcript': [scored(row) for row in rows_of(number)],
            **({'topics': topics_of(number)} if found.get('stage') else {})}


def seat_file(number: int, position: int) -> dict[str, Any]:
    """One seat's own file: its result, and every turn it took with what it received and what it replied."""
    found = store.discussion(number)
    seated = store.seats(number)
    seat = next((one for one in seated if one['position'] == position), None)
    if seat is None:
        raise store.Missing(f'No seat {position} at roundtable {number}.')
    imported = imported_of(found)
    logs = cast(dict[str, Any], imported.get('session_logs') or {}).get(str(position))
    return {'name': seat['name'], 'seat': seat['id'], 'kind': seat['kind'], 'table': table_of(found, seated),
            'legend': legend(found), 'result': seat_stats(seat, rows_of(number), imported),
            'turns': context(number, position), **({'session_log': logs} if logs else {})}


def all_in_one(number: int) -> dict[str, Any]:
    """The discussion and every seat's file in one, the legend and the table once at the top."""
    whole = discussion_file(number)
    seats_out = [{key: value for key, value in seat_file(number, int(seat['position'])).items()
                  if key not in ('legend', 'table')} for seat in store.seats(number)]
    return {**whole, 'seats': seats_out}


def file_name(seat: dict[str, Any]) -> str:
    return f'{int(seat["position"]):02d}-{re.sub(r"[^A-Za-z0-9]+", "-", str(seat["name"])).strip("-")}.json'
