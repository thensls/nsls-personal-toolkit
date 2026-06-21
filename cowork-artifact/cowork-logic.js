// Framework-free logic for the cowork-dashboard artifact. Inlined verbatim into
// cowork-dashboard.jsx between the COWORK-LOGIC sentinels; a drift-guard test
// keeps the two identical. Node-tested via companion/tests/test_cowork_logic.py.
//
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

function cycleProgress(p) {
  const steps = [0, 25, 50, 75, 100];
  const i = steps.indexOf(p);
  return steps[(i + 1) % steps.length];  // -1 (unknown) -> steps[0] == 0
}

function toggleDisposition(item, target) {
  const next = item.disposition === target ? "active" : target;
  return Object.assign({}, item, { disposition: next });
}

function dayStats(state) {
  const slots = (state.top3 || []).filter(function (it) {
    return it.text && it.disposition !== "deleted";
  });
  const top3Done = slots.filter(function (it) {
    return it.disposition === "done" || it.progress >= 100;
  }).length;
  const habits = state.habits || [];
  const habitsDone = habits.filter(function (h) { return h.percent >= 1.0; }).length;
  return { top3Done: top3Done, top3Total: slots.length,
    habitsDone: habitsDone, habitsTotal: habits.length };
}

function transition(state, action) {
  const s = Object.assign({}, state);
  if (action === "lock-in") { s.status = "active"; s.phase = "active"; s.mode = "command"; }
  else if (action === "close-day") { s.phase = "closing"; s.mode = "coach-evening"; }
  else if (action === "finish-close") { s.status = "closed"; s.mode = "results"; }
  return s;
}
// === COWORK-LOGIC:END ===

const coworkLogic = { serializeForSave, streakLabel, cycleProgress, toggleDisposition, dayStats, transition };
if (typeof module !== "undefined" && module.exports) { module.exports = { coworkLogic }; }
if (typeof window !== "undefined") { window.coworkLogic = coworkLogic; }
