(function(global) {
  'use strict';

  const MAX_ATTEMPTS = 4;

  function todayLocalStr(date = new Date()) {
    return date.getFullYear() + '-' +
      String(date.getMonth() + 1).padStart(2, '0') + '-' +
      String(date.getDate()).padStart(2, '0');
  }

  // FNV-1a + post-mix -> uniformly distributed 32-bit hash.
  function hashStr(s) {
    let h = 0x811c9dc5 >>> 0;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    h ^= h >>> 16; h = Math.imul(h, 0x85ebca6b) >>> 0;
    h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35) >>> 0;
    h ^= h >>> 16;
    return h >>> 0;
  }

  function getDailyAnswer(dateStr) {
    // Salt the date so future devs can rotate the puzzle space without
    // changing how dates are formatted.
    const h = hashStr('lunale-v1::' + dateStr);
    const percentage = (h % 100) + 1;
    const waxing = (Math.floor(h / 100) % 2) === 0;
    return { percentage, waxing, dateStr };
  }

  function phaseName(pct, waxing) {
    if (pct === 100) return 'Full Moon';
    if (pct === 1 && !waxing) return 'Waning Crescent';
    if (pct < 50) return waxing ? 'Waxing Crescent' : 'Waning Crescent';
    if (pct === 50) return waxing ? 'First Quarter' : 'Last Quarter';
    return waxing ? 'Waxing Gibbous' : 'Waning Gibbous';
  }

  function clueFor(diff) {
    const d = Math.abs(diff);
    if (d === 0) return { text: 'Nailed it!', exact: true, cls: 'exact' };
    if (d <= 4) return { text: 'Boiling!', cls: 'boiling' };
    if (d <= 10) return { text: 'Hot!', cls: 'hot' };
    if (d <= 15) return { text: 'Getting Hot', cls: 'getting-hot' };
    if (d <= 30) return { text: 'Cold', cls: 'cold' };
    return { text: 'Freezing', cls: 'freezing' };
  }

  function correctRound1Answer(answer) {
    if (answer.percentage === 100) return 'full';
    return answer.waxing ? 'waxing' : 'waning';
  }

  function correctRound2Answer(answer) {
    const p = answer.percentage;
    if (p < 50) return 'crescent';
    if (p === 50) return answer.waxing ? 'first_quarter' : 'third_quarter';
    return 'gibbous';
  }

  function illuminationDone(state, maxAttempts = MAX_ATTEMPTS) {
    return state.won || state.guesses.length >= maxAttempts;
  }

  function isLunarMaster(state) {
    if (!state.ended || !state.won) return false;
    if (!state.round1Correct) return false;
    if (!state.round2Skipped && !state.round2Correct) return false;
    return true;
  }

  function moonEmoji(pct, waxing) {
    if (pct >= 98) return '🌕';
    if (pct <= 2) return '🌑';
    if (pct < 50) return waxing ? '🌒' : '🌘';
    if (pct === 50) return waxing ? '🌓' : '🌗';
    return waxing ? '🌔' : '🌖';
  }

  function guessColor(diff) {
    const d = Math.abs(diff);
    if (d === 0) return '#67d77f';
    if (d <= 4) return '#c85a5a';
    if (d <= 10) return '#c8844a';
    if (d <= 15) return '#c8b44a';
    if (d <= 30) return '#6ba3d6';
    return '#cdd5de';
  }

  global.LunaleGame = {
    MAX_ATTEMPTS,
    clueFor,
    correctRound1Answer,
    correctRound2Answer,
    getDailyAnswer,
    guessColor,
    hashStr,
    illuminationDone,
    isLunarMaster,
    moonEmoji,
    phaseName,
    todayLocalStr,
  };
})(globalThis);
