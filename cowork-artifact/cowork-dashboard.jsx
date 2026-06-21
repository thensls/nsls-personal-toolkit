import { useState } from "react";

// Framework-free logic, inlined VERBATIM from cowork-logic.js. The block between
// the COWORK-LOGIC sentinels must match cowork-logic.js exactly — a drift-guard
// test (companion/tests/test_cowork_artifact.py) enforces it. Edit cowork-logic.js
// first, then copy the block here.
// === COWORK-LOGIC:BEGIN ===
function serializeForSave(state, opts) {
  opts = opts || {};
  return {
    type: "SAVE_DAY",
    schemaVersion: state.schemaVersion,
    saveId: opts.saveId,
    date: state.date,
    notePath: state.notePath,
    baseHash: state.baseHash,
    changes: {
      top3: (state.top3 || []).map(function (it) {
        return { slot: it.slot, text: it.text, progress: it.progress, disposition: it.disposition };
      }),
      bonus: state.bonus || [],
      unplanned: state.unplanned || [],
      habits: (state.habits || []).map(function (h) { return { id: h.id, percent: h.percent }; }),
      energy: state.energy || {},
      gratitude: state.gratitude || "",
      dailyInsight: state.dailyInsight || "",
      statusTransition: opts.statusTransition || null,
    },
  };
}

function streakLabel(habit) {
  if (!habit || !habit.streakDays || habit.status === "reset") return "";
  return "🔥" + habit.streakDays;
}
// === COWORK-LOGIC:END ===

const coworkLogic = { serializeForSave, streakLabel };

// Hardcoded realistic state for 2.1 (Phase 3 wires Claude's Python parse to produce this).
const SAMPLE = {
  schemaVersion: 1, date: "2026-06-17", notePath: "01-daily/2026-06-17.md",
  baseHash: "seed0000", mode: "command", status: "active", phase: "active",
  todayPretty: "Wednesday, June 17",
  top3: [
    { slot: 0, text: "Finish the toolkit spec", project: "Toolkit", weekRank: 1, progress: 75, disposition: "active" },
    { slot: 1, text: "Q3 LOP draft", project: "Growth", weekRank: 2, progress: 25, disposition: "active" },
    { slot: 2, text: "Reply to vendor", project: null, weekRank: null, progress: 100, disposition: "done" },
  ],
  bonus: [{ text: "Review Red's PR", progress: 0, disposition: "active" }],
  unplanned: [{ text: "Unblocked the cowork build", progress: 100, disposition: "done" }],
  habits: [
    { id: "walk", name: "Walk", emoji: "🚶", percent: 1.0, streakDays: 12, status: "ok" },
    { id: "read15", name: "Read 15m", emoji: "📖", percent: 1.0, streakDays: 5, status: "ok" },
    { id: "workout", name: "Workout", emoji: "💪", percent: 0.0, streakDays: 0, status: "ok" },
  ],
  energy: { morning: "High", evening: null },
  gratitude: "", dailyInsight: "", insightReflection: "",
};

function MorningCoachCards({ state }) { return <div data-mode="coach-morning">Morning Coach Cards — stub</div>; }
function CommandCenter({ state }) { return <div data-mode="command">Command Center — stub</div>; }
function EveningCoachCards({ state }) { return <div data-mode="coach-evening">Evening Coach Cards — stub</div>; }
function Results({ state }) { return <div data-mode="results">Results — stub</div>; }

export default function CoworkDashboard({ state = SAMPLE }) {
  const [draft] = useState(state);
  const mode = draft.mode; // resolved by Python; the artifact never re-derives it
  if (mode === "coach-morning") return <MorningCoachCards state={draft} />;
  if (mode === "coach-evening") return <EveningCoachCards state={draft} />;
  if (mode === "results") return <Results state={draft} />;
  return <CommandCenter state={draft} />; // 'command' default
}
