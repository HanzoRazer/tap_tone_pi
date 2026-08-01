# INSTRUMENT CLASS: MEASUREMENT
"""Command-line surface for the guided laboratory (DO-100).

The CLI is a thin, stateless shell around the engine. It holds no session
between invocations: every command takes the session in and prints the session
out, so an operator (or a test, or a future GUI) owns the state and the engine
owns the rules.

This module does transport only — parsing arguments, coercing a shell string to
the type a question expects, and serializing the result. It does not re-check
anything the engine already checks. A value that survives coercion is handed
straight to the engine, which decides whether it is acceptable.

Machine-readable JSON goes to stdout. Failures go to stderr as a JSON error
object carrying a stable ``GDL-*`` code — that object alone, with no prose
beside it, so stderr parses as a whole — and the process exits non-zero. No
output ever contains a host path, including when a session was read from a file
the operator named.

One coercion is worth stating plainly: a ``decimal`` answer is read with
``float``, so it carries binary floating-point precision, not exact decimal
precision. No question in a shipped workflow compares a decimal for equality;
a future one that needs exact decimal semantics needs a different answer kind
rather than a change here.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable, Sequence

from tap_tone_pi.guided_lab import engine
from tap_tone_pi.guided_lab.catalog import (
    get_workflow_definition,
    list_workflow_intents,
)
from tap_tone_pi.guided_lab.errors import (
    GuidedLabActionError,
    GuidedLabError,
    GuidedLabErrorCode,
    GuidedLabSessionError,
)
from tap_tone_pi.guided_lab.models import (
    GuidedLabSessionV1,
    QuestionNodeV1,
    WorkflowAnswerKind,
    WorkflowDefinitionV1,
    WorkflowEvidenceReferenceV1,
)

#: Actions that carry a value. An empty string still counts as supplied — an
#: empty answer is a real attempt, and the engine decides whether to accept it.
VALUE_ACTION_FLAGS = ("answer", "evidence")

#: Actions that are their own instruction.
FLAG_ACTION_FLAGS = (
    "acknowledge",
    "advance",
    "back",
    "pause",
    "resume",
    "abandon",
    "complete",
)

#: Every mutating action `act` supports. Exactly one may be given per call.
ACTION_FLAGS = VALUE_ACTION_FLAGS + FLAG_ACTION_FLAGS


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)


def _emit(payload: dict[str, Any]) -> int:
    print(_dump(payload))
    return 0


def _fail(error: GuidedLabError) -> int:
    """Write the error object to stderr and nothing else.

    Stderr carries one JSON document per failure and no prose alongside it, so
    a caller can parse the whole stream rather than hunt for the object in it.
    The code and message are inside that document; nothing is lost by not
    repeating them.
    """
    print(_dump({"error": error.to_dict()}), file=sys.stderr)
    return 1


def _guarded(action: Callable[[], dict[str, Any]]) -> int:
    """Run ``action`` and emit its payload, converting any failure to JSON.

    A guided-laboratory failure already carries its code. Anything else — a file
    that is not UTF-8, a defect nobody predicted — would otherwise escape as a
    Python traceback, which puts prose on stderr where a single JSON document is
    promised *and* prints the host paths of every frame. Neither is acceptable
    from a module that states it never emits a path, so an unexpected exception
    is reported as ``GDL-406`` carrying its class name and nothing else.
    """
    try:
        return _emit(action())
    except GuidedLabError as exc:
        return _fail(exc)
    except Exception as exc:  # noqa: BLE001 - deliberate: no traceback may escape
        return _fail(
            GuidedLabSessionError(
                GuidedLabErrorCode.UNEXPECTED_CLI_FAILURE,
                "the guided laboratory command failed unexpectedly",
                {"reason": type(exc).__name__},
            )
        )


def _session_envelope(
    definition: WorkflowDefinitionV1, session: GuidedLabSessionV1
) -> dict[str, Any]:
    """The single response shape every session-bearing command returns."""
    return {
        "workflow": {
            "workflow_id": definition.workflow_id,
            "workflow_version": definition.workflow_version,
            "title": definition.title,
            "purpose": definition.purpose,
        },
        "current_node": engine.get_current_node(definition, session).to_dict(),
        "session": session.to_dict(),
        "progress": engine.get_workflow_progress(definition, session).to_dict(),
    }


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


def _load_session(args: argparse.Namespace) -> GuidedLabSessionV1:
    """Read a session from ``--session-json`` or ``--session-file``.

    A file path supplied by the operator is used and then forgotten. It is
    never echoed into output, into the session, or into an error context.
    """
    raw = getattr(args, "session_json", None)
    session_file = getattr(args, "session_file", None)

    if raw and session_file:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.INVALID_ACTION_COMBINATION,
            "supply either --session-json or --session-file, not both",
        )
    if not raw and not session_file:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.INVALID_ACTION_COMBINATION,
            "supply a session with --session-json or --session-file",
        )

    if session_file:
        try:
            with open(session_file, "r", encoding="utf-8") as handle:
                raw = handle.read()
        except (OSError, UnicodeDecodeError) as exc:
            # UnicodeDecodeError is a ValueError, not an OSError, so decoding a
            # file that is not UTF-8 used to escape this handler entirely and
            # surface as a traceback naming the operator's path.
            raise GuidedLabSessionError(
                GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
                "the session file could not be read",
                {"reason": type(exc).__name__},
            ) from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
            "the session is not valid JSON",
            {"reason": "json_decode_error"},
        ) from exc

    return GuidedLabSessionV1.from_dict(payload)


def _coerce_answer(node: QuestionNodeV1, raw: str) -> Any:
    """Turn a shell string into the type the question holds.

    Coercion only. Whether the value is *allowed* is the engine's decision.

    A string the question's type cannot hold is an operator problem, not a
    transport one, so it raises :class:`GuidedLabActionError` under ``GDL-302``
    — the same class the engine raises for the same code.
    """
    kind = node.answer_kind
    if kind is WorkflowAnswerKind.BOOLEAN:
        lowered = raw.strip().lower()
        if lowered in ("true", "yes", "y", "1"):
            return True
        if lowered in ("false", "no", "n", "0"):
            return False
        raise GuidedLabActionError(
            GuidedLabErrorCode.ANSWER_TYPE_MISMATCH,
            "this step expects true or false",
            {"node_id": node.node_id, "received": raw},
        )
    if kind is WorkflowAnswerKind.INTEGER:
        try:
            return int(raw.strip())
        except ValueError as exc:
            raise GuidedLabActionError(
                GuidedLabErrorCode.ANSWER_TYPE_MISMATCH,
                "this step expects a whole number",
                {"node_id": node.node_id, "received": raw},
            ) from exc
    if kind is WorkflowAnswerKind.DECIMAL:
        try:
            return float(raw.strip())
        except ValueError as exc:
            raise GuidedLabActionError(
                GuidedLabErrorCode.ANSWER_TYPE_MISMATCH,
                "this step expects a number",
                {"node_id": node.node_id, "received": raw},
            ) from exc
    return raw


def _parse_evidence(raw: str) -> WorkflowEvidenceReferenceV1:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GuidedLabSessionError(
            GuidedLabErrorCode.SESSION_PAYLOAD_MALFORMED,
            "the evidence reference is not valid JSON",
            {"reason": "json_decode_error"},
        ) from exc
    return WorkflowEvidenceReferenceV1.from_dict(payload)


def _selected_actions(args: argparse.Namespace) -> list[str]:
    """Which actions the operator supplied, in declaration order."""
    selected = [
        flag for flag in VALUE_ACTION_FLAGS if getattr(args, flag, None) is not None
    ]
    selected.extend(
        flag for flag in FLAG_ACTION_FLAGS if getattr(args, flag, False) is True
    )
    return selected


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_guided_lab_list(args: argparse.Namespace) -> int:
    """List builder goals, available and not."""

    def run() -> dict[str, Any]:
        return {"intents": [intent.to_dict() for intent in list_workflow_intents()]}

    return _guarded(run)


def cmd_guided_lab_start(args: argparse.Namespace) -> int:
    """Open a new session on a workflow."""

    def run() -> dict[str, Any]:
        definition = get_workflow_definition(
            args.workflow_id, getattr(args, "workflow_version", None)
        )
        session = engine.start_session(definition, session_id=args.session_id)
        return _session_envelope(definition, session)

    return _guarded(run)


def cmd_guided_lab_resume(args: argparse.Namespace) -> int:
    """Reopen a paused session and report where it stands."""

    def run() -> dict[str, Any]:
        session = _load_session(args)
        definition = get_workflow_definition(
            session.workflow_id, session.workflow_version
        )
        session = engine.resume_session(definition, session)
        return _session_envelope(definition, session)

    return _guarded(run)


def cmd_guided_lab_show(args: argparse.Namespace) -> int:
    """Report a session's current state without changing it."""

    def run() -> dict[str, Any]:
        session = _load_session(args)
        definition = get_workflow_definition(
            session.workflow_id, session.workflow_version
        )
        return _session_envelope(definition, session)

    return _guarded(run)


