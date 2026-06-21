# Cowork Dashboard 2.1 Skeleton — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `cowork-dashboard` React artifact skeleton — a single self-contained `.jsx` that renders one of four modes off a Python-resolved `state.mode`, holds edits locally, and emits a versioned `SAVE_DAY` envelope on explicit save — with all framework-free logic in a Node-tested `cowork-logic.js`.

**Architecture:** Two files, no build step. `cowork-logic.js` holds pure, unit-tested logic (save-envelope construction, positional-slot serialization, streak display re-export). `cowork-dashboard.jsx` inlines that logic verbatim, then defines brand-styled presentational primitives, four mode components (stubbed in 2.1), and a root that routes on `state.mode` and owns Save. Logic is tested by shelling Node from pytest (the proven `test_streak_parity.py` pattern); a drift-guard test asserts the inlined copy matches the source. React components are verified by eyeball in cowork.

**Tech Stack:** Plain ES JS (no JSX) for logic; React (artifact runtime) + Tailwind for the `.jsx`; Node (already on PATH) for logic tests, invoked from pytest.

## Global Constraints

- Single self-contained `.jsx` — no build step, no npm, no bundler, no imports cowork can't resolve. Tailwind available in the artifact runtime. (Spec: Architecture.)
- NSLS brand tokens, exact hex: navy `#18315A`, bluegray `#33475B`, darkblue `#425B76`, teal `#0091AE`, gold `#EEB117`, lightblue `#E5F5F8`, white `#FFFFFF`, nearblack `#191919`. Teal = the one action accent; gold = done/streak/accomplishment, used sparingly. (Spec: Visual language.)
- Progress discs are **solid filled** (not hollow rings): not-started = light-gray disc; partial = teal conic sweep; full = teal disc; done = gold disc. (Spec: Visual language.)
- Type: `"Lexend Deca", -apple-system, system-ui, "Segoe UI", sans-serif` — NO external font `@import` (CDN blocked). (Spec: Visual language.)
- Portrait, single column, ~420px target content width (cowork side panel). (Spec: Visual language.)
- Mode is **resolved by Python and passed in as `state.mode`** — the artifact NEVER re-derives mode. (Spec: Mode routing.)
- Top-3 is **positional, exactly 3 slots, never compacted** — empty slots preserved through render AND serialization. (Spec: JSON contract + Save protocol.)
- Save is explicit only — no ambient autosave to chat/vault. Local draft persistence is allowed (local-only, no chat turns). (Spec: Save protocol + draft durability.)
- Logic lives in `cowork-logic.js` and is inlined verbatim into the `.jsx` between sentinel comments; a drift-guard test keeps them identical. (Spec: Source structure.)
- Node test pattern: shell `node` from a pytest test, feed JSON on stdin, compare to expected — mirror `companion/tests/test_streak_parity.py`. Skip if `node` absent.

---

### Task 1: `cowork-logic.js` — module scaffold + serializeForSave (positional slots)

**Files:**
- Create: `cowork-artifact/cowork-logic.js`
- Test: `companion/tests/test_cowork_logic.py`

**Interfaces:**
- Produces: `serializeForSave(state) -> { type:"SAVE_DAY", schemaVersion, saveId, date, notePath, baseHash, changes:{ top3, bonus, unplanned, habits, energy, gratitude, dailyInsight, statusTransition } }`. `top3` in `changes` is a 3-element positional array preserving empty slots (`{slot, text, progress, disposition}`); habits reduced to `{id, percent}`. `saveId` is passed in by the caller (`opts.saveId`) so it's deterministic/testable.
- CommonJS + `window` dual export object `coworkLogic`.

- [ ] **Step 1: Write the failing test**

