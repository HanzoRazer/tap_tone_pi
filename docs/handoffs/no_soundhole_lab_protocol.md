Annotated Lab Testing Protocol
Closed-Body / No-Soundhole Acoustic Calibration Specimens
1. Purpose

This protocol defines a controlled test method for building complete acoustic-guitar-style bodies without soundholes and using them as calibration specimens for:

top thickness
bracing design
bridge design
body compliance
soundhole geometry
spiral port design
tornavoz / liner depth

The central idea is:

separate body behavior from port behavior
	​


A no-soundhole body lets you measure the structural and modal behavior of the box before introducing Helmholtz port variables. This is especially important for novel spiral soundhole geometry because the sandbox material identifies several unknowns that cannot be solved from first principles alone: spiral end correction, two-port coupling, body-mode coupling, and tornavoz-induced mode splitting.

2. Experimental Classification
Specimen type
Closed-body acoustic calibration specimen

or:

Unported guitar-body test article
What it is

A full guitar-style body assembly:

back + sides + linings + top + bracing + bridge plate

with no soundhole initially cut.

What it is not

It is not a finished guitar.
It is not intended to sound good.
It is not a product prototype.
It is a measurement specimen.

3. Core Hypothesis

A guitar body can be decomposed experimentally into:

Body structure first
Port system second

The no-soundhole body measures:

top/back/rim/bracing/bridge structural behavior

before introducing:

soundhole area
effective neck length
spiral slot perimeter
multi-port coupling
tornavoz liner depth

This follows the math architecture already present in the repo: the acoustic stack currently treats body volume and Helmholtz behavior as a coupled design problem, and the math notes explicitly frame outline-to-volume-to-port coupling as a future design layer.

4. Required Instrumentation
Required
TTP Analyzer or tap-tone capture system
deflection rig
digital scale, 0.1 g resolution or better
deep-throat thickness caliper
hygrometer / thermometer
bridge-position marking jig
body fixture or mold
Strongly recommended
load cell
calibrated reference masses
dial indicator or digital displacement sensor
driven-sweep exciter
Chladni setup
camera with fixed overhead geometry
5. Controlled Variables

Each test body should control or record:

Variable	Required Control
body outline	same mold / same body family
back/sides material	same stock class if possible
top species	recorded per specimen
top thickness	measured grid
bracing pattern	documented and photographed
bridge plate	documented geometry and mass
dome radius	recorded top/back
humidity	recorded during all measurements
glue type	recorded
soundhole condition	none / round / offset / spiral / spiral+tornavoz
string load	none / simulated / full string tension
6. Specimen Series
Recommended minimum series
A0 — Closed body, no soundhole
A1 — Same body design with round reference soundhole
A2 — Same body design with offset soundhole
A3 — Same body design with dual spiral soundholes
A4 — Dual spiral + lower-treble tornavoz / liner
Stronger experimental series
B0 — No soundhole, stock bracing
B1 — No soundhole, alternate bracing
B2 — Round hole, same bracing as B1
B3 — Offset hole, same bracing as B1
B4 — Dual spiral, same bracing as B1
B5 — Dual spiral + 20 mm liner
B6 — Dual spiral + 40 mm liner
B7 — Dual spiral + 60 mm liner
B8 — Dual spiral + 80 mm liner

This separates:

bracing effects
from
soundhole effects
from
tornavoz effects
7. Measurement Sequence
Phase 1 — Pre-Assembly Material Characterization

Record:

top mass
top thickness grid h(x,y)
brace stock dimensions
bridge plate mass
wood density ρ
optional E_L / E_C from bending rig
Math example — plate stiffness sensitivity

For plate stiffness:

D∝Eh
3

A 5% thickness error causes approximately:

1.05
3
=1.158

or about:

+15.8% stiffness error

So top-thickness measurement is not optional.

Phase 2 — Closed-Body Baseline

Before cutting any soundhole:

mount body in repeatable fixture
measure tap response at bridge/saddle location
record TTP spectrum
identify primary body/top/back peaks
measure static bridge/top deflection
record humidity and temperature
Data products
T1_closed
B1_closed
dominant_peak_closed
Q_closed
δ_bridge_closed
δ_lower_bout_closed
mass_closed
Interpretation

