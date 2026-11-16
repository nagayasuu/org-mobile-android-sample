#!/usr/bin/env python3
"""Update one owned result comment via gh; never edit the PR body or CI settings."""

import argparse
import json
from pathlib import Path
import re
import subprocess


MARKER = '<!-- org-mobile-android-sample:verification-results:v1 -->'
HEADING = '## 検証・レビュー結果（更新）'


class ResultError(ValueError):
    """A public error code without response bodies, credentials or local paths."""


def positive_int(value):
    return type(value) is int and value > 0


def api(endpoint, method='GET', payload=None, paginate=False, jq=None):
    args = ['gh', 'api', '--hostname', 'github.com', '--method', method, endpoint,
            '-H', 'Accept: application/vnd.github+json']
    if paginate:
        args += ['--paginate', '--slurp']
    if jq is not None:
        args += ['--jq', jq]
    if payload is not None:
        args += ['--input', '-']
    try:
        result = subprocess.run(args, input=json.dumps(payload, ensure_ascii=False)
                                if payload is not None else None,
                                capture_output=True, text=True, encoding='utf-8', timeout=60)
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        raise ResultError('github-command-failed') from None
    if result.returncode:
        raise ResultError('github-command-failed')
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise ResultError('invalid-response') from None


def update(repo, pr, body, check=False):
    # Reject an issue number before accessing the shared issue-comment endpoint.
    number = api(f'repos/{repo}/pulls/{pr}', jq='.number')
    if not positive_int(number) or number != pr:
        raise ResultError('invalid-response')
    actor = api('user', jq='.id')
    if not positive_int(actor):
        raise ResultError('invalid-response')
    pages = api(f'repos/{repo}/issues/{pr}/comments?per_page=100', paginate=True)
    if not isinstance(pages, list) or not pages:
        raise ResultError('invalid-response')
    matches = []
    for page in pages:
        if not isinstance(page, list):
            raise ResultError('invalid-response')
        for comment in page:
            if not isinstance(comment, dict) or not isinstance(comment.get('body'), str):
                raise ResultError('invalid-response')
            user = comment.get('user')
            if user is None:
                continue
            if not isinstance(user, dict) or not positive_int(user.get('id')):
                raise ResultError('invalid-response')
            if user.get('id') == actor and comment['body'].startswith(MARKER+'\n'):
                if not positive_int(comment.get('id')):
                    raise ResultError('invalid-response')
                matches.append(comment)
    if len(matches) > 1:
        raise ResultError('ambiguous-comments')
    desired = MARKER+'\n'+HEADING+'\n\n'+body
    current = matches[0] if matches else None
    if current and current['body'] == desired:
        return {'status': 'unchanged',
                'comment_url': f'https://github.com/{repo}/pull/{pr}#issuecomment-{current["id"]}'}
    if check:
        return {'status': 'would-update' if current else 'would-create'}
    if current:
        response = api(f'repos/{repo}/issues/comments/{current["id"]}', 'PATCH', {'body': desired})
    else:
        response = api(f'repos/{repo}/issues/{pr}/comments', 'POST', {'body': desired})
    if not isinstance(response, dict) or not positive_int(response.get('id')):
        raise ResultError('invalid-response')
    if current and response['id'] != current['id']:
        raise ResultError('invalid-response')
    return {'status': 'updated' if current else 'created',
            'comment_url': f'https://github.com/{repo}/pull/{pr}#issuecomment-{response["id"]}'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, help='Explicit GitHub.com owner/repo')
    parser.add_argument('--pr', required=True, type=int)
    parser.add_argument('--body-file', required=True, type=Path, help='Reviewed, public UTF-8 result text')
    parser.add_argument('--check', action='store_true', help='Read-only preview; never POST or PATCH')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+', args.repo) \
            or args.repo.split('/')[-1] in ('.', '..') or args.pr <= 0:
        parser.error('use a GitHub.com owner/repo and a positive PR number')
    try:
        body = args.body_file.read_bytes().decode('utf-8')
        if not body.strip() or MARKER in body:
            raise ValueError('invalid body')
    except (OSError, ValueError):
        print(json.dumps({'status': 'error', 'error': 'invalid-body'}))
        return 2
    try:
        result = update(args.repo, args.pr, body, args.check)
    except ResultError as error:
        print(json.dumps({'status': 'error', 'error': str(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
