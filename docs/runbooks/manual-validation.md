---
title: Runbook — scenarios & manual validation (the standing practice)
tier: meta
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - CLAUDE.md
  - docs/COORDINATOR.md
  - docs/MODULE_SPEC.md
  - docs/CONDUIT.md
  - docs/ATLAS.md
  - docs/OPERATING_MODEL.md
  - docs/AUDIT.md
  - docs/audit-log.md
  - docs/NEXT.md
  - docs/TECH_DEBT.md
  - docs/runbooks/release-and-update.md
  - docs/recipes/add-a-module.md
---

# Runbook — scenarios & manual validation (the standing practice)

> **The standing rule:** every user-facing capability ships with **(1)** a Core test for its pure
> logic, **(2)** a numbered **scenario** in this file that recreates the desktop it needs, and
> **(3)** a recorded observation of what actually happened when a human ran it. This runbook is the
> canonical checklist that [CLAUDE.md](../../CLAUDE.md), [MODULE_SPEC.md](../MODULE_SPEC.md) and the
> roadmap gates all point at — keep it living.
>
> **One sentence:** host tests prove the math; only a real desktop proves the behavior — so a green
> `coord test` is never, under any circumstance, a claim about window placement, hotkey capture, DPI
> behavior, drag smoothness, the tray, or the UI.
>
> **⚠ Status: this runbook has never been executed by anyone** (**TD-9** in
> [TECH_DEBT.md](../TECH_DEBT.md)). It is a procedure written by someone who has never performed it,
> for an application that has never run. Its steps may be ambiguous, out of order, or impossible.
> **Revise it as you go, to say what actually had to be done** — a runbook is a record of a procedure
> that worked, not a plan for one. Until then, treat every scenario below as a draft with a
> deliberately empty result line.

---

## 1. Why this exists

`coord test` pins the **pure logic**: zone rectangles from a template and a work area, schedule
arithmetic across a DST boundary, chord arbitration between two modules, settings migration, the
predicate that decides whether a window is one a user would call "open." That is real coverage of the
part most likely to contain an arithmetic bug, and it runs on any operating system, in seconds, with
no hardware.

It is also, by construction, **blind to everything a user can see.** The
[Core/Shell split](../COORDINATOR.md) puts every decision in a `net9.0` project with zero Windows
dependencies — which is exactly why the tests are portable, and exactly why they cannot observe:

| What only a real desktop can answer | Why the tests structurally cannot |
|---|---|
| Did the window actually land where the math said? | The placement call is in the Shell adapter, and the window may clamp, refuse, or reposition itself ([ATLAS §7.3](../ATLAS.md)) |
| Is it *flush* to the edge, or overhanging by a few pixels? | The reported window rect includes an invisible resize border; the visible bounds are a separate attribute ([ATLAS §5.2](../ATLAS.md)) |
| Did the chord actually fire? | Registration is arbitrated by the operating system against every other application on the machine |
| Is the geometry right on a 150% monitor? | Scale factor is per-monitor and the process's DPI-awareness declaration is a manifest-level fact ([ATLAS §5](../ATLAS.md)) |
| Was the drag smooth? | Latency of an input-hook callback is a property of a running message loop ([CONDUIT §5](../CONDUIT.md)) |
| Did the tray icon come back after Explorer restarted? | Tray presence is a shell-lifetime concern with no test surface |
| Did settings survive the update? | It requires two builds, an install, and a real file on a real disk |
| Does the app even launch on a machine without the runtime? | Deployment shape is not a compile-time property (**TD-10**) |

Every one of those has a well-known failure mode, and every one of them is invisible to a green test
run. That is not a gap to be closed later; it is a permanent property of the architecture, and this
runbook is the other half of the evidence.

> **The failure this exists to prevent** is [OPERATING_MODEL §7](../OPERATING_MODEL.md)'s second
> shape — *a claim stronger than its evidence* — in its most tempting form: the tests are green, the
> build succeeded, the logic is obviously right, so the feature works. The window is twenty pixels
> off and nobody knows for three weeks.

---

## 2. The standing rule