This phase isolates:

structural box behavior

without Helmholtz port contribution.

8. Static Deflection Protocol
Sensor locations

Minimum:

saddle_line
rear_bridge_edge
lower_bout_center

Recommended:

saddle_line
bridge_center
rear_bridge_edge
lower_bout_center
lower_bout_bass
lower_bout_treble
soundhole_candidate_zone
Math example — static stiffness
k=
δ
F
	​


If a known load of:

F=20N

produces:

δ=0.80mm

then:

k=
0.80
20
	​

=25N/mm

If a later brace pattern gives:

δ=0.92mm

then:

k=
0.92
20
	​

=21.7N/mm

Compliance increased by:

0.80
0.92−0.80
	​

=15%

That is a meaningful structural change.

9. Bracing / Stiffness Field Interpretation

The repo math treats brace design as a stiffness field:

D
total
	​

(x,y)=D
plate
	​

(x,y)+
k
∑
	​

D
brace,k
	​

(x,y)

Brace optimization is framed as a constrained problem balancing acoustic output against deflection, stress, and mass.

Practical interpretation

The deflection rig measures a real-world projection of:

D(x,y)

A no-soundhole body lets you evaluate:

bracing and top thickness

before soundhole mass removal and port coupling enter the system.

10. Port Introduction Phase

After closed-body baseline:

Step 1 — Cut reference port

Examples:

round soundhole
offset soundhole
dual spiral soundholes
Step 2 — Repeat all measurements

Record:

T1_ported
A0_ported
dominant_peak_ported
Q_ported
δ_bridge_ported
δ_lower_bout_ported
Step 3 — Compute deltas
ΔT1=T1
ported
	​

−T1
closed
	​

Δδ=δ
ported
	​

−δ
closed
	​

ΔA0=A0
ported
	​

−A0
closed
	​

Interpretation

This shows what the soundhole itself changed.

11. Helmholtz Math Example

For a single port:

f
H
	​

=
2π
c
	​

VL
eff
	​

A
	​

	​


where:

c = speed of sound
A = port area
V = internal volume
L_eff = effective acoustic neck length

The math document notes that this predicts the uncoupled air resonance, while real guitars require plate-air coupling correction.

Example

Assume:

c = 343 m/s
A = 0.00785 m²
V = 0.020 m³
L_eff = 0.080 m

Then:

f
H
	​

=
2π
343
	​

0.020×0.080
0.00785
	​

	​

f
H
	​

=54.6×
4.906
	​

f
H
	​

≈121Hz

With plate-air correction:

f
assembled
	​

=f
H
	​

×0.92
f
assembled
	​

≈111Hz

The measured difference between predicted and actual becomes the calibration residual.

12. Spiral Soundhole Phase

For dual logarithmic spirals, the sandbox identifies the important unknowns:

spiral slot end correction
curved-slot acoustic coupling
two-port interaction
body-mode coupling

The spiral system is especially important because the uploaded sandbox notes that equal dual spirals behave like a summed equivalent port when symmetric, but a tornavoz on only one spiral introduces asymmetry and potential mode splitting.

Test sequence
S0 — no soundhole
S1 — upper spiral only
S2 — lower spiral only
S3 — both spirals open
S4 — both spirals + lower-treble liner 20 mm
S5 — both spirals + lower-treble liner 40 mm
S6 — both spirals + lower-treble liner 60 mm
S7 — both spirals + lower-treble liner 80 mm

This sequence lets you distinguish:

single-port response
summed two-port response
asymmetric liner response
mode splitting
13. Tornavoz / Liner Protocol
Design rule

For the dual-spiral system:

upper-bass spiral = primary open port
lower-treble spiral = experimental tornavoz / liner port

The sandbox identifies the locked working decision as a single tornavoz on the lower-treble spiral only, with cylindrical liner depth as the main tuning variable.

Liner depth sweep

Recommended first sweep:

0 mm
20 mm
40 mm
60 mm
80 mm
Measurement requirement

The sandbox notes that tornavoz coupling can create two resonances where one existed before, and resolving those peaks requires adequate FFT resolution.

Math example — effect of increasing L_eff

Since:

f
H
	​

∝
L
eff
	​

	​

1
	​


If:

L_eff = 20 mm