def cmd_guided_lab_act(args: argparse.Namespace) -> int:
    """Apply exactly one action to a session."""

    def run() -> dict[str, Any]:
        selected = _selected_actions(args)
        if len(selected) != 1:
            raise GuidedLabSessionError(
                GuidedLabErrorCode.INVALID_ACTION_COMBINATION,
                "supply exactly one action per invocation",
                {"supplied": sorted(selected), "expected_count": 1},
            )

        session = _load_session(args)
        definition = get_workflow_definition(
            session.workflow_id, session.workflow_version
        )
        action = selected[0]

        if action == "answer":
            node = engine.get_current_node(definition, session)
            # Coerce only where there is a question to coerce for. On any other
            # node the raw string goes through and the engine owns the refusal.
            value = (
                _coerce_answer(node, args.answer)
                if isinstance(node, QuestionNodeV1)
                else args.answer
            )
            session = engine.answer_question(definition, session, value)
        elif action == "acknowledge":
            session = engine.acknowledge_instruction(definition, session)
        elif action == "evidence":
            session = engine.attach_evidence(
                definition, session, _parse_evidence(args.evidence)
            )
        elif action == "advance":
            session = engine.advance_session(definition, session)
        elif action == "back":
            session = engine.go_back(definition, session)
        elif action == "pause":
            session = engine.pause_session(definition, session)
        elif action == "resume":
            session = engine.resume_session(definition, session)
        elif action == "abandon":
            session = engine.abandon_session(definition, session)
        else:  # complete
            session = engine.complete_session(definition, session)

        return _session_envelope(definition, session)

    return _guarded(run)


