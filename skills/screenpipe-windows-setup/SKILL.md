---
name: screenpipe-windows-setup
description: 'Use when setting up Screenpipe on Windows as the PC alternative to Familiar (Familiar is macOS-only); when /close-day, /familiar, or /self-insight report no screen activity; when a meeting transcript is missing or contains only your own voice; when edits to store.bin do not stick; when a Screenpipe update breaks capture or the screenpipe tools vanish from Claude Desktop; or when reading the Screenpipe database directly from a script.'
---

# Screenpipe on Windows — what the installer won't tell you

## SAFETY: THREE-TIER PERMISSION MODEL

1. **Read-only** — querying `db.sqlite`, `GET /health`, listing the GPU, reading
   `store.bin`. Runs without friction.
2. **Configuration** — editing `store.bin`, changing `ignoredWindows`, installing
   the Claude Desktop MCP shim. Requires closing the app; back up `store.bin`
   first and say which keys will change.
3. **Irreversible or off-machine** — never proactively offered. Explain, confirm,
   then proceed:
   - Setting a **cloud transcription engine** — meeting audio then leaves the
     machine for a third-party vendor (§2).
   - **Lowering `localRetentionDays`** — deletes captured history immediately,
     with no undo and no warning (§6).
   - **`listenOnLan: true`** — exposes the capture API to the network.

Continuous screen capture on a work machine is a data-governance decision, not
just a settings one. Before pointing this at a machine holding member or client
data, clear it with whoever owns that policy.

## Purpose

Familiar is macOS-only, so on Windows the whole personal-capture layer —
`/familiar`, the activity reconstruction in `/close-day`, the screen data
`/self-insight` reads — has no source unless Screenpipe is running *and
configured correctly*. Installing it is easy: download, sign in, done.
**Configuring it so it actually captures what you think it's capturing is not.**

This skill is the difference between those two. Every item below is a failure
that looks like success: capture appears to be running, the app is healthy, and
the data isn't there when you go looking for it weeks later. None of it is in
the documentation, because all of it was found by losing something.

Screenpipe gives you continuous local screen + audio capture, OCR'd, queryable
through a local API (`localhost:3030`) and a SQLite DB (`~/.screenpipe/db.sqlite`).
For connecting other systems, use `/connect` — this skill covers Screenpipe only.

Verified against Screenpipe **2.4.285** on Windows 11 (2026-07). Setting names
drift between versions — if a key below isn't in your `store.bin`, check the UI
before assuming it's gone.

---

## 1. Config edits silently revert

Screenpipe rewrites `~/.screenpipe/store.bin` (JSON, despite the name) from
memory when it exits. Edit it while the app is running and your changes vanish
on quit, with no error.

**Always:** quit → confirm the process is gone → back up → edit → relaunch.

```powershell
Get-Process screenpipe-app -ErrorAction SilentlyContinue
Copy-Item ~\.screenpipe\store.bin ~\.screenpipe\store.bin.bak-CHANGE-YYYYMMDD
```

## 2. Local Whisper silently drops meeting audio without CUDA

`"audioTranscriptionEngine"` defaults to local Whisper, which needs an NVIDIA
GPU. On AMD or Intel graphics it appears to work and then produces nothing —
you find out when you go looking for a transcript that was never written.

```powershell
Get-CimInstance Win32_VideoController | Select-Object Name
```

No NVIDIA? Use a cloud engine — `"deepgram"` plus `"deepgramApiKey"`. Deepgram
signup includes free credit that covers ordinary meeting volume. Keep the key in
your secrets store, never in a script or a commit.

**A cloud engine is the one setting that makes Screenpipe stop being local.**
Screen capture and OCR stay on the machine; meeting audio — both sides of it —
goes to a third-party vendor. Clear that separately from the install itself.

## 3. The other side of a call is only captured if it plays out loud

`"useSystemDefaultAudio": true` captures system output — the other participants.
But **Bluetooth headset output is not captured at all.** If calls go to
Bluetooth, you record only your own voice and never notice until you read a
one-sided transcript.

Route call audio through a device Screenpipe records: wired/USB speakers, or a
USB mic's monitor output.

Related: **don't gate capture on meeting detection.** The detector is unreliable
enough that "only record during meetings" loses real meetings. Record
continuously, filter later.

Watch the double negative: `"disableMeetingDetector": false` leaves the detector
**on**, which is what you want. The rule is about not letting capture depend on
it.

## 4. Updates reset settings and break capture

Set `"autoUpdate": false`. Update deliberately, after backing up `store.bin`.
The Claude Desktop MCP shim is the usual casualty — if the screenpipe tools
disappear from Desktop, reinstall it with the bundled bun:

```powershell
& "$env:LOCALAPPDATA\screenpipe\bun.exe" x screenpipe-mcp@latest
```

Then point `%APPDATA%\Claude\claude_desktop_config.json` at the installed shim
(`...\.bun\bin\screenpipe-mcp.exe`, double-backslashed). The
`SCREENPIPE_API_KEY` it wants is Screenpipe's own local API key, shown in
Screenpipe's settings — not a third-party key.

Also: Claude Desktop can destabilize from the *number* of connectors listed, not
just active ones. If it white-screens after you add one, that's the likely cause.

## 5. Reading the DB directly — two traps

Scripted use should read `~/.screenpipe/db.sqlite` rather than going through
MCP; it's faster and survives MCP breakage. The `frames` table carries
`app_name`, `window_name`, `browser_url`, `timestamp`, `focused`.

