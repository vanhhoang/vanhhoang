# Terminal profile

A dark charcoal terminal with gray text, square borders, subtle scanlines, shell prompts, a typewriter command, and a blinking block cursor. Muted amber highlights repository/star counts, the contribution total, and the cursor. Charts use desaturated slate-blue and gray shades. Reduced-motion visitors see a static command. The SVG is an illustration; actual navigation links appear below it in the README.

The layout uses six framed TUI panes inspired by btop: Profile, GitHub Pulse, Activity, Language Mix, Contributions, and Timeline. Pane titles interrupt the thin borders; amber highlights the profile pane and key counters. Identity appears once in the profile pane. The public README ends with a compact row of links: Repositories, Activity, and Stars. Technical explanations and maintenance commands live in this document.

## Animation

The panes appear sequentially and language/event bars grow to their actual values. The closing command types in and its cursor blinks. A three-column streak card appears above the contribution heatmap, with Year Contributions, Current Streak, and Longest Streak. Its amber ring draws on entry and the flame pulses gently when a streak is active. The entire Contributions pane remains above the daily Timeline.

All motion uses embedded SVG/CSS with no scripts or external services. `prefers-reduced-motion: reduce` disables every animation, reveals all content immediately, and displays the final command as static text. A [review preview](previews/README.md) includes a PNG and the previous SVG for comparison.

## Data and meaning

The generator reads public information directly from GitHub:

- Identity and account creation date: `GET /users/vanhhoang`. An empty bio uses a general welcome message. No location, employer, or job title is inferred.
- Repositories, followers, following, and public gists: public account/repository data. All repository pages are fetched.
- Stars received: sum of stargazer counts on original public repositories, excluding forks.
- Contribution activity: the calendar and yearly total visible on the public GitHub profile. These are GitHub's contribution definitions, not a commit count. The public chart may include anonymized private contributions if the account owner enables them.
- Active days and longest streak: dates with nonzero activity in that displayed calendar; the longest streak counts consecutive dates, not contribution intensity. Future dates are excluded.
- Streak card: totals and streaks are scoped to the displayed contribution year, not lifetime account activity. Current streak ends today or yesterday; yesterday remains eligible while today is in progress. Two empty days end the current streak. Longest-streak ties use the earliest run in the displayed year. Each streak shows its actual date range, with an explicit empty state when no run exists. The ring is decorative, not a completion percentage. A standalone version is generated as `assets/streak.svg` from the same data and layout.
- Public event monitor and daily log: `GET /users/vanhhoang/events/public`, paginated up to GitHub's 300-event / 30-day limit. The histogram shows the last 14 UTC dates from those returned events; the type breakdown covers the available 30-day window. Push events are not commit counts. Daily logs summarize event types without featuring any repository. GitHub may delay event delivery by 30 seconds to 6 hours. Missing API data fails the refresh; it is not substituted with zero.
- Account age: days since the public account creation date, as of the UTC snapshot date. Source/fork ratio includes all owned public repositories; archived repositories are counted separately.
- Languages: each original public repository's primary language, counted once per repository. Forks and repositories with no classified language are excluded. Percentages describe repository counts, not code bytes, skill level, or time spent coding.

Sources:

- https://docs.github.com/en/rest/users/users#get-a-user
- https://docs.github.com/en/rest/repos/repos#list-repositories-for-a-user
- https://docs.github.com/en/rest/activity/events#list-public-events-for-a-user
- https://github.com/users/vanhhoang/contributions
- https://docs.github.com/en/account-and-profile/concepts/contributions-visible-on-your-profile

Streak card layout reference: https://github.com/DenverCoder1/github-readme-streak-stats. The implementation here uses the local Python renderer and the existing public contribution calendar rather than the hosted widget.

## Refresh

`.github/workflows/update-profile.yml` runs at minute 17 of every hour, on relevant pushes to main/master, and through **Actions → Refresh terminal profile → Run workflow**. It uses the built-in `GITHUB_TOKEN`; no personal access token or external image service is required. The token is sent only to GitHub's REST API. The job writes `assets/header.svg` and `assets/streak.svg` back to the repo.

After the files reach the repository's default branch, the workflow can refresh the profile automatically. This is a periodic snapshot, not a live socket. The terminal displays its UTC sync time; GitHub Actions scheduling and image caching may delay updates. Scheduled workflows can be disabled after 60 days of inactivity in public repositories. A manual run or re-enabling the workflow restores updates.

The contribution calendar is parsed from GitHub's public HTML. If GitHub changes its markup or a fetch fails, generation fails and the last successful SVG remains in place rather than displaying invented zero values. Inspect the Actions run for errors.

GitHub documentation: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

## Local commands

```sh
python3 scripts/generate_profile.py
python3 -m unittest discover -s tests -v
```

The script uses only Python's standard library. `GITHUB_TOKEN` is optional for local runs and increases REST rate limits when supplied through the environment. Do not put a token in source files.

Edit colors and layout in `scripts/generate_profile.py`; `assets/header.svg` is generated output. README navigation links remain editable in `README.md`.
