# Theme-aware terminal profile

The README preserves the original animated six-pane terminal: Profile, GitHub Pulse, Activity, Language Mix, Contributions, and Timeline. It embeds a single full-width dashboard for the visitor's light/dark mode, followed by the original Repositories, Activity and Stars navigation. The SVG background is transparent; neutral panel fills and borders use low opacity rather than a fixed page color, allowing GitHub's Light, Dark and Dark dimmed backgrounds to show through.

The two dashboard palettes are selected with GitHub's `#gh-dark-mode-only` and `#gh-light-mode-only` fragments on explicit image links. The dark palette is designed to remain readable on both Dark and Dark dimmed. The SVG does not detect every named theme or inherit GitHub CSS variables; its typography and chart colors retain the selected light/dark palette. Counts and text labels make meaning available without relying only on hue. Public names and bios are escaped as text.

The dashboard is generated as `assets/header-dark.svg` and `assets/header-light.svg`, with `assets/header.svg` preserving its previous URL. Standalone charts and animated streak cards remain available in both palettes for reuse and [preview](previews/README.md). Maintenance notes stay in this document instead of expanding the public profile into a separate report.

## Data sources and definitions

All published values come from GitHub. No sample values are used when refreshing the real profile.

| Display | Source / definition |
| --- | --- |
| Identity, joined date, followers, following, public gists | `GET /users/{login}`. Account age is calculated at the UTC snapshot date. An empty bio uses a general welcome message, without inventing a job title or employer. |
| Owned public repositories, originals, forks | `GET /users/{login}/repos?type=owner&per_page=100&page=N`; fetch every page. Archived repositories remain included. |
| Stars received | Sum of `stargazers_count` on original owned public repositories; forks excluded. Starring someone else's repository is an outgoing activity event and does not increase this total. |
| Language mix | Each original public repository contributes one count for its primary `language`. Forks and unclassified repositories are excluded. This measures repository share, not code bytes, expertise or coding time. |
| Contributions / heatmap | GraphQL `user.contributionsCollection(from:, to:).contributionCalendar`: exact `contributionCount`, `contributionLevel`, and `totalContributions`. The query requests today and the preceding 364 UTC dates. Calendar data can include anonymized counts according to GitHub's visibility rules; private repository names and commit details are never queried. |
| Calendar fallback | Without a token, or if GraphQL explicitly rejects the workflow integration's account-level access, read GitHub's public contribution calendar. Parse exact counts from each day's tooltip, never infer them from the 0–4 heatmap level. Filter to the same 365 UTC dates and calculate the total from those counts. The actual source is recorded in the snapshot. |
| Current / longest streak | Consecutive dates with a positive contribution count in the displayed 365-date window. Yesterday remains eligible while today is in progress. Two empty dates end the current streak. Longest ties use the earliest run. These are window records, not lifetime records. |
| Activity / timeline | `GET /users/{login}/events/public`, up to three 100-event pages. Ignore private, future and older-than-30-day events; deduplicate by event ID. Group into UTC dates. The chart total covers 14 UTC dates; the available-window total covers 30 days. Push events are not commit counts. |

GitHub's event feed exposes at most 300 recent events and can lag by 30 seconds to 6 hours. A zero bar means no events were returned for that UTC date; it does not prove there was no activity. The terminal labels the available API window. Full activity history would require a separate collection service; this repository does not pretend the events endpoint provides it.

## Integrity and saved data

`assets/profile-data.json` contains the most recently fetched real data, the UTC fetch timestamp, a schema version and the contribution source. Only the public fields needed to regenerate this profile are stored. Credentials are never included.

Before replacing anything, the generator checks that:

- All 365 dates have a nonnegative integer contribution count and a valid matching activity level.
- Daily contribution counts add up to the reported total.
- GraphQL has no errors or missing data. Only an explicit integration-permission rejection may switch to the validated public-calendar fallback; unrelated API errors fail the refresh.
- Every generated SVG parses as XML.

Fetch, validation or rendering failures leave the previous README, snapshot and charts intact. Outputs are prepared in memory, then each file is replaced atomically. A filesystem failure during the final write can require rerunning the generator; GitHub Actions does not commit a failed generation.

The snapshot is also a reproducible offline input. Offline regeneration keeps its original sync time, so stale data cannot appear freshly fetched.

## Automatic refresh

`.github/workflows/update-profile.yml` runs at minute 17 of every hour, on relevant source/test/workflow pushes to main/master, and through **Actions → Refresh terminal profile → Run workflow**. It checks out the latest default branch, runs the regression suite, fetches real GitHub data, and commits the generated README, JSON and SVGs if they changed. Generated-only commits do not trigger this workflow again.

The built-in `GITHUB_TOKEN` is supplied only through the environment and sent only to `api.github.com`. No extra secret is required for the public-calendar fallback. A failed GraphQL request caused by rate limits, a partial response or a server error does not silently become zero data. Workflow failures remain visible in Actions.

This is an hourly snapshot, not a live socket. Scheduling and GitHub image caching can delay what visitors see. Public-repository schedules can be disabled after 60 days without repository activity; re-enable or manually run the workflow if needed. Publishing the modified workflow to the repository's default branch is necessary before it can run.

## Local commands

Uses only Python's standard library:

```sh
# Fetch public data; uses GraphQL when GITHUB_TOKEN is available.
python3 scripts/generate_profile.py --username vanhhoang

# Offline regeneration from the last real snapshot, without changing its timestamp.
python3 scripts/generate_profile.py --from-snapshot assets/profile-data.json

# Verify calculations, response validation, theme output and failure handling.
python3 -m unittest discover -s tests -v
```

`--output-dir` and `--readme` let you write previews to another location. Edit `scripts/presentation.py` for the README wrapper and palettes; edit `scripts/generate_profile.py` for data collection or the terminal layout. `README.md` and files in `assets/` are generated and will be overwritten on refresh. The renderer intentionally keeps the original single-terminal README structure across hourly updates.

Charts use a short fade animation. The supplemental terminal retains its entrance, bar-growth, streak-ring, typewriter and cursor effects. All animations respect `prefers-reduced-motion: reduce`. No JavaScript is embedded in the README or SVGs.

## Sources

- [GitHub theme context for Markdown images](https://github.blog/changelog/2021-11-24-specify-theme-context-for-images-in-markdown/)
- [Primer theme attributes and palettes](https://github.com/primer/design/blob/main/content/foundations/primitives/getting-started.mdx)
- [User REST API](https://docs.github.com/en/rest/users/users#get-a-user)
- [Repository REST API](https://docs.github.com/en/rest/repos/repos#list-repositories-for-a-user)
- [GraphQL contribution calendar](https://docs.github.com/en/graphql/reference/users#contributioncalendar)
- [Public calendar fallback](https://github.com/users/vanhhoang/contributions)
- [Public events and their limits](https://docs.github.com/en/rest/activity/events)
- [Scheduled workflow behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
