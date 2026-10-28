from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import generate_profile as profile


def calendar_fixture():
    calendar = profile.ContributionParser()
    today = date(2026, 10, 28)
    cells = ''.join(
        f'<td data-level="{i % 5}" data-date="{today - timedelta(days=i)}"></td>'
        for i in range(365)
    )
    calendar.feed('<h2 id="js-contribution-activity-description">1,234 contributions in the last year</h2>' + cells)
    return calendar


class ProfileTests(unittest.TestCase):
    def test_calendar_parses_dates_levels_and_thousands(self):
        calendar = calendar_fixture()
        self.assertEqual(calendar.total, 1234)
        self.assertEqual(len(calendar.days), 365)
        self.assertEqual(calendar.days[date(2026, 10, 27)], 1)

    def test_changed_or_partial_calendar_fails_instead_of_fabricating_zero(self):
        for html in ('<html>Sign in</html>', '<h2 id="js-contribution-activity-description">0 contributions</h2>'):
            calendar = profile.ContributionParser()
            calendar.feed(html)
            with self.assertRaises(ValueError):
                _ = calendar.total

    def test_star_and_language_totals_exclude_forks_and_unclassified_languages(self):
        repos = [
            {'fork': False, 'language': 'Python', 'stargazers_count': 3},
            {'fork': False, 'language': None, 'stargazers_count': 2},
            {'fork': True, 'language': 'JavaScript', 'stargazers_count': 999},
        ]
        result = profile.summary(repos)
        self.assertEqual(result['stars'], 5)
        self.assertEqual(result['originals'], 2)
        self.assertEqual(result['forks'], 1)
        self.assertEqual(dict(result['languages']), {'Python': 1})

    @patch.object(profile, 'fetch')
    def test_repository_pagination(self, fetch):
        fetch.side_effect = [json.dumps([{'id': i} for i in range(100)]), '[{"id":100}]']
        self.assertEqual(len(profile.repositories('vanhhoang')), 101)
        self.assertIn('page=2', fetch.call_args.args[0])

    @patch.object(profile, 'fetch')
    def test_public_events_stop_at_github_300_event_limit(self, fetch):
        fetch.return_value = json.dumps([{'id': i} for i in range(100)])
        self.assertEqual(len(profile.public_events('vanhhoang')), 300)
        self.assertEqual(fetch.call_count, 3)
        self.assertIn('page=3', fetch.call_args.args[0])

    def test_activity_window_excludes_private_future_and_old_events(self):
        now = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
        events = [
            {'created_at': '2026-10-27T23:30:00Z', 'type': 'WatchEvent', 'public': True},
            {'created_at': '2026-10-27T22:00:00Z', 'type': 'WatchEvent', 'public': True},
            {'created_at': '2026-10-26T22:00:00Z', 'type': 'ForkEvent', 'public': True},
            {'created_at': '2026-10-27T23:30:00Z', 'type': 'PushEvent', 'public': False},
            {'created_at': '2026-10-29T23:30:00Z', 'type': 'PushEvent', 'public': True},
            {'created_at': '2026-09-20T23:30:00Z', 'type': 'PushEvent', 'public': True},
        ]
        result = profile.activity_summary(events, now)
        self.assertEqual(result['total'], 3)
        self.assertEqual(result['daily'][date(2026, 10, 27)], 2)
        self.assertEqual(result['kinds']['PushEvent'], 0)
        self.assertEqual(result['log'][date(2026, 10, 26)]['ForkEvent'], 1)

    def test_longest_streak_uses_consecutive_active_dates_not_activity_level(self):
        calendar = profile.ContributionParser()
        calendar.days = {date(2026, 10, 20): 4, date(2026, 10, 21): 1,
                         date(2026, 10, 22): 3, date(2026, 10, 24): 1,
                         date(2026, 10, 25): 0, date(2026, 10, 29): 4}
        result = profile.contribution_summary(calendar, date(2026, 10, 28))
        self.assertEqual(result, {'active_days': 4, 'longest_streak': 3})
        self.assertEqual(profile.contribution_summary(profile.ContributionParser(), date(2026, 10, 28)),
                         {'active_days': 0, 'longest_streak': 0})

    def test_activity_labels_do_not_confuse_pushes_with_commits(self):
        self.assertEqual(profile.event_phrase('PushEvent', 2), 'made 2 pushes')
        self.assertEqual(profile.event_phrase('WatchEvent', 1), 'starred 1 repository')

    def test_current_streak_includes_today_and_yesterday_grace(self):
        calendar = profile.ContributionParser()
        calendar.days = {date(2026, 10, 25): 1, date(2026, 10, 26): 4, date(2026, 10, 27): 2}
        for today in (date(2026, 10, 27), date(2026, 10, 28)):
            stats = profile.streak_details(calendar, today)
            self.assertEqual(stats['current'], 3)
            self.assertEqual(stats['current_start'], date(2026, 10, 25))
            self.assertEqual(stats['current_end'], date(2026, 10, 27))
        self.assertEqual(profile.streak_details(calendar, date(2026, 10, 29))['current'], 0)

    def test_streak_ranges_handle_leap_day_and_longest_ties(self):
        calendar = profile.ContributionParser()
        calendar.days = {date(2024, 2, 28): 1, date(2024, 2, 29): 1, date(2024, 3, 1): 1,
                         date(2024, 3, 4): 1, date(2024, 3, 5): 1, date(2024, 3, 6): 1}
        stats = profile.streak_details(calendar, date(2024, 3, 6))
        self.assertEqual(stats['longest'], 3)
        self.assertEqual(stats['longest_start'], date(2024, 2, 28))
        self.assertEqual(stats['longest_end'], date(2024, 3, 1))
        self.assertEqual(stats['current_start'], date(2024, 3, 4))

    def test_empty_streak_and_future_activity_do_not_create_false_streaks(self):
        calendar = profile.ContributionParser()
        calendar.days = {date(2026, 10, 28): 0, date(2026, 10, 29): 4}
        stats = profile.streak_details(calendar, date(2026, 10, 28))
        self.assertEqual(stats['current'], 0)
        self.assertEqual(stats['longest'], 0)
        self.assertIsNone(stats['longest_start'])
        self.assertEqual(profile.date_range(None, None), 'No active streak')

    def test_contribution_grid_preserves_dates_and_levels(self):
        calendar = calendar_fixture()
        cells = profile.contribution_cells(calendar, date(2026, 10, 28))
        self.assertEqual({cell['date']: cell['level'] for cell in cells}, calendar.days)
        self.assertEqual(len({(cell['x'], cell['y']) for cell in cells}), len(calendar.days))

    def test_contribution_grid_ignores_future_dates(self):
        calendar = calendar_fixture()
        calendar.days[date(2026, 10, 29)] = 4
        dates = {cell['date'] for cell in profile.contribution_cells(calendar, date(2026, 10, 28))}
        self.assertNotIn(date(2026, 10, 29), dates)

    def test_render_escapes_public_text_and_handles_empty_language_data(self):
        person = {'login': 'vanhhoang', 'name': 'Vanh <&>', 'bio': 'Hello <world> & friends',
                  'created_at': '2023-04-07T03:14:07Z', 'followers': 2, 'following': 10, 'public_gists': 0}
        svg = profile.render(person, [], calendar_fixture(), datetime(2026, 10, 28, tzinfo=timezone.utc))
        parsed = ET.fromstring(svg)
        self.assertEqual(parsed.tag, '{http://www.w3.org/2000/svg}svg')
        self.assertIn('Hello &lt;world&gt; &amp; friends', svg)
        self.assertIn('No language data', svg)
        self.assertNotIn('__TYPE_', svg)
        self.assertIn('2026-10-28 00:00 UTC', svg)

    def test_incomplete_fetch_keeps_last_successful_svg(self):
        person = {'login': 'vanhhoang', 'name': 'Vanh'}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'header.svg'
            target.write_text('last successful snapshot')
            with patch.object(sys, 'argv', ['generate_profile.py', '--output', str(target)]), \
                 patch.object(profile, 'fetch', side_effect=[json.dumps(person), '[]', '<html>Unavailable</html>']):
                with self.assertRaises(ValueError):
                    profile.main()
            self.assertEqual(target.read_text(), 'last successful snapshot')


if __name__ == '__main__':
    unittest.main()
