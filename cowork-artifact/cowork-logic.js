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
// === COWORK-LOGIC:END ===

const coworkLogic = { serializeForSave, streakLabel };
if (typeof module !== "undefined" && module.exports) { module.exports = { coworkLogic }; }
if (typeof window !== "undefined") { window.coworkLogic = coworkLogic; }
