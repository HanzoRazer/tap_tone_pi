"""CLI surface for the guided laboratory (DO-100).

The CLI is stateless between invocations: a session goes in as JSON and comes
back out as JSON. These tests drive the canonical parser from
``tap_tone_pi.cli.main`` so registration is exercised alongside behaviour.
"""

from __future__ import annotations

import json

import pytest

from tap_tone_pi.cli.main import build_parser
from tap_tone_pi.guided_lab.cli import ACTION_FLAGS

ANALYZER_WORDS = ("fft", "spectrum", "analyzer", "rayleigh", "modal", "coherence")


def run(argv: list[str], capsys) -> tuple[int, dict, str]:
    """Invoke the unified CLI and return (exit code, stdout JSON, stderr)."""
    args = build_parser().parse_args(argv)
    code = args.fn(args)
    captured = capsys.readouterr()
    payload = json.loads(captured.out) if captured.out.strip() else {}
    return code, payload, captured.err


def start_session(capsys, session_id: str = "s-cli") -> dict:
    code, payload, _ = run(
        ["guided-lab", "start", "plate_measurement_setup", "--session-id", session_id],
        capsys,
    )
    assert code == 0
    return payload["session"]


def act(capsys, session: dict, *flags: str) -> tuple[int, dict, str]:
    return run(
        ["guided-lab", "act", "--session-json", json.dumps(session), *flags], capsys
    )


class TestRegistration:
    def test_guided_lab_is_registered_on_the_unified_parser(self):
        args = build_parser().parse_args(["guided-lab", "list"])
        assert callable(args.fn)

    def test_existing_commands_still_parse(self):
        for command in ("devices", "sessions", "last"):
            args = build_parser().parse_args([command])
            assert callable(args.fn)

    def test_act_requires_a_subcommand(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["guided-lab"])


class TestRegistrationIsolation:
    """A guided laboratory that will not load must not take the CLI with it."""

    @staticmethod
    def _break_registration(monkeypatch):
        import tap_tone_pi.guided_lab.cli as guided_lab_cli

        def explode(_sub):
            raise RuntimeError("duplicate workflow key")

        monkeypatch.setattr(guided_lab_cli, "add_guided_lab_subcommand", explode)

    def test_unrelated_commands_still_parse(self, monkeypatch):
        self._break_registration(monkeypatch)
        for command in ("devices", "sessions", "last"):
            args = build_parser().parse_args([command])
            assert callable(args.fn)

    def test_the_stub_reports_the_failure_as_gdl_405(self, monkeypatch, capsys):
        self._break_registration(monkeypatch)
        args = build_parser().parse_args(["guided-lab", "list"])
        code = args.fn(args)
        captured = capsys.readouterr()
        assert code != 0
        assert captured.out == ""
        payload = json.loads(captured.err)
        assert payload["error"]["code"] == "GDL-405"
        assert "duplicate workflow key" in payload["error"]["context"]["reason"]

    def test_the_subcommand_is_reported_missing_rather_than_absent(self, monkeypatch):
        """A silently missing command reads as 'never existed'."""
        self._break_registration(monkeypatch)
        parser = build_parser()
        assert parser.parse_args(["guided-lab"]) is not None


class TestList:
    def test_list_returns_builder_goals(self, capsys):
        code, payload, err = run(["guided-lab", "list"], capsys)
        assert code == 0
        assert err == ""
        titles = [intent["title"] for intent in payload["intents"]]
        assert "I want to prepare a plate measurement" in titles

    def test_no_title_leads_with_an_analyzer_name(self, capsys):
        _, payload, _ = run(["guided-lab", "list"], capsys)
        for intent in payload["intents"]:
            lowered = intent["title"].lower()
            for word in ANALYZER_WORDS:
                assert word not in lowered

    def test_unavailable_intents_are_labelled_with_a_reason(self, capsys):
        _, payload, _ = run(["guided-lab", "list"], capsys)
        unavailable = [i for i in payload["intents"] if not i["available"]]
        assert unavailable
        for intent in unavailable:
            assert intent["unavailable_reason"]

    def test_output_is_sorted_and_stable(self, capsys):
        args = build_parser().parse_args(["guided-lab", "list"])
        args.fn(args)
        first = capsys.readouterr().out
        args.fn(args)
        second = capsys.readouterr().out
        assert first == second
        keys = list(json.loads(first)["intents"][0].keys())
        assert keys == sorted(keys)


