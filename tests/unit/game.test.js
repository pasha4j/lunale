import { describe, expect, test } from 'vitest';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const context = { Math, Date };
context.globalThis = context;
vm.runInNewContext(readFileSync('src/game.js', 'utf8'), context);

const {
  MAX_ATTEMPTS,
  clueFor,
  correctRound1Answer,
  correctRound2Answer,
  getDailyAnswer,
  guessColor,
  hashStr,
  illuminationDone,
  isLunarWizard,
  moonEmoji,
  phaseName,
  todayLocalStr,
} = context.LunaleGame;

describe('date and daily answer helpers', () => {
  test('formats local dates as yyyy-mm-dd', () => {
    expect(todayLocalStr(new Date(2026, 4, 7))).toBe('2026-05-07');
  });

  test('hashStr is stable and unsigned', () => {
    expect(hashStr('lunale-v1::2026-05-07')).toBe(203811937);
    expect(hashStr('lunale-v1::2026-05-07')).toBeGreaterThanOrEqual(0);
  });

  test('getDailyAnswer returns the stable answer for a known date', () => {
    expect(getDailyAnswer('2026-05-07')).toEqual({
      percentage: 38,
      waxing: false,
      dateStr: '2026-05-07',
    });
  });
});

describe('moon phase helpers', () => {
  test('names major phase cases', () => {
    expect(phaseName(100, true)).toBe('Full Moon');
    expect(phaseName(1, false)).toBe('Waning Crescent');
    expect(phaseName(25, true)).toBe('Waxing Crescent');
    expect(phaseName(50, true)).toBe('First Quarter');
    expect(phaseName(50, false)).toBe('Last Quarter');
    expect(phaseName(75, false)).toBe('Waning Gibbous');
  });

  test('maps daily answer to round answers', () => {
    expect(correctRound1Answer({ percentage: 100, waxing: true })).toBe('full');
    expect(correctRound1Answer({ percentage: 12, waxing: true })).toBe('waxing');
    expect(correctRound1Answer({ percentage: 12, waxing: false })).toBe('waning');

    expect(correctRound2Answer({ percentage: 12, waxing: true })).toBe('crescent');
    expect(correctRound2Answer({ percentage: 50, waxing: true })).toBe('first_quarter');
    expect(correctRound2Answer({ percentage: 50, waxing: false })).toBe('third_quarter');
    expect(correctRound2Answer({ percentage: 80, waxing: false })).toBe('gibbous');
  });

  test('chooses share moon emoji', () => {
    expect(moonEmoji(100, true)).toBe('🌕');
    expect(moonEmoji(1, true)).toBe('🌑');
    expect(moonEmoji(25, true)).toBe('🌒');
    expect(moonEmoji(25, false)).toBe('🌘');
    expect(moonEmoji(50, true)).toBe('🌓');
    expect(moonEmoji(50, false)).toBe('🌗');
    expect(moonEmoji(75, true)).toBe('🌔');
    expect(moonEmoji(75, false)).toBe('🌖');
  });
});

describe('guess feedback helpers', () => {
  test('returns clue buckets by absolute distance', () => {
    expect(clueFor(0)).toEqual({ text: 'Nailed it!', exact: true, cls: 'exact' });
    expect(clueFor(4)).toEqual({ text: 'Boiling!', cls: 'boiling' });
    expect(clueFor(10)).toEqual({ text: 'Hot!', cls: 'hot' });
    expect(clueFor(15)).toEqual({ text: 'Getting Hot', cls: 'getting-hot' });
    expect(clueFor(30)).toEqual({ text: 'Cold', cls: 'cold' });
    expect(clueFor(31)).toEqual({ text: 'Freezing', cls: 'freezing' });
  });

  test('returns share colors by absolute distance', () => {
    expect(guessColor(0)).toBe('#67d77f');
    expect(guessColor(4)).toBe('#c85a5a');
    expect(guessColor(10)).toBe('#c8844a');
    expect(guessColor(15)).toBe('#c8b44a');
    expect(guessColor(30)).toBe('#6ba3d6');
    expect(guessColor(31)).toBe('#cdd5de');
  });
});

describe('state-derived helpers', () => {
  test('detects when illumination is complete', () => {
    expect(illuminationDone({ won: false, guesses: [] })).toBe(false);
    expect(illuminationDone({ won: true, guesses: [31] })).toBe(true);
    expect(illuminationDone({ won: false, guesses: [1, 2, 3, 4, 5, 6] })).toBe(true);
    expect(illuminationDone({ won: false, guesses: [1, 2, 3] }, 3)).toBe(true);
    expect(MAX_ATTEMPTS).toBe(6);
  });

  test('detects Lunar Wizard state', () => {
    expect(isLunarWizard({
      ended: true,
      won: true,
      round1Correct: true,
      round2Correct: true,
      round2Skipped: false,
    })).toBe(true);

    expect(isLunarWizard({
      ended: true,
      won: true,
      round1Correct: true,
      round2Correct: false,
      round2Skipped: true,
    })).toBe(true);

    expect(isLunarWizard({
      ended: true,
      won: true,
      round1Correct: true,
      round2Correct: false,
      round2Skipped: false,
    })).toBe(false);
  });
});
