# DO-100 — Guided Digital Laboratory Foundation

## Status

**QUEUED / NOT STARTED — implementation begins only after this handoff is reviewed and authorized.**

(DO-99, the prior gate, is complete and merged; see `CURRENT.md`.)

This Dev Order defines the first implementation increment for positioning Tap Tone Pi as:

> **The Guided Digital Laboratory for Guitar Builders**

The objective is not to add another scientific calculator surface. The objective is to establish a question-and-answer workflow spine that translates a builder's practical goal into a controlled, repeatable laboratory procedure.

---

## 1. Objective

Add a deterministic guided-workflow foundation that can lead a user from a builder-oriented question to the correct measurement procedure without requiring the user to begin by selecting an analyzer, scientific model, FFT mode, or calculator.

The first release shall provide:

- a builder-intent entry point;
- a declarative workflow definition format;
- a deterministic question-and-answer state engine;
- explicit procedure steps and acceptance gates;
- a resumable workflow session record;
- one non-destructive reference workflow proving the architecture end to end.

The reference workflow shall be **Evaluate a Plate Measurement Setup**. It guides the user through specimen identity, preparation state, measurement intent, acquisition readiness, and required evidence, but it shall not calculate a target thickness or issue a luthiery recommendation in this Dev Order.

DO-100 proves the guided-laboratory interaction model before domain calculators and interpretation are attached.

---

## 2. Product Principle

Tap Tone Pi shall behave like a laboratory procedure with instruments embedded inside it, not like a collection of instruments waiting for the user to determine the procedure.

The default interaction model is:

```text
builder goal
→ guided questions
→ procedure preparation
→ measurement readiness checks
→ evidence collection
→ validation
→ result handoff
→ permanent session record
```

The application shall not begin by asking the user to choose an FFT, spectrum analyzer, modal model, or formula.

The guiding design rule is:

> Never ask for a scientific parameter until the workflow has explained why it is needed, how it should be obtained, and how the system will determine whether it is trustworthy.

---

## 3. Architectural Context

### Subsystem

New package:

```text
tap_tone_pi/guided_lab/
```

This package owns guided procedure definitions, workflow state transitions, answer validation, and workflow-session serialization.

### Upstream dependencies

- existing measurement and evidence contracts;
- existing session/provenance concepts;
- existing analyzer capabilities;
- existing server and desktop entry points;
- Laboratory Manual registry introduced by DO-97.

### Downstream consumers

- desktop GUI;
- future server API;
- future Plate Thickness workflow;
- future Wolf Note Diagnosis workflow;
- future Brace Tuning and before/after experiment workflows;
- Viewer Pack and evidence exporters.

### Constitutional boundary

The guided workflow layer may:

- sequence questions and procedure steps;
- validate answer shape and required evidence presence;
- explain measurement preparation;
- invoke existing measurement capabilities through explicit adapters;
- record workflow progress and operator decisions;
- expose uncertainty, ambiguity, and incomplete evidence.

It may not:

- invent scientific acceptance limits;
- mutate acquisition parameters without an explicit user action;
- convert advisory output into an automatic manufacturing instruction;
- decide that wood should be removed;
- claim a luthiery conclusion unsupported by validated evidence;
- embed undocumented formulas or hidden domain rules.

The measurement core remains authoritative for measured values. The workflow engine remains authoritative only for procedure state.

---

## 4. Scope

### In scope

1. A frozen, serializable workflow contract.
2. A frozen, serializable workflow-session contract.
3. Deterministic transition utilities.
4. Builder-oriented intent selection.
5. Question nodes with explicit answer types.
6. Instruction nodes.
7. Evidence-requirement nodes.
8. Review and completion nodes.
9. Pause, resume, back, and replace-answer behavior.
10. Stable validation error codes.
11. One reference workflow: `plate_measurement_setup_v1`.
12. A minimal CLI surface for exercising the workflow without committing to a final GUI design.
13. Tests for contracts, transitions, serialization, invalid definitions, and the reference workflow.
14. Documentation of the product boundary and extension pattern.

