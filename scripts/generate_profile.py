#!/usr/bin/env python3
"""Render a classic terminal profile from GitHub's public data. No dependencies."""

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import textwrap
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
COLORS = ['#22252b', '#35424c', '#506774', '#7394a1', '#9abcca']
LANGUAGE_COLORS = ['#91a6b8', '#747d89', '#555e69', '#414953']


def fetch(url):
    headers = {'User-Agent': 'github-terminal-profile', 'Accept': 'application/vnd.github+json'}
    if url.startswith('https://api.github.com/') and os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                return response.read().decode('utf-8')
        except (HTTPError, URLError, TimeoutError) as error:
            if isinstance(error, HTTPError) and error.code < 500 and error.code != 429:
                raise
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def repositories(username):
    result = []
    page = 1
    while True:
        batch = json.loads(fetch(
            f'https://api.github.com/users/{username}/repos?type=owner&per_page=100&page={page}'
        ))
        result.extend(batch)
        if len(batch) < 100:
            return result
        page += 1


def public_events(username):
    result = []
    # GitHub's events timeline exposes at most 300 events in its 30-day window.
    for page in range(1, 4):
        batch = json.loads(fetch(
            f'https://api.github.com/users/{username}/events/public?per_page=100&page={page}'
        ))
        result.extend(batch)
        if len(batch) < 100:
            break
    return result


def activity_summary(events, now):
    cutoff = now - timedelta(days=30)
    recent = []
    daily = Counter()
    kinds = Counter()
    log = {}
    for event in events:
        if not event.get('public', True):
            continue
        created = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
        if not cutoff <= created <= now:
            continue
        recent.append(event)
        daily[created.date()] += 1
        kinds[event['type']] += 1
        log.setdefault(created.date(), Counter())[event['type']] += 1
    return {'total': len(recent), 'daily': daily, 'kinds': kinds, 'log': log}


def contribution_summary(calendar, today):
    active = sorted(day for day, level in calendar.days.items() if level > 0 and day <= today)
    longest = current = 0
    previous = None
    for day in active:
        current = current + 1 if previous and day - previous == timedelta(days=1) else 1
        longest = max(longest, current)
        previous = day
    return {'active_days': len(active), 'longest_streak': longest}


def streak_details(calendar, today):
    active = sorted(day for day, level in calendar.days.items() if level > 0 and day <= today)
    runs = []
    for day in active:
        if runs and day - runs[-1][-1] == timedelta(days=1):
            runs[-1].append(day)
        else:
            runs.append([day])
    longest = max(runs, key=len, default=[])
    # Yesterday still counts while today is in progress; two empty days end a streak.
    current = runs[-1] if runs and today - runs[-1][-1] <= timedelta(days=1) else []
    return {'current': len(current), 'current_start': current[0] if current else None,
            'current_end': current[-1] if current else None,
            'longest': len(longest), 'longest_start': longest[0] if longest else None,
            'longest_end': longest[-1] if longest else None}


def date_range(start, end, empty='No active streak'):
    if start is None or end is None:
        return empty
    if start == end:
        return f'{start:%d %b %Y}'
    return f'{start:%d %b %Y} - {end:%d %b %Y}'


