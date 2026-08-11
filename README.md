# 🎮 Game Release Calendar — PC • PS5 • Nintendo

A GitHub Pages-ready, subscribable iCalendar feed for:

- PC
- PlayStation 5
- Nintendo Switch
- Nintendo Switch 2
- Full game releases
- DLC and expansions
- Add-on packs
- Major/substantial content updates
- New-platform releases and major remasters/collections

The included seed data contains **144 dated events** as of August 11, 2026.

## Permanent feed

After GitHub Pages is enabled, your calendar feed will be:

`https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/game-releases.ics`

The same `.ics` URL works as the source feed for Apple Calendar and Google Calendar.

## Fast setup

1. Create a new **public** GitHub repository. A name such as `game-release-calendar` works well.
2. Upload **all files and folders in this package** to the repository root.
3. Commit them to the `main` branch.
4. Open **Settings → Pages**.
5. Under **Build and deployment → Source**, choose **GitHub Actions**.
6. Open the **Actions** tab. The included `Build and deploy game release calendar` workflow will build, validate, and publish the site.
7. When deployment finishes, open the Pages URL. The landing page automatically shows and copies the correct permanent feed URL.

## Updating releases

Edit `data/releases.json`. Then commit the change.

The GitHub Actions workflow:
1. rebuilds `game-releases.ics`,
2. validates the event count and required fields,
3. deploys the refreshed file to the **same permanent URL**.

Do not rename `game-releases.ics` after subscribers begin using it.

### Existing events

Keep the existing `uid` unchanged when changing an event's date, price, notes, or source. This helps calendar clients recognize it as the same event.

If you make a meaningful change to an existing event, increment its `sequence` number. The builder also includes `LAST-MODIFIED` based on `last_verified`.

### New event example

```json
{
  "uid": "leave-this-blank-or-create-a-stable-id",
  "date": "2026-11-20",
  "title": "Example Game",
  "platforms": ["PC", "PS5"],
  "release_type": "Game",
  "price": "$59.99",
  "notes": "Standard edition.",
  "source": "https://official.example.com/release",
  "status": "confirmed",
  "last_verified": "2026-08-11",
  "sequence": 0
}
```

If `uid` is omitted or blank, `scripts/build_calendar.py` generates one from the title and release type.

## Apple Calendar

Open the Pages landing page on an Apple device and use **Subscribe in Apple Calendar**. The page converts the permanent HTTPS feed address to `webcal:` for the subscription handoff.

You can also copy the HTTPS feed URL and add it as a subscribed calendar manually.

## Google Calendar

On desktop Google Calendar:

**Other calendars → + → From URL**

Paste the permanent HTTPS address ending in `/game-releases.ics`.

## Files

- `game-releases.ics` — live subscribable calendar
- `index.html` — public landing page with search/filtering and subscription controls
- `data/releases.json` — editable source-of-truth release data
- `data/metadata.json` — generated feed metadata
- `scripts/build_calendar.py` — standard-library iCalendar generator
- `scripts/validate_calendar.py` — basic validation
- `.github/workflows/pages.yml` — GitHub Pages build/deploy workflow
- `.nojekyll` — tells Pages to serve the static files as-is

## Automation boundary

The repository automatically **builds and publishes** changes to the data, but it does not independently research the web for newly announced games. A separate updater needs to change `data/releases.json` (manually, via a bot, or via an integration) before GitHub can publish those new facts.

That separation is intentional: it prevents an unattended scraper from silently adding bad dates or prices to the calendar.

## Data policy

Prefer official publisher, developer, PlayStation, Nintendo, and storefront announcements. Use reputable release calendars for discovery, and clearly mark information that has not been verified directly.