### Out of scope

- target plate-thickness calculations;
- Gore and Gilet formula implementation;
- automatic long/cross/twist mode identification;
- wolf-note diagnosis;
- curve comparison UI;
- new FFT or audio-processing algorithms;
- AI-generated questions;
- model training or adaptive recommendations;
- free-form conversational branching;
- GUI redesign;
- authentication, cloud accounts, or remote synchronization;
- manufacturing advice;
- replacement of existing acquisition, evidence, or Viewer Pack contracts.

---

## 5. Design Decisions

### 5.1 The workflow is declarative

Workflow definitions are data, not chains of GUI callbacks.

A workflow definition contains stable node IDs and explicit transitions. Runtime behavior must be testable without a GUI, microphone, or server.

### 5.2 The engine is deterministic

Given the same workflow definition, session state, and answer, the next state must be identical.

No language model participates in transition selection in DO-100.

### 5.3 Builder intent is the entry point

The public catalog describes goals such as:

- evaluate a plate;
- compare before and after work;
- investigate a possible wolf note;
- validate a measurement setup.

It does not expose internal analyzer names as the first decision.

Only `Evaluate a Plate Measurement Setup` is executable in DO-100. Other intents may appear only as unavailable catalog entries when needed to prove catalog semantics; they must be clearly marked unavailable and must not dead-end into fabricated workflows.

### 5.4 Answers are typed

Initial answer kinds:

- `single_choice`;
- `boolean`;
- `integer`;
- `decimal`;
- `text`;
- `measurement_reference`.

Every question declares its answer kind, requirement status, allowed values or numeric bounds where applicable, and a short explanation of why the answer is needed.

### 5.5 Questions and instructions are separate node types

An instruction is not represented as a question with a fake confirmation answer.

Initial node kinds:

- `question`;
- `instruction`;
- `evidence_requirement`;
- `review`;
- `complete`.

### 5.6 Navigation is explicit and auditable

The engine supports:

- answer current question;
- acknowledge instruction;
- attach an evidence reference;
- move back;
- replace an earlier answer;
- resume from serialized state;
- abandon without deleting the record.

Replacing an earlier answer invalidates all downstream node completions and evidence attachments whose reachability depends on that answer.

### 5.7 No hidden raw paths

Workflow sessions may store stable evidence IDs or logical references. They must not introduce new storage of unrestricted host filesystem paths.

### 5.8 Procedure guidance is source-linked

Any instruction that asserts a domain procedure must carry one or more source references.

The reference workflow may use internal procedure placeholders only when they are explicitly labeled as provisional and non-authoritative. A placeholder may test the engine, but it may not masquerade as validated luthiery doctrine.

### 5.9 Scientific truth and workflow usability remain separate

Six months of workshop use may refine question order, wording, recovery paths, and validation prompts. It does not by itself validate formulas or scientific claims.

### 5.10 Versioning

Workflow definitions use stable IDs and semantic integer versions:

```text
workflow_id = "plate_measurement_setup"
workflow_version = 1
```

A session records the exact workflow ID and version it began with. DO-100 does not migrate active sessions between workflow versions.

---

## 6. Core Contracts

### `WorkflowIntentV1`

Required fields:

- `intent_id`
- `title`
- `summary`
- `workflow_id`
- `available`
- `unavailable_reason`

### `WorkflowDefinitionV1`

Required fields:

- `workflow_id`
- `workflow_version`
- `title`
- `purpose`
- `entry_node_id`
- `nodes`
- `source_references`

### `WorkflowNodeV1`

Required common fields:

- `node_id`
- `kind`
- `title`
- `body`
- `why_this_matters`
- `source_reference_ids`