def streak_card(calendar, today):
    """Three-column streak card, using only the displayed contribution year."""
    stats = streak_details(calendar, today)
    svg = ['<g role="group" aria-label="Contribution streaks for the displayed year">',
           '<path d="M326 17V157M666 17V157" stroke="#343943"/>']

    def text(x, y, value, cls='', size=None):
        style = f' style="font-size:{size}px;font-weight:700"' if size else ''
        svg.append(f'<text x="{x}" y="{y}" text-anchor="middle" class="{cls}"{style}>{escape(str(value))}</text>')

    text(164, 75, f'{calendar.total:,}', 'bright', 31)
    text(164, 113, 'Year Contributions', 'small')
    text(164, 139, date_range(min(calendar.days), min(today, max(calendar.days))), 'dim tiny')
    color = '#d9b36c' if stats['current'] else '#69717e'
    svg.append('<circle cx="496" cy="66" r="42" fill="none" stroke="#2b3038" stroke-width="4"/>')
    svg.append(f'<circle class="streak-ring" cx="496" cy="66" r="42" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" stroke-dasharray="244 20" transform="rotate(-76 496 66)"/>')
    svg.append('<rect x="482" y="7" width="28" height="34" fill="#131519"/>')
    flame_class = 'streak-flame' if stats['current'] else ''
    svg.append(f'<path class="{flame_class}" transform="translate(484 8)" d="M12 0C15 8 21 9 21 17C21 23 16 27 11 27C5 27 1 23 1 18C1 14 3 11 6 8C6 13 8 15 10 13C13 10 11 5 12 0Z" fill="{color}"/>')
    text(496, 77, stats['current'], 'accent' if stats['current'] else 'bright', 31)
    text(496, 130, 'Current Streak', 'accent small')
    text(496, 153, date_range(stats['current_start'], stats['current_end']), 'dim tiny')
    text(828, 75, stats['longest'], 'bright', 31)
    text(828, 113, 'Longest Streak', 'small')
    text(828, 139, date_range(stats['longest_start'], stats['longest_end'], 'No contributions yet'), 'dim tiny')
    svg.append('</g>')
    return ''.join(svg)


def render_streak_svg(calendar, now):
    """Standalone version of the card embedded in the Contributions pane."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="228" viewBox="0 0 1040 228" role="img" aria-labelledby="title desc">
<title id="title">GitHub activity / contribution streaks</title>
<desc id="desc">Contribution statistics for the year displayed on the GitHub calendar, as of {now:%Y-%m-%d %H:%M UTC}. Current streak includes yesterday while today is in progress.</desc>
<style>
  text{{font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;font-size:17px;fill:#b9bec8;}}
  .bright{{fill:#e2e5eb;}} .dim{{fill:#838a96;}} .accent{{fill:#d9b36c;}}
  .small{{font-size:13px;}} .tiny{{font-size:12px;}}
  .streak-ring{{animation:ring-in 1.1s ease-out both;}}
  .streak-flame{{animation:flame-glow 3s ease-in-out infinite;}}
  @keyframes ring-in{{from{{stroke-dasharray:0 264;}}to{{stroke-dasharray:244 20;}}}}
  @keyframes flame-glow{{0%,100%{{opacity:1;}}50%{{opacity:.7;}}}}
  @media(prefers-reduced-motion:reduce){{.streak-ring,.streak-flame{{animation:none!important;}}}}
</style>
<rect x="1" y="1" width="1038" height="226" rx="5" fill="#131519" stroke="#363b43"/>
<text x="24" y="23" class="dim tiny">GITHUB ACTIVITY / PAST YEAR</text>
<text x="1016" y="23" text-anchor="end" class="dim tiny">UTC</text>
<g transform="translate(24 36)">{streak_card(calendar, now.date())}</g>
</svg>'''


def event_phrase(kind, count):
    labels = {
        'WatchEvent': ('starred', 'repository', 'repositories'),
        'ForkEvent': ('forked', 'repository', 'repositories'),
        'PushEvent': ('made', 'push', 'pushes'),
        'IssuesEvent': ('updated', 'issue', 'issues'),
        'PullRequestEvent': ('updated', 'pull request', 'pull requests'),
        'PullRequestReviewEvent': ('submitted', 'review', 'reviews'),
        'CreateEvent': ('created', 'ref/repository', 'refs/repositories'),
        'DeleteEvent': ('deleted', 'ref', 'refs'),
        'ReleaseEvent': ('published/updated', 'release', 'releases'),
        'IssueCommentEvent': ('posted', 'issue/PR comment', 'issue/PR comments'),
    }
    verb, singular, plural = labels.get(kind, ('recorded', kind, kind + ' events'))
    return f'{verb} {count} {singular if count == 1 else plural}'


class ContributionParser(HTMLParser):
    """Read dates/levels and the total from GitHub's public contribution calendar."""

    def __init__(self):
        super().__init__()
        self.days = {}
        self.heading = []
        self.in_heading = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'td' and 'data-date' in attrs and 'data-level' in attrs:
            day = date.fromisoformat(attrs['data-date'])
            level = int(attrs['data-level'])
            if level not in range(5):
                raise ValueError('Unexpected contribution level')
            self.days[day] = level
        if tag == 'h2' and attrs.get('id') == 'js-contribution-activity-description':
            self.in_heading = True

    def handle_endtag(self, tag):
        if tag == 'h2':
            self.in_heading = False

    def handle_data(self, data):
        if self.in_heading:
            self.heading.append(data)

    @property
    def total(self):
        match = re.search(r'([\d,]+)\s+contributions?\b', ' '.join(self.heading))
        if not match or len(self.days) < 350:
            raise ValueError('GitHub calendar markup changed or data is incomplete; keeping previous SVG')
        return int(match.group(1).replace(',', ''))


