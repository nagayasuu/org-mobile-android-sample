#!/usr/bin/env python3
"""Aggregate explicitly supplied Codex exec JSONL events by comparable trial conditions."""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
from statistics import median


METRICS = ('input_tokens', 'cached_input_tokens', 'output_tokens')
CONDITIONS = ('condition', 'task_kind', 'revision', 'environment', 'model',
              'reasoning_effort', 'review_mode')
MEASUREMENTS = {
    'first_response_seconds': False, 'generation_seconds': False, 'completion_seconds': False,
    'tool_calls': True, 'rereads': True, 'retries': True, 'compactions': True,
    'truncations': True, 'additional_reads': True, 'source_chars': True,
    'first_edit_input_tokens': True, 'review_rework': True,
}


def number(value, integer=False):
    if isinstance(value, bool) or not isinstance(value, int if integer else (int, float)):
        raise ValueError('usage and cost must be nonnegative numbers')
    if value < 0 or (isinstance(value, float) and not math.isfinite(value)):
        raise ValueError('usage and cost must be finite and nonnegative')
    return value


def event_usage(path):
    totals = dict.fromkeys(METRICS, 0)
    completed = 0
    complete = True
    terminal = None
    with path.open(encoding='utf-8') as source:
        for line in source:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError('event must be an object')
            kind = event.get('type')
            if kind in ('turn.started', 'turn.failed', 'turn.completed'):
                terminal = kind
            if kind == 'turn.failed':
                # No usage is reported for failed turns in this supported schema.
                complete = False
            if kind == 'error':
                complete = False
            if kind != 'turn.completed':
                continue
            usage = event.get('usage')
            if not isinstance(usage, dict):
                raise ValueError('completed turn requires usage')
            values = {key: number(usage.get(key), integer=True) for key in METRICS}
            if values['cached_input_tokens'] > values['input_tokens']:
                raise ValueError('cached input cannot exceed input')
            for key in METRICS:
                totals[key] += values[key]
            completed += 1
    return totals, complete and completed > 0 and terminal == 'turn.completed'


def measurement_summary(records):
    result = {}
    for key in MEASUREMENTS:
        values = sorted(record[4]['measurements'][key] for record in records
                        if record[4]['measurements'][key] is not None)
        if not values:
            continue
        complete = len(values) == len(records)
        result[key] = {'observed': len(values), 'missing': len(records) - len(values),
                       'total': sum(values) if complete else None,
                       'median': median(values) if complete else None,
                       'p95': values[math.ceil(len(values) * 0.95) - 1]
                       if complete and len(values) >= 20 else None}
    return result


def summarize(manifest, directory):
    trials = manifest.get('trials')
    if not isinstance(trials, list) or not trials:
        raise ValueError('trials must be a nonempty list')
    groups = defaultdict(list)
    ids, paths = set(), set()
    for trial in trials:
        if not isinstance(trial, dict):
            raise ValueError('trial must be an object')
        for key in ('id', *CONDITIONS):
            if not isinstance(trial.get(key), str) or not trial[key].strip():
                raise ValueError(f'trial requires nonempty {key}')
        if trial['id'] in ids:
            raise ValueError('duplicate trial id')
        ids.add(trial['id'])
        for key in ('success', 'agents_complete'):
            if type(trial.get(key)) is not bool:
                raise ValueError(f'{key} must be a boolean')
        task_id = trial.get('task_id')
        if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
            raise ValueError('task_id must be a nonempty string or null')
        measurements = trial.get('measurements', {})
        if not isinstance(measurements, dict) or measurements.keys() - MEASUREMENTS.keys():
            raise ValueError('measurements contains unsupported keys')
        measurements = {key: number(measurements[key], integer=integer)
                        if measurements.get(key) is not None else None
                        for key, integer in MEASUREMENTS.items()}
        agents = trial.get('agents')
        if not isinstance(agents, list) or not agents:
            raise ValueError('agents must be a nonempty list')
        totals = dict.fromkeys(METRICS, 0)
        complete = trial['agents_complete']
        cost, cost_complete = 0, True
        agent_ids = set()
        for agent in agents:
            if not isinstance(agent, dict) or not isinstance(agent.get('id'), str) or not agent['id'].strip():
                raise ValueError('agent requires nonempty id')
            if agent['id'] in agent_ids:
                raise ValueError('duplicate agent id')
            agent_ids.add(agent['id'])
            events = agent.get('events')
            if events is None:
                complete = False
            elif isinstance(events, str) and events:
                path = (directory / events).resolve()
                if path in paths:
                    raise ValueError('event file reused; would double count usage')
                paths.add(path)
                usage, covered = event_usage(path)
                complete = complete and covered
                for key in METRICS:
                    totals[key] += usage[key]
            else:
                raise ValueError('events must be a path or null')
            if agent.get('cost_usd') is None:
                cost_complete = False
            else:
                cost += number(agent['cost_usd'])
        groups[tuple(trial[key] for key in CONDITIONS)].append(
            (trial['success'], complete, totals, cost if cost_complete else None,
             {'id': trial['id'], 'task_id': task_id, 'success': trial['success'],
              'measurements': measurements}))
    result = []
    for conditions, records in sorted(groups.items()):
        successes = sum(record[0] for record in records)
        complete = all(record[1] for record in records)
        totals = {key: sum(record[2][key] for record in records) for key in METRICS}
        costs = [record[3] for record in records]
        cost = sum(costs) if all(value is not None for value in costs) else None
        result.append({**dict(zip(CONDITIONS, conditions)), 'trials': len(records),
                       'successes': successes, 'success_rate': successes / len(records),
                       'usage_complete': complete, 'observed_tokens': totals,
                       'uncached_input_tokens': totals['input_tokens'] - totals['cached_input_tokens']
                       if complete else None,
                       'cache_ratio': totals['cached_input_tokens'] / totals['input_tokens']
                       if complete and totals['input_tokens'] else None,
                       'input_tokens_per_success': totals['input_tokens'] / successes
                       if complete and successes else None,
                       'cost_usd': cost,
                       'cost_usd_per_success': cost / successes
                       if complete and successes and cost is not None else None,
                       'measurements': measurement_summary(records),
                       'trial_results': [{key: value for key, value in record[4].items()
                                          if key != 'measurements'} for record in records]})
    return {'groups': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--compact', action='store_true', help='Same JSON fields without formatting whitespace')
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        if not isinstance(manifest, dict):
            raise ValueError('manifest must be an object')
        result = summarize(manifest, args.manifest.resolve().parent)
        print(json.dumps(result, ensure_ascii=False, indent=None if args.compact else 2,
                         separators=(',', ':') if args.compact else None, allow_nan=False))
    except (OSError, UnicodeError, ValueError) as error:
        # Do not echo event contents: JSONL may contain source code or private text.
        parser.exit(1, f'{type(error).__name__}: cannot aggregate; check manifest and event schema\n')


if __name__ == '__main__':
    main()