Kind-specific payloads are represented by explicit frozen dataclasses or a validated tagged union. Do not use an untyped `dict[str, Any]` as the primary node contract.

### `WorkflowTransitionV1`

Required fields:

- `from_node_id`
- `condition`
- `to_node_id`

Initial condition forms:

- always;
- answer equals;
- answer in set;
- boolean true/false;
- evidence present.

### `GuidedLabSessionV1`

Required fields:

- `session_id`
- `workflow_id`
- `workflow_version`
- `status`
- `current_node_id`
- `answers`
- `acknowledged_node_ids`
- `evidence_references`
- `visited_node_ids`
- `started_at`
- `updated_at`
- `completed_at`

Initial session statuses:

- `active`
- `paused`
- `completed`
- `abandoned`

### `WorkflowAnswerV1`

Required fields:

- `node_id`
- `answer_kind`
- typed value;
- `answered_at`
- `revision`.

### Serialization

All public contracts use the repository's established frozen-dataclass and `.to_dict()` style unless current package conventions require an equivalent typed implementation.

JSON output must be deterministic:

- stable key names;
- stable list ordering;
- UTC timestamps;
- no non-finite numbers;
- no host-specific path values.

---

## 7. Error Codes

Use stable machine-readable codes with human-readable messages.

### Definition errors — `GDL-1xx`

- `GDL-101` duplicate node ID
- `GDL-102` missing entry node
- `GDL-103` transition references unknown node
- `GDL-104` unreachable required node
- `GDL-105` no completion node reachable
- `GDL-106` ambiguous transition set
- `GDL-107` unsupported answer kind
- `GDL-108` invalid question constraints
- `GDL-109` missing required source reference

### Session errors — `GDL-2xx`

- `GDL-201` workflow/version mismatch
- `GDL-202` current node missing
- `GDL-203` invalid session status transition
- `GDL-204` corrupted downstream history
- `GDL-205` session already terminal

### Operator-action errors — `GDL-3xx`

- `GDL-301` action not valid for node kind
- `GDL-302` answer type mismatch
- `GDL-303` answer outside allowed values
- `GDL-304` required evidence missing
- `GDL-305` back navigation unavailable
- `GDL-306` replacement target not previously answered

Errors must never silently coerce an invalid answer into a valid one.

---

## 8. Reference Workflow: Plate Measurement Setup V1

The workflow proves the guided interaction model without calculating a thickness recommendation.

### Builder goal

> Prepare and document a plate measurement session correctly.

### Required stages

1. **Identify the specimen**
   - top, back, test panel, or other;
   - joined or unjoined;
   - species or user-entered material label;
   - stable specimen identifier.

2. **Identify the builder's immediate purpose**
   - characterize material;
   - establish a baseline;
   - compare after material removal;
   - verify an earlier measurement.

3. **Choose measurement entry mode**
   - capture a new measurement;
   - attach an existing measurement reference;
   - manual values for workflow testing only.

4. **Preparation instructions**
   - present source-linked or explicitly provisional setup instructions;
   - require acknowledgment before proceeding.

5. **Readiness questions**
   - specimen dimensions available;
   - mass available;
   - acquisition device ready;
   - stable specimen support prepared;
   - environmental record available or explicitly skipped with reason.

6. **Evidence requirements**
   - specimen record reference;
   - measurement/session reference;
   - operator acknowledgment of setup completion.

7. **Review**
   - display collected answers;
   - identify missing requirements;
   - permit correction before completion.

8. **Complete**
   - return a `GuidedLabSessionV1` marked complete;
   - state that the setup record is complete;
   - make no claim that plate properties or target thickness have been determined.

### Non-goal language

The completion message must not say:

- the plate is suitable;
- the measurement is scientifically valid;
- the plate should be thinned;
- a target thickness has been calculated;
- a resonance mode has been correctly identified.

Those conclusions require later validated measurement and model workflows.

---

## 9. File-by-File Patch Plan

