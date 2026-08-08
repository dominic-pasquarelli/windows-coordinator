---
title: Operating Model — why Windows Coordinator is shaped this way
tier: meta
status: stable
updated: 2026-08-08
audited: 2026-08-08
related:
  - CLAUDE.md
  - docs/COORDINATOR.md
  - docs/DOC_SPEC.md
  - docs/AUDIT.md
  - docs/MODULE_SPEC.md
  - docs/NEXT.md
  - docs/TECH_DEBT.md
  - docs/runbooks/manual-validation.md
---

# Operating Model — why Windows Coordinator is shaped this way

> The **rationale** beneath the rules. Other docs state *what* the discipline is — bump `updated`,
> shelve a module with a "Where to resume" section, do not build on speculation, capture stray ideas
> in the inbox, put friction-removal first. This doc says **why** each of those is load-bearing
> rather than ceremony. If a rule ever feels like bureaucracy, the answer is here.
>
> **One sentence:** Windows Coordinator is built in bursts around a day job and shifting interests,
> so the whole architecture is optimized to make **stopping and resuming nearly free** — and almost
> everything else (the module boundary, the snapshot protocol, the documentation discipline, the
> obsession with the platform getting out of the way) follows from that.

---

## 1. The premise — built in bursts, resumed cold

This project is not built in one sustained push. It is built in **evenings and weekends around a day
job**, in bursts driven by whatever is currently interesting or currently annoying: window layout
this month, timers next month, a clipboard utility a year from now after some unrelated frustration
finally tips over. Any module may be put down for months and picked back up completely cold.