# ---------------------------------------------------------------------------
# Parser wiring
# ---------------------------------------------------------------------------


def _add_session_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--session-json",
        default=None,
        help="Session record as a JSON string",
    )
    parser.add_argument(
        "--session-file",
        default=None,
        help="File holding a session record (the path is never echoed back)",
    )


def add_guided_lab_subcommand(subparsers: Any) -> None:
    """Register the ``guided-lab`` command group."""
    p_gl = subparsers.add_parser(
        "guided-lab",
        help="Guided Digital Laboratory workflows",
        description=(
            "Work through a measurement procedure starting from a builder "
            "goal. Sessions are resumable and are passed in and out as JSON; "
            "the CLI keeps no state between invocations."
        ),
    )
    gl_sub = p_gl.add_subparsers(dest="guided_lab_cmd", required=True)

    p_list = gl_sub.add_parser("list", help="List builder goals")
    p_list.set_defaults(fn=cmd_guided_lab_list)

    p_start = gl_sub.add_parser("start", help="Start a workflow session")
    p_start.add_argument("workflow_id", help="Workflow to start")
    p_start.add_argument(
        "--workflow-version", type=int, default=None, help="Pin a workflow version"
    )
    p_start.add_argument(
        "--session-id", default=None, help="Use a specific session identifier"
    )
    p_start.set_defaults(fn=cmd_guided_lab_start)

    p_resume = gl_sub.add_parser("resume", help="Resume a paused session")
    _add_session_arguments(p_resume)
    p_resume.set_defaults(fn=cmd_guided_lab_resume)

    p_show = gl_sub.add_parser("show", help="Show a session without changing it")
    _add_session_arguments(p_show)
    p_show.set_defaults(fn=cmd_guided_lab_show)

    p_act = gl_sub.add_parser("act", help="Apply one action to a session")
    _add_session_arguments(p_act)
    p_act.add_argument("--answer", default=None, help="Answer the current question")
    p_act.add_argument(
        "--acknowledge", action="store_true", help="Acknowledge the current instruction"
    )
    p_act.add_argument(
        "--evidence", default=None, help="Attach an evidence reference as JSON"
    )
    p_act.add_argument("--advance", action="store_true", help="Move to the next step")
    p_act.add_argument(
        "--back", action="store_true", help="Return to the previous step"
    )
    p_act.add_argument("--pause", action="store_true", help="Pause the session")
    p_act.add_argument("--resume", action="store_true", help="Resume the session")
    p_act.add_argument(
        "--abandon", action="store_true", help="Close without completing"
    )
    p_act.add_argument("--complete", action="store_true", help="Close the record")
    p_act.set_defaults(fn=cmd_guided_lab_act)


def main(argv: Sequence[str] | None = None) -> int:
    """Standalone entry point, mainly for tests."""
    parser = argparse.ArgumentParser(prog="ttp guided-lab")
    sub = parser.add_subparsers(dest="cmd", required=True)
    add_guided_lab_subcommand(sub)
    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.fn(args))


__all__ = [
    "ACTION_FLAGS",
    "add_guided_lab_subcommand",
    "cmd_guided_lab_act",
    "cmd_guided_lab_list",
    "cmd_guided_lab_resume",
    "cmd_guided_lab_show",
    "cmd_guided_lab_start",
]