### Create `tap_tone_pi/guided_lab/__init__.py`

Export only the supported public contracts and utilities.

### Create `tap_tone_pi/guided_lab/models.py`

Define frozen enums/dataclasses for:

- workflow intents;
- workflow definitions;
- node variants;
- transitions;
- answers;
- evidence references;
- guided-lab sessions;
- validation findings.

Provide deterministic `.to_dict()` methods following existing repository style.

### Create `tap_tone_pi/guided_lab/errors.py`

Define:

- stable error-code enum;
- typed definition/session/action exceptions;
- path-free, deterministic error serialization.

### Create `tap_tone_pi/guided_lab/validation.py`

Implement pure validators for:

- unique node IDs;
- valid entry node;
- valid transition references;
- transition determinism;
- reachability;
- reachable completion;
- answer constraints;
- source-reference integrity.

No GUI, server, audio, or filesystem dependency.

### Create `tap_tone_pi/guided_lab/engine.py`

Implement pure transition functions:

- `start_session()`;
- `answer_question()`;
- `acknowledge_instruction()`;
- `attach_evidence()`;
- `advance_session()`;
- `go_back()`;
- `replace_answer()`;
- `pause_session()`;
- `resume_session()`;
- `abandon_session()`;
- `complete_session()`.

Functions return new session values rather than mutating shared state.

### Create `tap_tone_pi/guided_lab/catalog.py`

Expose builder-oriented workflow intents and resolve available workflow definitions by stable ID/version.

The catalog must not import GUI modules.

### Create `tap_tone_pi/guided_lab/workflows/__init__.py`

Export packaged workflow definitions through a narrow registry interface.

### Create `tap_tone_pi/guided_lab/workflows/plate_measurement_setup_v1.py`

Define the complete reference workflow as declarative typed data.

Avoid embedding transition logic in ad hoc Python conditionals outside the common condition model.

### Create `tap_tone_pi/guided_lab/cli.py`

Provide a thin terminal runner for development and testability:

```text
ttp guided-lab list
ttp guided-lab start plate_measurement_setup
ttp guided-lab resume <session-json>
```

The CLI is not the final product UI. It exists to prove that the engine is interface-independent.

Do not implement an unbounded interactive shell. Use one prompt at a time and explicit serialized session output.

### Modify the canonical CLI registration module

Register the `guided-lab` command group using the repository's existing command pattern.

No unrelated CLI reorganization.

### Create `tests/test_guided_lab_models.py`

Test contract construction, immutability, deterministic serialization, enum handling, and timestamp requirements.

### Create `tests/test_guided_lab_validation.py`

Test every `GDL-1xx` definition error and valid reference workflow acceptance.

### Create `tests/test_guided_lab_engine.py`

Test deterministic transitions, navigation, answer replacement, downstream invalidation, pause/resume, terminal-state behavior, and evidence requirements.

### Create `tests/test_guided_lab_plate_setup_workflow.py`

Exercise every reference-workflow branch from start to completion and verify prohibited conclusions are absent.

### Create `tests/test_cli_guided_lab.py`

Test command registration, list/start/resume behavior, deterministic JSON, and invalid workflow/session failures.

### Modify `pyproject.toml`

Only if package-data registration is required by the chosen workflow-definition representation. Prefer typed Python definitions in DO-100 to avoid adding a packaging surface without need.

### Modify `README.md`

Add a concise section:

- product positioning;
- guided-workflow concept;
- CLI development surface;
- explicit statement that DO-100 does not make manufacturing recommendations.

### Modify `docs/dev_orders/CURRENT.md`

After DO-99 completes, promote DO-100 to Current and record DO-99 as Previous/Complete.

Do not mark DO-100 active before DO-99 is merged.

### Modify `SPRINTS.md`

Only when an existing backlog item is graduated or a concrete deferred item emerges during implementation. Do not use the backlog as a second implementation checklist.

