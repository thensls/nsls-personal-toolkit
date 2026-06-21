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
  // close-day enters the CLOSING REVIEW (Command Center in closing mode — mark
  // progress on each task, add unplanned wins). continue-close then moves to the
  // Insight/Gratitude evening cards. finish-close commits the closed day.
  if (action === "lock-in") { s.status = "active"; s.phase = "active"; s.mode = "command"; }
  else if (action === "close-day") { s.phase = "closing"; s.mode = "command"; }
  else if (action === "continue-close") { s.phase = "closing"; s.mode = "coach-evening"; }
  else if (action === "finish-close") { s.status = "closed"; s.mode = "results"; }
  return s;
}

function addUnplanned(state, text) {
  const t = (text || "").trim();
  if (!t) return state;  // blank is a no-op
  const list = (state.unplanned || []).slice();
  list.push({ text: t, progress: 0, disposition: "active" });
  return Object.assign({}, state, { unplanned: list });
}
// === COWORK-LOGIC:END ===

const coworkLogic = { serializeForSave, streakLabel, cycleProgress, toggleDisposition, dayStats, transition, addUnplanned };

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

function TaskRow({ item, onItemChange }) {
  const struck = item.disposition === "done" || item.disposition === "deleted";
  const editable = typeof onItemChange === "function";
  const tapDisc = editable
    ? () => onItemChange(Object.assign({}, item, { progress: coworkLogic.cycleProgress(item.progress) }))
    : undefined;
  return (
    <div style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "11px 0",
      borderTop: "1px solid #EDF1F6" }}>
      <span onClick={tapDisc} style={{ cursor: editable ? "pointer" : "default", flex: "none" }}>
        <Disc progress={item.progress} disposition={item.disposition} />
      </span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, color: T.nearblack, lineHeight: 1.3,
          textDecoration: struck ? "line-through" : "none",
          opacity: item.disposition === "deleted" ? 0.5 : 1 }}>{item.text || "—"}</div>
        {(item.project || item.weekRank) && (
          <div style={{ fontSize: 11, color: T.darkblue, marginTop: 3 }}>
            {item.project}{item.weekRank ? ` · week rank ${item.weekRank}` : ""}</div>)}
      </div>
      {editable ? (
        <div style={{ display: "flex", gap: 8, marginTop: 1 }}>
          <button title="Mark done" onClick={() => onItemChange(coworkLogic.toggleDisposition(item, "done"))}
            style={{ border: "none", background: "none", cursor: "pointer", fontSize: 14, padding: 0,
              color: item.disposition === "done" ? T.gold : "#C5CDD8" }}>✓</button>
          <button title="Delete (reversible)" onClick={() => onItemChange(coworkLogic.toggleDisposition(item, "deleted"))}
            style={{ border: "none", background: "none", cursor: "pointer", fontSize: 13, padding: 0,
              color: item.disposition === "deleted" ? "#C2433B" : "#C5CDD8" }}>✕</button>
        </div>
      ) : (item.progress > 0 && (
        <div style={{ fontSize: 11, fontWeight: 600, marginTop: 2,
          color: item.disposition === "done" || item.progress >= 100 ? T.gold : T.teal }}>
          {item.progress}%</div>))}
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

function ActionBar({ dirty, onSave, onCloseDay }) {
  return (
    <>
      <div style={{ display: "flex", gap: 10 }}>
        <button onClick={onSave} style={{ background: T.gold, color: T.navy, border: "none",
          borderRadius: 11, padding: 13, fontWeight: 700, fontSize: 14, flex: 2,
          fontFamily: T.font, cursor: "pointer", opacity: dirty ? 1 : 0.7 }}>
          Save progress{dirty ? "" : " ✓"}</button>
        <button onClick={onCloseDay} style={{ background: "transparent", color: "#C9D8EE",
          border: "1px solid #34507e", borderRadius: 11, padding: 13, fontWeight: 600,
          fontSize: 14, flex: 1, fontFamily: T.font, cursor: "pointer" }}>
          Close Day</button>
      </div>
      <div style={{ textAlign: "center", fontSize: 11, color: "#9DB2CE", marginTop: 10 }}>
        {dirty ? "Unsaved changes — saves once, to your vault" : "Saved · no autosave"}</div>
    </>
  );
}