A conventional project structure punishes this shape badly. Value lands only when the project
*finishes*, so an abandoned project produces nothing but a folder you feel guilty about. Windows
Coordinator inverts the bet. **The MVP and the product are the same thing.** One module sitting in
the tray, doing one useful job, with no other module present, is already a complete, shipped,
genuinely useful deliverable — the host exists to load exactly that, and principle 1 in
[COORDINATOR §7](COORDINATOR.md#7-non-negotiable-principles) says so out loud. A burst therefore
**banks value whether or not the interest that drove it lasts**. If Zones is the only module that
ever ships, the toolbox is still a tool the owner uses every day.

The architecture's job is to make sure no burst is wasted, and that any burst is resumable.

The single cost the whole design exists to eliminate is **context re-acquisition** — the price of
stopping one thread and re-orienting onto another, or back onto the same one six months later. That
cost is what actually kills hobby projects: not the difficulty of the remaining work, but the hour
you must spend rediscovering what the remaining work *was*. Drive it toward zero and shifting
interests stop being a failure mode and become the *input* the system runs on.

## 2. The snapshot protocol is a throttle, not a filing cabinet

The [snapshot and steering protocol](../CLAUDE.md) — capture first, then if the thread is drifting,
*offer* to park it, and if the owner wants to dig in, drop a restore anchor and continue — exists to
drive context re-acquisition toward zero. It is not an archival system. Its design choices follow
directly from the premise:

- **It steers but never forces.** A hard gate ("finish the settings migration before you touch
  Zones") creates friction, and **friction on a burst-driven project becomes avoidance**. Not
  rebellion — avoidance. The evening simply gets spent on something else, and three of those in a row
  is a shelved project. The protocol *offers* and *reminds*; it never blocks. The flow state of a
  burst is the single most valuable and most fragile input the project has, and forcing breaks it.
- **It makes detours safe.** Because a detour drops a restore anchor *before* the descent, you can go
  deep without getting lost — the rope back is tied before you climb down. This is what lets the work
  be depth-first and breadth-first at once: range wide when nothing is pressing, commit hard when a
  direction appears, and pay no penalty for switching.

The anchor is the actual mechanism, and it is worth being precise about why. Memory of "what I was
doing before this tangent" is exactly the thing that does not survive an interruption — a phone call,
the end of an evening, a context summarization in an AI session. A one-line anchor written down
survives all three. A think-through is only *bounded* if it reliably ends by returning to the parked
work; otherwise the rabbit hole quietly becomes the new main thread and the original work is lost
without anyone deciding to abandon it.

The protocol is not bookkeeping. It is the control surface that makes interest-switching cheap.

## 3. Capture is free; building costs

A captured idea, or a parked decision written down with its trade-offs, hardens the design against
edge cases for the price of a few minutes. And the module boundary makes that capture genuinely
consequence-free: a module that is explored, sketched, and abandoned simply **never ships in the
tray**. It costs nothing to carry as a note.

The trap is letting that truth leak one word over. **There is no cost to *capturing* a feature; there
is a real cost to *building* one** — memory in a process that sits resident all day, a settings
surface that must be migrated forever after, a new failure mode on the desktop, a validation pass
that a human has to physically perform. The discipline (no speculative modules; a pillar exists only
once it has a real first consumer) is precisely the rule that keeps "free to capture" from sliding
into "free to build." Get the value of the rabbit hole — the captured insight, the hardened design —
without paying its cost until a real need justifies the build.

This is why Conduit and Atlas exist and a third pillar does not, and why the [Shell is deliberately
*not* a pillar yet](COORDINATOR.md): it has one consumer. It graduates the day a second independent
consumer needs the same registry-driven surface — a `coord` subcommand or a web view rendering the
identical module settings schema — and not a day earlier. Naming that trigger is how a deferral stays
a decision rather than becoming an oversight.

**The corollary — build-now is only what is expensive to retrofit onto shipped installs.** "Building
costs" raises a second question once you *do* build: of everything a later feature will need, how
much must exist **now** so that later is not foreclosed? The **additive-schema rule**
([COORDINATOR §7](COORDINATOR.md#7-non-negotiable-principles) principle 6 — a new field is read with
a default, so old settings still load) answers most of it. **Most deep machinery is free to defer:**
keep the seam clean, drop a recall hook, build nothing.

What is *not* free to defer is the small set that is painful to graft onto an installation already
running on a machine you are not sitting at:

| Retrofit-expensive seam | Why it cannot wait |
|---|---|
| **Update / delivery channel** | It is the pipe every deferred feature later travels through. Without it, "we can add that later" is a promise the architecture cannot keep — the install freezes at whatever version was copied onto the machine. |
| **Module identity** | Stable ids are what settings, hotkey bindings, and update manifests reference. Renaming identity after installs exist orphans every binding that pointed at the old name. |
| **Settings migration** | A user's settings file is the one artifact you cannot regenerate. If versioning and a migration mechanism are not there from the first release, the only upgrade path is a reset — which destroys the one thing the user actually owns. |
| **Trigger arbitration** | Once two modules own raw input hooks directly, centralizing conflict resolution means rewriting both. Conduit must own registration from the start or it never can. |

Those four get built now. Everything else is a seam you deliberately leave **empty**, plus a recall
hook so it can resurface. This is the disciplined form of "build the tools now that let the later
stuff be built" — *not* speculative generality (abstractions for consumers that never arrive, exactly
what this section forbids), but the irreducible retrofit-expensive substrate and nothing more.

**The other half — a capture buffer needs a *drain*, not just a recall hook.** Capture-is-free plus a
recall hook gets an idea *in* and lets it *resurface*. Neither empties the buffer once an item
**settles**. So the symmetric discipline: **every capture buffer names both how items come back and
how they leave.**

| Buffer | Recall (how it comes back) | Drain (how it leaves) |
|---|---|---|
| [NEXT.md](NEXT.md) | it is the first thing read on resume | settled work moves to [HISTORY.md](HISTORY.md) |
| [INBOX.md](INBOX.md) | triage proposes a destination | mark `triaged → <where>`, then prune landed entries to git — it is a *buffer, not an archive* |
| [decisions/](decisions/) | a `Proposed` ADR needs a recall hook in NEXT | a settled one-shot gets a closure token so the active set stays a one-line grep |
| [TECH_DEBT.md](TECH_DEBT.md) | each item carries a trip-wire | resolved items move to the paid-down ledger |

Drain at a freeze or at a threshold, never as a gate — the same never-force spirit as §2, a nudge
rather than a wall. Without it, a project that captures relentlessly slowly buries its live working
set under its own settled history, and the buffer that was supposed to reduce friction becomes a
thing you avoid opening.

## 4. Resume fidelity is the keystone

Every benefit above is downstream of one thing: **resumption actually working.** The restore anchor
has to restore. The half-finished module has to still be where the doc says it is. The thing shelved
in March has to come back in an hour, not a day. That is the single point of failure for the entire
model, and it is protected above almost everything else.

This is *why* two rules that can look like overhead are in fact load-bearing:

- **"Documentation is a load-bearing deliverable"**
  ([COORDINATOR §7](COORDINATOR.md#7-non-negotiable-principles) principle 9) — the docs *are* the
  restore mechanism. A phase is not done until a cold reader could resume from them.
  That is not tidiness; it is the rope.
- **The [`audited`](DOC_SPEC.md) accuracy flag** — the docs work as a **coordinate system**, not just
  a list of places. This project is built from a small set of repeating shapes: a module with a Core
  and a Shell adapter, a typed capability, a trigger intent declared to Conduit, a snapshot read from
  Atlas. Because the shapes repeat, you can be dropped at an *unfamiliar* point in the tree and
  re-localize by matching what you see against a known shape. That property only holds while the
  shapes still correspond to the code — the map-to-territory contract.

  **A drifted doc is worse than a missing one.** A missing doc is honest: it tells you to go read the
  code. A drifted doc is a coordinate grid that still looks coherent while pointing at nothing — you
  navigate confidently to a place that no longer exists, and the confident wrong belief costs more
  than the absent one. `audited` is the periodic re-confirmation that the grid still matches the
  ground, which is exactly why it is a *different* claim from `updated`
  ([DOC_SPEC §3](DOC_SPEC.md)): editing prose is not the same act as checking it against reality.

## 5. Two systems — the surface map and the connective substrate

The project runs on two complementary memory systems doing different jobs, and confusing them is how
people end up with either a beautiful wiki attached to nothing or a working system nobody can find
their way back into.

- **The surface map** — the documentation. It holds the *coordinates* of work already done, so a
  thread can be found again even when nothing currently points at it. The doc set, the generated
  [map](MAP.md), and the decision log are this layer. Its job is retrieval.
- **The connective substrate** — the platform itself. Its job is to let finished and half-finished
  work *reach each other*. Atlas's monitor, work-area, and DPI model was built because Zones needed
  to compute zone rectangles; the moment it exists, a future window-restore module gets the hard part
  for free, and it was never designed for that module. Conduit's schedule triggers are built for
  Chrono; a future focus-session module inherits them without Conduit changing. This is **emergent
  recombination, not planned reuse** — nobody wrote Atlas *for* the restore module, and that is the
  point. It is possible only because every part speaks the same capability contract and is
  addressable by a stable name.

A scattered set of finished utilities is an archive: each one useful, none aware of the others. A set
built on a shared substrate gets more capable every time you add to it, with no single addition aimed
at the others. That compounding is the actual return on the structure, and it is what makes it worth
having a "platform" for a toolbox that might only ever have two modules in it.

The documentation is a connective substrate of the same kind. Where two pieces of code cannot yet
reach each other, a pair of cross-linked documents holds the path open until they can — a link is the
cheapest possible placeholder for a connection you have decided on but not built.

## 6. Friction-removal is what graduates the platform

A capability graduates from "a thing you are excited about" to "infrastructure you rely on" when it
becomes **frictionless at the point of use** — not when it becomes maximally capable. A tool you once
fixated on stays useful long after the fascination fades *precisely because reaching for it stops
requiring you to re-engage with it.* It has gotten out of the way.

Windows Coordinator graduates the same way, but only if the layers split correctly. The **platform**
— the host, settings, the update channel, [Conduit](CONDUIT.md), [Atlas](ATLAS.md) — has to become
the invisible, get-out-of-the-way layer. The **modules** stay in the high-engagement zone where the
interesting domain work actually lives, because that is where the fascination is, and the fascination
is the fuel. The standing rule that falls out: **friction-removal is the highest-leverage platform
work**, and it outranks adding module capability whenever the two compete for the same deliberate
effort. That ranking governs where *discretionary* effort goes when you are choosing between two
things; it is emphatically not a license to override a live module fixation, which §2's never-force
rule protects. Platform and module work usually alternate rather than compete.

Two consequences are worth stating plainly.

**The app must never make the desktop worse.** This is the corollary specific to a productivity tool
and it is the sharpest constraint in the project. A utility that steals a hotkey the user needed,
introduces a stutter into a window drag, adds latency to a monitor wake, or sits at measurable CPU
while idle has **negative value** — it is worse than not existing, because the user now pays a
constant tax for an occasional benefit and eventually uninstalls it in irritation. Everything about
the desktop is felt continuously; a feature is noticed once. This is why reliability outranks
features here in a way it does not in most hobby projects, why input hooks must never block
([COORDINATOR §7](COORDINATOR.md#7-non-negotiable-principles) principles 7–8), why the host must
survive a module failing to load (principle 12), and why "stock Windows feel" is an architectural
requirement rather than an aesthetic
preference. A tool that behaves like part of Windows is one you stop noticing; a tool you stop
noticing is one that has graduated.

**The invisible layer must be trusted blind.** The entire value of infrastructure is using it without
inspecting it first. The moment you have to re-verify that hotkey registration actually took, or that
settings actually persisted, it is a project again rather than a substrate. So reliability, clear
diagnostics, and honest failure reporting in the platform are not polish — they are what make the
substrate load-bearing. Spend disproportionate care there.

## 7. The evidence standard — what "it works" is allowed to mean

Everything above is about making stopping and resuming cheap. This section is about the thing that
makes a resumed thread worth resuming: **the repository's claims have to be true.** A drifted doc
(§4) is a coordinate grid pointing at nothing; a false success message is the same failure one layer
down, inside the running system.

> **The standard:** a successful `coord` command must mean the claimed outcome actually occurred.

**A success that did not happen is worse than a failure.** A failure is information — you know where
you stand and you go fix it. A false success is a wrong belief that everything downstream gets built
on, and it is discovered much later, at much greater cost, usually by the user.

Three failure shapes recur often enough to name and watch for:

1. **A check that cannot fail** — a guard, gate, or test whose passing carries no information. A
   boundary check that silently matches nothing, a test whose assertion is unreachable, a validation
   that returns success when its input is missing.
2. **A claim stronger than its evidence** — most often, a green host-side test run described as if it
   proved behavior on the actual desktop.
3. **An error discovered after the expensive step** — a validation that runs only once the
   irreplaceable manual pass, the release upload, or the user's real settings file is already spent.

**The operational rule that falls out: when you add a guard, prove it fails without the fix.** A
guard that has never been observed to fail is indistinguishable from a comment. Break the thing
deliberately, watch the check go red, then repair it — otherwise you have shipped confidence, not
verification.

### The current concrete instance — state it plainly

This standard is not abstract here; the project is presently in exactly the situation it describes,
and every doc that touches build or test status must say so:

- **The Python tooling is executed and verified.** `tools/coord/coord.py` and the doc-audit checker
  under `tools/doc-audit/` are stdlib-only Python 3.11, and they have actually been run. When
  `coord audit` or `coord map --check` reports a result, that result is real.
- **The C# compiles, and the Core logic is tested — as of 2026-08-08.** GitHub Actions at commit `7aef6ff` (2026-08-08) built every project on **Ubuntu** and on **Windows** — 0 warnings, under `TreatWarningsAsErrors` — and the Core suites passed: **45 tests, 0 failed, 0 skipped** (Atlas 25, Platform 20). No .NET SDK
  has ever been present in the environment this repository is authored in, so **CI was the first
  compiler this project ever had**; the first revision of that pipeline skipped the build whenever
  no solution file existed, which is how a repository can end up carefully documenting an unverified
  state while the means to verify it sits idle. The lesson is worth more than the fix: *describing a
  limitation precisely is not the same as removing it*, and it is easy to mistake the first for
  rigor.
- **What that still does not license.** No Shell adapter exists, no module exists, and nothing has
  ever run on Windows. "Compiles" and "the Core tests pass" are now checkable; **"works" is not**,
  and only [manual-validation.md](runbooks/manual-validation.md) on a real desktop can make it so.

There is a second, structural instance that will outlive the first. Because of the Core/Shell split
([COORDINATOR.md](COORDINATOR.md)), a green `coord test` — once a .NET SDK exists to run it — proves
the **Core** logic: zone-rectangle math, schedule computation, settings migration, state machines. It
proves **nothing** about window placement, hotkey capture, DPI and multi-monitor behavior, tray
lifecycle, or anything a user can see. Those are validated by a human executing
[docs/runbooks/manual-validation.md](runbooks/manual-validation.md) on a real desktop, and by nothing
else. The split is what makes host testing possible at all; the price of that gift is being precise
forever after about which half a green run covers.

This standard is also *why* §3's "capture is free" does not extend to claims. Capturing an untested
idea costs nothing. Recording an untested idea as a **verified** one costs the map-to-territory
contract that §4 identifies as the keystone — and once that contract is broken, none of the rest of
this model works.

---

## See also

- [CLAUDE.md](../CLAUDE.md) — standing orientation: the snapshot intake & steering protocol, and a
  working copy of the principles (the rules this doc motivates).
- [COORDINATOR.md](COORDINATOR.md) — the platform architecture: the host, the Core/Shell split, the
  two pillars, and the Shell's pillar-graduation trigger. Its
  [§7](COORDINATOR.md#7-non-negotiable-principles) is the **canonical** home of the principle list —
  every citation in this doc points there.
- [MODULE_SPEC.md](MODULE_SPEC.md) — the module contract, including the shelving requirements that
  are resume fidelity applied at the module level.
- [DOC_SPEC.md](DOC_SPEC.md) — the documentation contract and the `updated` / `audited` flags:
  resume fidelity applied at the doc level.
- [AUDIT.md](AUDIT.md) — how this doc's own **fidelity** gets audited: does the project's *practice*
  still match this model? Writing the philosophy down is what made it checkable.
- [runbooks/manual-validation.md](runbooks/manual-validation.md) — the human-executed desktop pass
  that §7 says is the only thing that can validate Shell-side behavior.