**Never mark desktop-dependent work "done" on a green test run alone.** Not "basically done," not
"done pending validation," not "done — will check on the desktop later." The word for that state is
**Core-verified, pending manual validation**, and it is a perfectly respectable thing to write down.

Concretely, a user-facing capability is done when all three exist:

1. **A Core test** for its pure logic, passing via `coord test`.
2. **A scenario** in §4 of this file that recreates the desktop conditions the capability needs, with
   definite pass criteria per step.
3. **A recorded observation** (§6): what was run, on what machine, with what monitor arrangement and
   scaling, on what date, and what actually happened — including the parts that were wrong.

When you cannot get to a Windows machine — which will be often — **write the scenario anyway and
leave it unrun.** A scenario written while the design is fresh is far better than one reconstructed
six weeks later, and leaving it visibly unrun is the honest state. Say plainly what is Core-verified
and what is pending-manual; do not round up.

---

## 3. What a scenario is

A **scenario** is this project's answer to "the config I used to test this": a **written, numbered,
reproducible desktop setup** — monitor arrangement, scaling factors, the applications open, the
starting layout — that anyone can recreate in a couple of minutes and step through deterministically.

It is the dual of a unit-test fixture, for a system whose fixtures are made of hardware and other
people's applications.

**A good scenario has five properties.**

- **It names its rig precisely.** "Two monitors" is not a rig. "Primary 2560×1440 at 100%, secondary
  1920×1080 at 150%, secondary positioned to the *left* of primary" is a rig — and the arrangement
  matters, because a monitor to the left of the primary has negative X coordinates and that is where
  the bugs live.
- **It is recreatable from the text alone.** If reproducing it requires knowing something that is
  only in your head, it is a memory, not a scenario.
- **It is short.** A couple of minutes. A twenty-minute scenario gets skipped, and a skipped check is
  a check that cannot fail — failure shape 1.
- **It is named for what it proves, not what it looks like.** `mixed-DPI dual monitor`, not
  `two screens`.
- **Every step has a definite observable outcome.** "Confirm it looks right" is not a pass criterion.
  "The window's left edge is flush with the monitor's left work-area edge, with no visible gap and no
  overhang onto the adjacent monitor" is.

**Where scenarios live:** here, in §4, numbered `S<n>` and never renumbered — a scenario id is
referenced from module docs, from the audit log, and from release records, so it is as permanent as a
capability id. Retire a scenario by marking it retired; do not reuse its number.

**Every user-facing capability ships with one.** If a capability does not suggest a scenario, that is
usually a sign it is not actually user-facing — or that you have not yet thought about how it fails.

### 3.1 The scenario template

```markdown
### S<n> — <name: what it proves>

**Proves:** the one class of bug this catches, in one sentence.
**Rig:** monitors (resolution · scaling · arrangement), applications open, starting layout.
**Preconditions:** build/version, settings state, anything that must be true before step 1.

**Steps**
1. <action> → **expect:** <definite, observable outcome>
2. …

**Pass:** the complete condition for calling this scenario passed.
**If it fails:** where the bug most likely is — which project, which coordinate space, which contract.
**Time:** ~N minutes.
**Last run:** never · <date> on <machine> — <result>
```

The **Last run** line is the point of the whole format. A scenario with no run line is a plan; a
scenario with a dated run line is evidence. Undated validation is not validation.

---

## 4. The seed scenarios

Six scenarios that will matter, seeded at bootstrap. They are ordered by yield — S1 first because it
catches more real bugs than the other five together.

**None of them has ever been run.** Every **Last run** line below says `never`, and that is accurate,
not a placeholder to be quietly filled in.

---

### S1 — mixed-DPI dual monitor

**Proves:** that geometry survives the three coordinate spaces — that a rectangle computed in Core
arrives on the correct monitor, at the correct size, flush to the correct edge, on a display whose
scale factor is not 100%. This is the single highest-yield scenario in the project, because
coordinate-space errors produce *no error at all* — just numbers that are wrong by a scale factor or
an offset, on one monitor only, in a way that looks like sloppiness rather than a bug.