class TestStart:
    def test_start_emits_the_full_envelope(self, capsys):
        code, payload, err = run(
            ["guided-lab", "start", "plate_measurement_setup"], capsys
        )
        assert code == 0
        assert err == ""
        assert set(payload) == {"workflow", "current_node", "session", "progress"}

    def test_start_lands_on_the_entry_question(self, capsys):
        session = start_session(capsys)
        assert session["current_node_id"] == "q_specimen_id"
        assert session["status"] == "active"
        assert session["schema_version"] == "guided_lab_session_v1"

    def test_start_honours_an_injected_session_id(self, capsys):
        session = start_session(capsys, session_id="fixed-id")
        assert session["session_id"] == "fixed-id"

    def test_unknown_workflow_is_gdl_402(self, capsys):
        code, _, err = run(["guided-lab", "start", "not_a_workflow"], capsys)
        assert code != 0
        assert "GDL-402" in err

    def test_unavailable_intent_workflow_is_gdl_404(self, capsys):
        """A listed-but-unbuilt goal is not the same failure as a typo."""
        code, _, err = run(["guided-lab", "start", "plate_thickness_survey"], capsys)
        assert code != 0
        assert "GDL-404" in err
        assert "GDL-402" not in err
        assert json.loads(err)["error"]["context"]["unavailable_reason"]

    def test_error_object_goes_to_stderr_as_json(self, capsys):
        code, _, err = run(["guided-lab", "start", "not_a_workflow"], capsys)
        assert code != 0
        payload = json.loads(err)
        assert payload["error"]["code"] == "GDL-402"

    def test_stderr_is_the_error_object_and_nothing_else(self, capsys):
        """A machine consumer parses the whole stream, not part of it."""
        _, _, err = run(["guided-lab", "start", "not_a_workflow"], capsys)
        assert set(json.loads(err)) == {"error"}
        assert err.strip().endswith("}")


class TestActions:
    def test_answer_then_advance(self, capsys):
        session = start_session(capsys)
        code, payload, _ = act(capsys, session, "--answer", "TOP-2026-014")
        assert code == 0
        assert payload["session"]["answers"][0]["value"] == "TOP-2026-014"

        code, payload, _ = act(capsys, payload["session"], "--advance")
        assert code == 0
        assert payload["session"]["current_node_id"] == "q_specimen_type"

    def test_boolean_answers_are_coerced(self, capsys):
        session = start_session(capsys)
        for value in ("TOP-1", "top", "joined", "Sitka", "characterize_material"):
            _, payload, _ = act(capsys, session, "--answer", value)
            _, payload, _ = act(capsys, payload["session"], "--advance")
            session = payload["session"]
        _, payload, _ = act(capsys, session, "--answer", "capture_new")
        _, payload, _ = act(capsys, payload["session"], "--advance")
        _, payload, _ = act(capsys, payload["session"], "--acknowledge")
        _, payload, _ = act(capsys, payload["session"], "--advance")
        session = payload["session"]
        assert session["current_node_id"] == "q_ready_dimensions"

        _, payload, _ = act(capsys, session, "--answer", "yes")
        answer = [
            a
            for a in payload["session"]["answers"]
            if a["node_id"] == "q_ready_dimensions"
        ][0]
        assert answer["value"] is True

    def test_unparseable_boolean_is_gdl_302(self, capsys):
        session = start_session(capsys)
        for value in ("TOP-1", "top", "joined", "Sitka", "characterize_material"):
            _, payload, _ = act(capsys, session, "--answer", value)
            _, payload, _ = act(capsys, payload["session"], "--advance")
            session = payload["session"]
        _, payload, _ = act(capsys, session, "--answer", "capture_new")
        _, payload, _ = act(capsys, payload["session"], "--advance")
        _, payload, _ = act(capsys, payload["session"], "--acknowledge")
        _, payload, _ = act(capsys, payload["session"], "--advance")
        code, _, err = act(capsys, payload["session"], "--answer", "maybe")
        assert code != 0
        assert "GDL-302" in err

    def test_value_outside_the_choices_is_gdl_303(self, capsys):
        session = start_session(capsys)
        _, payload, _ = act(capsys, session, "--answer", "TOP-1")
        _, payload, _ = act(capsys, payload["session"], "--advance")
        code, _, err = act(capsys, payload["session"], "--answer", "side")
        assert code != 0
        assert "GDL-303" in err

    def test_wrong_action_for_the_node_is_gdl_301(self, capsys):
        session = start_session(capsys)
        code, _, err = act(capsys, session, "--acknowledge")
        assert code != 0
        assert "GDL-301" in err

    def test_pause_and_resume_round_trip(self, capsys):
        session = start_session(capsys)
        code, payload, _ = act(capsys, session, "--pause")
        assert code == 0
        assert payload["session"]["status"] == "paused"

        code, payload, _ = run(
            [
                "guided-lab",
                "resume",
                "--session-json",
                json.dumps(payload["session"]),
            ],
            capsys,
        )
        assert code == 0
        assert payload["session"]["status"] == "active"

    def test_abandon_marks_terminal(self, capsys):
        session = start_session(capsys)
        code, payload, _ = act(capsys, session, "--abandon")
        assert code == 0
        assert payload["session"]["status"] == "abandoned"

    def test_acting_on_a_terminal_session_is_gdl_205(self, capsys):
        session = start_session(capsys)
        _, payload, _ = act(capsys, session, "--abandon")
        code, _, err = act(capsys, payload["session"], "--advance")
        assert code != 0
        assert "GDL-205" in err

    def test_back_from_the_entry_node_is_gdl_305(self, capsys):
        session = start_session(capsys)
        code, _, err = act(capsys, session, "--back")
        assert code != 0
        assert "GDL-305" in err

    def test_evidence_reference_is_parsed_from_json(self, capsys):
        session = start_session(capsys)
        code, _, err = act(
            capsys,
            session,
            "--evidence",
            json.dumps(
                {
                    "evidence_id": "ev-1",
                    "evidence_kind": "specimen_record",
                    "source_system": "tap_tone_pi",
                }
            ),
        )
        # The entry node is a question, so the engine refuses the action.
        assert code != 0
        assert "GDL-301" in err

    def test_show_does_not_change_the_session(self, capsys):
        session = start_session(capsys)
        code, payload, _ = run(
            ["guided-lab", "show", "--session-json", json.dumps(session)], capsys
        )
        assert code == 0
        assert payload["session"] == session


