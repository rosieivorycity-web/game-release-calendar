# Setup Checklist

## 1 — Create the repository
Create a GitHub repository, ideally named `game-release-calendar`.

For GitHub Free, make it public if you want GitHub Pages without relying on a paid private-repository Pages entitlement.

## 2 — Upload this package
Upload the contents of this folder to the root of the repository. Preserve the folders:

- `.github/workflows/pages.yml`
- `data/`
- `scripts/`

Commit to `main`.

## 3 — Enable Pages
Go to:

**Repository → Settings → Pages → Build and deployment → Source → GitHub Actions**

The included workflow follows GitHub's custom Pages deployment flow:
checkout → build → validate → configure Pages → upload Pages artifact → deploy.

## 4 — Wait for the first deployment
Open **Actions** and select `Build and deploy game release calendar`.

When it completes successfully, GitHub will show the Pages URL.

If your repository is named `game-release-calendar`, it will normally resemble:

`https://YOUR-USERNAME.github.io/game-release-calendar/`

Your permanent calendar feed is:

`https://YOUR-USERNAME.github.io/game-release-calendar/game-releases.ics`

## 5 — Subscribe

### Apple Calendar / iPhone / iPad / Mac
Open the landing page and choose **Subscribe in Apple Calendar**, or add the permanent `.ics` URL as a subscribed calendar.

### Google Calendar
On the desktop Google Calendar website choose:

**Other calendars → + → From URL**

Paste the permanent `.ics` feed URL.

## 6 — Future updates
Update `data/releases.json` and commit the change. GitHub Pages will rebuild and redeploy the same URL.

The workflow also runs once each morning in `America/Denver`. This scheduled run is useful for validation and for any future updater you connect, but the included repository does not scrape the web by itself.

## Important
Do not delete and recreate existing release entries just because a date changes. Keep their `uid`, change the date, update `last_verified`, and increment `sequence`.
