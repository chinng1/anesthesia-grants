#!/usr/bin/env python3
"""Monthly health check for grants.json: broken links and deadlines that need attention.

Prints a Markdown report. It never edits grants.json; a person reviews the report
and makes the changes. Standard library only.

    python3 check_grants.py                  # full check, report to stdout
    python3 check_grants.py --no-links       # deadlines only (fast)
    python3 check_grants.py --today 2027-01-10 --out report.md
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
from pathlib import Path
import re
import ssl
import urllib.error
import urllib.request

SOON_DAYS = 42          # CLAUDE.md: "soon" means under 6 weeks out
STALE_DATA_DAYS = 120   # warn if _meta.updated is older than this
USER_AGENT = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/130.0 Safari/537.36')
BLOCKED_CODES = {401, 403, 429}  # many funder sites block bots but are fine

MONTHS = {m: i for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], start=1)}
DATE_RE = re.compile(
    r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|'
    r'Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(\d{1,2})(?:st|nd|rd|th)?'
    r'(?:,?\s+(20\d\d))?\b')
YEAR_RE = re.compile(r'\b(20\d\d)\b')


def mentioned_dates(text):
    """Yield (month, day, year_or_None) for every 'Mon D[, YYYY]' in text."""
    for month, day, year in DATE_RE.findall(text):
        m, d = MONTHS[month[:3].lower()], int(day)
        if 1 <= d <= 31:
            yield m, d, int(year) if year else None


def next_occurrence(month, day, today):
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            return None
        if candidate >= today:
            return candidate
    return None


def check_deadline(grant, today):
    """Return (problem, suggestion) tuples for one grant's deadline text."""
    text = grant.get('deadline', '')
    kind = grant.get('deadline_type')
    issues = []
    upcoming = []
    for month, day, year in mentioned_dates(text):
        if year:
            try:
                when = date(year, month, day)
            except ValueError:
                continue
            if when < today:
                issues.append((f'mentions {when:%b %-d, %Y}, which has passed',
                               'find the next cycle date'))
            else:
                upcoming.append(when)
        else:
            when = next_occurrence(month, day, today)
            if when:
                upcoming.append(when)
    if not issues:
        years = {int(y) for y in YEAR_RE.findall(text)}
        if years and max(years) < today.year:
            issues.append((f'only mentions {max(years)}, a past year', 'update to the current cycle'))
    soonest = min(upcoming) if upcoming else None
    is_soon = soonest is not None and (soonest - today).days <= SOON_DAYS
    if is_soon and kind != 'soon':
        issues.append((f'next date {soonest:%b %-d} is {(soonest - today).days} day(s) away',
                       'set deadline_type to "soon"'))
    if kind == 'soon' and not is_soon:
        issues.append(('marked "soon" but no date in the next 6 weeks',
                       'set deadline_type to "ok" or "unknown"'))
    return issues


def check_url(url, timeout=20):
    """Return (status, detail). status: ok | blocked | broken."""
    context = ssl.create_default_context()
    for method in ('HEAD', 'GET'):
        request = urllib.request.Request(url, method=method, headers={
            'User-Agent': USER_AGENT, 'Accept': 'text/html,*/*;q=0.8'})
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                return 'ok', str(response.status)
        except urllib.error.HTTPError as exc:
            if method == 'HEAD' and exc.code in (400, 403, 404, 405, 500, 501, 503):
                continue  # some servers reject HEAD; retry with GET
            if exc.code in BLOCKED_CODES:
                return 'blocked', f'HTTP {exc.code}'
            return 'broken', f'HTTP {exc.code}'
        except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError, ValueError) as exc:
            reason = getattr(exc, 'reason', exc)
            if method == 'HEAD':
                continue
            return 'broken', str(reason)[:100]
    return 'broken', 'no response'


def md_escape(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def build_report(db, today, check_links, workers):
    grants = db['grants']
    lines = [f'# Grant database check — {today:%B %-d, %Y}', '',
             f'{len(grants)} grants, database v{db["_meta"].get("version", "?")}, '
             f'last updated {db["_meta"].get("updated", "?")}.', '']

    try:
        updated = date.fromisoformat(db['_meta'].get('updated', ''))
        age = (today - updated).days
        if age > STALE_DATA_DAYS:
            lines += [f'> ⚠️ The database was last updated {age} days ago. '
                      'Consider a full review of deadlines and amounts.', '']
    except ValueError:
        pass

    deadline_rows = []
    for g in grants:
        for problem, fix in check_deadline(g, today):
            deadline_rows.append((g, problem, fix))
    lines += [f'## Deadlines needing attention ({len(deadline_rows)})', '']
    if deadline_rows:
        lines += ['| Grant | Deadline text | Problem | Suggested fix |', '|---|---|---|---|']
        for g, problem, fix in deadline_rows:
            lines.append(f'| [{md_escape(g["title"])}]({g["url"]}) `{g["id"]}` | '
                         f'{md_escape(g["deadline"])} | {problem} | {fix} |')
    else:
        lines.append('None.')
    lines.append('')

    unknown = sum(1 for g in grants if g.get('deadline_type') == 'unknown')
    lines += [f'{unknown} grants have deadline_type "unknown" (no checkable date); '
              'spot-check a few each month.', '']

    if check_links:
        urls = [g['url'] for g in grants]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(check_url, urls))
        broken = [(g, d) for g, (s, d) in zip(grants, results) if s == 'broken']
        blocked = [(g, d) for g, (s, d) in zip(grants, results) if s == 'blocked']
        ok = sum(1 for s, _ in results if s == 'ok')
        lines += [f'## Links: {ok} OK, {len(blocked)} blocked bots, {len(broken)} broken', '']
        if broken:
            lines += ['### Broken (check these by hand)', '',
                      '| Grant | URL | Error |', '|---|---|---|']
            for g, detail in broken:
                lines.append(f'| {md_escape(g["title"])} `{g["id"]}` | {g["url"]} | {md_escape(detail)} |')
            lines.append('')
        if blocked:
            lines += ['<details><summary>Blocked automated checks (usually fine; '
                      'see Known URL Caveats in CLAUDE.md)</summary>', '']
            lines += [f'- {md_escape(g["title"])}: {g["url"]} ({d})' for g, d in blocked]
            lines += ['', '</details>', '']

    lines += ['---', 'Generated by `check_grants.py`. It never changes grants.json: '
              'fix entries by hand (or with Claude), commit, and push to update the site.']
    return '\n'.join(lines), len(deadline_rows), (len(broken) if check_links else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', type=Path, default=Path(__file__).parent / 'grants.json')
    parser.add_argument('--today', type=date.fromisoformat, default=date.today())
    parser.add_argument('--no-links', action='store_true', help='skip the URL check')
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--out', type=Path, help='also write the report to this file')
    args = parser.parse_args()

    db = json.loads(args.json.read_text())
    report, n_deadlines, n_broken = build_report(db, args.today, not args.no_links, args.workers)
    print(report)
    if args.out:
        args.out.write_text(report)
    print(f'\nSummary: {n_deadlines} deadline issues, {n_broken} broken links.', flush=True)


if __name__ == '__main__':
    main()
