# Phase 0.2 — Counter Round-Trip Test Artifact

**Purpose:** prove an artifact can hand its state back to Claude, who writes it to the vault
in one turn. This is the gate before any real UI is built.

It also **probes open question O2** (how does an artifact return data to Claude?). The
component feature-detects every hand-back mechanism it can find (`window.claude`, message
passing to the parent frame, etc.) and shows you on-screen what's available — so we learn the
real mechanism instead of guessing.

## How to run it (in the cowork project)

Paste this to the cowork agent:

> Render the React component below as an artifact. It's a counter with a Save button. When I
> click Save, take the counter value it reports and write it to
> `50-reference/cowork-counter.md` as a single line: `count: <N>` plus the current timestamp.
> Tell me **how** you received the value — did the artifact hand it to you automatically
> (and via what API), or did I have to copy it from the screen into chat?

**Report back:** the hand-back mechanism (auto via an API, or manual copy), and whether the
file got written with the right number.

## Success criteria

- [ ] Artifact renders and the counter increments/decrements.
- [ ] The "What this runtime exposes" panel lists whatever hand-back APIs exist (or says none).
- [ ] On Save, the counter value reaches Claude and lands in `50-reference/cowork-counter.md`.
- [ ] We can state, in one sentence, the mechanism the real save step will use.

## Component

```jsx
import { useState, useEffect } from "react";

export default function CounterTest() {
  const [count, setCount] = useState(0);
  const [probe, setProbe] = useState([]);
  const [saved, setSaved] = useState(null);

  // Probe the runtime for any artifact->Claude hand-back mechanism (open question O2).
  useEffect(() => {
    const found = [];
    if (typeof window !== "undefined") {
      if (window.claude) {
        found.push("window.claude present: " + Object.keys(window.claude).join(", "));
        if (typeof window.claude.complete === "function") found.push("window.claude.complete() exists");
      } else {
        found.push("window.claude: NOT present");
      }
      found.push("window.parent !== window: " + (window.parent !== window));
      found.push("postMessage available: " + (typeof window.postMessage === "function"));
    }
    setProbe(found);
  }, []);

  // Try every plausible hand-back path; whichever works tells us the mechanism.
  async function save() {
    const payload = { count, ts: new Date().toISOString() };
    let how = "none — relay manually: " + JSON.stringify(payload);
    try {
      if (window.claude && typeof window.claude.complete === "function") {
        await window.claude.complete("SAVE_COUNTER " + JSON.stringify(payload));
        how = "window.claude.complete()";
      } else if (window.parent !== window) {
        window.parent.postMessage({ type: "cowork:save", payload }, "*");
        how = "postMessage to parent (type cowork:save)";
      }
    } catch (e) {
      how = "error: " + e.message;
    }
    setSaved(how);
  }

  return (
    <div style={{ fontFamily: "system-ui", padding: 24, maxWidth: 480 }}>
      <h2 style={{ margin: 0 }}>Counter round-trip test</h2>
      <p style={{ color: "#78716c", marginTop: 4 }}>Phase 0.2 — artifact → Claude → vault</p>

      <div style={{ display: "flex", alignItems: "center", gap: 16, margin: "20px 0" }}>
        <button onClick={() => setCount((c) => c - 1)} style={btn}>−</button>
        <span style={{ fontSize: 40, fontWeight: 700, minWidth: 60, textAlign: "center" }}>{count}</span>
        <button onClick={() => setCount((c) => c + 1)} style={btn}>+</button>
      </div>

      <button onClick={save} style={{ ...btn, width: "auto", background: "#1d4ed8", color: "white", padding: "10px 18px" }}>
        Save → write count:{count} to vault
      </button>

      {saved && (
        <p style={{ marginTop: 12, fontSize: 13 }}>
          Hand-back attempt: <code>{saved}</code>
        </p>
      )}

      <div style={{ marginTop: 24, padding: 12, background: "#f5f5f4", borderRadius: 8, fontSize: 12 }}>
        <strong>What this runtime exposes:</strong>
        <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
          {probe.map((p, i) => (<li key={i}><code>{p}</code></li>))}
        </ul>
      </div>
    </div>
  );
}

const btn = {
  fontSize: 20,
  width: 44,
  height: 44,
  borderRadius: 8,
  border: "1px solid #d6d3d1",
  background: "white",
  cursor: "pointer",
};
```
