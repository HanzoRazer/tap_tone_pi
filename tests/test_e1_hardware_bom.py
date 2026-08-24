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
            >= checker.rung(checker.OWNERSHIP_CLAIMED_FROM)
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
        assert checker.rung("REJECTED") < checker.rung(checker.OWNERSHIP_CLAIMED_FROM)

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
        assert any("not a\n" not in p and "not a BOM local_id" in p for p in problems)

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
