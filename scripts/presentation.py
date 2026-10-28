"""Presentation only: the original terminal README and transparent SVG palettes."""

from datetime import timedelta
from html import escape
import re


PALETTES = {
    'dark': {'text': '#c9d1d9', 'bright': '#f0f3f6', 'dim': '#9da7b3',
             'accent': '#d9b36c', 'bars': ['#9bb9d1', '#a4adba', '#7d8fa2'],
             'levels': ['#8c959f26', '#4b6978', '#648a9e', '#88acbe', '#b5d6e5']},
    'light': {'text': '#303944', 'bright': '#1f2328', 'dim': '#596779',
              'accent': '#85551d', 'bars': ['#436b8a', '#667383', '#7a687c'],
              'levels': ['#8c959f26', '#c0d4de', '#8fb1c3', '#5e8aa3', '#315f7b']},
}


def apply_theme(svg, theme):
    """Adapt the retained full-terminal and streak layouts without opaque backgrounds."""
    palette = PALETTES[theme]
    replacements = {
        '#101114': 'none', '#131519': '#8c959f0a', '#202228': '#8c959f18',
        '#b9bec8': palette['text'], '#e2e5eb': palette['bright'],
        '#838a96': palette['dim'], '#d9b36c': palette['accent'],
        '#363b43': '#8c959f66', '#343943': '#8c959f55', '#6c5c3e': palette['accent'],
        '#2b3038': '#8c959f33', '#20242b': '#8c959f22', '#22262d': '#8c959f22',
        '#92a5b6': palette['bars'][0], '#91a6b8': palette['bars'][0],
        '#747d89': palette['bars'][1], '#555e69': palette['bars'][2],
        '#414953': palette['dim'], '#69717e': palette['dim'],
        '#4b515b': '#8c959f66', '#7a838f': palette['dim'],
    }
    replacements.update(zip(['#22252b', '#35424c', '#506774', '#7394a1', '#9abcca'], palette['levels']))
    return re.sub(r'#[0-9a-fA-F]{6}\b', lambda match: replacements.get(match[0], match[0]), svg)


def document(title, description, width, height, content, theme):
    p = PALETTES[theme]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>
