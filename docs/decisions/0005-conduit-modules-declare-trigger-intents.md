# ADR 0005 — Conduit — modules declare trigger intents and never own raw input hooks

Date: 2026-08-08
Status: Accepted

## Context

Every module in this toolbox needs to be woken by something. A window-management module wants a chord
(`Win`+`Alt`+`Left`) and needs to know when a drag begins and ends. A timer module wants to fire every
twenty-five minutes and again at nine in the morning. A future clipboard module wants a global key.

The default implementation of each is three lines of Win32 **inside the module**: call
`RegisterHotKey`, install a `SetWinEventHook`, start a `Timer`. It works immediately, it needs no
infrastructure, and it is what nearly every Windows utility does. The case for centralizing this
instead has to be made against something that genuinely works, which is why it needs an ADR rather
than an assertion.

### The failure story that motivates the rule

Zones ships first and registers `Win`+`Alt`+`Left` with `RegisterHotKey`. It works. Six months later,
a Palette module is written — a different burst, a different evening, no memory of what Zones claimed
— and it registers the same chord.

`RegisterHotKey` returns `false` for the second caller. Whichever module loaded second now silently
does nothing. There is no error dialog, because a module that cannot register a hotkey has no sensible
place to complain. There is no log entry the user will ever read. There is nothing in the settings UI
that could display a conflict, **because no component in the system knows that both requests exist** —
each module made its own call and got its own answer. The user's report will be that the hotkey
"stopped working sometimes," and the *sometimes* is module load order, which depends on directory
enumeration order, which is not a policy anyone chose.

Now try to fix it after the fact. To show the user a conflict, something must know every requested
chord — which means taking registration away from both modules, which means rewriting both of them and
every module written between them. That rewrite is the retrofit, and it is why
[OPERATING_MODEL.md](../OPERATING_MODEL.md) lists trigger arbitration among the four seams that must
exist from the start or never can.

## Decision

**Conduit owns every input and wake mechanism in the process. A module declares what it wants and
never names how it is delivered.**

A module registers typed **trigger intents** — a hotkey chord, a window event subscription, a
schedule, a tray action, a recognized input gesture — each naming a **capability id** and never a
mechanism. Conduit performs the registration, arbitrates conflicts, and dispatches events to the
declaring module. The full taxonomy, the per-intent guarantees, and the refusal model are specified in
[CONDUIT.md](../CONDUIT.md); this ADR decides only that the ownership sits there.

The prohibition is explicit: **a module never calls `RegisterHotKey`, never installs a hook, never
owns a timer, never reads raw input.** That prohibition is partly self-enforcing, because all of those
are Windows calls and a module's Core project may not reference Windows at all
([ADR 0003](0003-the-core-shell-split.md)) — so the only place a module could break the rule is its
own Shell adapter, which the same boundary check covers.

### The three properties only central ownership can provide

**A conflict becomes visible.** One registry of intents means the settings surface can say *Palette
wants a chord Zones already owns* and offer a rebind. This is not a nicety; it is the difference
between a bug the user can resolve and a bug the user experiences as flakiness. Refusals must
therefore be first-class data — a typed reason that reaches the UI — not a swallowed `false`. A
central arbiter that refuses silently has reproduced the original failure one level up, with more
code.

**The hook thread stays fast.** Input hooks sit on the desktop's critical path: a slow callback does
not make this application sluggish, it makes *the machine* sluggish. One owner can enforce
resolve-once-execute-cheap, dispatch off the hook thread, and coalesce and throttle high-frequency
sources. N modules each installing their own hook is N independent opportunities to stall every
application the user is running, and no place from which to notice.

**Rebinding is uniform.** When every trigger is declared data rather than an embedded call, changing a
chord is a settings edit for all modules at once, and the "which key does what" list is derivable
rather than curated by hand.

## Consequences

**The first module pays visible friction.** Wanting a hotkey becomes a declaration plus a settings row
instead of one line of Win32. That friction is the decision working as intended, and it is worth
naming so nobody in a later session mistakes it for an accident.

**Conduit must exist before any module is useful**, which orders the roadmap: the pillars come before
the first module ([COORDINATOR.md §8](../COORDINATOR.md)). A project that wants to show something
working quickly will feel this ordering as a cost.

**A mechanism Conduit does not model blocks the module that needs it.** If a module wants something
outside the taxonomy, the taxonomy has to grow before the module can. This is deliberate — the set of
intents is closed on purpose so that extending it is a decision with an owner rather than an accident
that happens inside one module's adapter — but it means Conduit's design is on the critical path for
work that has nothing to do with input.

**The intent taxonomy is a permanent contract**, in the same way capability ids are
([MODULE_SPEC.md](../MODULE_SPEC.md)): settings files and user rebindings reference declared intents,
so renaming or restructuring one is a settings migration
([ADR 0007](0007-settings-schema-additive-versioned-migrated.md)), not a refactor.

**Conduit becomes a single point of failure.** Everything that wakes anything runs through it. The
mitigation is the degradation principle — a module whose intent cannot be satisfied is refused
explicitly and the rest keeps running — but the concentration of risk is real, and it is the price of
the concentration of knowledge that makes arbitration possible at all.

**Almost none of this exists.** Conduit's declaration types compile (CI `7aef6ff`, 2026-08-08); the arbiter, the registry and the dispatcher are unwritten, and nothing has been compiled
([TD-1](../TECH_DEBT.md)); no hotkey has ever been registered by this project, and no hook-callback
latency has ever been measured ([TD-11](../TECH_DEBT.md)).

## Alternatives considered

**Let modules own their hooks now, and add a conflict registry when it hurts.** Rejected — this is the
failure story above, and the retrofit it implies is the specific thing the build-now test in
[OPERATING_MODEL.md](../OPERATING_MODEL.md) exists to catch. Deferring it does not defer the cost; it
defers the *notice*, and moves the cost to the moment when there are several modules to rewrite rather
than none.

**A shared helper library that modules call voluntarily.** The tempting middle ground: keep the Win32
in one place, keep ownership distributed. Rejected because a helper library **cannot arbitrate** —
arbitration requires knowing about requests it did not receive, and a library only sees the calls that
were made through it. Convention plus a helper is exactly the arrangement that appears to work and
fails silently, which is worse than the naive version because it looks like it has been handled.

**Let Windows arbitrate and log the failure.** That is, keep `RegisterHotKey`'s first-caller-wins
behavior and write a line to a log when it returns `false`. Rejected: a log is not a place a user
looks, load order is not a policy anyone chose, and "first caller wins" produces different behavior on
different machines for reasons no one can see. It is the failure story with a log line added.

**A full input pipeline that exposes raw events to modules.** The opposite error, and worth recording
because it is the direction a sophisticated design tends to drift. Rejected: exposing raw input makes
every module a candidate for stalling the desktop, and makes the coalescing and throttling guarantees
unenforceable — Conduit could promise them and no longer deliver them. Modules receive *recognized*
events; the recognition is the pillar's job.

**Fold triggers into the platform host rather than a named pillar.** Rejected on boundaries rather
than mechanics: input and wake behavior has enough surface — a taxonomy, arbitration policy, refusal
semantics, threading guarantees — to be its own concern with its own document, and folding it into the
host would blur the line the audit's modularity lens is meant to police. The Shell, by contrast,
genuinely is host-level today ([COORDINATOR.md §5.1](../COORDINATOR.md)), which is the worked contrast
for what does and does not earn pillar status.