```python
# companion/tests/test_cowork_logic.py
"""Node tests for cowork-logic.js (the artifact's framework-free logic).

Shells `node` to exercise the pure helpers, mirroring test_streak_parity.py.
Skips cleanly if node is unavailable.
"""
import json, shutil, subprocess
from pathlib import Path
import pytest

LOGIC_JS = Path(__file__).resolve().parents[2] / "cowork-artifact" / "cowork-logic.js"

def _run(fn_call_js, payload):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    if not LOGIC_JS.exists():
        pytest.fail(f"cowork-logic.js not found at {LOGIC_JS}")
    harness = (
        "const m=require(process.argv[1]);"
        "const input=JSON.parse(require('fs').readFileSync(0,'utf8'));"
        f"process.stdout.write(JSON.stringify({fn_call_js}));"
    )
    proc = subprocess.run([node, "-e", harness, str(LOGIC_JS)],
                          input=json.dumps(payload), capture_output=True, text=True)
    if proc.returncode != 0:
        pytest.fail(f"node failed:\n{proc.stderr}")
    return json.loads(proc.stdout)

SAMPLE_STATE = {
    "schemaVersion": 1, "date": "2026-06-17", "notePath": "01-daily/2026-06-17.md",
    "baseHash": "abc123", "mode": "command", "status": "active", "phase": "active",
    "top3": [
        {"slot": 0, "text": "Spec", "project": "Toolkit", "weekRank": 1, "progress": 75, "disposition": "active"},
        {"slot": 1, "text": "", "project": None, "weekRank": None, "progress": 0, "disposition": "active"},
        {"slot": 2, "text": "Vendor", "project": None, "weekRank": None, "progress": 100, "disposition": "done"},
    ],
    "bonus": [{"text": "PR", "progress": 0, "disposition": "active"}],
    "unplanned": [{"text": "Unblock", "progress": 100, "disposition": "done"}],
    "habits": [{"id": "walk", "name": "Walk", "emoji": "🚶", "percent": 1.0, "streakDays": 12, "status": "ok"}],
    "energy": {"morning": "High", "evening": None},
    "gratitude": "", "dailyInsight": "", "insightReflection": "",
}

def test_serialize_envelope_shape():
    env = _run("m.coworkLogic.serializeForSave(input, {saveId:'sid-1'})", SAMPLE_STATE)
    assert env["type"] == "SAVE_DAY"
    assert env["schemaVersion"] == 1
    assert env["saveId"] == "sid-1"
    assert env["date"] == "2026-06-17"
    assert env["notePath"] == "01-daily/2026-06-17.md"
    assert env["baseHash"] == "abc123"

def test_serialize_preserves_positional_empty_slots():
    env = _run("m.coworkLogic.serializeForSave(input, {saveId:'sid-1'})", SAMPLE_STATE)
    top3 = env["changes"]["top3"]
    assert len(top3) == 3                       # never compacted
    assert top3[1]["slot"] == 1
    assert top3[1]["text"] == ""                # empty slot survives
    assert top3[0]["progress"] == 75
    assert top3[2]["disposition"] == "done"

def test_serialize_reduces_habits():
    env = _run("m.coworkLogic.serializeForSave(input, {saveId:'sid-1'})", SAMPLE_STATE)
    assert env["changes"]["habits"] == [{"id": "walk", "percent": 1.0}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/python -m pytest companion/tests/test_cowork_logic.py -q`
Expected: FAIL — `cowork-logic.js not found` (pytest.fail) on each test.

- [ ] **Step 3: Write minimal implementation**

```javascript
// cowork-artifact/cowork-logic.js
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
// === COWORK-LOGIC:END ===

const coworkLogic = { serializeForSave };
if (typeof module !== "undefined" && module.exports) { module.exports = { coworkLogic }; }
if (typeof window !== "undefined") { window.coworkLogic = coworkLogic; }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `~/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/python -m pytest companion/tests/test_cowork_logic.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add cowork-artifact/cowork-logic.js companion/tests/test_cowork_logic.py
git commit -m "feat(cowork): serializeForSave with positional slots + SAVE_DAY envelope"
```

---

### Task 2: `cowork-logic.js` — streak display re-export + statusTransition

**Files:**
- Modify: `cowork-artifact/cowork-logic.js`
- Modify: `companion/tests/test_cowork_logic.py`

**Interfaces:**
- Produces: `coworkLogic.streakLabel(habit) -> string` (e.g. `"🔥12"` when `streakDays>0` and `status!=='reset'`, else `""`). `serializeForSave(state, {statusTransition})` carries the transition through.

- [ ] **Step 1: Write the failing test**

```python
# append to companion/tests/test_cowork_logic.py
def test_streak_label_active():
    out = _run("m.coworkLogic.streakLabel(input)",
               {"streakDays": 12, "status": "ok"})
    assert out == "🔥12"

