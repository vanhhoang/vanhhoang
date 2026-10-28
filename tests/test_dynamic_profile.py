"""Regression checks for API integrity, refresh failure and theme-neutral rendering."""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from io import BytesIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import generate_profile as profile


NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
PERSON = {'login': 'example', 'name': 'Example <&>', 'bio': 'Hello | **world** <script>',
          'created_at': '2023-04-07T03:14:07Z', 'followers': 2, 'following': 10, 'public_gists': 0}
REPOS = [{'id': 1, 'name': 'one', 'fork': False, 'language': 'Python', 'stargazers_count': 3},
         {'id': 2, 'name': 'two', 'fork': True, 'language': 'JavaScript', 'stargazers_count': 99}]
EVENTS = [{'id': '1', 'type': 'WatchEvent', 'created_at': '2026-10-27T12:00:00Z', 'public': True}]


def graphql_fixture():
    days = []
    for i in reversed(range(365)):
        active = i in (1, 2, 3, 10)
        days.append({'date': str(NOW.date() - timedelta(days=i)),
                     'contributionCount': 2 if active else 0,
                     'contributionLevel': 'SECOND_QUARTILE' if active else 'NONE'})
    return {'data': {'user': {'contributionsCollection': {'contributionCalendar': {
        'totalContributions': 8,
        'weeks': [{'contributionDays': days[i:i + 7]} for i in range(0, len(days), 7)]}}}}}


def calendar_fixture():
    return profile.calendar_from_graphql(graphql_fixture(), NOW.date())


def html_fixture():
    calendar = calendar_fixture()
    cells = []
    for i, day in enumerate(calendar.days):
        count = calendar.counts[day]
        cells.append(f'<td id="d{i}" data-date="{day}" data-level="{calendar.days[day]}"></td>'
                     f'<tool-tip for="d{i}">{count} contributions on October 1st.</tool-tip>')
    return '<h2 id="js-contribution-activity-description">8 contributions</h2>' + ''.join(cells)