def summary(repos):
    # Fork popularity belongs to its upstream project, so count original repos only.
    originals = [repo for repo in repos if not repo['fork']]
    languages = Counter(repo['language'] for repo in originals if repo.get('language'))
    return {
        'originals': len(originals),
        'forks': len(repos) - len(originals),
        'stars': sum(repo['stargazers_count'] for repo in originals),
        'languages': languages,
    }


def contribution_cells(calendar, today):
    start = min(calendar.days)
    start -= timedelta(days=(start.weekday() + 1) % 7)
    cells = []
    for day, level in sorted(calendar.days.items()):
        if day > today:
            continue
        offset = (day - start).days
        cells.append({'date': day, 'level': level,
                      'x': 73 + (offset // 7) * 17, 'y': 881 + (offset % 7) * 17})
    return cells


def render(profile, repos, calendar, now, events=None):
    info = summary(repos)
    login = profile['login']
    name = profile.get('name') or login
    today = now.date()
    total = calendar.total
    contributions = contribution_summary(calendar, today)
    activity = activity_summary(events or [], now)
    age = (today - date.fromisoformat(profile['created_at'][:10])).days
    svg = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="1350" viewBox="0 0 1040 1350" role="img" aria-labelledby="title desc">
<title id="title">GitHub personal terminal — TUI edition</title>
<defs>
  <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><path d="M0 3.5H4" stroke="#000" stroke-opacity=".045"/></pattern>
  <clipPath id="screen"><rect x="16" y="60" width="1008" height="1244"/></clipPath>
  <clipPath id="typing"><rect class="draw" width="__TYPE_WIDTH__" height="24" style="animation:draw 1.2s steps(__TYPE_COUNT__,end) 2.4s both"/></clipPath>
</defs>
<style>
  text{font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;font-size:17px;fill:#b9bec8;}
  .bright{fill:#e2e5eb;} .dim{fill:#838a96;} .accent{fill:#d9b36c;}
  .small{font-size:13px;} .tiny{font-size:12px;} .label{font-size:12px;letter-spacing:.7px;}
  .enter{animation:enter .35s ease-out var(--delay,0s) both;}
  .draw{animation:draw .85s ease-out var(--delay,0s) both;}
  .bar-rise{animation:rise .65s ease-out var(--delay,0s) both;}
  .blink{animation:blink 1.2s step-end infinite;}
  .cursor{animation:cursor-travel 1.2s steps(__TYPE_COUNT__,end) 2.4s both,blink 1.2s step-end 3.6s infinite;}
  .static-command{display:none;}
  .streak-ring{animation:ring-in 1.1s ease-out .6s both;}
  .streak-flame{animation:flame-glow 3s ease-in-out infinite;}
  @keyframes ring-in{from{stroke-dasharray:0 264;}to{stroke-dasharray:244 20;}}
  @keyframes flame-glow{0%,100%{opacity:1;}50%{opacity:.7;}}
  @keyframes enter{from{opacity:0;transform:translateY(4px);}to{opacity:1;transform:translateY(0);}}
  @keyframes draw{from{width:0;}} @keyframes rise{from{height:0;}}
  @keyframes blink{0%,100%{opacity:1;}50%{opacity:0;}}
  @keyframes cursor-travel{from{transform:translateX(-__TYPE_WIDTH__px);}to{transform:translateX(0);}}
  @media(prefers-reduced-motion:reduce){
    .enter,.draw,.bar-rise,.blink,.cursor,.streak-ring,.streak-flame{animation:none!important;}
    .moving-command{display:none;} .static-command{display:inline;}
  }
</style>
<rect x="1" y="1" width="1038" height="1348" rx="5" fill="#101114" stroke="#363b43"/>
<rect x="16" y="16" width="1008" height="34" rx="2" fill="#202228"/>
<text x="30" y="38" class="bright small">[ TTY 01 ]  PERSONAL TERMINAL</text>
<text x="1010" y="38" text-anchor="end" class="dim small">GITHUB / PUBLIC PROFILE</text>
<text x="28" y="72" class="dim tiny">PROFILE   /   ACTIVITY   /   CONTRIBUTIONS   /   TIMELINE</text>
''']

    def text(x, y, value, cls='', extra=''):
        svg.append(f'<text x="{x}" y="{y}" class="{cls}" {extra}>{escape(str(value))}</text>')

    def panel(x, y, width, height, title, delay=0, active=False):
        svg.append(f'<g class="enter" style="--delay:{delay}s"><rect x="{x}" y="{y}" width="{width}" height="{height}" rx="4" fill="#131519" stroke="{"#6c5c3e" if active else "#363b43"}"/>')
        svg.append(f'<rect x="{x + 12}" y="{y - 10}" width="{len(title) * 7.9 + 20:.1f}" height="20" fill="#101114"/>')
        text(x + 22, y + 4, title, 'accent small' if active else 'bright small')

    svg.append(f'<desc id="desc">{escape(name)} (@{escape(login)}). {len(repos)} public repositories, {profile["followers"]} followers, {total} contributions. Account age {age} days. Contribution calendar shows actual profile activity levels. Synced {now:%Y-%m-%d %H:%M UTC}.</desc>')

    panel(24, 96, 380, 218, '01 / PROFILE', .05, True)
    text(46, 150, name[:18].upper(), 'bright', 'style="font-size:35px;font-weight:700;letter-spacing:3px"')
    text(46, 181, f'@{login}', 'accent')
    text(46, 212, f'SINCE {profile["created_at"][:10]} / {age:,} DAYS', 'dim small')
    bio = profile.get('bio') or 'Ideas, experiments, and things I make along the way.'
    for i, row in enumerate(textwrap.wrap(bio, width=36)[:3]):
        text(46, 247 + i * 22, row, '', 'style="font-size:14px"')
    svg.append('</g>')

    panel(424, 96, 592, 218, '02 / GITHUB PULSE', .15)
    metrics = [('PUBLIC REPOS', len(repos)), ('FOLLOWERS', profile['followers']),
               ('STARS RECEIVED', info['stars']), ('FOLLOWING', profile['following'])]
    for i, (label, value) in enumerate(metrics):
        x, y = 448 + (i % 2) * 284, 133 + (i // 2) * 79
        text(x, y, label, 'dim label')
        text(x, y + 35, f'{value:,}', 'accent' if i in (0, 2) else 'bright', 'style="font-size:30px;font-weight:700"')
    text(448, 292, f'{info["originals"]} originals / {info["forks"]} forks / {profile["public_gists"]} public gists', 'dim small')
    svg.append('</g>')

    panel(24, 340, 592, 254, '03 / ACTIVITY', .3)
    text(46, 384, f'{activity["total"]} public events' if events is not None else 'Activity unavailable', 'accent')
    text(592, 384, '14-DAY CHART / UTC', 'dim tiny', 'text-anchor="end"')
    dates = [today - timedelta(days=i) for i in reversed(range(14))]
    peak = max((activity['daily'][day] for day in dates), default=0) or 1
    for i, day in enumerate(dates):
        count = activity['daily'][day]
        x, height = 47 + i * 38, 100 * count / peak
        svg.append(f'<rect x="{x}" y="410" width="25" height="100" fill="#20242b"/>')
        if count:
            svg.append(f'<g transform="translate({x} 510) scale(1 -1)"><rect class="bar-rise" style="--delay:{.55 + i * .025:.3f}s" width="25" height="{height:.1f}" fill="#92a5b6"><title>{day}: {count} public events returned</title></rect></g>')
    text(46, 535, dates[0].strftime('%d %b'), 'dim tiny')
    text(592, 535, today.strftime('%d %b'), 'dim tiny', 'text-anchor="end"')
    kinds = activity['kinds']
    text(46, 565, f'STAR {kinds["WatchEvent"]}  /  FORK {kinds["ForkEvent"]}  /  PUSH {kinds["PushEvent"]}', 'small')
    text(592, 582, 'COUNTS: AVAILABLE 30-DAY WINDOW', 'dim tiny', 'text-anchor="end"')
    svg.append('</g>')

    panel(636, 340, 380, 254, '04 / LANGUAGE MIX', .45)
    languages = info['languages']
    groups = languages.most_common(3)
    if len(languages) > 3:
        groups = languages.most_common(2) + [('Other', sum(c for _, c in languages.most_common()[2:]))]
    denominator = sum(languages.values())
    for i, (language, count) in enumerate(groups):
        y = 385 + i * 48
        text(658, y, language[:16], 'small')
        text(994, y, f'{count / denominator:.0%}', 'small', 'text-anchor="end"')
        svg.append(f'<rect x="658" y="{y + 12}" width="336" height="8" fill="#22262d"/><rect class="draw" style="--delay:{.7 + i * .1:.2f}s" x="658" y="{y + 12}" width="{336 * count / denominator:.1f}" height="8" fill="{LANGUAGE_COLORS[i]}"/>')
    if not groups:
        text(658, 385, 'No language data', 'dim small')
    text(658, 551, f'{len(languages)} languages / {denominator} classified repos', 'dim small')
    text(658, 578, 'PRIMARY LANGUAGE / ORIGINAL REPOS', 'dim tiny')
    svg.append('</g>')

    panel(24, 620, 992, 412, '05 / CONTRIBUTIONS', .6)
    text(994, 648, 'PAST YEAR / UTC', 'dim tiny', 'text-anchor="end"')
    svg.append('<g transform="translate(24 650)">' + streak_card(calendar, today) + '</g>')
    text(46, 832, f'{contributions["active_days"]} active days in the displayed year', 'dim small')
    start = min(calendar.days)
    start -= timedelta(days=(start.weekday() + 1) % 7)
    last_month = start.strftime('%b') if start.day > 21 else None
    for column in range(((min(today, max(calendar.days)) - start).days // 7) + 1):
        week = start + timedelta(weeks=column)
        month = week.strftime('%b')
        if month != last_month and column < 51:
            text(67 + column * 17, 860, month, 'dim tiny')
            last_month = month
    for cell in contribution_cells(calendar, today):
        svg.append(f'<rect x="{cell["x"] - 5.5}" y="{cell["y"] - 5.5}" width="11" height="11" rx="1" fill="{COLORS[cell["level"]]}"><title>{cell["date"]}: contribution level {cell["level"]}/4</title></rect>')
    text(46, 1011, f'{min(calendar.days):%d %b %Y} - {min(today, max(calendar.days)):%d %b %Y}', 'dim tiny')
    text(802, 1011, 'LESS', 'dim tiny')
    for i, color in enumerate(COLORS):
        svg.append(f'<rect x="{841 + i * 17}" y="1001" width="11" height="11" rx="1" fill="{color}"/>')
    text(994, 1011, 'MORE', 'dim tiny', 'text-anchor="end"')
    svg.append('</g>')

    panel(24, 1058, 992, 218, '06 / TIMELINE', .8)
    days = sorted(activity['log'], reverse=True)[:4]
    if days:
        svg.append(f'<path d="M55 1102V{1102 + (len(days) - 1) * 38}" stroke="#4b515b" stroke-width="1.5"/>')
    for i, day in enumerate(days):
        y = 1108 + i * 38
        if not i:
            svg.append(f'<rect x="38" y="{y - 22}" width="964" height="33" rx="3" fill="#d9b36c" opacity=".045"/>')
        svg.append(f'<circle cx="55" cy="{y - 5}" r="4" fill="{"#d9b36c" if not i else "#7a838f"}" stroke="#131519" stroke-width="2"/>')
        text(77, y, str(day), 'dim small')
        phrases = [event_phrase(kind, count) for kind, count in activity['log'][day].most_common()]
        text(248, y, textwrap.shorten(' / '.join(phrases), width=66, placeholder=' ...'), 'bright small' if not i else 'small')
    if not days:
        text(46, 1112, 'No public events returned in the API window.' if events is not None else 'Public event feed unavailable.', 'dim small')
    text(46, 1257, 'Public activity / grouped by day', 'dim tiny')
    text(994, 1257, 'EVENTS, NOT COMMIT COUNTS', 'dim tiny', 'text-anchor="end"')
    svg.append('</g>')

    command = 'echo "Stay curious. Keep creating."'
    prefix = f'{login}@github:~$ '
    # 17px monospace text has a 10.2px character advance.
    x, width = 28 + len(prefix) * 10.2, len(command) * 10.2
    svg[0] = svg[0].replace('__TYPE_WIDTH__', f'{width:g}').replace('__TYPE_COUNT__', str(len(command)))
    text(28, 1307, prefix, 'bright')
    svg.append(f'<g class="moving-command" transform="translate({x:g} 1288)"><g clip-path="url(#typing)"><text y="19">{escape(command)}</text></g><rect class="cursor" x="{width:g}" width="9" height="20" fill="#d9b36c"/></g>')
    text(x, 1307, command, 'static-command')
    svg.append('<rect x="16" y="1323" width="1008" height="16" fill="#202228"/>')
    text(28, 1335, f'LAST SYNC {now:%Y-%m-%d %H:%M UTC}', 'dim tiny')
    text(1012, 1335, 'PUBLIC DATA / REFRESH ~1H', 'dim tiny', 'text-anchor="end"')
    svg.append('<rect x="16" y="60" width="1008" height="1244" fill="url(#scan)" pointer-events="none"/>\n</svg>\n')
    return ''.join(svg)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username', default='vanhhoang')
    parser.add_argument('--output', type=Path, default=ROOT / 'assets/header.svg')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', args.username):
        parser.error('Invalid GitHub username')
    profile = json.loads(fetch(f'https://api.github.com/users/{args.username}'))
    repos = repositories(args.username)
    calendar = ContributionParser()
    calendar.feed(fetch(f'https://github.com/users/{args.username}/contributions'))
    _ = calendar.total
    events = public_events(args.username)
    now = datetime.now(timezone.utc)
    result = render(profile, repos, calendar, now, events)
    card = render_streak_svg(calendar, now)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for output, content in ((args.output, result), (args.output.parent / 'streak.svg', card)):
        temporary = output.with_suffix('.svg.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(output)
    print(f'Updated {args.output}: {len(repos)} public repos, {calendar.total} profile contributions')


if __name__ == '__main__':
    main()