def test_streak_label_zero_is_blank():
    out = _run("m.coworkLogic.streakLabel(input)",
               {"streakDays": 0, "status": "ok"})
    assert out == ""

def test_serialize_carries_status_transition():
    env = _run("m.coworkLogic.serializeForSave(input, {saveId:'s', statusTransition:'active'})", SAMPLE_STATE)
    assert env["changes"]["statusTransition"] == "active"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/python -m pytest companion/tests/test_cowork_logic.py -k "streak_label or status_transition" -q`
Expected: FAIL — `m.coworkLogic.streakLabel is not a function` (statusTransition test already passes from Task 1).

- [ ] **Step 3: Write minimal implementation**

Add inside the sentinel block (before the `=== COWORK-LOGIC:END ===` line):

```javascript
function streakLabel(habit) {
  if (!habit || !habit.streakDays || habit.status === "reset") return "";
  return "🔥" + habit.streakDays;
}
```

And add `streakLabel` to the `coworkLogic` object:

```javascript
const coworkLogic = { serializeForSave, streakLabel };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `~/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/python -m pytest companion/tests/test_cowork_logic.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add cowork-artifact/cowork-logic.js companion/tests/test_cowork_logic.py
git commit -m "feat(cowork): streakLabel display helper + statusTransition passthrough"
```

---

### Task 3: `cowork-dashboard.jsx` — artifact shell, SAMPLE state, mode routing, inlined logic

**Files:**
- Create: `cowork-artifact/cowork-dashboard.jsx`
- Test: `companion/tests/test_cowork_artifact.py`

**Interfaces:**
- Consumes: the `=== COWORK-LOGIC:BEGIN/END ===` block from `cowork-logic.js` (inlined verbatim).
- Produces: a default-exported `CoworkDashboard` React component; a `SAMPLE` state constant matching the spec's JSON contract; routing that renders `<MorningCoachCards/>`, `<CommandCenter/>`, `<EveningCoachCards/>`, or `<Results/>` based on `state.mode`.

- [ ] **Step 1: Write the failing test (drift guard + structural asserts)**

```python
# companion/tests/test_cowork_artifact.py
"""Structural tests for the cowork-dashboard artifact source.

The .jsx is verified visually in a real cowork session; here we only assert the
machine-checkable invariants: the inlined logic matches cowork-logic.js (drift
guard), the four modes are wired, and the brand tokens / constraints are present.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "cowork-artifact"
JSX = ROOT / "cowork-dashboard.jsx"
LOGIC = ROOT / "cowork-logic.js"

def _sentinel_block(text):
    m = re.search(r"// === COWORK-LOGIC:BEGIN ===\n(.*?)\n// === COWORK-LOGIC:END ===",
                  text, re.DOTALL)
    return m.group(1) if m else None

def test_jsx_exists():
    assert JSX.exists()

def test_inlined_logic_matches_source():
    jsx_block = _sentinel_block(JSX.read_text())
    logic_block = _sentinel_block(LOGIC.read_text())
    assert jsx_block is not None, "no COWORK-LOGIC sentinel block in the .jsx"
    assert logic_block is not None, "no COWORK-LOGIC sentinel block in cowork-logic.js"
    assert jsx_block == logic_block, "inlined logic has drifted from cowork-logic.js"

def test_routes_all_four_modes():
    src = JSX.read_text()
    for mode in ("coach-morning", "command", "coach-evening", "results"):
        assert mode in src, f"mode {mode} not referenced"
    for comp in ("MorningCoachCards", "CommandCenter", "EveningCoachCards", "Results"):
        assert comp in src, f"component {comp} not defined"

def test_sample_state_has_contract_fields():
    src = JSX.read_text()
    for field in ("schemaVersion", "mode", "status", "phase", "top3", "habits", "baseHash"):
        assert field in src, f"SAMPLE missing {field}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/python -m pytest companion/tests/test_cowork_artifact.py -q`