1. **Timestamps are UTC with 9-digit (nanosecond) fractions** — Python's
   `fromisoformat` rejects them outright.
2. **Windows consoles are cp1252** and crash on emoji in window titles.

```python
import re, sys
sys.stdout.reconfigure(encoding="utf-8")
ts = re.sub(r"(\.\d{6})\d+", r"\1", raw_ts).replace("Z", "+00:00")
```

## 6. Retention deletes silently

`"localRetentionDays"` rolls off old media with no warning that history is
thinning. Anything needed beyond that window has to be archived out by your own
job, before it ages out.

Retention is also your disk budget — continuous multi-monitor capture becomes
the largest thing on the machine, and roll-off is the only thing holding it
flat. Check what `~/.screenpipe/data/` weighs after two weeks of real capture
before settling on a window.

---

## Known-good settings

Everything above, plus the smaller defaults worth changing. Merge into the
`settings` object with the app closed. Two lines are hardware-specific and must
not be pasted blind: `audioTranscriptionEngine` (see #2) and `audioDevices`
(copy your device name exactly from the Screenpipe UI, including the `(input)`
suffix).

```json
{
  "audioTranscriptionEngine": "deepgram",
  "deepgramApiKey": "PASTE_KEY_FROM_YOUR_SECRETS_STORE",
  "transcriptionMode": "batch",
  "audioChunkDuration": 30,
  "meetingLiveTranscriptionEnabled": true,

  "audioDevices": ["EXACT_DEVICE_NAME_FROM_SCREENPIPE_UI"],
  "useSystemDefaultAudio": true,
  "disableMeetingDetector": false,

  "ocrEngine": "windows-native",
  "useAllMonitors": true,
  "videoQuality": "low",
  "maxSnapshotWidth": 1920,
  "extractionThreadPriority": "below_normal",
  "pauseExtractionOnInputMs": 150,

  "localRetentionEnabled": true,
  "localRetentionDays": 90,
  "localRetentionMode": "media",

  "ignoredWindows": [
    "Private", "Incognito", "VPN", "Keepass", "vault", "Wallpaper",
    "Settings", "Recorder", "OBS Studio", "screenpipe",
    "LockApp.exe", "SearchHost.exe", "ShellExperienceHost.exe",
    "PickerHost.exe", "Taskmgr.exe", "SnippingTool.exe"
  ],
  "usePiiRemoval": false,

  "autoUpdate": false,
  "port": 3030,
  "apiAuth": true,
  "listenOnLan": false
}
```

`ocrEngine: windows-native` is the working engine on Windows. The extraction
priority/pause settings keep capture from fighting the foreground app.
`usePiiRemoval: false` because redaction mangles the window titles and URLs that
downstream scripts parse — revisit it against the governance note above.

`ignoredWindows` matches substrings of window titles, so short entries are
powerful and can over-match. Add your password manager, wallets, and anything
client-confidential, then review after a day of real capture.

## Verify

```powershell
Get-Process screenpipe-app -ErrorAction SilentlyContinue | Select-Object Name
curl.exe http://localhost:3030/health
```

That only proves the app launched — both silent failures above look exactly like
this. Verify the data, not the process.

```python
import sqlite3, pathlib
db = sqlite3.connect(pathlib.Path.home() / ".screenpipe" / "db.sqlite")
print(db.execute(
    "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM frames"
).fetchone())
```

A `MAX(timestamp)` stuck hours ago means capture has stopped while the app still
looks healthy.

Then **make a two-minute test call through the audio path you actually use**,
and check the transcript for two things: that it exists (§2), and that the other
person is in it (§3). Nothing short of a live call catches either.

Finally, confirm the screenpipe tools are listed in Claude Desktop.

## When data is missing — the loop

Screenpipe fails quietly, so the instinct to "check if it's running" resolves
almost nothing: the app is nearly always running. Work the loop instead —
**observe what's missing → find the layer it died at → fix that layer → re-verify
with fresh data, not old data.**

The layers, in the order data moves through them: capture (app running) → write
(frames landing in `db.sqlite`) → transcription (audio → text) → retention (still
present) → access (MCP shim or direct DB read).

Start from the symptom:

| Symptom | Layer | First thing to check |
|---|---|---|
| `/close-day` or `/familiar` shows no activity | capture | Is the app running? `curl localhost:3030/health` |
| App healthy, frame count flat | write | Capture stopped silently — restart, then re-check `MAX(timestamp)` |
| Meeting happened, no transcript at all | transcription | Did `audioTranscriptionEngine` revert to local Whisper? (§2) |
| Transcript has only your own voice | transcription | Call audio went out over Bluetooth (§3) |
| Settings won't stick | config | App was open when `store.bin` was edited (§1) |
| Nothing older than N days | retention | Working as configured — the window is the answer (§6) |
| screenpipe tools gone from Claude Desktop | access | An update replaced the MCP shim — reinstall it (§4) |
| Script crashes or returns nothing | access | Timestamp fractions or console encoding (§5) |

Re-verify against data captured **after** the fix. A transcript that was never
written does not appear retroactively, so confirming a transcription fix always
means holding a new call, not re-reading the old meeting.

## Related skills

- `/familiar` — the macOS counterpart; this skill is its PC-side prerequisite.
- `/close-day`, `/self-insight` — the consumers. If either reports missing screen
  activity, start with the loop above.
- `/connect` — for wiring up any other external system.