class DynamicProfileTests(unittest.TestCase):
    def test_graphql_uses_real_counts_not_heatmap_levels(self):
        calendar = calendar_fixture()
        self.assertEqual(calendar.total, 8)
        self.assertEqual(len(calendar.counts), 365)
        self.assertEqual(calendar.source, 'github-graphql')
        self.assertEqual(profile.streak_details(calendar, NOW.date())['current'], 3)
        data = graphql_fixture()
        data['data']['user']['contributionsCollection']['contributionCalendar']['weeks'][0]['contributionDays'][0].update(
            contributionCount=12, contributionLevel='FIRST_QUARTILE')
        data['data']['user']['contributionsCollection']['contributionCalendar']['totalContributions'] += 12
        self.assertEqual(profile.calendar_from_graphql(data, NOW.date()).counts[date(2025, 10, 29)], 12)

    def test_graphql_rejects_errors_partial_dates_and_inconsistent_totals(self):
        for mode in ('errors', 'missing', 'duplicate', 'bad_total', 'negative'):
            with self.subTest(mode=mode):
                data = graphql_fixture()
                raw = data['data']['user']['contributionsCollection']['contributionCalendar']
                if mode == 'errors':
                    data['errors'] = [{'message': 'Resource limit'}]
                elif mode == 'missing':
                    raw['weeks'][0]['contributionDays'].pop()
                elif mode == 'duplicate':
                    raw['weeks'][0]['contributionDays'].append(deepcopy(raw['weeks'][0]['contributionDays'][0]))
                elif mode == 'negative':
                    raw['weeks'][0]['contributionDays'][0]['contributionCount'] = -1
                else:
                    raw['totalContributions'] = 999
                with self.assertRaises(ValueError):
                    profile.calendar_from_graphql(data, NOW.date())

    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test-token'})
    @patch.object(profile, 'fetch')
    def test_authenticated_calendar_requests_bounded_graphql_period(self, fetch):
        fetch.return_value = json.dumps(graphql_fixture())
        profile.contribution_calendar('example', NOW)
        self.assertEqual(fetch.call_args.args[0], 'https://api.github.com/graphql')
        variables = fetch.call_args.args[1]['variables']
        self.assertEqual(variables['from'], '2025-10-29T00:00:00Z')
        self.assertEqual(variables['login'], 'example')

    @patch.dict(os.environ, {}, clear=True)
    @patch.object(profile, 'fetch')
    def test_unauthenticated_fallback_reads_exact_tooltip_counts(self, fetch):
        fetch.return_value = html_fixture()
        calendar = profile.contribution_calendar('example', NOW)
        self.assertEqual(calendar.counts, calendar_fixture().counts)
        self.assertEqual(calendar.source, 'github-public-calendar')

    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test-token'})
    @patch.object(profile, 'fetch')
    def test_integration_permission_fallback_still_validates_real_public_data(self, fetch):
        fetch.side_effect = [json.dumps({'errors': [{'type': 'FORBIDDEN',
                            'message': 'Resource not accessible by integration'}]}), html_fixture()]
        self.assertEqual(profile.contribution_calendar('example', NOW).total, 8)
        self.assertEqual(fetch.call_count, 2)

    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test-token'})
    @patch.object(profile, 'fetch')
    def test_other_graphql_errors_fail_without_silent_source_change(self, fetch):
        fetch.return_value = json.dumps({'errors': [{'type': 'RESOURCE_LIMITS_EXCEEDED'}]})
        with self.assertRaises(ValueError):
            profile.contribution_calendar('example', NOW)
        self.assertEqual(fetch.call_count, 1)

    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test-token'})
    @patch.object(profile, 'fetch')
    def test_http_permission_denial_can_fallback_but_rate_limit_cannot(self, fetch):
        for message, fallback in [('Resource not accessible by integration', True),
                                  ('API rate limit exceeded', False)]:
            with self.subTest(message=message):
                fetch.reset_mock()
                error = HTTPError('https://api.github.com/graphql', 403, 'Forbidden', {},
                                  BytesIO(json.dumps({'message': message}).encode()))
                fetch.side_effect = [error, html_fixture()]
                if fallback:
                    self.assertEqual(profile.contribution_calendar('example', NOW).total, 8)
                    self.assertEqual(fetch.call_count, 2)
                else:
                    with self.assertRaises(HTTPError):
                        profile.contribution_calendar('example', NOW)
                    self.assertEqual(fetch.call_count, 1)

    def test_html_fallback_rejects_levels_without_exact_counts(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(profile, 'fetch', return_value=
                '<h2 id="js-contribution-activity-description">8 contributions</h2>' + ''.join(
                    f'<td data-date="{d}" data-level="{level}"></td>'
                    for d, level in calendar_fixture().days.items())):
            with self.assertRaises(ValueError):
                profile.contribution_calendar('example', NOW)

    def test_duplicate_events_do_not_inflate_chart_or_timeline(self):
        activity = profile.activity_summary(EVENTS + EVENTS, NOW)
        self.assertEqual(activity['total'], 1)
        self.assertEqual(activity['daily'][date(2026, 10, 27)], 1)

    def test_snapshot_roundtrip_preserves_timestamp_and_minimizes_public_fields(self):
        snapshot = profile.make_snapshot({**PERSON, 'token': 'not-public'}, REPOS,
                                         calendar_fixture(), EVENTS, NOW)
        person, repos, calendar, events, now = profile.unpack_snapshot(snapshot)
        self.assertEqual(now, NOW)
        self.assertEqual(calendar.counts, calendar_fixture().counts)
        self.assertNotIn('token', json.dumps(snapshot))
        self.assertEqual(person, {key: PERSON[key] for key in ('login', 'name', 'bio', 'created_at')})
        self.assertEqual(repos, REPOS)
        self.assertEqual(events, EVENTS)

    def test_light_dark_charts_have_transparent_surfaces_and_real_counts(self):
        files = profile.build_outputs(PERSON, REPOS, calendar_fixture(), EVENTS, NOW)
        for theme in ('dark', 'light'):
            for kind in ('header', 'streak', 'activity', 'languages', 'contributions'):
                with self.subTest(theme=theme, kind=kind):
                    svg = files[f'{kind}-{theme}.svg']
                    ET.fromstring(svg)
                    self.assertNotIn('fill="#101114"', svg)
                    self.assertNotIn('fill="#131519"', svg)
                    self.assertIn('prefers-reduced-motion', svg)
        heatmap = ET.fromstring(files['contributions-light.svg'])
        titles = heatmap.findall('.//{http://www.w3.org/2000/svg}rect/{http://www.w3.org/2000/svg}title')
        self.assertEqual(len(titles), 365)
        self.assertIn('2026-10-27: 2 contributions', [t.text for t in titles])
        months = [node for node in heatmap.findall('{http://www.w3.org/2000/svg}text')
                  if node.attrib['y'] == '47']
        self.assertEqual(len({node.attrib['x'] for node in months}), len(months))
        self.assertNotEqual(files['activity-dark.svg'], files['activity-light.svg'])

    def test_readme_preserves_original_terminal_layout_and_switches_theme_safely(self):
        files = profile.build_outputs(PERSON, REPOS, calendar_fixture(), EVENTS, NOW)
        readme = files['README.md']
        self.assertIn('Example &lt;&amp;&gt;', readme)
        self.assertNotIn('<script>', readme)
        for theme in ('dark', 'light'):
            self.assertIn(f'href="assets/header-{theme}.svg#gh-{theme}-mode-only"', readme)
            self.assertIn(f'src="assets/header-{theme}.svg"', readme)
        self.assertNotIn('| Public repos |', readme)
        self.assertIn('width="100%"', readme)
        for label in ('Repositories', 'Activity', 'Stars', 'Thanks for stopping by.'):
            self.assertIn(label, readme)

    def test_failed_refresh_preserves_readme_snapshot_and_both_themes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / 'assets'
            assets.mkdir()
            targets = [root / 'README.md', assets / 'profile-data.json', assets / 'activity-light.svg',
                       assets / 'activity-dark.svg']
            for target in targets:
                target.write_text('previous successful data')
            args = ['generate_profile.py', '--username', 'example', '--output-dir', str(assets),
                    '--readme', str(root / 'README.md')]
            with patch.object(sys, 'argv', args), patch.object(profile, 'contribution_calendar',
                    side_effect=ValueError('Incomplete calendar')), patch.object(profile, 'fetch',
                    side_effect=[json.dumps(PERSON), json.dumps(REPOS)]):
                with self.assertRaises(ValueError):
                    profile.main()
            for target in targets:
                self.assertEqual(target.read_text(), 'previous successful data')

    def test_offline_render_uses_no_network_and_keeps_original_freshness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / 'saved.json'
            snapshot.write_text(json.dumps(profile.make_snapshot(PERSON, REPOS, calendar_fixture(), EVENTS, NOW)))
            args = ['generate_profile.py', '--username', 'example', '--from-snapshot', str(snapshot),
                    '--output-dir', str(root / 'assets'), '--readme', str(root / 'README.md')]
            with patch.object(sys, 'argv', args), patch.object(profile, 'fetch') as fetch:
                profile.main()
            fetch.assert_not_called()
            self.assertIn('2026-10-28 12:00 UTC', (root / 'assets/header-dark.svg').read_text())
            saved = json.loads((root / 'assets/profile-data.json').read_text())
            self.assertEqual(saved['fetched_at'], NOW.isoformat())


if __name__ == '__main__':
    unittest.main()