Expected: FAIL — `test_jsx_exists` (file missing) and the rest.

- [ ] **Step 3: Write minimal implementation**

Create `cowork-artifact/cowork-dashboard.jsx`. Paste the `=== COWORK-LOGIC:BEGIN ===`…`=== COWORK-LOGIC:END ===` block **verbatim** from `cowork-logic.js` (copy the current contents of that block exactly — the drift-guard test enforces equality). Then add the React shell:

```jsx
import { useState } from "react";

// === COWORK-LOGIC:BEGIN ===
// <<< paste the exact block from cowork-logic.js here, verbatim >>>
// === COWORK-LOGIC:END ===

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `~/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/python -m pytest companion/tests/test_cowork_artifact.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add cowork-artifact/cowork-dashboard.jsx companion/tests/test_cowork_artifact.py
git commit -m "feat(cowork): dashboard artifact shell — SAMPLE state, mode routing, 4 stubbed modes"
```

---

### Task 4: Brand-styled presentational primitives + Command Center stub fleshed to the cockpit-portrait look

**Files:**
- Modify: `cowork-artifact/cowork-dashboard.jsx`
- Modify: `companion/tests/test_cowork_artifact.py`

**Interfaces:**
- Produces: `<Disc progress disposition>`, `<TaskRow item>`, `<Panel title>`, `<HabitChip habit>`, `<Header state>`, `<SaveBar onSave dirty>` presentational components; `CommandCenter` renders the real cockpit-portrait layout (header, banner, Top 3 with discs, Bonus/unplanned, habits, save bar) from `state`.

- [ ] **Step 1: Write the failing test**

```python
# append to companion/tests/test_cowork_artifact.py
def test_brand_tokens_present():
    src = JSX.read_text()
    for hexv in ("#18315A", "#0091AE", "#EEB117"):  # navy, teal, gold
        assert hexv in src, f"brand color {hexv} missing"

def test_font_stack_has_no_cdn_import():
    src = JSX.read_text()
    assert "Lexend Deca" in src
    assert "fonts.googleapis" not in src and "@import" not in src

def test_primitives_defined():
    src = JSX.read_text()
    for comp in ("Disc", "TaskRow", "Panel", "HabitChip", "Header", "SaveBar"):
        assert comp in src, f"primitive {comp} not defined"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/python -m pytest companion/tests/test_cowork_artifact.py -k "brand or font or primitives" -q`
Expected: FAIL — primitives not defined / brand hex absent (the stub had no colors).

- [ ] **Step 3: Write minimal implementation**

Add a `T` token object and the primitives, and replace the `CommandCenter` stub. Discs are solid (conic-gradient fill for partial, solid teal full, solid gold done). Keep inline `style` objects (Tailwind also fine; inline keeps brand hex literal for the test and avoids depending on Tailwind config). Representative code:

```jsx
const T = { navy:"#18315A", bluegray:"#33475B", darkblue:"#425B76", teal:"#0091AE",
  gold:"#EEB117", lightblue:"#E5F5F8", white:"#FFFFFF", nearblack:"#191919",
  font:'"Lexend Deca",-apple-system,system-ui,"Segoe UI",sans-serif' };

function Disc({ progress = 0, disposition = "active" }) {
  let bg;
  if (disposition === "done" || progress >= 100) bg = T.gold;
  else if (progress <= 0) bg = "#E5EAF1";
  else bg = `conic-gradient(${T.teal} ${progress}%, #E5EAF1 0)`;
  return <span style={{ width:24, height:24, borderRadius:"50%", background:bg,
    flex:"none", opacity: disposition === "deleted" ? 0.4 : 1 }} />;
}