class TestActionCombinations:
    def test_exactly_one_action_is_required(self, capsys):
        session = start_session(capsys)
        code, _, err = act(capsys, session)
        assert code != 0
        assert "GDL-403" in err

    def test_two_actions_are_rejected(self, capsys):
        session = start_session(capsys)
        code, _, err = act(capsys, session, "--advance", "--pause")
        assert code != 0
        assert "GDL-403" in err

    def test_answer_alongside_a_flag_is_rejected(self, capsys):
        session = start_session(capsys)
        code, _, err = act(capsys, session, "--answer", "TOP-1", "--advance")
        assert code != 0
        assert "GDL-403" in err

    def test_an_empty_answer_still_counts_as_an_action(self, capsys):
        session = start_session(capsys)
        code, _, err = act(capsys, session, "--answer", "")
        assert code != 0
        # Rejected by the constraint, not by the action-combination guard.
        assert "GDL-303" in err
        assert "GDL-403" not in err

    def test_every_declared_action_flag_is_accepted_by_the_parser(self):
        parser = build_parser()
        for flag in ACTION_FLAGS:
            argv = ["guided-lab", "act", "--session-json", "{}", f"--{flag}"]
            if flag in ("answer", "evidence"):
                argv.append("x")
            assert parser.parse_args(argv) is not None


class TestSessionInput:
    def test_malformed_json_is_gdl_401(self, capsys):
        code, _, err = run(
            ["guided-lab", "act", "--session-json", "{not json", "--advance"], capsys
        )
        assert code != 0
        assert "GDL-401" in err

    def test_unknown_session_field_is_gdl_401(self, capsys):
        session = start_session(capsys)
        session["unexpected_field"] = "x"
        code, _, err = act(capsys, session, "--advance")
        assert code != 0
        assert "GDL-401" in err

    def test_wrong_schema_version_is_gdl_401(self, capsys):
        session = start_session(capsys)
        session["schema_version"] = "guided_lab_session_v2"
        code, _, err = act(capsys, session, "--advance")
        assert code != 0
        assert "GDL-401" in err

    def test_supplying_no_session_is_gdl_403(self, capsys):
        code, _, err = run(["guided-lab", "act", "--advance"], capsys)
        assert code != 0
        assert "GDL-403" in err

    def test_supplying_both_session_inputs_is_gdl_403(self, capsys, tmp_path):
        session_file = tmp_path / "session.json"
        session_file.write_text("{}", encoding="utf-8")
        code, _, err = run(
            [
                "guided-lab",
                "act",
                "--session-json",
                "{}",
                "--session-file",
                str(session_file),
                "--advance",
            ],
            capsys,
        )
        assert code != 0
        assert "GDL-403" in err

    def test_session_file_is_read(self, capsys, tmp_path):
        session = start_session(capsys)
        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(session), encoding="utf-8")
        code, payload, _ = run(
            ["guided-lab", "show", "--session-file", str(session_file)], capsys
        )
        assert code == 0
        assert payload["session"] == session

    def test_unreadable_session_file_is_gdl_401_without_the_path(
        self, capsys, tmp_path
    ):
        missing = tmp_path / "no_such_session.json"
        code, _, err = run(
            ["guided-lab", "show", "--session-file", str(missing)], capsys
        )
        assert code != 0
        assert "GDL-401" in err
        assert str(missing) not in err
        assert "no_such_session" not in err