function EnergyPicker({ value, onPick }) {
  const opts = ["Low", "Medium", "High"];
  return (
    <div style={{ display: "flex", gap: 8 }}>
      {opts.map((o) => (
        <button key={o} onClick={() => onPick(o)} style={{ flex: 1, padding: "9px 0",
          borderRadius: 10, fontFamily: T.font, fontSize: 13, cursor: "pointer",
          border: "1px solid " + (value === o ? T.teal : "#D7DEE8"),
          background: value === o ? T.lightblue : "#fff",
          color: value === o ? T.navy : T.darkblue, fontWeight: value === o ? 600 : 400 }}>
          {o}</button>
      ))}
    </div>
  );
}

function CoachShell({ title, subtitle, children }) {
  return (
    <div style={{ background: T.navy, borderRadius: 20, padding: 18, maxWidth: 420,
      margin: "0 auto", fontFamily: T.font }}>
      <div style={{ color: "#fff", padding: "4px 6px 14px" }}>
        <div style={{ fontSize: 20, fontWeight: 600 }}>{title}</div>
        {subtitle && <div style={{ fontSize: 12, color: "#9DB2CE", marginTop: 4 }}>{subtitle}</div>}
      </div>
      {children}
    </div>
  );
}

function CoachButton({ label, onClick }) {
  return (
    <button onClick={onClick} style={{ background: T.gold, color: T.navy, border: "none",
      borderRadius: 11, padding: 13, fontWeight: 700, fontSize: 14, width: "100%",
      fontFamily: T.font, cursor: "pointer" }}>{label}</button>
  );
}

function MorningCoachCards({ state, onUpdate, onLockIn }) {
  function setEnergy(v) {
    onUpdate(Object.assign({}, state, { energy: Object.assign({}, state.energy, { morning: v }) }));
  }
  return (
    <div data-mode="coach-morning">
      <CoachShell title="Good morning" subtitle={(state.todayPretty || state.date) + " · plan your day"}>
        <Panel title="How's your energy this morning?">
          <EnergyPicker value={state.energy && state.energy.morning} onPick={setEnergy} />
        </Panel>
        <Panel title="Your Top 3" hint="confirm or edit">
          {state.top3.map((it) => <TaskRow key={it.slot} item={it} />)}
        </Panel>
        <CoachButton label="Complete 'Open Day' →" onClick={onLockIn} />
      </CoachShell>
    </div>
  );
}

function EveningTextarea({ value, onChange }) {
  return (
    <textarea rows={3} defaultValue={value || ""} onChange={(e) => onChange(e.target.value)}
      style={{ width: "100%", border: "1px solid #D7DEE8", borderRadius: 8, padding: 8,
        fontSize: 13, fontFamily: T.font, boxSizing: "border-box", resize: "vertical" }} />
  );
}

function EveningCoachCards({ state, onUpdate, onFinishClose }) {
  const stats = coworkLogic.dayStats(state);
  function setField(k, v) { onUpdate(Object.assign({}, state, { [k]: v })); }
  function setEvening(v) {
    onUpdate(Object.assign({}, state, { energy: Object.assign({}, state.energy, { evening: v }) }));
  }
  return (
    <div data-mode="coach-evening">
      <CoachShell title="Closing the day"
        subtitle={`${stats.top3Done}/${stats.top3Total} Top 3 · ${stats.habitsDone}/${stats.habitsTotal} habits`}>
        <Panel title="Reflection">
          <EveningTextarea value={state.insightReflection} onChange={(v) => setField("insightReflection", v)} />
        </Panel>
        <Panel title="Gratitude (optional)">
          <EveningTextarea value={state.gratitude} onChange={(v) => setField("gratitude", v)} />
        </Panel>
        <Panel title="Evening energy">
          <EnergyPicker value={state.energy && state.energy.evening} onPick={setEvening} />
        </Panel>
        <CoachButton label="Done — close the day" onClick={onFinishClose} />
      </CoachShell>
    </div>
  );
}