function TaskRow({ item }) {
  const struck = item.disposition === "done" || item.disposition === "deleted";
  return (
    <div style={{ display:"flex", gap:12, alignItems:"flex-start", padding:"11px 0",
      borderTop:"1px solid #EDF1F6" }}>
      <Disc progress={item.progress} disposition={item.disposition} />
      <div style={{ flex:1 }}>
        <div style={{ fontSize:14, color:T.nearblack,
          textDecoration: struck ? "line-through" : "none",
          opacity: item.disposition === "deleted" ? 0.5 : 1 }}>{item.text || "—"}</div>
        {(item.project || item.weekRank) && (
          <div style={{ fontSize:11, color:T.darkblue, marginTop:3 }}>
            {item.project}{item.weekRank ? ` · week rank ${item.weekRank}` : ""}</div>)}
      </div>
      {item.progress > 0 && <div style={{ fontSize:11, fontWeight:600,
        color: item.disposition==="done"||item.progress>=100 ? T.gold : T.teal }}>{item.progress}%</div>}
    </div>
  );
}

function Panel({ title, hint, children }) {
  return (
    <section style={{ background:T.white, borderRadius:14, padding:16, marginBottom:12 }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10 }}>
        <h2 style={{ fontSize:11, letterSpacing:".13em", textTransform:"uppercase",
          color:T.darkblue, fontWeight:600, margin:0 }}>{title}</h2>
        {hint && <span style={{ fontSize:10, color:"#9aa7b6" }}>{hint}</span>}
      </div>
      {children}
    </section>
  );
}

function HabitChip({ habit }) {
  const hit = habit.percent >= 1.0;
  return (
    <div style={{ display:"flex", gap:6, alignItems:"center", border:"1px solid #EDF1F6",
      borderRadius:10, padding:"8px 11px", fontSize:12, color: hit ? T.bluegray : "#9aa7b6",
      borderColor: hit ? "#F2DFA6" : "#EDF1F6", background: hit ? "#FEFAF0" : T.white }}>
      <span>{habit.emoji} {habit.name}</span>
      {coworkLogic.streakLabel(habit) && (
        <span style={{ color:T.gold, fontWeight:600 }}>{coworkLogic.streakLabel(habit)}</span>)}
    </div>
  );
}

function Header({ state }) {
  return (
    <div style={{ color:T.white, padding:"4px 6px 16px" }}>
      <div style={{ fontSize:19, fontWeight:600 }}>{state.todayPretty || state.date}</div>
      <div style={{ display:"flex", gap:10, alignItems:"center", marginTop:7 }}>
        <span style={{ fontSize:10, letterSpacing:".12em", textTransform:"uppercase",
          color:"#9DB2CE", border:"1px solid #34507e", borderRadius:999, padding:"3px 9px" }}>
          {state.mode}</span>
        {state.energy?.morning && <span style={{ fontSize:12, color:"#9DB2CE", marginLeft:"auto" }}>
          Energy <b style={{ color:T.gold }}>{state.energy.morning}</b></span>}
      </div>
    </div>
  );
}

function SaveBar({ dirty, onSave }) {
  return (
    <>
      <button onClick={onSave} style={{ background:T.gold, color:T.navy, border:"none",
        borderRadius:11, padding:13, fontWeight:700, fontSize:14, width:"100%",
        fontFamily:T.font, cursor:"pointer", opacity: dirty ? 1 : 0.7 }}>
        Save progress{dirty ? "" : " ✓"}</button>
      <div style={{ textAlign:"center", fontSize:11, color:"#9DB2CE", marginTop:10 }}>
        {dirty ? "Unsaved changes — saves once, to your vault" : "Saved · no autosave"}</div>
    </>
  );
}