class TestOutputDiscipline:
    def test_success_writes_nothing_to_stderr(self, capsys):
        code, _, err = run(["guided-lab", "list"], capsys)
        assert code == 0
        assert err == ""

    def test_failure_writes_nothing_to_stdout(self, capsys):
        args = build_parser().parse_args(["guided-lab", "start", "not_a_workflow"])
        code = args.fn(args)
        captured = capsys.readouterr()
        assert code != 0
        assert captured.out == ""
        assert captured.err != ""

    def test_json_is_indented_and_key_sorted(self, capsys):
        args = build_parser().parse_args(["guided-lab", "list"])
        args.fn(args)
        out = capsys.readouterr().out
        assert out.startswith("{\n")
        assert json.dumps(json.loads(out), indent=2, sort_keys=True) == out.strip()

    def test_session_output_never_contains_a_host_path(self, capsys, tmp_path):
        session = start_session(capsys)
        session_file = tmp_path / "session.json"
        session_file.write_text(json.dumps(session), encoding="utf-8")
        args = build_parser().parse_args(
            ["guided-lab", "show", "--session-file", str(session_file)]
        )
        args.fn(args)
        out = capsys.readouterr().out
        assert str(tmp_path) not in out
        assert "session.json" not in out
        assert "C:\\" not in out

    def test_no_output_mentions_an_analyzer_first(self, capsys):
        _, payload, _ = run(["guided-lab", "list"], capsys)
        blob = json.dumps(payload).lower()
        assert "i want to" in blob
        for word in ("fft", "rayleigh", "ritz"):
            assert word not in blob


class TestNoTracebackEscapes:
    """Stderr must hold one JSON error object, never a Python traceback.

    A traceback breaks the documented stderr contract twice over: it puts prose
    where a single parseable document is promised, and every frame it prints
    names a host path — in a module whose docstring states no output ever
    contains one.
    """

    def test_a_session_file_that_is_not_utf8_is_reported_as_json(
        self, tmp_path, capsys
    ):
        bad = tmp_path / "session.bin"
        bad.write_bytes(b"\xff\xfe\x00\x80\x81\x82")
        code, _, err = run(["guided-lab", "show", "--session-file", str(bad)], capsys)
        assert code == 1
        payload = json.loads(err)
        assert payload["error"]["code"] == "GDL-401"

    def test_the_undecodable_file_error_names_no_path(self, tmp_path, capsys):
        bad = tmp_path / "session.bin"
        bad.write_bytes(b"\xff\xfe\x00\x80")
        _, _, err = run(["guided-lab", "show", "--session-file", str(bad)], capsys)
        assert str(tmp_path) not in err
        assert "Traceback" not in err
        assert "session.bin" not in err

    def test_the_reason_is_the_exception_class_only(self, tmp_path, capsys):
        bad = tmp_path / "session.bin"
        bad.write_bytes(b"\xff\xfe\x00\x80")
        _, _, err = run(["guided-lab", "show", "--session-file", str(bad)], capsys)
        assert json.loads(err)["error"]["context"]["reason"] == "UnicodeDecodeError"

    def test_a_missing_session_file_is_reported_as_json(self, tmp_path, capsys):
        missing = tmp_path / "nope.json"
        code, _, err = run(
            ["guided-lab", "show", "--session-file", str(missing)], capsys
        )
        assert code == 1
        assert json.loads(err)["error"]["code"] == "GDL-401"
        assert str(tmp_path) not in err

    def test_an_unexpected_failure_becomes_gdl_406(self, capsys, monkeypatch):
        import tap_tone_pi.guided_lab.cli as gl_cli

        def boom() -> None:
            raise RuntimeError(r"host path C:\Users\someone\secret would leak")

        monkeypatch.setattr(gl_cli, "list_workflow_intents", boom)
        code, _, err = run(["guided-lab", "list"], capsys)
        assert code == 1
        payload = json.loads(err)
        assert payload["error"]["code"] == "GDL-406"
        assert payload["error"]["context"]["reason"] == "RuntimeError"

    def test_an_unexpected_failure_leaks_neither_message_nor_path(
        self, capsys, monkeypatch
    ):
        import tap_tone_pi.guided_lab.cli as gl_cli

        def boom() -> None:
            raise RuntimeError(r"C:\Users\someone\secret")

        monkeypatch.setattr(gl_cli, "list_workflow_intents", boom)
        _, _, err = run(["guided-lab", "list"], capsys)
        assert "C:" not in err
        assert "secret" not in err
        assert "Traceback" not in err

    def test_stderr_stays_a_single_json_document(self, capsys, monkeypatch):
        import tap_tone_pi.guided_lab.cli as gl_cli

        def boom() -> None:
            raise RuntimeError("x")

        monkeypatch.setattr(gl_cli, "list_workflow_intents", boom)
        _, _, err = run(["guided-lab", "list"], capsys)
        json.loads(err)  # parses whole, with nothing beside it
