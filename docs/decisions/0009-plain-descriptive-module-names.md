# ADR 0009 — Plain descriptive module names (a deliberate departure from Axon's codenames)

Date: 2026-08-08
Status: Accepted

## Context

[ADR 0001](0001-adopt-the-axon-documentation-and-operating-protocols.md) ports Axon's protocols
wholesale. Axon also has a naming convention, and it is a good one: its modular units and its
cross-cutting subsystems all carry evocative codenames — Lumen, Glyph, Vista, Tactus, Plexus, Forge,
Spatial, Cortex. That convention earns its keep there in two specific ways. A distinct word is a
**memorable hook**: in a system with many interacting parts, "that's a Lumen concern" locates a
boundary instantly, and you can grep for it and find precisely the subsystem and nothing else. And a
codename gives a subsystem an identity that **survives its own implementation being rewritten**, which
matters in a project where the internals of a component may be replaced twice before the concept
settles.

The default move for this project is to carry the convention across, and the obvious first draft of
this repository did exactly that. It is being deliberately not carried across — for modules — and the
reason is an audience distinction that does not exist in Axon.

**A module here is user-facing.** It appears in the tray menu, in the settings sidebar, in the list of
hotkeys, in whatever the user reads when they are trying to find out which part of this toolbox moves
windows around. Axon's engines are read by whoever is building the system; this project's modules are
read by whoever is *using* it — who is the same person, six months later, in a different mode, with no
patience for a glossary.

The parity target settles it. PowerToys names its utilities FancyZones, Awake, PowerRename,
Always On Top — descriptive, occasionally cute, never opaque. It is the same instinct that makes a
Windows settings page legible, and this project's whole product requirement is to feel like it belongs
on that desktop.

## Decision

**Descriptive where the audience is the user; evocative where the audience is the architecture.** The
rule is a boundary, not a blanket, and the boundary is the user-facing surface.

**Module names are plain and descriptive**, taken from the user's vocabulary and named after what the
module does: **Zones** (M1) and **Chrono** (M2) are the two on the roadmap. The unbuilt ideas parked
in [vision.md](../vision.md) follow the same rule — Launcher, Clipboard, PinTop, Palette, Focus,
Restore — and each of those names is a description rather than a brand.

**Pillars keep evocative names.** [Conduit](../CONDUIT.md) and [Atlas](../ATLAS.md) are architectural
vocabulary read only by someone working on the codebase. Nothing in the UI mentions them. A name the
user will never see is free to be a hook, and here it is worth more than the descriptive alternative:
"InputService" and "DesktopService" are easy to confuse with each other and with a dozen framework
types, whereas "goes through Conduit" is unambiguous and greppable. The rules that matter most in this
architecture — *a module never names an input mechanism*, *a module never enumerates the desktop* —
are sharper with a proper noun on the other side of them.

**The project name and the CLI are descriptive for the same reason as modules.** "Windows Coordinator"
and `coord` ([ADR 0010](0010-coord-as-the-single-developer-entry-point.md)) are read by a person
trying to work out what this is, including the owner returning cold.

**Chrono is the honest edge case.** It is a mild codename for "timers," and it does not fully obey the
rule. It stays for two reasons: it is a common English root that reads as *time* to essentially
anyone, and "Timers" collides with the framework's own timer vocabulary in a way that makes every
sentence about it ambiguous. If it ever confuses a user in the settings list, changing a module's
display label is free — the id is permanent, the label is not
([MODULE_SPEC.md](../MODULE_SPEC.md)) — which is part of why this whole decision is low-risk.

## Consequences

**The documentation loses Axon's vocabulary hooks, and this is a genuine loss.** It is worth stating
plainly rather than conceding rhetorically. In Axon you can write "that's a Lumen concern" and the
boundary is unmistakable. Here you write "that's a Zones concern" and it reads like an ordinary
sentence about window zones — ambiguous at exactly the moments when precision matters most, which are
the moments when someone is deciding whether a piece of logic belongs to the module or the pillar. The
mitigation is conventional and typographic: module names are capitalized and used as proper nouns
throughout the documentation, and the surrounding sentence is expected to carry more weight than it
would with a codename. That is weaker than a distinct word, and no amount of convention fully closes
the gap.

**Search is worse.** `grep -r Lumen` finds a subsystem; a case-insensitive search for "zones" finds
the subsystem plus every sentence containing the word. Type and project naming absorbs some of it —
`ZonesModule`, `Coordinator.Zones.Core` — and those are the searches that matter most in code. In
prose, the loss stands.

**A descriptive name can go stale when scope drifts.** A module called Zones that grows
window-restore behavior is misnamed, and the name will be the last thing anyone updates. The position
this project takes is that the *scope drift* is the defect and the misleading name is the symptom
usefully pointing at it — a codename would have hidden the drift by being equally accurate before and
after.

**Two naming conventions in one repository require explanation**, which is this ADR's reason for
existing. The rule has to be discoverable, or the first person to add a pillar will name it
`WindowService` and the first person to add a module will call it Nimbus.

**Neither module exists.** Zones and Chrono are roadmap entries with no code
([COORDINATOR.md §8](../COORDINATOR.md)), and no module exists to carry a name yet ([TD-5](../TECH_DEBT.md)). The
convention is therefore being applied to names before it is applied to anything those names refer to.

## Alternatives considered

**Codenames throughout, full parity with Axon.** The consistent choice, and it would have preserved
the vocabulary hooks the consequences above admit losing. Rejected because it optimizes for the wrong
audience: the user-facing surface *is* the product, and requiring a glossary to find the feature that
moves windows fails the stock-Windows-feel goal at the level of language rather than pixels. A user
opening the settings window should not have to learn anything.

**Descriptive throughout, pillars included** — `InputService` and `DesktopService`. Rejected for a
reason that only became clear when the pillar rules were written down. Those names are
indistinguishable from ordinary infrastructure classes, and the rules that depend on them lose their
teeth: "a module never installs a hook — it goes through the input service" reads as advice, while
"it goes through Conduit" reads as a boundary with an owner. A named thing can refuse; a service layer
sounds like something you can work around.

**A codename internally with a descriptive display name in the UI** — module id `lumen`, label
"Zones". Technically available today, since [MODULE_SPEC.md](../MODULE_SPEC.md) already separates a
permanent id from a freely changeable label. Rejected because it means every conversation, every
document, and every debugging session carries two names for one thing, and translating between them is
exactly the context-re-acquisition cost that [OPERATING_MODEL.md](../OPERATING_MODEL.md) says the
whole architecture exists to eliminate. Paying it permanently to buy a nicer grep is a bad trade.

**Namespaced descriptive names** — `Coordinator.WindowZones`, `Coordinator.Timers` — on the theory that
the namespace supplies the distinctiveness the bare word lacks. Not adopted as the naming rule, but
partially true in practice: project and type names do carry the prefix, and that is where searching
works. The user-facing name stays short, because the tray menu is not a namespace.