function CommandCenter({ state, dirty, onSave }) {
  return (
    <div style={{ background:T.navy, borderRadius:20, padding:18, maxWidth:420,
      margin:"0 auto", fontFamily:T.font }}>
      <Header state={state} />
      {state.phase !== "closing" ? (
        <div style={{ background:"#22406E", borderRadius:12, padding:"11px 13px",
          color:"#C9D8EE", fontSize:12, marginBottom:14 }}>
          <b style={{ color:"#fff" }}>Good job —</b> mark progress any time. Type <code>done</code> when closing the day.</div>
      ) : (
        <div style={{ background:"#22406E", borderRadius:12, padding:"11px 13px",
          color:"#C9D8EE", fontSize:12, marginBottom:14 }}>
          <b style={{ color:"#fff" }}>Closing the day —</b> finish marking progress, then type <code>done</code>.</div>
      )}
      <Panel title="Top 3" hint="tap a disc to set 0–100%">
        {state.top3.map((it) => <TaskRow key={it.slot} item={it} />)}
      </Panel>
      <Panel title="Bonus & unplanned">
        {[...state.bonus, ...state.unplanned].map((it, i) => <TaskRow key={i} item={it} />)}
      </Panel>
      <Panel title="Habits today">
        <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
          {state.habits.map((h) => <HabitChip key={h.id} habit={h} />)}
        </div>
      </Panel>
      <SaveBar dirty={dirty} onSave={onSave} />
    </div>
  );
}
```

Update the root to pass `dirty`/`onSave` (wired fully in Task 5; pass `dirty={false}` and a no-op for now):

```jsx
return <CommandCenter state={draft} dirty={false} onSave={() => {}} />;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `~/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/python -m pytest companion/tests/test_cowork_artifact.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add cowork-artifact/cowork-dashboard.jsx companion/tests/test_cowork_artifact.py
git commit -m "feat(cowork): cockpit-portrait primitives + real Command Center layout"
```

---

### Task 5: Wire Save (sendPrompt envelope) + local-draft mechanism + dirty indicator

**Files:**
- Modify: `cowork-artifact/cowork-dashboard.jsx`
- Modify: `companion/tests/test_cowork_artifact.py`

**Interfaces:**
- Consumes: `coworkLogic.serializeForSave`, the global `sendPrompt(text)` (cowork runtime).
- Produces: a Save handler that builds the envelope and calls `sendPrompt("SAVE_DAY " + JSON.stringify(envelope))`; a `dirty` flag flipped by edits; a local-draft persist/restore keyed by `date + baseHash` using `localStorage` if present, falling back to an in-memory ref.

- [ ] **Step 1: Write the failing test**

```python
# append to companion/tests/test_cowork_artifact.py
def test_save_uses_sendprompt_envelope():
    src = JSX.read_text()
    assert "serializeForSave" in src
    assert "sendPrompt(" in src
    assert "SAVE_DAY " in src  # the chat-message prefix Claude parses

def test_draft_persistence_with_fallback():
    src = JSX.read_text()
    assert "localStorage" in src              # local draft (no chat turn)
    # graceful fallback when localStorage is unavailable in the runtime
    assert "typeof localStorage" in src or "try" in src

def test_dirty_indicator_wired():
    src = JSX.read_text()
    assert "dirty" in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/python -m pytest companion/tests/test_cowork_artifact.py -k "sendprompt or draft or dirty" -q`
Expected: FAIL — `sendPrompt(` and `localStorage` absent (Task 4 used a no-op onSave).

- [ ] **Step 3: Write minimal implementation**

Replace the root component with a stateful version. A monotonically increasing counter gives a deterministic-enough `saveId` without `Date.now()`/`Math.random()` (which are fine in a real artifact runtime, but a counter avoids any reliance on them):

```jsx
export default function CoworkDashboard({ state = SAMPLE }) {
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
    } catch (e) { /* in-memory only; draft survives re-render via React state */ }
  }

  function save() {
    const envelope = coworkLogic.serializeForSave(draft, { saveId: `${draft.date}-${saveCount + 1}` });
    setSaveCount(saveCount + 1);
    if (typeof sendPrompt === "function") {
      sendPrompt("SAVE_DAY " + JSON.stringify(envelope));
    }
    setDirty(false);
    try {
      if (typeof localStorage !== "undefined") localStorage.removeItem(draftKey);
    } catch (e) { /* nothing to clear */ }
  }

  const mode = draft.mode; // resolved by Python; never re-derived here
  const common = { state: draft, dirty, onSave: save, onUpdate: update };
  if (mode === "coach-morning") return <MorningCoachCards {...common} />;
  if (mode === "coach-evening") return <EveningCoachCards {...common} />;
  if (mode === "results") return <Results {...common} />;
  return <CommandCenter {...common} />;
}
```

