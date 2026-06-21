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

// NSLS brand tokens (exact hex). teal = the one action accent; gold = done /
// streak / accomplishment, used sparingly. Lexend Deca with a system fallback —
// NO external font import (artifact CDN is blocked).
const T = {
  navy: "#18315A", bluegray: "#33475B", darkblue: "#425B76", teal: "#0091AE",
  gold: "#EEB117", lightblue: "#E5F5F8", white: "#FFFFFF", nearblack: "#191919",
  font: '"Lexend Deca",-apple-system,system-ui,"Segoe UI",sans-serif',
};

// Solid progress disc (never a hollow ring): light-gray = not started,
// teal conic sweep = partial, solid teal = full, solid gold = done.
function Disc({ progress = 0, disposition = "active" }) {
  let bg;
  if (disposition === "done" || progress >= 100) bg = T.gold;
  else if (progress <= 0) bg = "#E5EAF1";
  else bg = `conic-gradient(${T.teal} ${progress}%, #E5EAF1 0)`;
  return (
    <span style={{ width: 24, height: 24, borderRadius: "50%", background: bg,
      flex: "none", marginTop: 1, opacity: disposition === "deleted" ? 0.4 : 1 }} />
  );
}

function TaskRow({ item }) {
  const struck = item.disposition === "done" || item.disposition === "deleted";
  return (
    <div style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "11px 0",
      borderTop: "1px solid #EDF1F6" }}>
      <Disc progress={item.progress} disposition={item.disposition} />
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, color: T.nearblack, lineHeight: 1.3,
          textDecoration: struck ? "line-through" : "none",
          opacity: item.disposition === "deleted" ? 0.5 : 1 }}>{item.text || "—"}</div>
        {(item.project || item.weekRank) && (
          <div style={{ fontSize: 11, color: T.darkblue, marginTop: 3 }}>
            {item.project}{item.weekRank ? ` · week rank ${item.weekRank}` : ""}</div>)}
      </div>
      {item.progress > 0 && (
        <div style={{ fontSize: 11, fontWeight: 600, marginTop: 2,
          color: item.disposition === "done" || item.progress >= 100 ? T.gold : T.teal }}>
          {item.progress}%</div>)}
    </div>
  );
}

function Panel({ title, hint, children }) {
  return (
    <section style={{ background: T.white, borderRadius: 14, padding: 16, marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <h2 style={{ fontSize: 11, letterSpacing: ".13em", textTransform: "uppercase",
          color: T.darkblue, fontWeight: 600, margin: 0 }}>{title}</h2>
        {hint && <span style={{ fontSize: 10, color: "#9aa7b6" }}>{hint}</span>}
      </div>
      {children}
    </section>
  );
}

function HabitChip({ habit }) {
  const hit = habit.percent >= 1.0;
  const label = coworkLogic.streakLabel(habit);
  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center", borderRadius: 10,
      padding: "8px 11px", fontSize: 12, color: hit ? T.bluegray : "#9aa7b6",
      border: "1px solid " + (hit ? "#F2DFA6" : "#EDF1F6"), background: hit ? "#FEFAF0" : T.white }}>
      <span>{habit.emoji} {habit.name}</span>
      {label && <span style={{ color: T.gold, fontWeight: 600 }}>{label}</span>}
    </div>
  );
}

function Header({ state }) {
  return (
    <div style={{ color: T.white, padding: "4px 6px 16px" }}>
      <div style={{ fontSize: 19, fontWeight: 600 }}>{state.todayPretty || state.date}</div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 7 }}>
        <span style={{ fontSize: 10, letterSpacing: ".12em", textTransform: "uppercase",
          color: "#9DB2CE", border: "1px solid #34507e", borderRadius: 999, padding: "3px 9px" }}>
          {state.mode}</span>
        {state.energy && state.energy.morning && (
          <span style={{ fontSize: 12, color: "#9DB2CE", marginLeft: "auto" }}>
            Energy <b style={{ color: T.gold }}>{state.energy.morning}</b></span>)}
      </div>
    </div>
  );
}

function SaveBar({ dirty, onSave }) {
  return (
    <>
      <button onClick={onSave} style={{ background: T.gold, color: T.navy, border: "none",
        borderRadius: 11, padding: 13, fontWeight: 700, fontSize: 14, width: "100%",
        fontFamily: T.font, cursor: "pointer", opacity: dirty ? 1 : 0.7 }}>
        Save progress{dirty ? "" : " ✓"}</button>
      <div style={{ textAlign: "center", fontSize: 11, color: "#9DB2CE", marginTop: 10 }}>
        {dirty ? "Unsaved changes — saves once, to your vault" : "Saved · no autosave"}</div>
    </>
  );
}

function MorningCoachCards({ state }) { return <div data-mode="coach-morning">Morning Coach Cards — stub</div>; }
function EveningCoachCards({ state }) { return <div data-mode="coach-evening">Evening Coach Cards — stub</div>; }
function Results({ state }) { return <div data-mode="results">Results — stub</div>; }

function CommandCenter({ state, dirty, onSave }) {
  const closing = state.phase === "closing";
  return (
    <div data-mode="command" style={{ background: T.navy, borderRadius: 20, padding: 18,
      maxWidth: 420, margin: "0 auto", fontFamily: T.font }}>
      <Header state={state} />
      <div style={{ background: "#22406E", borderRadius: 12, padding: "11px 13px",
        color: "#C9D8EE", fontSize: 12, lineHeight: 1.45, marginBottom: 14 }}>
        {closing ? (
          <><b style={{ color: "#fff" }}>Closing the day —</b> finish marking progress, then type <code>done</code>.</>
        ) : (
          <><b style={{ color: "#fff" }}>Good job —</b> mark progress any time. Type <code>done</code> when closing the day.</>
        )}
      </div>
      <Panel title="Top 3" hint="tap a disc to set 0–100%">
        {state.top3.map((it) => <TaskRow key={it.slot} item={it} />)}
      </Panel>
      <Panel title="Bonus & unplanned">
        {[...state.bonus, ...state.unplanned].map((it, i) => <TaskRow key={i} item={it} />)}
      </Panel>
      <Panel title="Habits today">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {state.habits.map((h) => <HabitChip key={h.id} habit={h} />)}
        </div>
      </Panel>
      <SaveBar dirty={dirty} onSave={onSave} />
    </div>
  );
}

export default function CoworkDashboard({ state = SAMPLE }) {
  const [draft] = useState(state);
  const mode = draft.mode; // resolved by Python; the artifact never re-derives it
  if (mode === "coach-morning") return <MorningCoachCards state={draft} />;
  if (mode === "coach-evening") return <EveningCoachCards state={draft} />;
  if (mode === "results") return <Results state={draft} />;
  return <CommandCenter state={draft} dirty={false} onSave={() => {}} />; // 'command' default
}