<style>
text{{font:14px 'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;fill:{p['text']};}}
.bright{{fill:{p['bright']};font-weight:700;}}.dim{{fill:{p['dim']};}}.accent{{fill:{p['accent']};}}
.small{{font-size:12px;}}.tiny{{font-size:11px;}}
.panel{{fill:#8c959f;fill-opacity:.04;stroke:#8c959f;stroke-opacity:.35;}}
.track{{fill:#8c959f;fill-opacity:.16;}}
.bar{{animation:appear .6s ease-out both;}}
@keyframes appear{{from{{opacity:0;}}to{{opacity:1;}}}}
@media(prefers-reduced-motion:reduce){{.bar{{animation:none!important;}}}}
</style>
{''.join(content)}
</svg>
'''


def text(x, y, value, cls='', end=False):
    anchor = ' text-anchor="end"' if end else ''
    return f'<text x="{x}" y="{y}" class="{cls}"{anchor}>{escape(str(value))}</text>'


def activity_chart(activity, now, theme):
    p = PALETTES[theme]
    dates = [now.date() - timedelta(days=i) for i in reversed(range(14))]
    peak = max((activity['daily'][day] for day in dates), default=0) or 1
    total = sum(activity['daily'][day] for day in dates)
    parts = ['<rect x="1" y="1" width="638" height="248" rx="5" class="panel"/>',
             text(22, 29, '14-DAY PUBLIC ACTIVITY / UTC', 'small'),
             text(618, 29, f'{total} events shown', 'accent small', True)]
    for i, day in enumerate(dates):
        count, x = activity['daily'][day], 23 + i * 43
        height = 115 * count / peak
        parts.append(f'<rect x="{x}" y="65" width="33" height="115" class="track"/>')
        if count:
            parts.append(f'<rect x="{x}" y="{180 - height:.2f}" width="33" height="{height:.2f}" class="bar" fill="{p["bars"][0]}"><title>{day}: {count} public events returned</title></rect>')
            parts.append(text(x + 25, 57, count, 'tiny', True))
    parts.extend([text(22, 203, f'{dates[0]:%d %b} - {dates[-1]:%d %b %Y}', 'dim small'),
                  text(618, 203, f'Peak: {peak if total else 0} / day', 'dim small', True),
                  text(22, 231, 'Available events only; API cap: 300 events / 30 days.', 'dim tiny')])
    return document('Public activity over 14 UTC dates',
                    f'{total} events returned for {dates[0]} through {dates[-1]}. Not commit counts. Snapshot {now.isoformat()}.',
                    640, 250, parts, theme)


def language_chart(info, now, theme):
    p, languages = PALETTES[theme], info['languages']
    groups = languages.most_common(3)
    if len(languages) > 3:
        groups = languages.most_common(2) + [('Other', sum(n for _, n in languages.most_common()[2:]))]
    denominator = sum(languages.values())
    parts = ['<rect x="1" y="1" width="438" height="248" rx="5" class="panel"/>',
             text(22, 29, 'PRIMARY LANGUAGE / ORIGINAL REPOS', 'small')]
    for i, (language, count) in enumerate(groups):
        y = 68 + i * 45
        parts.extend([text(22, y, language[:22], 'small'),
                      text(418, y, f'{count}/{denominator} · {count / denominator:.0%}', 'small', True),
                      f'<rect x="22" y="{y + 10}" width="396" height="8" class="track"/>',
                      f'<rect x="22" y="{y + 10}" width="{396 * count / denominator:.2f}" height="8" class="bar" fill="{p["bars"][i]}"/>'])
    if not groups:
        parts.append(text(22, 80, 'No classified original repositories.', 'dim small'))
    parts.extend([text(22, 210, f'{len(languages)} languages / {denominator} classified repos', 'dim small'),
                  text(22, 232, 'Repository share, not code bytes or proficiency.', 'dim tiny')])
    return document('Primary language distribution',
                    f'Each original public repository counts once. Forks and unclassified repositories excluded. Snapshot {now.isoformat()}.',
                    440, 250, parts, theme)


def contribution_chart(calendar, now, theme):
    p = PALETTES[theme]
    first = min(calendar.days)
    start = first - timedelta(days=(first.weekday() + 1) % 7)
    parts = ['<rect x="1" y="1" width="1038" height="218" rx="5" class="panel"/>',
             text(22, 26, f'{calendar.total:,} contributions / past 365 UTC dates', 'small'),
             text(1018, 26, 'PUBLIC PROFILE CALENDAR', 'dim tiny', True)]
    # Label whole weeks, so a month boundary inside the first week cannot draw
    # two month names at the same x coordinate.
    month = start.month if start.day > 21 else None
    for column in range((now.date() - start).days // 7 + 1):
        week = start + timedelta(weeks=column)
        if week.month != month and column < 52:
            parts.append(text(23 + column * 19, 47, week.strftime('%b'), 'dim tiny'))
        month = week.month
    for day, level in sorted(calendar.days.items()):
        offset = (day - start).days
        x, y = 23 + offset // 7 * 19, 55 + offset % 7 * 19
        count = calendar.counts[day]
        parts.append(f'<rect x="{x}" y="{y}" width="14" height="14" rx="2" fill="{p["levels"][level]}"><title>{day}: {count} contribution{"s" if count != 1 else ""}</title></rect>')
    parts.extend([text(22, 207, f'{first:%d %b %Y} - {now:%d %b %Y} / UTC', 'dim tiny'),
                  text(858, 207, 'LESS', 'dim tiny')])
    for i, color in enumerate(p['levels']):
        parts.append(f'<rect x="{895 + i * 18}" y="196" width="12" height="12" rx="2" fill="{color}"/>')
    parts.append(text(1018, 207, 'MORE', 'dim tiny', True))
    return document('GitHub contribution calendar',
                    f'{calendar.total} contributions, {first} through {now.date()}. Daily counts come from {calendar.source}. Snapshot {now.isoformat()}.',
                    1040, 220, parts, theme)


def render_charts(info, activity, calendar, now, theme):
    return {'activity': activity_chart(activity, now, theme),
            'languages': language_chart(info, now, theme),
            'contributions': contribution_chart(calendar, now, theme)}



def render_readme(person):
    """Keep the original single-terminal layout; only its palette changes by theme."""
    login = person['login']
    name = person.get('name') or login
    alt = escape(f'{name} (@{login}) — personal terminal with GitHub counters, activity, '
                 'languages, contributions, streaks and timeline. Last sync appears in the status bar.', quote=True)
    return f'''<p align="center">
  <a href="assets/header-dark.svg#gh-dark-mode-only">
    <img src="assets/header-dark.svg" alt="{alt}" width="100%" />
  </a>
  <a href="assets/header-light.svg#gh-light-mode-only">
    <img src="assets/header-light.svg" alt="{alt}" width="100%" />
  </a>
</p>

<p align="center">
  <a href="https://github.com/{login}?tab=repositories">Repositories</a>
  &nbsp; · &nbsp;
  <a href="https://github.com/{login}?tab=overview">Activity</a>
  &nbsp; · &nbsp;
  <a href="https://github.com/{login}?tab=stars">Stars</a>
</p>

<p align="center">
  <sub>Thanks for stopping by. · <a href="docs/design.md">Data &amp; updates</a></sub>
</p>
'''