---

## 10. Utility Interfaces

Recommended public utility signatures:

```python
validate_workflow_definition(
    definition: WorkflowDefinitionV1,
) -> tuple[WorkflowValidationFindingV1, ...]

start_session(
    definition: WorkflowDefinitionV1,
    *,
    session_id: str | None = None,
    started_at: datetime | None = None,
) -> GuidedLabSessionV1

answer_question(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    value: AnswerValue,
    *,
    answered_at: datetime | None = None,
) -> GuidedLabSessionV1

acknowledge_instruction(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    *,
    acknowledged_at: datetime | None = None,
) -> GuidedLabSessionV1

attach_evidence(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    evidence: WorkflowEvidenceReferenceV1,
) -> GuidedLabSessionV1

replace_answer(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
    *,
    node_id: str,
    value: AnswerValue,
    answered_at: datetime | None = None,
) -> GuidedLabSessionV1

get_current_node(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
) -> WorkflowNodeV1

get_workflow_progress(
    definition: WorkflowDefinitionV1,
    session: GuidedLabSessionV1,
) -> WorkflowProgressV1
```

Time and ID injection are permitted for deterministic tests. Production defaults may mint UUIDs and UTC timestamps.

---

## 11. Test Cases

### Contract tests

1. All public dataclasses are frozen.
2. `.to_dict()` output is JSON serializable.
3. Serialization is deterministic.
4. Session records exact workflow version.
5. Timestamps are UTC-aware.
6. Non-finite decimal values are rejected.
7. Host path objects are not valid evidence references.

### Definition validation tests

1. Duplicate node IDs → `GDL-101`.
2. Missing entry node → `GDL-102`.
3. Unknown transition target → `GDL-103`.
4. Unreachable required node → `GDL-104`.
5. No reachable completion → `GDL-105`.
6. Two simultaneously valid transitions → `GDL-106`.
7. Unknown answer kind → `GDL-107`.
8. Invalid numeric bounds or empty choices → `GDL-108`.
9. Domain instruction without required source → `GDL-109`.
10. Reference workflow validates with zero findings.

### Engine tests

1. Same definition/session/action yields identical next state except injected time/ID.
2. Wrong answer type → `GDL-302`.
3. Choice outside declared set → `GDL-303`.
4. Instruction cannot be answered as a question → `GDL-301`.
5. Evidence node cannot advance without evidence → `GDL-304`.
6. Back navigation returns to the previous reachable node.
7. Replacing an earlier branch answer removes unreachable downstream answers and evidence.
8. Pause/resume preserves current node and history.
9. Completed and abandoned sessions reject further actions → `GDL-205`.
10. A session for version 1 cannot run against version 2 → `GDL-201`.

### Reference-workflow tests

1. Top plate/new capture path completes.
2. Back plate/existing measurement path completes.
3. Test-panel/manual test path completes.
4. Before/after purpose requests a baseline reference.
5. Environmental-record skip requires a reason.
6. Review identifies every missing requirement.
7. Correcting a specimen type invalidates dependent downstream answers.
8. Completion output includes workflow/session/evidence lineage.
9. Completion output contains no target thickness.
10. Completion output contains no instruction to remove wood.
11. Completion output contains no claim of correct modal identification.

### CLI tests

1. `ttp guided-lab list` shows builder goals, not analyzer names.
2. Unavailable workflows are labeled unavailable.
3. Start emits the first node and session JSON.
4. Resume accepts valid serialized state.
5. Corrupt JSON fails non-zero with a stable code.
6. Unknown workflow fails non-zero with a stable code.
7. CLI output contains no raw host paths.

### Regression gates

- existing measurement-core tests remain unchanged;
- existing server tests remain unchanged;
- existing agent/advisory-boundary tests remain unchanged;
- no new import from `guided_lab` into measurement-core modules;
- no circular dependency between `guided_lab`, GUI, server, or agent packages.