Update the stubbed mode components to accept the extra props without erroring (they already ignore extras). `CommandCenter` already takes `state, dirty, onSave`.

- [ ] **Step 4: Run test to verify it passes**

Run: `~/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/python -m pytest companion/tests/test_cowork_artifact.py -q`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add cowork-artifact/cowork-dashboard.jsx companion/tests/test_cowork_artifact.py
git commit -m "feat(cowork): wire sendPrompt SAVE_DAY envelope + local draft + dirty indicator"
```

---

### Task 6: Full suite green + publish a preview artifact for visual verification

**Files:**
- Verify only (no new source); optional `cowork-artifact/mockups/` preview.

- [ ] **Step 1: Run the entire test suite**

Run: `~/.claude/local-plugins/nsls-personal-toolkit/companion/.venv/bin/python -m pytest companion -q`
Expected: PASS — all prior tests (186+) plus the new cowork-logic (6) and cowork-artifact (10) tests green.

- [ ] **Step 2: Visual verification (cowork-side)**

The `.jsx` renders only in cowork. Produce a static HTML preview of the `CommandCenter` (transpile-free: copy the JSX markup into a plain HTML file, as the mockups already do) OR hand Davo the `.jsx` to paste into a real cowork session. Confirm against the cockpit-portrait mockup: navy frame, solid discs (teal partial / gold done), compact habit chips with streaks, gold save bar, narrow column. Per the spec's verification discipline, the authoritative check is a real cowork session, not a simulator.

- [ ] **Step 3: Commit any preview + a one-line plan-status note**

```bash
git add -A
git commit -m "chore(cowork): 2.1 skeleton complete — suite green, preview for cowork verification"
```

---

## Self-Review

**1. Spec coverage:**
- Visual language (cockpit-portrait, brand tokens, solid discs, font stack, portrait width) → Tasks 4, plus token/font/width tests. ✓
- Source structure (`cowork-logic.js` + `.jsx` inlined, drift guard) → Tasks 1–3 + drift-guard test. ✓
- Mode routing resolved in Python, `state.mode`, no JS re-derivation → Task 3 (routes on `draft.mode`, comment), Global Constraints. ✓
- JSON state contract (positional top3, dispositions, habits, energies, status/phase) → Task 1 SAMPLE + serialize tests; Task 3 SAMPLE constant. ✓
- SAVE_DAY versioned envelope (schemaVersion, saveId, baseHash, changes) → Task 1 + Task 5 wiring. ✓
- Conflict-aware field-level patch on save → this is **Claude's save-handler prompt contract (Phase 3)**, not artifact code; the artifact's job (carry baseHash + saveId + field-level `changes`) is covered in Tasks 1/5. Noted as out-of-scope-for-2.1-code in the spec. ✓
- Local draft durability + dirty indicator → Task 5. ✓
- Testing (Node-from-pytest, drift guard, eyeball) → Tasks 1–5 tests + Task 6. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows full code. The Task 3 inlined block says "paste verbatim from cowork-logic.js" — that's an explicit copy instruction enforced by the drift-guard test, not a vague placeholder. ✓

**3. Type consistency:** `serializeForSave(state, opts)`, `streakLabel(habit)`, `coworkLogic` export name, `CoworkDashboard`/`CommandCenter`/`Disc`/`TaskRow`/`Panel`/`HabitChip`/`Header`/`SaveBar`, prop names (`state`, `dirty`, `onSave`, `onUpdate`) are consistent across Tasks 1–5. ✓

**Note (carried from spec):** verifying `localStorage` availability in the real cowork runtime is flagged for a Phase-0-style check; Task 5 already guards it with try/catch + `typeof` so the artifact degrades to in-memory if it's blocked.
