// Canonical streak rule — JS DISPLAY COPY for the cowork artifact.
//
// The authoritative rule lives in Python (companion/streak.py) and the prose
// in skills/close-day/SKILL.md. This file is a verbatim behavioral port for
// rendering streak state inside the Claude Desktop artifact. It must stay in
// lockstep with streak.py — companion/tests/test_streak_parity.py asserts the
// two agree over the canonical sequences. If you change the rule, change
// streak.py first, then mirror it here.
//
// A log entry is { date: 'YYYY-MM-DD', percent: number } where percent is
// 0.0 (miss), 0.5 (partial), or 1.0 (done). Logs are ordered oldest-first,
// the same as the Python DayResult list.

// Walk the log from most recent backwards. Sum partial/miss contributions
// until a 100% day closes the chain.
//   - done (>= 1.0): resets concern to 0, walk stops.
//   - partial (0 < p < 1.0): + 0.5 concern.
//   - miss (= 0.0): + 1.0 concern.
function computeConcern(log) {
  let concern = 0.0;
  for (let i = log.length - 1; i >= 0; i--) {
    const p = log[i].percent;
    if (p >= 1.0) break;
    if (p > 0) concern += 0.5;
    else concern += 1.0;
  }
  return concern;
}

// Map a concern score to a status bucket. Thresholds match streak.py.
function statusFor(concern) {
  if (concern >= 2.0) return "reset";
  if (concern >= 1.5) return "at_risk";
  if (concern >= 1.0) return "one_miss";
  return "ok";
}

// Count consecutive days from today backwards that haven't reset. A day
// triggers reset when cumulative concern up to and including that day >= 2.0.
// Single-pass O(n), mirroring streak.py.streak_days.
function streakDays(log) {
  let concern = 0.0;
  let days = 0;
  for (let i = log.length - 1; i >= 0; i--) {
    const p = log[i].percent;
    if (p >= 1.0) concern = 0.0;
    else if (p > 0) concern += 0.5;
    else concern += 1.0;
    if (concern >= 2.0) break;
    days += 1;
  }
  return days;
}

// Expose for CommonJS (the parity-test node harness) and for browser/artifact
// globals, without assuming either is present.
const streakRule = { computeConcern, statusFor, streakDays };
if (typeof module !== "undefined" && module.exports) {
  module.exports = streakRule;
}
if (typeof window !== "undefined") {
  window.streakRule = streakRule;
}