**Rig:**
- **Primary:** any resolution, **100%** scaling.
- **Secondary:** any resolution, **150%** scaling.
- **Arrangement: secondary placed to the LEFT of primary.** This is not decoration. The
  virtual-screen origin is the primary monitor's top-left, so a display to its left occupies
  **negative X** — and code that assumes `(0,0)` is the desktop corner, or clamps coordinates to
  non-negative, is broken here and nowhere else ([ATLAS §5.1](../ATLAS.md)).
- Two ordinary resizable applications open (a file explorer window and a text editor are fine).

**Preconditions:** a build that can place a window; a layout with at least two zones per monitor.

**Steps**

1. Read the desktop topology (whatever surface exposes it — the Shell's diagnostics, or a log line)
   → **expect:** two monitors, the secondary's rectangle has a **negative** X origin, and the two
   scale factors are reported as **1.0 and 1.5 independently**, not one machine-wide value.
2. Place a window into a zone on the **100%** monitor → **expect:** it lands in that zone, and its
   left edge is **flush** with the zone's left edge — no gap, no overhang.
3. Place a window into the equivalent zone on the **150%** monitor → **expect:** the same visual
   result. A window that is right on the 100% monitor and 1.5× too large (or 2/3 too small) on the
   150% one is an unconverted effective/physical pixel value, and it is the classic instance.
4. Drag a window from the 100% monitor to the 150% monitor and snap it → **expect:** it lands
   correctly. This is the hard case: the window is told to move, the system notifies it of the DPI
   change, the application resizes itself in response, and the final rectangle must be **re-applied**
   ([ATLAS §7.1](../ATLAS.md)). A naive single call lands wrong here specifically.
5. Snap two windows into adjacent zones on the same monitor → **expect:** they appear edge to edge,
   neither overlapping nor gapped. Apparent overlap of a few pixels is the invisible resize border —
   the visible bounds come from a separate attribute ([ATLAS §5.2](../ATLAS.md)).
6. Snap a window to a zone touching the taskbar edge → **expect:** it respects the **work area**, not
   the full monitor rectangle. A window under the taskbar means a full-rect/work-area confusion.

**Pass:** all six steps, on both monitors, with no visible gap, overhang, or size error.

**If it fails:** first ask *which* monitor it failed on. Failing only on the 150% one is a
scale-factor conversion; failing on both is layout math (which should have been caught by a Core
test — if it was not, add that test before fixing anything); failing only after crossing monitors is
the DPI-transition re-apply in step 4; being consistently off by a handful of pixels in one direction
is the two-rects problem in step 5.

**Time:** ~5 minutes once the rig exists.
**Last run:** never.

---

### S2 — hotkey conflict, refused visibly

**Proves:** that a chord which cannot be obtained produces a **surfaced refusal**, not a feature that
is installed, enabled, documented, and silently does nothing. This is the worst failure mode
available to a utility, because the user cannot distinguish it from their own misunderstanding.

**Rig:** single monitor is fine. A **second application already holding a global chord** — anything
that registers a system-wide hotkey will do; note in your run record exactly which application and
which chord, because "some other app" is not reproducible.

**Preconditions:** a module declaring a chord intent. For step 3 you need two modules declaring the
**same** chord — the reference module from P1 plus one real module is enough.

**Steps**

1. Configure a module's chord to a combination the other application already holds, and start the app
   → **expect:** the registration is **refused**, the module still loads and runs, and the refusal is
   **visible in the Shell** next to the binding, naming the reason
   (`HeldOutsideThisApplication` — [CONDUIT §4](../CONDUIT.md)).
2. Press the chord → **expect:** the other application responds, ours does not, and nothing about our
   app is in a broken state. A refused intent is not a fault.
3. Configure **two of our own modules** to the same chord → **expect:** exactly one wins, the loser is
   told and shown, the refusal names **which module** holds it, and — critically — **restarting the
   app produces the same winner**. Arbitration ordered by stable module id, never by load order
   ([CONDUIT §4](../CONDUIT.md)).
4. Rebind the loser to a free chord in the Shell → **expect:** it is granted without a restart, and
   the winner keeps its chord.
5. Try to bind a chord the operating system reserves → **expect:** refused at registration with
   `ReservedBySystem`, surfaced as a message, not as a silently dead key.

**Pass:** every refusal is visible and correctly attributed; no module is faulted by losing a chord;
the winner in step 3 is identical across three consecutive restarts.

**If it fails:** a *silent* refusal is the serious finding — it means a registration result is being
discarded somewhere between Conduit and the Shell. A non-deterministic winner in step 3 means
arbitration is keying on load order, which is the retrofit-expensive bug this pillar exists to
prevent.

**Time:** ~5 minutes.
**Last run:** never.

---

### S3 — monitor hot-plug (undock / redock)

**Proves:** that the desktop model survives the topology changing underneath it, and that windows and
saved layouts do something defensible rather than something surprising when a monitor disappears.

**Rig:** a laptop with an external display, or any machine where a display can be physically or
logically disconnected. Windows placed in zones on **both** displays before you start.

**Preconditions:** a saved per-monitor layout for both displays.

**Steps**

1. With both displays active, snap windows into zones on each → **expect:** correct placement (S1
   already covers the geometry; here you are only establishing the starting state).
2. **Disconnect the external display** → **expect:** the app does not crash, does not hang, and does
   not spin the CPU. Windows on the removed display are relocated by Windows itself; note where they
   went — that behavior is the operating system's, not ours, and the scenario records it rather than
   asserting it.
3. Read the topology again → **expect:** one monitor, and the **topology generation has changed**
   ([ATLAS §4.1](../ATLAS.md)). Any snapshot taken before the change must be recognizable as stale
   rather than silently used.
4. Snap a window now → **expect:** it uses the *current* single-monitor layout, not a cached
   two-monitor one. A window flying to coordinates that no longer exist on any display is the
   signature failure.
5. **Reconnect the display** → **expect:** the topology returns, the per-monitor layout for that
   display is recognized as the same display (not treated as a new unknown one), and snapping works
   again without a restart.
6. Repeat the disconnect/reconnect **three times in quick succession** → **expect:** no accumulated
   duplicate monitors, no leaked overlay windows, no growing memory, and the app still responds.

**Pass:** no crash, no stale-coordinate placement, layouts re-associated with the right display, and
the app in a clean state after three cycles.

**If it fails:** placement to nonexistent coordinates means a snapshot was cached across a topology
change. Layouts not re-associating means monitor identity is being keyed on something unstable
(position or index) rather than a durable identifier — that is a design finding, not a bug fix, and
it belongs in [ATLAS.md](../ATLAS.md).

**Time:** ~5 minutes.
**Last run:** never.

---

### S4 — a window we are not permitted to move

**Proves:** that an impossible operation degrades gracefully and **says so**, rather than failing
silently or retrying forever. An unelevated process cannot manipulate windows owned by an elevated
one; that is the security model working correctly, and it must arrive as a surfaced refusal
([ATLAS §7.3](../ATLAS.md)).

**Rig:** single monitor is fine. Open **one window from an elevated process** (any tool you routinely
run as administrator) alongside two ordinary windows.

**Preconditions:** Windows Coordinator running **unelevated** — which is the normal, intended state.

**Steps**

1. Try to snap the **elevated** window into a zone → **expect:** nothing moves, and the outcome is
   `Refused(Elevated)` — visible to the user with an honest explanation, not a silent no-op and not
   an exception dialog.
2. Immediately snap an **ordinary** window → **expect:** it works normally. One refusal must not put
   the module or the pillar into a bad state.
3. Snap a group where **one** of several targets is elevated → **expect:** the others are placed, the
   elevated one is reported as refused, and the result distinguishes the two. A call that returns a
   bare success for the whole group is the exact instance of *a claim stronger than its evidence*.
4. Find a window that **enforces its own geometry** (an application with a minimum size or a fixed
   aspect ratio) and snap it into a smaller zone → **expect:** `PlacedDifferently` with the actual
   rectangle — a first-class outcome, not an error and not a lie.
5. Try to snap a shell surface (the taskbar, or Start) → **expect:** `Refused(NotAnApplicationWindow)`.

**Pass:** every impossible case produces a specific, surfaced outcome; no silent failures; no retry
loops; ordinary windows are unaffected throughout.

**If it fails:** a bare boolean or a swallowed exception anywhere on the placement path is the root
cause. Placement returns an outcome, not `void` — if the code does not have somewhere to put
`PlacedDifferently`, the contract was implemented incompletely.

**Time:** ~4 minutes.
**Last run:** never.

---

### S5 — Explorer restart (tray survival)

**Proves:** that the tray presence — the entire visible existence of a tray-resident toolbox —
survives the Windows shell restarting. Explorer restarts on its own, on updates, and whenever a user
kills it to fix something else. An application whose only UI affordance silently disappears at that
moment has effectively uninstalled itself.

**Rig:** single monitor is fine. Windows Coordinator running, tray icon present, at least one module
enabled with an active chord.

**Steps**

1. Confirm the tray icon is present and its menu opens → **expect:** normal.
2. **Restart Explorer** (end the `explorer.exe` task and let it restart, or restart it from Task
   Manager) → **expect:** the desktop and taskbar return.
3. Look at the notification area → **expect:** **our tray icon is back.** This is the whole scenario.
   The icon is registered with a shell that has just been replaced; it must be re-registered on the
   shell-restart notification rather than assumed to persist.
4. Open the tray menu → **expect:** it opens and its items are correct, including any enabled/checked
   state, which is computed when the menu opens rather than on a timer ([CONDUIT §3.4](../CONDUIT.md)).
5. Press an active chord → **expect:** it still fires. Chord registration is not owned by Explorer, so
   this should be unaffected — confirm it, because "the whole app died quietly" and "only the icon
   died" look identical from the notification area.
6. Check the process is still the **same process** (same PID) → **expect:** yes. If the app restarted
   itself, that is a different behavior with different consequences for settings and state, and it
   must be a decision, not a surprise.

**Pass:** icon returns, menu works, chords still fire, same process, no duplicate icons.

**If it fails:** a missing icon means the shell-restart message is not being handled. **Two** icons
means it is being handled more than once. Either way this is Shell-adapter work, and it is exactly
the class of defect no test in this repository can ever see.

**Time:** ~3 minutes.
**Last run:** never.

---

### S6 — settings survive an update

**Proves:** the load-bearing promise of [principle 6](../COORDINATOR.md) — settings are the source of
truth and survive updates. This is also the acceptance check for the delivery channel in
[release-and-update.md](release-and-update.md), and the reason that channel is in the build-now set:
without it, every deferred feature is stranded on every install already running.

**Rig:** single monitor is fine. **Two builds** — an older one and a newer one — where the newer
contains at least one settings-schema change.

**Preconditions:** the older build installed and running; a settings state that is *distinctive* — not
defaults. Change a layout, bind a non-default chord, set a module option away from its default, and
**write down exactly what you set**.

**Steps**

1. With the old build, apply the distinctive settings and confirm they take effect → **expect:**
   normal behavior with your values.
2. Note the settings file location and its schema version → **expect:** you can find it and read it.
   If you cannot, that is a finding: a settings store nobody can inspect is one nobody can debug.
3. **Install the newer build over the existing install** (the real path, not a clean install) →
   **expect:** it completes, and the app starts.
4. Inspect the settings → **expect:** **every value from step 1 is still there.** Not defaults. Not
   "mostly." Every one.
5. If the newer build made an **additive** change (a new field), confirm the old file loaded and the
   new field took its default → **expect:** no error, no reset, no prompt.
6. If the newer build made a **structural** change, confirm the migration chain ran → **expect:** the schema
   version advanced and the old values are represented correctly in the new shape. The migration must
   have a Core test that **fails without the migration** — verify that test exists and has been
   observed failing ([OPERATING_MODEL §7](../OPERATING_MODEL.md)).
7. Restart the app → **expect:** settings persist across the restart, too. A migration that works in
   memory and does not write is a bug that hides for exactly one session.

**Pass:** no value lost, no unrequested reset, no prompt, and the migration test observed red before
it was green.

**If it fails:** **a settings reset is a P0 defect**, not a rough edge. It is the one failure that
destroys the user's accumulated configuration, and it is unrecoverable. If it happens once, the fix is
not just the bug — it is a settings backup written immediately before any migration
([release-and-update.md §6](release-and-update.md)).

**Time:** ~10 minutes, plus producing two builds.
**Last run:** never.

---

## 4.1 Zones scenarios (M1) — written ahead of the module, on purpose

These six are written before Zones exists so the module has a target rather than a retrospective.
Each names the thing no test can reach. Design:
[src/modules/zones/docs/ARCHITECTURE.md](../../src/modules/zones/docs/ARCHITECTURE.md).

### Z-1 — snap into a zone, on the monitor you meant

**Proves:** drag-to-snap places a window in the zone the cursor was over, on the right monitor, with
the right geometry — the basic claim of the module.

1. Two monitors, a layout with at least three zones on each.
2. Drag a window into a zone on the **secondary** monitor, snap modifier held. **Expect:** it fills
   the zone; the overlay disappears on release.
3. Repeat onto the primary. **Expect:** same.
4. Compare the window's *visible* edges to the zone edges. **Expect:** flush — no one-pixel gap, no
   overhang. A hairline of wallpaper means the invisible-border compensation is wrong, not the math.

### Z-2 — a stack forms, and cycling walks it

**Proves:** the headline feature, end to end.

1. Drop three windows onto the same zone. **Expect:** each lands in front; the previous one is behind
   it, not minimised — check the taskbar still shows all three.
2. `Win` + wheel over that zone. **Expect:** the next window comes to the front, one per detent.
3. Keep going. **Expect:** it cycles round; no window is skipped or lost.
4. Wheel the other way. **Expect:** the reverse order exactly.

### Z-3 — the wheel hook does not slow the desktop down

**Proves:** the hook budget under real load — the risk that Zones makes every scroll on the machine
slightly worse.

1. With a stack armed, scroll normally in a browser, an editor, and a file list — **without** the
   modifier. **Expect:** indistinguishable from Coordinator not running. Any perceptible stutter is a
   finding, and a serious one.
2. Repeat while the machine is busy (a build running). **Expect:** the same.
3. Record the measured hook latency if instrumentation exists; otherwise record the subjective
   verdict and say that is what it is.

### Z-4 — the foreground lock ⚠ **run this first**

**Proves:** whether `Activate` is permitted at all — the module's largest unknown
([ADR 0014](../decisions/0014-atlas-explicit-raise-and-activate.md)).

1. `zones.activate-on-cycle` **off**. Cycle a stack. **Expect:** the window comes to the front and
   keyboard focus does **not** move — type, and the characters go where they went before.
2. Turn it **on**. Cycle again. **Expect:** either focus moves, **or** a surfaced
   `Refused(ForegroundLocked)`. **A silent no-op is a defect** — the whole point of the refusal is
   that it is visible.
3. Record which happened, on which Windows build. This single observation decides whether the setting
   is worth keeping.

### Z-5 — swallowing does not break scrolling

**Proves:** the fail-open rule, which is what stops the module making the desktop worse.

1. Over a **stacked** zone: `Win`+wheel cycles, and a bare wheel scrolls the front window normally.
2. Over an **unstacked** window: `Win`+wheel does **nothing** and does not swallow the event —
   confirm by checking the window did not scroll either.
3. Remove windows until the stack has one left. **Expect:** the zone disarms — `Win`+wheel over it
   now behaves exactly as in step 2.

### Z-6 — the overlay always comes down

**Proves:** the paired `MoveSizeStart`/`MoveSizeEnd` guarantee, whose failure mode is an overlay
stuck on the user's screen.

1. Start a drag with the modifier, then press **Escape**. **Expect:** overlay gone, window unmoved.
2. Start a drag, release outside any zone. **Expect:** overlay gone, window left where dropped.
3. Start a drag and **lock the session** mid-drag (Win+L), then unlock. **Expect:** no overlay.
4. Start a drag and unplug a monitor mid-drag. **Expect:** no overlay; no crash.

---

## 5. The per-release checklist

Run before anything is delivered to a machine — including the owner's second machine, which is the
trip-wire that makes the delivery channel urgent ([NEXT.md](../NEXT.md)).

**Always, every release:**

| # | Check | Evidence |
|---|---|---|
| 1 | `coord audit` — zero ERROR | exit code + finding count |
| 2 | `coord map --check` — index current | exit code |
| 3 | `coord test` — Core suites green, on Linux **and** on Windows | pass counts for both |
| 4 | `coord build` — every project compiles, Release configuration | SDK version + machine |
| 5 | **S1** mixed-DPI dual monitor | run record (§6) |
| 6 | **S5** Explorer restart | run record |
| 7 | **S6** settings survive the update — over the **previous release**, not a clean install | run record |
| 8 | Cold start on a machine **without** the dev toolchain | what it needed (**TD-10**) |
| 9 | Idle memory and idle CPU, noted as numbers | compare with the previous release (**TD-11**) |

**Conditionally, when the release touches that surface:**

| Touched | Also run |
|---|---|
| Anything geometric — layouts, placement, zone math | **S1** in full, plus **S3** |
| Anything input-shaped — chords, hooks, gestures, tray items | **S2**, plus **S5** step 5 |
| Anything that enumerates or observes the desktop | **S3**, plus **S4** |
| Any settings-schema change | **S6** in full, including step 6 |
| A new module | every scenario that module's docs name, plus **S1** and **S6** |
| Anything in Zones | **Z-1**…**Z-6**; `Z-4` before any other Zones work |

**A release with an unrun applicable scenario is not blocked — it is *recorded as such*.** Write down
which scenarios were skipped and why. That is the never-force rule ([OPERATING_MODEL §2](../OPERATING_MODEL.md))
applied here: a hard gate on a manual procedure becomes a gate that gets quietly ignored, and an
ignored gate is a check that cannot fail. An honest "S3 not run — no external display available
today" is worth more than a ticked box.

---

## 6. Recording evidence

An observation that is not written down did not happen. This is the same rule as the audit log, for
the same reason: repository health has to be a **tracked quantity**, not a memory.

### 6.1 What to write down

```markdown
**S<n> — <name>** · <YYYY-MM-DD>
Machine:   <name/model>, Windows <version + build>
Monitors:  <resolution @ scaling, arrangement>  — e.g. 2560x1440 @100% primary, 1920x1080 @150% left
Build:     <version / commit>, <packaged|unpackaged>, SDK <version>
Result:    PASS | PASS WITH NOTES | FAIL | NOT RUN (<why>)
Observed:  <what actually happened, including anything unexpected that did not fail the scenario>
Follow-up: <NEXT.md item / TD-NN row / ADR / Pitfalls entry — or "none">
```

Four fields carry the weight, and omitting any of them makes the record unusable later:

- **The date.** Undated validation is not validation.
- **The monitor arrangement and scaling.** "Validated on my desktop" tells the next reader nothing;
  half the interesting bugs only exist at 150%.
- **The build.** A pass against a build you can no longer identify cannot be regressed against.
- **What was observed, not what was expected.** Write what the screen did. If a step passed but
  something else looked odd, that note is often the most valuable line in the record.

### 6.2 Where it goes

| Where | What goes there |
|---|---|
| **This file** — the scenario's `Last run:` line | date, machine, one-word result. Keeps the scenario itself honest at a glance. |
| **[docs/audit-log.md](../audit-log.md)** — the **Health** block of the audit entry | the full record above. This is the durable, chronological home; the format is [AUDIT §7](../AUDIT.md). |
| **The module's own `README.md` and `docs/NEXT.md`** | the module's honest status line — *what was manually validated, on what, and when* ([MODULE_SPEC §7](../MODULE_SPEC.md), item 5). |
| **Root [README.md](../../README.md) → Pitfalls** | anything that bit you and would bite the next person. Newest at top. This list is how we stop relearning the same lesson. |
| **[docs/TECH_DEBT.md](../TECH_DEBT.md)** | a limitation you decided to accept rather than fix — with its trip-wire. |

### 6.3 What a FAIL is worth

A recorded failure is worth **more** to the next session than a vague "in progress." It names the
machine, the conditions, and the symptom, which is most of a reproduction. Record failures with the
same care as passes, and resist the reflex to fix-then-record — the pre-fix observation is the part
that cannot be reconstructed.

---

## 7. The honesty rule, restated

Say exactly what was verified, on what hardware, with what scaling, on what date. Nothing broader.

| Do not write | Write |
|---|---|
| "Zones works." | "Zone placement passed S1 on 2026-mm-dd (2560×1440 @100% + 1920×1080 @150%, secondary left). Single-monitor 100%-only setups untested." |
| "Hotkeys are validated." | "S2 steps 1–4 passed on 2026-mm-dd; step 5 (reserved system chord) not run." |
| "Tested on Windows." | "Windows 11 26xxx, unpackaged build, one machine. Not tested packaged, not tested on Windows 10." |
| "The tests pass, so the placement is right." | "Core tests green (N/N). Placement is Core-verified only; S1 has never been run." |
| "Validated." | "Validated *what*, on *what*, *when*." |

Two phrases carry specific, non-interchangeable meanings in this repository, and blurring them is the
defect this whole runbook exists to prevent:

- **Core-verified** — a green `coord test`. A statement about decision logic. Portable, cheap, and
  blind to the desktop.
- **Manually validated** — a human ran a numbered scenario on a named machine on a stated date and
  wrote down what happened.

Neither implies the other, and **neither is implied by a green `coord audit`**, which is a statement
about text ([AUDIT §8](../AUDIT.md)).

---

## 8. Adding a scenario

```
[ ] It has a real trigger — a user-facing capability, or a failure that bit you once
[ ] Next free S<n>; never reuse a retired number
[ ] Fill the template (§3.1) — rig, preconditions, numbered steps, definite pass criteria
[ ] Every step has an observable outcome; delete any step whose outcome is "looks right"
[ ] "If it fails" names WHERE the bug probably is — that is what makes it useful at 11pm
[ ] Under ~10 minutes, or split it in two
[ ] Named for what it proves, not what it looks like
[ ] Cross-referenced from the capability's module docs, so the two cannot drift apart
[ ] Added to the §5 conditional table under the surface it exercises
[ ] `Last run: never` — and leave it that way until someone actually runs it
```

And the standing habit from the evidence standard, applied here: **when a scenario is written to
catch a specific bug, confirm it would have caught it.** A scenario that has never been observed
failing is indistinguishable from a comment.

---

## 9. Status

**Never executed.** No build exists to validate, no scenario has been run, and no machine has been
recorded. This is **TD-9** in [TECH_DEBT.md](../TECH_DEBT.md) and it fires the first time there is
anything at all to look at — including the P1 reference module simply appearing in the Shell.

The first person to run any of this should expect the procedure itself to be wrong in places. Fix it
as you go, bump `updated`, and record the run. That first record is the moment this project acquires
its first piece of evidence about the desktop.

---

## See also

- [MODULE_SPEC.md §6](../MODULE_SPEC.md) — the testing requirements this runbook is the other half of.
- [ATLAS.md §5, §7](../ATLAS.md) — coordinate spaces and the placement contract behind S1 and S4.
- [CONDUIT.md §3–§4](../CONDUIT.md) — trigger intents, arbitration, and refusals behind S2 and S5.
- [release-and-update.md](release-and-update.md) — the delivery path S6 validates.
- [recipes/add-a-module.md](../recipes/add-a-module.md) — where "add a scenario" appears in the
  module workflow.
- [AUDIT.md §7](../AUDIT.md) — the audit-log entry format that carries the Health block.
- [OPERATING_MODEL.md §7](../OPERATING_MODEL.md) — the evidence standard this runbook implements.
