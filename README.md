# Lunale

**Lunale** is a daily moon illumination guessing game for the web.

Play it at [thelunale.com](https://thelunale.com).

Each day, players see a rendered moon phase and try to guess the moon's illumination percentage in six attempts. After the illumination round, they answer phase-direction and phase-type questions for a chance to earn a Lunar Wizard badge.

## Features

- Daily deterministic puzzle
- Six-guess illumination round with hot/cold clues and higher/lower hints
- Follow-up phase rounds for waxing/waning and phase type
- Local statistics, streaks, guess distribution, and badge count
- Shareable result text
- Responsive mobile-first layout

## Project Structure

```text
.
├── index.html              # Main game UI and browser-side app flow
├── privacy.html            # Privacy policy page
├── src/game.js             # Pure game/date/phase helper logic
├── styles/main.css         # Game styling
├── assets/images/          # Logos, moon texture, badge, social image
├── tests/unit/game.test.js # Vitest coverage for core game logic
├── robots.txt
├── sitemap.xml
├── ads.txt
└── CNAME
```

## Development

Install dependencies:

```bash
npm install
```

Run tests:

```bash
npm test
```

The app is static. For quick local development, open `index.html` directly in a browser, or serve the directory with any static file server:

```bash
npx serve .
```

## Deployment

Lunale does not need a build step. Deploy the repository contents as a static site, making sure these files and folders are included:

- `index.html`
- `privacy.html`
- `src/`
- `styles/`
- `assets/`
- `robots.txt`
- `sitemap.xml`
- `ads.txt`
- `CNAME`

## Data And Privacy

Game state and statistics are stored in the player's browser using `localStorage`, with cookies used as a fallback for hosted deployments. The game has no custom backend.

The production page includes Google Analytics and Google AdSense scripts. See [privacy.html](privacy.html) for the user-facing privacy policy.

## Testing Notes

Core game behavior is covered in `tests/unit/game.test.js`, including:

- Daily answer
- Phase naming and round-answer mapping
- Clue and color buckets
- Completion state
- Lunar Wizard eligibility

Run `npm test` before shipping changes to game logic.

## Credits

Moon photo: Gregory H. Revera, [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) via [Wikimedia Commons](https://en.wikipedia.org/wiki/File:FullMoon2010.jpg).

## License

MIT. See [LICENSE](LICENSE).