function Results({ state }) {
  const stats = coworkLogic.dayStats(state);
  const e = state.energy || {};
  return (
    <div data-mode="results">
      <CoachShell title={state.todayPretty || state.date} subtitle="Day closed · read-only">
        <Panel title="The day">
          <div style={{ fontSize: 13, color: T.bluegray }}>
            {stats.top3Done}/{stats.top3Total} Top 3 done · {stats.habitsDone}/{stats.habitsTotal} habits</div>
          <div style={{ fontSize: 12, color: T.darkblue, marginTop: 8 }}>
            Energy — morning <b>{e.morning || "—"}</b> · evening <b>{e.evening || "—"}</b></div>
        </Panel>
        {state.insightReflection && (
          <Panel title="Reflection">
            <div style={{ fontSize: 13, color: T.bluegray, whiteSpace: "pre-wrap" }}>{state.insightReflection}</div>
          </Panel>)}
        {state.gratitude && (
          <Panel title="Gratitude">
            <div style={{ fontSize: 13, color: T.bluegray, whiteSpace: "pre-wrap" }}>{state.gratitude}</div>
          </Panel>)}
        <Panel title="Top 3">
          {state.top3.map((it) => <TaskRow key={it.slot} item={it} />)}
        </Panel>
      </CoachShell>
    </div>
  );
}

function AddUnplannedInput({ onAdd }) {
  const [text, setText] = useState("");
  function submit() { const t = text.trim(); if (!t) return; onAdd(t); setText(""); }
  return (
    <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
      <input value={text} onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
        placeholder="Add an unplanned win…"
        style={{ flex: 1, border: "1px solid #D7DEE8", borderRadius: 8, padding: "8px 10px",
          fontSize: 13, fontFamily: T.font, boxSizing: "border-box" }} />
      <button onClick={submit} style={{ border: "1px solid " + T.teal, color: T.teal,
        background: "#fff", borderRadius: 8, padding: "8px 14px", fontSize: 13, fontWeight: 600,
        fontFamily: T.font, cursor: "pointer" }}>Add</button>
    </div>
  );
}

function CommandCenter({ state, dirty, onSave, onCloseDay, onContinueClose, onItemChange, onAddUnplanned }) {
  // Phase-aware. Active: mark progress freely; Save progress + Close Day. Closing
  // (the review step reached via Close Day): same task rows + add-unplanned, banner
  // says "review what happened", and the CTA continues into the evening cards.
  // The "type done"-style closing copy never appears in the active phase.
  const closing = state.phase === "closing";
  return (
    <div data-mode="command" style={{ background: T.navy, borderRadius: 20, padding: 18,
      maxWidth: 420, margin: "0 auto", fontFamily: T.font }}>
      <Header state={state} />
      <div style={{ background: "#22406E", borderRadius: 12, padding: "11px 13px",
        color: "#C9D8EE", fontSize: 12, lineHeight: 1.45, marginBottom: 14 }}>
        {closing ? (
          <><b style={{ color: "#fff" }}>Closing the day —</b> review what happened: set each item's progress, add anything unplanned, then continue.</>
        ) : (
          <><b style={{ color: "#fff" }}>Good job —</b> mark progress any time. Click <b>Close Day</b> when you're ready to wrap up.</>
        )}
      </div>
      <Panel title="Top 3" hint="tap a disc to set 0–100%">
        {state.top3.map((it, i) => (
          <TaskRow key={it.slot} item={it}
            onItemChange={onItemChange ? (next) => onItemChange("top3", i, next) : undefined} />
        ))}
      </Panel>
      <Panel title="Bonus & unplanned">
        {state.bonus.map((it, i) => (
          <TaskRow key={"b" + i} item={it}
            onItemChange={onItemChange ? (next) => onItemChange("bonus", i, next) : undefined} />
        ))}
        {state.unplanned.map((it, i) => (
          <TaskRow key={"u" + i} item={it}
            onItemChange={onItemChange ? (next) => onItemChange("unplanned", i, next) : undefined} />
        ))}
        {onAddUnplanned && <AddUnplannedInput onAdd={onAddUnplanned} />}
      </Panel>
      <Panel title="Habits today">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {state.habits.map((h) => <HabitChip key={h.id} habit={h} />)}
        </div>
      </Panel>
      {closing ? (
        <CoachButton label="Continue to close →" onClick={onContinueClose} />
      ) : (
        <ActionBar dirty={dirty} onSave={onSave} onCloseDay={onCloseDay} />
      )}
    </div>
  );
}