and the liner increases it to:

L_eff = 40 mm

then:

f
old
	​

f
new
	​

	​

=
40
20
	​

	​

=0.707

So a 120 Hz air resonance would shift toward:

120×0.707=84.8Hz

That is why liner depth is powerful and must be tested incrementally.

14. Modal Area / Radiation Interpretation

The repo math states that radiated power scales with modal area squared:

P
rad
	​

=
2
1
	​

ρ
0
	​

c
0
	​

n
∑
	​

σ
n
	​

∣v
n
	​

∣
2
A
n
2
	​


and explicitly notes that doubling modal area quadruples radiated power.

Practical interpretation

A soundhole or brace change that barely shifts frequency may still matter if it changes:

A_n

That is why Chladni or modal-shape capture eventually matters.

Math example

If a brace/soundhole change increases:

A
1
	​


by 15%:

A
1,new
	​

=1.15A
1,old
	​


then:

P
old
	​

P
new
	​

	​

=1.15
2
=1.3225

or approximately:

+32% radiated power for that mode
15. Data Sheet Template

For each specimen:

Specimen ID:
Build Date:
Body Shape:
Top Species:
Back/Sides:
Brace Pattern:
Bridge Plate:
Top Radius:
Back Radius:
Soundhole State:
Tornavoz State:
RH:
Temperature:
Top Mass:
Body Mass:
Top h(x,y) grid file:
TTP file:
Deflection file:
Photos:
Notes:
Measurement fields
T1:
T2:
B1:
A0:
Dominant Peak:
Q:
δ_saddle:
δ_rear_bridge:
δ_lower_bout_center:
Measured f_H:
Predicted f_H:
Residual:
16. Residual Calculations
Frequency residual
R
f
	​

=f
measured
	​

−f
predicted
	​

Percent residual
R
%
	​

=
f
predicted
	​

f
measured
	​

−f
predicted
	​

	​

×100
Deflection residual
R
δ
	​

=δ
measured
	​

−δ
predicted
	​

Example

Predicted:

f_H = 100 Hz

Measured:

f_H = 92 Hz
R
f
	​

=92−100=−8Hz
R
%
	​

=
100
−8
	​

×100=−8%

Interpretation:

model overpredicted air resonance by 8%

This residual becomes the calibration input for future bodies.

17. Pass / Re-Test Criteria
Good calibration specimen
measurements repeat within acceptable range
body remains structurally stable
port modifications are traceable
no uncontrolled variable changed
Re-test if
humidity changed materially
fixture moved
sensor zero drifted
body mounting changed
glue joint failed
peak identification is ambiguous
Reject specimen as calibration standard if
bracing deviated from plan
top thickness is undocumented
soundhole cut is undocumented
body geometry differs from intended test set
measurement files are missing
18. Recommended First Test Program
Batch 1 — Body behavior
1. Closed dreadnought-style body, no soundhole
2. Same design with round soundhole
3. Same design with offset soundhole
Batch 2 — Spiral behavior
4. Dual spiral, no liner
5. Dual spiral + 20 mm liner
6. Dual spiral + 40 mm liner
7. Dual spiral + 60 mm liner
Batch 3 — Bracing comparison
8. X-braced reference
9. Tacoma-style A-frame
10. A-frame + transverse reinforcement

The Tacoma/VSB sandbox repeatedly frames the dual-spiral design as novel rather than a copy of an existing bracing pattern, so the correct experimental stance is to treat the first bodies as calibration and learning specimens, not as production instruments.

19. Most Important Lab Rule

Do not change two major variables at once.

Bad:

new bracing + new spiral size + new tornavoz + new top thickness

Good:

same body
same bracing
same top thickness
only liner depth changes

This is the difference between:

anecdotal lutherie

and:

measured acoustic design
20. Protocol Summary

The protocol is:

Build closed body.
Measure structural/modal baseline.
Cut controlled port.
Measure port effect.
Add spiral/tornavoz variants.
Measure coupled effects.
Compute residuals.
Feed residuals back into math.

The governing principle is:

measure the body first, then measure the hole
	​


That is the lab version of the repo’s larger acoustic design thesis:

geometry + stiffness + measurement
→ calibrated acoustic prediction
DEVELOPER MODE
