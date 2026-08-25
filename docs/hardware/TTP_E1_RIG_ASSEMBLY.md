# TTP E1 — Rig Assembly Architecture

**Status:** architecture specified; nothing built.
**Dev Order:** DO-104P

Component identities: [BOM](TTP_E1_HARDWARE_BOM.md).
Connectors and electrical limits: [interface matrix](TTP_E1_INTERFACE_MATRIX.md).

---

## Exploded sequence

Assembly order, bottom up. Each step is also the order of disassembly, which
matters because a tip or stinger change during E1 must not require dismounting
the shaker.

```
 1  bench / table
 2  STAND-001 base                    ← mass independent of the specimen support
 3  STAND-001 vertical column
 4  SHAKER-001 body mount             ← rigid; reaction path down to the base
 5  SHAKER-001                        ← body grounded, NEVER riding the specimen
 6  FORCE-001 on the armature         ← threaded stud
 7  STINGER-001                       ← threaded to the transducer
 8  TIP-001                           ← replaceable without touching steps 4–6
 9  REF-STRUCT-001 on its own support ← independent of STAND-001
10  MIC-001 on its own mount          ← position, distance, orientation recorded
```

Steps 2–8 form the driven assembly. Steps 9–10 are the specimen and the observer,
and they are deliberately supported separately: if the specimen support and the
shaker stand share a path, the rig measures the bench.

## Signal architecture

```
                    HOST-001 (Pi 5)
                    ├── signal_gen ──► DAC out ──► AMP-001 ──► SHAKER-001
                    │                                              │
                    │                                         FORCE-001
                    │                                              │
                    │                                        STINGER-001
                    │                                              │
                    │                                           TIP-001
                    │                                              │
                    │                                     REF-STRUCT-001
                    │                                              │
                    │                                          (acoustic)
                    │                                              │
                    │                                          MIC-001
                    │                                              │
                    │                                       PREAMP-001
                    │                                              │
                    └──── ADC-001 ◄── ch0 PRECOND-001 ◄── FORCE-001 signal
                                  ◄── ch1 ────────────────────┘
```

One ADC, one sample clock, two channels acquired simultaneously. ch0 carries
measured force; ch1 carries acoustic pressure. That pair is what makes the
transfer quantity's unit derivable rather than assumed.

## Mount orientation

| Element | Orientation | Why |
| --- | --- | --- |
| Shaker axis | Normal to the specimen surface at the drive point | Off-axis drive puts lateral load through the stinger, which the stinger is designed *not* to transmit |
| Stinger | Coaxial with the shaker armature | Any misalignment becomes a lateral force the force channel does not measure |
| Microphone | Recorded distance and angle; off the drive axis | Avoid direct mechanical coupling and shadowing |
| Reference structure | Supported per its own recorded condition | Support condition is part of the configuration, not a detail |

## Grounding

Two distinct meanings, both required, easily confused:

**Mechanical grounding.** The shaker body reacts against the stand and the
stand against the bench. The reaction must not travel through the specimen. If
the shaker body can move relative to the bench, its mass joins the moving
system.

**Electrical grounding.** The conditioner output reaches an unbalanced RCA
input. Sensor cable shielding, conditioner ground, and the Pi's ground share a
reference, and a loop between them appears as mains-frequency content on the
force channel. Cable routing and a single ground reference are part of the
design, not a debugging step.

## Cable strain relief

Cable tension applied to the stinger or the specimen is a slow, invisible source
of drift: it loads the drive point without appearing anywhere in the metadata.
Every cable leaving the driven assembly is anchored to the stand before it
leaves the rig, and the anchor point is part of the recorded configuration.

## Adjustable axes

| Axis | Required | Note |
| --- | --- | --- |
| Vertical (Z) | Yes | Sets contact and preload against the specimen |
| Lateral (X/Y) | Preferred | Moves the drive point without rebuilding; E4 reciprocity needs at least two points |
| Rotation | No | Not required for E1 |

Any adjustment that changes the drive point is a **configuration change**, and
during E1 that is expected and legitimate — the rig is what is under test. From
E2 onward, the configuration is frozen and a change ends the study.

## Safety

- Power the amplifier **last** and at minimum gain; a shaker at full drive with
  no contact can damage the armature.
- Verify the drive signal at low level before contact, per protocol Stage 8.
- Do not exceed the shaker's rated stroke; a stinger cannot save an armature
  driven past its limit.
- Confirm the force channel reads essentially nothing with no contact. Anything
  else is a finding to record *before* proceeding, not a nuisance to zero out.
- Keep the conditioner's output inside the ADC's ±3 V limit. Attenuate in
  hardware; the ADC has no headroom to spare and software cannot undo clipping.

## Assembly constraints established by DO-104S selection

These are **constraints the recommended components impose**, derived from their
datasheets. They are not assembly observations: no rig has been assembled, and
nothing below has been done.

### One thread standard through the drive train

The exciter table, the transducer, and the stinger stock are all 10-32 UNF. No
adapter is needed anywhere between the armature and the tip. Two consequences
for assembly:

- The transducer ships with a thread locker and 10-32 to 10-32 mounting studs as
  supplied accessories. Torque and thread preparation are part of the
  configuration, not incidental.
- Because every joint uses the same thread, a joint can be assembled in the
  wrong order without resistance. The exploded sequence above is the authority
  on order.

### The current limit is set before first energizing

The recommended amplifier has a continuously variable current limit spanning
1 A to 5 A rms, and the exciter's maximum input current is 1.8 A rms. The
amplifier's own product data instructs limiting output current to 1.8 A for this
exciter.

**This is a pre-power step, not a tuning step.** The amplifier can deliver
roughly three times what the exciter tolerates, and the limit is the only thing
preventing that.

### The force channel carries no mains ground

The recommended conditioner is battery powered, which keeps a mains ground path
out of the force channel. That is a deliberate property of the selection and it
constrains assembly: substituting a mains-powered conditioner reintroduces a
ground path into ch0 and its effect on the measurement becomes an open question.

The practical cost is that the conditioner has a battery state. A hundred hours
of alkaline life is ample for E1, but a flat battery presents as no signal rather
than as a degraded one.

### Mass at the drive point

The recommended transducer is 22.7 g overall, and its datasheet does not break
out the specimen-side end mass that actually loads the drive point. The stinger
target remains roughly 1–2 g.

**The transducer's end mass is likely to dominate the combined contact mass**,
which makes `combined_contact_mass_g` a measurement rather than a sum of
catalogue figures. Weighing happens at assembly; it cannot be derived from any
document referenced here.

### Stand loading

The recommended exciter weighs 1.1 kg. The stand carries that weight plus the
reaction force, with a path to the base that stays independent of the specimen
support.

### Six interconnects, four of them adapters

The [interface matrix](TTP_E1_INTERFACE_MATRIX.md) enumerates them. Four cross
connector families — 10-32 coaxial to BNC, BNC to RCA, RCA to BNC, and Speakon
to banana — so cable procurement is not a generic accessory purchase and an
assembly attempt is blocked without them.

---

## What this document is not

Not a fabrication drawing, and not evidence that anything has been built. The
first physical assembly happens under DO-104E, and its as-built configuration is
recorded there against these identities.
