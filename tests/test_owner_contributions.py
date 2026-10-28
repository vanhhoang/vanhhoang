"""An owner-visible year must not degrade into the workflow token's sparse view."""

from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import generate_profile as profile
from test_dynamic_profile import NOW, PERSON, REPOS, EVENTS, calendar_fixture


def owner_response():
    """Synthetic API fixture: 966 contributions over the requested 365 dates."""
    days = []
    for i in range(365):
        count = 3 if i < 236 else 2
        days.append({'date': str(NOW.date() - timedelta(days=364 - i)),
                     'contributionCount': count,
                     'contributionLevel': 'THIRD_QUARTILE' if count == 3 else 'SECOND_QUARTILE'})
    return {'data': {'viewer': {'login': 'example'}, 'user': {'contributionsCollection': {
        'restrictedContributionsCount': 961,
        'contributionCalendar': {'totalContributions': 966,
                                'weeks': [{'contributionDays': days[i:i + 7]}
                                          for i in range(0, len(days), 7)]}}}}}


class OwnerContributionTests(unittest.TestCase):
    @patch.dict(os.environ, {'PROFILE_TOKEN': 'owner-test-token', 'GITHUB_TOKEN': 'workflow-test-token'}, clear=True)
    @patch.object(profile, 'fetch')
    def test_owner_view_keeps_dense_daily_data_in_the_same_365_date_window(self, fetch):
        fetch.return_value = json.dumps(owner_response())
        calendar = profile.contribution_calendar('example', NOW, require_owner=True)
        self.assertEqual(calendar.total, 966)
        self.assertEqual(calendar.restricted_count, 961)  # Included in total; never add twice.
        self.assertEqual(len(calendar.counts), 365)
        self.assertEqual(sum(calendar.counts.values()), 966)
        self.assertEqual(calendar.visibility, 'owner-authenticated')
        self.assertEqual(min(calendar.counts).isoformat(), '2025-10-29')
        self.assertEqual(profile.streak_details(calendar, NOW.date())['current'], 365)
        request = fetch.call_args.args[1]
        self.assertEqual(request['variables']['login'], 'example')
        self.assertEqual(request['variables']['from'], '2025-10-29T00:00:00Z')
        self.assertIn('contributionsCollection(from:$from,to:$to)', request['query'])
        self.assertNotIn('owner-test-token', json.dumps(request))
        self.assertEqual(fetch.call_count, 1)
        files = profile.build_outputs(PERSON, REPOS, calendar, EVENTS, NOW)
        self.assertIn('966', files['header-dark.svg'])
        self.assertIn('Year Contributions', files['header-dark.svg'])
        self.assertNotIn('LIMITED VIEW', files['header-dark.svg'])
        snapshot = profile.make_snapshot(PERSON, REPOS, calendar, EVENTS, NOW)
        restored = profile.unpack_snapshot(snapshot)[2]
        self.assertEqual(restored.visibility, 'owner-authenticated')
        self.assertEqual(restored.counts, calendar.counts)
        self.assertNotIn('owner-test-token', json.dumps(snapshot))

    @patch.dict(os.environ, {'GITHUB_TOKEN': 'workflow-test-token'}, clear=True)
    @patch.object(profile, 'fetch')
    def test_full_year_requirement_cannot_fall_back_to_a_workflow_or_public_view(self, fetch):
        with self.assertRaisesRegex(ValueError, 'PROFILE_TOKEN'):
            profile.contribution_calendar('example', NOW, require_owner=True)
        fetch.assert_not_called()

    @patch.dict(os.environ, {'PROFILE_TOKEN': 'owner-test-token'}, clear=True)
    @patch.object(profile, 'fetch')
    def test_wrong_account_or_owner_errors_never_fall_back(self, fetch):
        for mode in ('wrong_owner', 'forbidden', 'partial'):
            with self.subTest(mode=mode):
                fetch.reset_mock()
                response = owner_response()
                if mode == 'wrong_owner':
                    response['data']['viewer']['login'] = 'someone-else'
                elif mode == 'forbidden':
                    response['errors'] = [{'type': 'FORBIDDEN', 'message': 'Not authorized'}]
                else:
                    response['data']['user']['contributionsCollection']['contributionCalendar']['weeks'].pop()
                fetch.return_value = json.dumps(response)
                with self.assertRaises(ValueError):
                    profile.contribution_calendar('example', NOW)
                self.assertEqual(fetch.call_count, 1)

    @patch.dict(os.environ, {'PROFILE_TOKEN': 'owner-test-token', 'GITHUB_TOKEN': 'workflow-test-token'}, clear=True)
    @patch.object(profile, 'urlopen')
    def test_owner_token_is_used_only_for_owner_endpoints_and_requires_read_user(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers = {'X-OAuth-Scopes': 'read:user'}
        response.read.return_value = b'{}'
        urlopen.return_value = response
        profile.fetch('https://api.github.com/graphql', {'query': 'query { viewer { login } }'})
        self.assertEqual(urlopen.call_args.args[0].get_header('Authorization'), 'Bearer owner-test-token')
        profile.fetch('https://api.github.com/user')
        self.assertEqual(urlopen.call_args.args[0].get_header('Authorization'), 'Bearer owner-test-token')
        profile.fetch('https://api.github.com/users/example')
        self.assertEqual(urlopen.call_args.args[0].get_header('Authorization'), 'Bearer workflow-test-token')
        profile.fetch('https://github.com/users/example/contributions')
        self.assertIsNone(urlopen.call_args.args[0].get_header('Authorization'))
        response.headers = {'X-OAuth-Scopes': 'public_repo'}
        with self.assertRaisesRegex(ValueError, 'read:user'):
            profile.fetch('https://api.github.com/graphql', {'query': 'query { viewer { login } }'})

    @patch.dict(os.environ, {'PROFILE_TOKEN': 'owner-test-token'}, clear=True)
    @patch.object(profile, 'fetch')
    def test_private_profile_uses_owner_counts_and_does_not_save_private_user_fields(self, fetch):
        fetch.return_value = json.dumps({**PERSON, 'followers': 27, 'following': 43,
                                        'email': 'private@example.test', 'total_private_repos': 19})
        person = profile.account_profile('example')
        self.assertEqual(fetch.call_args.args[0], 'https://api.github.com/user')
        self.assertEqual(person['followers'], 27)
        self.assertEqual(person['following'], 43)
        snapshot = profile.make_snapshot(person, REPOS, calendar_fixture(), EVENTS, NOW)
        self.assertEqual(snapshot['profile']['followers'], 27)
        self.assertNotIn('email', snapshot['profile'])
        self.assertNotIn('total_private_repos', snapshot['profile'])

    @patch.dict(os.environ, {'PROFILE_TOKEN': 'owner-test-token'}, clear=True)
    @patch.object(profile, 'fetch')
    def test_wrong_owner_profile_does_not_fall_back_to_public_zero_counts(self, fetch):
        fetch.return_value = json.dumps({**PERSON, 'login': 'someone-else'})
        with self.assertRaises(ValueError):
            profile.account_profile('example')
        self.assertEqual(fetch.call_count, 1)

    @patch.dict(os.environ, {}, clear=True)
    @patch.object(profile, 'fetch')
    def test_local_public_profile_preview_still_works_without_an_owner_token(self, fetch):
        fetch.return_value = json.dumps(PERSON)
        self.assertEqual(profile.account_profile('example'), PERSON)
        self.assertEqual(fetch.call_args.args[0], 'https://api.github.com/users/example')

    def test_legacy_snapshot_is_marked_limited_instead_of_claiming_complete_data(self):
        calendar = calendar_fixture()
        snapshot = profile.make_snapshot(PERSON, REPOS, calendar, EVENTS, NOW)
        for field in ('visibility', 'restricted_count'):
            snapshot['calendar'].pop(field)
        loaded = profile.unpack_snapshot(snapshot)[2]
        self.assertEqual(loaded.visibility, 'viewer-limited')
        header = profile.build_outputs(PERSON, REPOS, loaded, EVENTS, NOW)['header-dark.svg']
        self.assertIn('Visible Contributions', header)
        self.assertIn('LIMITED VIEW / UTC', header)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / 'legacy.json'
            legacy.write_text(json.dumps(snapshot))
            args = ['generate_profile.py', '--username', 'example', '--from-snapshot', str(legacy),
                    '--output-dir', str(root / 'assets'), '--readme', str(root / 'README.md')]
            with patch.object(sys, 'argv', args):
                profile.main()
            upgraded = json.loads((root / 'assets/profile-data.json').read_text())
            self.assertEqual(upgraded['calendar']['visibility'], 'viewer-limited')
            self.assertEqual(upgraded['fetched_at'], snapshot['fetched_at'])
            self.assertEqual(upgraded['calendar']['total'], snapshot['calendar']['total'])

    @patch.dict(os.environ, {'GITHUB_TOKEN': 'workflow-test-token'}, clear=True)
    def test_missing_owner_secret_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / 'assets'
            assets.mkdir()
            targets = [root / 'README.md', assets / 'header-dark.svg', assets / 'profile-data.json']
            for target in targets:
                target.write_text('previous successful snapshot')
            args = ['generate_profile.py', '--username', 'example', '--require-owner-calendar',
                    '--output-dir', str(assets), '--readme', str(root / 'README.md')]
            with patch.object(sys, 'argv', args), patch.object(profile, 'fetch',
                    side_effect=[json.dumps(PERSON), json.dumps(REPOS)]) as fetch:
                with self.assertRaisesRegex(ValueError, 'PROFILE_TOKEN'):
                    profile.main()
                self.assertEqual(fetch.call_count, 2)
            for target in targets:
                self.assertEqual(target.read_text(), 'previous successful snapshot')


if __name__ == '__main__':
    unittest.main()
