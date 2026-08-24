"""E1 hardware BOM and register integrity (DO-104P).

DO-104P is a procurement order, so its failures are not runtime errors — they
are a chain that cannot connect, or a document claiming something nobody owns.
The second kind is what survives into evidence, and it is what these tests hold.

The rule they exist for: **a design selection is not a possession.** The
repository's authoritative hardware stack specification design-selects a
Raspberry Pi 5, a HiFiBerry ADC, and an OPA1612 preamp, and the repository holds
no evidence that any of them physically exists — every captured session under
`runs_phase2/` is synthetic or a demo fixture. Nothing may reach RECEIVED on the
strength of a design document.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HARDWARE = REPO_ROOT / "docs" / "hardware"


def load_checker():
    path = REPO_ROOT / "scripts" / "check_e1_hardware_bom.py"
    spec = importlib.util.spec_from_file_location("check_e1_hardware_bom", path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def checker():
    return load_checker()


@pytest.fixture(scope="module")
def bom(checker):
    return checker.parse_table(checker.BOM_PATH, "local_id")


@pytest.fixture(scope="module")
def register(checker):
    return checker.parse_table(checker.REGISTER_PATH, "local_id")


def row_for(rows, local_id):
    return next(row for row in rows if row["local_id"] == local_id)


class TestTheDocumentsExist:
    @pytest.mark.parametrize(
        "name",
        [
            "TTP_E1_HARDWARE_REQUIREMENTS.md",
            "TTP_E1_HARDWARE_BOM.md",
            "TTP_E1_HARDWARE_SELECTION_RATIONALE.md",
            "TTP_E1_INTERFACE_MATRIX.md",
            "TTP_E1_RIG_ASSEMBLY.md",
            "TTP_E1_HARDWARE_IDENTITY_REGISTER.md",
            "TTP_E1_PROCUREMENT_STATUS.md",
            "TTP_E1_DATASHEET_MANIFEST.json",
        ],
    )
    def test_document_present(self, name):
        assert (HARDWARE / name).exists()

    def test_the_manifest_is_valid_json(self):
        payload = json.loads(
            (HARDWARE / "TTP_E1_DATASHEET_MANIFEST.json").read_text(encoding="utf-8")
        )
        assert payload["schema_version"] == "ttp_e1_datasheet_manifest_v1"
        assert isinstance(payload["entries"], list)

    def test_no_datasheet_is_recorded_for_an_unselected_part(self):
        # An empty list is the accurate state, not an unfinished one.
        payload = json.loads(
            (HARDWARE / "TTP_E1_DATASHEET_MANIFEST.json").read_text(encoding="utf-8")
        )
        assert payload["entries"] == []


class TestTheRealDocumentsAreConsistent:
    def test_the_checker_passes_the_committed_documents(self, checker):
        assert checker.main([]) == 0

    def test_every_required_class_has_a_row(self, checker, bom):
        present = {row["component_class"] for row in bom}
        assert set(checker.REQUIRED_CLASSES) <= present

    def test_nothing_is_claimed_as_owned(self, checker, bom):
        # The whole point of the current state. If this ever fails, either
        # hardware arrived or a document started lying.
        owned = [
            row["local_id"]
            for row in bom
            if checker.rung(row["status"])
            >= checker.rung(checker.PHYSICAL_POSSESSION_CLAIMED_FROM)
        ]
        assert owned == []

    def test_the_stack_designs_are_selected_not_received(self, bom):
        for local_id in ("HOST-001", "ADC-001", "PREAMP-001"):
            assert row_for(bom, local_id)["status"] == "SELECTED"

    def test_every_register_entry_is_not_received(self, register):
        assert {row["inspection_status"] for row in register} == {"NOT_RECEIVED"}

    def test_no_serial_number_is_invented_before_receipt(self, checker, register):
        for row in register:
            assert not checker.is_set(row["serial_number"]), row["local_id"]


class TestOwnershipCannotBeClaimedFromADesign:
    """The check DO-104P was written to enforce."""

    def make(self, checker, status="RECEIVED", **register_overrides):
        bom = [
            {
                "local_id": "ADC-001",
                "component_class": "adc_interface",
                "manufacturer": "HiFiBerry",
                "model": "DAC+ ADC Pro",
                "supplier": "a supplier",
                "status": status,
            }
        ]
        entry = {
            "local_id": "ADC-001",
            "serial_number": "TBD",
            "asset_label": "TBD",
            "received_date": "TBD",
            "inspection_status": "NOT_RECEIVED",
        }
        entry.update(register_overrides)
        return bom, [entry]

    def test_received_without_serial_or_asset_label_is_refused(self, checker):
        bom, register = self.make(checker)
        problems = checker.check_ownership(bom, register)
        assert any("not a possession" in p for p in problems)

    def test_received_with_a_serial_is_accepted(self, checker):
        bom, register = self.make(
            checker,
            serial_number="SN-12345",
            received_date="2026-09-01",
            inspection_status="INSPECTED_OK",
        )
        assert checker.check_ownership(bom, register) == []

    def test_a_fabricated_part_may_use_an_asset_label_instead(self, checker):
        # A stinger has no manufacturer serial but still needs an identity.
        bom, register = self.make(
            checker,
            asset_label="TTP-ASSET-014",
            received_date="2026-09-01",
            inspection_status="INSPECTED_OK",
        )
        assert checker.check_ownership(bom, register) == []

    def test_received_with_no_register_entry_at_all_is_refused(self, checker):
        bom, _ = self.make(checker)
        problems = checker.check_ownership(bom, [])
        assert any("no identity-register entry" in p for p in problems)

    def test_received_while_the_register_says_not_received_is_refused(self, checker):
        bom, register = self.make(
            checker, serial_number="SN-1", received_date="2026-09-01"
        )
        problems = checker.check_ownership(bom, register)
        assert any("NOT_RECEIVED" in p for p in problems)

    def test_bench_ready_after_a_failed_inspection_is_refused(self, checker):
        bom, register = self.make(
            checker,
            status="BENCH_READY",
            serial_number="SN-1",
            received_date="2026-09-01",
            inspection_status="INSPECTED_PROBLEM",
        )
        problems = checker.check_ownership(bom, register)
        assert any("inspected with a problem" in p for p in problems)

    def test_selected_needs_no_ownership_evidence(self, checker):
        # Design selection is legitimate and evidences nothing physical.
        bom, register = self.make(checker, status="SELECTED")
        assert checker.check_ownership(bom, register) == []


class TestTheRegisterMustNameRealComponents:
    """An orphan register row is a place a serial number can attach to nothing.

    The register is what an ownership claim is checked against. A row that no
    BOM component matches — a mistyped id, or one left behind after a component
    was renumbered — would sit there looking authoritative while describing
    nothing.
    """

    def entry(self, local_id="ADC-001", **overrides):
        row = {
            "local_id": local_id,
            "serial_number": "TBD",
            "asset_label": "TBD",
            "received_date": "TBD",
            "inspection_status": "NOT_RECEIVED",
        }
        row.update(overrides)
        return row

    def bom(self):
        return [{"local_id": "ADC-001"}, {"local_id": "FORCE-001"}]

    def test_a_row_naming_a_real_component_is_accepted(self, checker):
        assert checker.check_register([self.entry()], self.bom()) == []

    def test_an_orphan_row_is_refused(self, checker):
        problems = checker.check_register([self.entry("ADC-099")], self.bom())
        assert any("not a BOM component" in p for p in problems)

    def test_a_mistyped_id_is_refused(self, checker):
        problems = checker.check_register([self.entry("FORSE-001")], self.bom())
        assert any("FORSE-001" in p for p in problems)

    def test_a_duplicate_row_is_refused(self, checker):
        problems = checker.check_register([self.entry(), self.entry()], self.bom())
        assert any("duplicate identity-register entry" in p for p in problems)

    def test_an_unknown_inspection_status_is_refused(self, checker):
        problems = checker.check_register(
            [self.entry(inspection_status="PROBABLY_FINE")], self.bom()
        )
        assert any("unknown inspection_status" in p for p in problems)

    def test_a_missing_inspection_column_is_refused_not_crashed(self, checker):
        row = self.entry()
        del row["inspection_status"]
        problems = checker.check_register([row], self.bom())
        assert any("unknown inspection_status" in p for p in problems)

    def test_the_committed_register_names_only_real_components(
        self, checker, register, bom
    ):
        assert checker.check_register(register, bom) == []


class TestStatusLadder:
    def base_row(self, **overrides):
        row = {
            "local_id": "FORCE-001",
            "component_class": "force_transducer",
            "manufacturer": "TBD",
            "model": "TBD",
            "supplier": "TBD",
            "status": "TBD",
        }
        row.update(overrides)
        return row

    def all_classes(self, checker, extra):
        rows = [
            self.base_row(
                local_id=f"X-{index}",
                component_class=cls,
            )
            for index, cls in enumerate(checker.REQUIRED_CLASSES)
            if cls != extra["component_class"]
        ]
        return rows + [extra]

    def test_selected_without_a_model_is_refused(self, checker):
        row = self.base_row(status="SELECTED", manufacturer="Acme")
        problems = checker.check_bom(self.all_classes(checker, row))
        assert any("names no model" in p for p in problems)

    def test_selected_without_a_manufacturer_is_refused(self, checker):
        row = self.base_row(status="SELECTED", model="Model X")
        problems = checker.check_bom(self.all_classes(checker, row))
        assert any("names no manufacturer" in p for p in problems)

    def test_ordered_without_a_supplier_is_refused(self, checker):
        row = self.base_row(status="ORDERED", manufacturer="Acme", model="Model X")
        problems = checker.check_bom(self.all_classes(checker, row))
        assert any("names no supplier" in p for p in problems)

    def test_an_unknown_status_is_refused(self, checker):
        row = self.base_row(status="PROBABLY_FINE")
        problems = checker.check_bom(self.all_classes(checker, row))
        assert any("unknown status" in p for p in problems)

    def test_rejected_is_a_terminal_status_not_a_rung(self, checker):
        # REJECTED sits off the ladder, so it can never satisfy an ownership
        # claim by accident.
        assert checker.rung("REJECTED") == -1
        assert checker.rung("REJECTED") < checker.rung(
            checker.PHYSICAL_POSSESSION_CLAIMED_FROM
        )

    def test_a_duplicate_local_id_is_refused(self, checker):
        rows = self.all_classes(checker, self.base_row())
        problems = checker.check_bom(rows + [self.base_row()])
        assert any("duplicate local_id" in p for p in problems)

    def test_a_missing_required_class_is_refused(self, checker):
        problems = checker.check_bom([self.base_row()])
        assert any("required component class" in p for p in problems)

    def test_an_unknown_component_class_is_refused(self, checker):
        row = self.base_row(component_class="flux_capacitor")
        problems = checker.check_bom(self.all_classes(checker, row))
        assert any("not a known class" in p for p in problems)

    def test_the_conditional_attenuator_is_permitted_but_not_required(self, checker):
        rows = [
            self.base_row(local_id=f"X-{i}", component_class=cls)
            for i, cls in enumerate(checker.REQUIRED_CLASSES)
        ]
        assert checker.check_bom(rows) == []
        rows.append(self.base_row(local_id="ATTEN-001", component_class="attenuator"))
        assert checker.check_bom(rows) == []


class TestDatasheetManifest:
    def test_an_entry_for_an_unknown_component_is_refused(self, checker):
        manifest = {"entries": [{"component_id": "GHOST-001", "sha256": "a" * 64}]}
        problems = checker.check_manifest(manifest, [{"local_id": "ADC-001"}])
        assert any("not a BOM local_id" in p for p in problems)

    def test_a_malformed_digest_is_refused(self, checker):
        manifest = {
            "entries": [
                {
                    "component_id": "ADC-001",
                    "sha256": "not-a-digest",
                    "source_url": "https://example.invalid/ds.pdf",
                }
            ]
        }
        problems = checker.check_manifest(manifest, [{"local_id": "ADC-001"}])
        assert any("no SHA-256" in p for p in problems)

    def test_an_entry_with_no_source_is_refused(self, checker):
        manifest = {"entries": [{"component_id": "ADC-001", "sha256": "b" * 64}]}
        problems = checker.check_manifest(manifest, [{"local_id": "ADC-001"}])
        assert any("neither a source" in p for p in problems)

    def test_a_duplicate_identity_is_refused(self, checker):
        entry = {
            "component_id": "ADC-001",
            "sha256": "c" * 64,
            "source_url": "https://example.invalid/ds.pdf",
        }
        problems = checker.check_manifest(
            {"entries": [entry, dict(entry)]}, [{"local_id": "ADC-001"}]
        )
        assert any("duplicate datasheet identity" in p for p in problems)

    def test_an_entry_that_is_not_an_object_is_reported_not_crashed(self, checker):
        # A hand-edited manifest can put a bare string in the list. A validator
        # that raises on bad input tells nobody which input broke it.
        problems = checker.check_manifest(
            {"entries": ["ADC-001", 7, None]}, [{"local_id": "ADC-001"}]
        )
        assert len(problems) == 3
        assert all("is not an object" in p for p in problems)

    def test_a_well_formed_entry_passes(self, checker):
        manifest = {
            "entries": [
                {
                    "component_id": "ADC-001",
                    "sha256": "d" * 64,
                    "source_url": "https://example.invalid/ds.pdf",
                    "retrieved_at": "2026-09-01T00:00:00Z",
                }
            ]
        }
        assert checker.check_manifest(manifest, [{"local_id": "ADC-001"}]) == []


class TestTableParsing:
    def test_a_shifted_row_is_refused_rather_than_padded(self, checker, tmp_path):
        # A shifted column turns one component's serial into another's.
        path = tmp_path / "bom.md"
        path.write_text(
            "| local_id | status |\n| --- | --- |\n| A-1 | TBD | extra |\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            checker.parse_table(path, "local_id")

    def test_a_missing_required_column_is_refused(self, checker, tmp_path):
        # Without this the first row access raises a KeyError, and a traceback
        # names the column but not the document, the row, or the fix.
        path = tmp_path / "bom.md"
        path.write_text(
            "\n".join(["| local_id | status |", "| --- | --- |", "| A-1 | TBD |"]),
            encoding="utf-8",
        )
        with pytest.raises(ValueError) as excinfo:
            checker.parse_table(path, "local_id", checker.REQUIRED_BOM_COLUMNS)
        assert "missing column(s)" in str(excinfo.value)
        assert "manufacturer" in str(excinfo.value)

    def test_a_table_with_every_required_column_parses(self, checker, tmp_path):
        path = tmp_path / "bom.md"
        header = " | ".join(checker.REQUIRED_BOM_COLUMNS)
        dashes = " | ".join("---" for _ in checker.REQUIRED_BOM_COLUMNS)
        values = " | ".join("x" for _ in checker.REQUIRED_BOM_COLUMNS)
        path.write_text(
            "\n".join([f"| {header} |", f"| {dashes} |", f"| {values} |"]),
            encoding="utf-8",
        )
        rows = checker.parse_table(path, "local_id", checker.REQUIRED_BOM_COLUMNS)
        assert len(rows) == 1

    def test_the_committed_documents_carry_every_required_column(self, checker):
        checker.parse_table(checker.BOM_PATH, "local_id", checker.REQUIRED_BOM_COLUMNS)
        checker.parse_table(
            checker.REGISTER_PATH, "local_id", checker.REQUIRED_REGISTER_COLUMNS
        )

    def test_a_missing_table_is_refused(self, checker, tmp_path):
        path = tmp_path / "empty.md"
        path.write_text("no table here\n", encoding="utf-8")
        with pytest.raises(ValueError):
            checker.parse_table(path, "local_id")

    @pytest.mark.parametrize("placeholder", ["TBD", "n/a", "-", "", "none"])
    def test_placeholders_do_not_count_as_values(self, checker, placeholder):
        assert not checker.is_set(placeholder)

    def test_a_real_value_counts(self, checker):
        assert checker.is_set("SN-12345")

    def test_a_missing_cell_is_not_a_value(self, checker):
        # A malformed document can put None where a string belongs; the
        # validator reports on it rather than raising.
        assert not checker.is_set(None)

    def test_a_non_string_value_counts(self, checker):
        assert checker.is_set(42)


class TestProtocolConsistency:
    def test_the_protocol_cannot_lag_a_selection(self, checker):
        # This check caught a real staleness when it was first run: the protocol
        # still said TBD for the audio interface the BOM design-selects.
        bom = [
            {
                "local_id": "SHAKER-001",
                "component_class": "shaker",
                "status": "SELECTED",
                "model": "Model X",
            }
        ]
        problems = checker.check_protocol(bom)
        assert any("still says TBD for 'Shaker'" in p for p in problems)

    def test_a_tbd_selection_does_not_require_the_protocol_to_move(self, checker):
        bom = [
            {
                "local_id": "SHAKER-001",
                "component_class": "shaker",
                "status": "TBD",
                "model": "TBD",
            }
        ]
        assert checker.check_protocol(bom) == []


class TestTheSummaryUsesTheFrameworksVocabulary:
    """The footer is where a reader forms an impression, so it must be exact.

    "Nothing is owned" reads as contradicting three rows the BOM deliberately
    records as design-selected. The distinction the whole order rests on is
    between choosing a component and holding one, and the summary has to keep
    it.
    """

    def test_it_separates_design_selection_from_possession(self, checker, capsys):
        checker.main(["--summary"])
        out = capsys.readouterr().out
        assert "design-selected, possession unconfirmed: 3" in out
        assert "recorded as physically received:         0" in out

    def test_it_does_not_claim_nothing_is_owned(self, checker, capsys):
        checker.main(["--summary"])
        out = capsys.readouterr().out
        assert "nothing is owned" not in out
        assert "No component is recorded as physically received" in out

    def test_it_says_why_bench_bring_up_cannot_begin(self, checker, capsys):
        checker.main(["--summary"])
        out = capsys.readouterr().out
        assert "not evidence of possession" in out
        assert "DO-104E cannot begin bench bring-up" in out


class TestTheCheckerIsReadOnly:
    def test_it_writes_nothing(self):
        source = (REPO_ROOT / "scripts" / "check_e1_hardware_bom.py").read_text(
            encoding="utf-8"
        )
        for marker in ("write_text(", "mkdir(", "unlink(", "open("):
            assert marker not in source

    def test_it_recommends_no_products(self):
        # DO-104P §7: the validator must not recommend products or infer a
        # missing specification.
        source = (REPO_ROOT / "scripts" / "check_e1_hardware_bom.py").read_text(
            encoding="utf-8"
        )
        for marker in ("def recommend", "def suggest", "def infer"):
            assert marker not in source