export default function CoworkDashboard({ state = SAMPLE }) {
  // Local draft is keyed by date + baseHash so a stale draft can't be restored
  // onto a note that changed underneath us. Persisted to localStorage when the
  // runtime allows it (local-only — NOT the forbidden chat/vault autosave);
  // otherwise it survives re-render via React state alone.
  const draftKey = `cowork-draft:${state.date}:${state.baseHash}`;

  function loadDraft() {
    try {
      if (typeof localStorage !== "undefined") {
        const raw = localStorage.getItem(draftKey);
        if (raw) return JSON.parse(raw);
      }
    } catch (e) { /* localStorage blocked — fall through to seeded state */ }
    return state;
  }

  const [draft, setDraft] = useState(loadDraft);
  const [dirty, setDirty] = useState(false);
  const [saveCount, setSaveCount] = useState(0);

  function update(next) {
    setDraft(next);
    setDirty(true);
    try {
      if (typeof localStorage !== "undefined") localStorage.setItem(draftKey, JSON.stringify(next));
    } catch (e) { /* in-memory only; draft still survives re-render via React state */ }
  }

  // save() takes the state to persist EXPLICITLY (defaults to current draft) so
  // transition handlers can save the post-transition state without waiting for
  // React's async setDraft — avoids a stale-snapshot write.
  function save(stateToSave) {
    const s = stateToSave || draft;
    // Deterministic saveId without Date.now()/Math.random(): date + a counter.
    const envelope = coworkLogic.serializeForSave(s, { saveId: `${s.date}-${saveCount + 1}` });
    setSaveCount(saveCount + 1);
    if (typeof sendPrompt === "function") {
      sendPrompt("SAVE_DAY " + JSON.stringify(envelope));
    }
    setDirty(false);
    try {
      if (typeof localStorage !== "undefined") localStorage.removeItem(draftKey);
    } catch (e) { /* nothing to clear */ }
  }

  // Replace item at index `i` in list `which` ("top3" | "bonus" | "unplanned").
  function changeItem(which, i, next) {
    const list = (draft[which] || []).slice();
    list[i] = next;
    update(Object.assign({}, draft, { [which]: list }));
  }

  function addUnplanned(text) { update(coworkLogic.addUnplanned(draft, text)); }

  function lockIn() { const next = coworkLogic.transition(draft, "lock-in"); setDraft(next); save(next); }
  function closeDay() { update(coworkLogic.transition(draft, "close-day")); }
  function continueClose() { update(coworkLogic.transition(draft, "continue-close")); }
  function finishClose() { const next = coworkLogic.transition(draft, "finish-close"); setDraft(next); save(next); }

  const mode = draft.mode; // resolved by Python; the artifact never re-derives it
  const common = {
    state: draft, dirty, onSave: () => save(), onUpdate: update,
    onCloseDay: closeDay, onContinueClose: continueClose, onLockIn: lockIn,
    onFinishClose: finishClose, onItemChange: changeItem, onAddUnplanned: addUnplanned,
  };
  if (mode === "coach-morning") return <MorningCoachCards {...common} />;
  if (mode === "coach-evening") return <EveningCoachCards {...common} />;
  if (mode === "results") return <Results {...common} />;
  return <CommandCenter {...common} />; // 'command' default
}