---

## 12. Rollout Order

### Stage 0 — Grounding

Before implementation:

1. confirm canonical CLI registration location;
2. confirm frozen-dataclass serialization conventions;
3. identify existing evidence-reference types suitable for reuse;
4. identify whether a stable session-ID utility already exists;
5. record any repo reality that conflicts with this handoff before coding.

### Stage 1 — Failing contract and validator tests

Add model and invalid-definition tests first.

No CLI or GUI work.

### Stage 2 — Contracts and error vocabulary

Implement `models.py` and `errors.py` until contract tests pass.

### Stage 3 — Definition validator

Implement pure graph and constraint validation.

The reference workflow must not be added until invalid-definition coverage is green.

### Stage 4 — Deterministic engine

Implement session start, actions, transitions, navigation, and downstream invalidation.

### Stage 5 — Reference workflow

Add `plate_measurement_setup_v1` and exercise all branches.

### Stage 6 — Catalog

Expose builder-oriented intents and workflow resolution.

### Stage 7 — Thin CLI

Register and test the development CLI surface.

### Stage 8 — Documentation and audit

Update README and, only after DO-99 completion, `CURRENT.md`.

Run package-boundary and serialization checks.

### Stage 9 — Full verification

Run:

```bash
python -m pytest -q tests/test_guided_lab_models.py
python -m pytest -q tests/test_guided_lab_validation.py
python -m pytest -q tests/test_guided_lab_engine.py
python -m pytest -q tests/test_guided_lab_plate_setup_workflow.py
python -m pytest -q tests/test_cli_guided_lab.py
python -m ruff check tap_tone_pi/guided_lab tests/test_guided_lab_*.py tests/test_cli_guided_lab.py
python -m ruff format --check tap_tone_pi/guided_lab tests/test_guided_lab_*.py tests/test_cli_guided_lab.py
python -m compileall -q tap_tone_pi
python -m pytest -q
```

Also run the repository's canonical pre-commit and boundary-verification commands.

---

## 13. Acceptance Criteria

DO-100 is complete only when:

1. workflow definitions are typed, frozen, deterministic, and validated;
2. the engine runs independently of GUI, server, audio hardware, and AI;
3. builder goals, not analyzer names, are the public entry point;
4. a session can pause, serialize, resume, go back, and replace an answer;
5. replacing an earlier answer safely invalidates downstream state;
6. every domain instruction is source-linked or visibly provisional;
7. the plate-setup workflow completes without issuing a thickness or manufacturing recommendation;
8. all stable error codes are tested;
9. no raw host paths enter workflow records or CLI output;
10. existing measurement, server, and advisory boundaries remain green;
11. README explains the Guided Digital Laboratory positioning;
12. `CURRENT.md` is promoted only after DO-99 is complete.

---

## 14. Definition of Done

The increment is done when a first-time operator can begin with:

> **I want to prepare a plate measurement**

and the software can deterministically guide that operator through the required questions, preparation acknowledgments, evidence references, review, correction, and completion record—without forcing the operator to understand or select the underlying scientific instruments first.

The increment is not done merely because a wizard screen exists. The workflow must be procedure-driven, resumable, auditable, source-aware, and independently testable.

---

## 15. Follow-On Dev Orders

The following are intentionally deferred until the foundation is proven:

- **DO-101 — Guided Plate Thickness Workflow**: validated measurements → transparent model inputs → calculation → evidence-separated result.
- **DO-102 — Guided Before/After Experiment Workflow**: baseline → documented operation → modified measurement → comparison evidence.
- **DO-103 — Guided Wolf-Note Investigation**: suspect note capture → adjacent-note controls → decay/response comparison → evidence-based finding.
- **DO-104 — Guided-Lab Desktop Experience**: builder-goal home screen and graphical procedure runner using the same engine.

These identifiers are planning placeholders only and are not authorized implementation work.
