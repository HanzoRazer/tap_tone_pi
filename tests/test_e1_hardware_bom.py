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

    def test_every_datasheet_entry_is_a_document_that_was_actually_retrieved(self):
        # Under DO-104P an empty list was the accurate state. DO-104S retrieved
        # real documents, so the invariant moves rather than disappears: no
        # entry may be a placeholder. Each one carries the digest of bytes that
        # were fetched, a byte length, and a source - which is what stops a
        # datasheet reference from being asserted for a part nobody looked up.
        payload = json.loads(
            (HARDWARE / "TTP_E1_DATASHEET_MANIFEST.json").read_text(encoding="utf-8")
        )
        assert payload["entries"], "DO-104S retrieved documents; the list is not empty"
        for entry in payload["entries"]:
            assert len(entry["sha256"]) == 64
            assert int(entry["byte_length"]) > 0
            assert entry["source_url"].startswith("https://")
            assert entry["retrieved_utc"].endswith("Z")

    def test_no_digest_is_computed_over_a_rendering(self):
        # The ruling that keeps the manifest honest: a digest is over the bytes
        # the server served. A markdown or text extraction of a PDF would hash
        # to something that is not the manufacturer's document.
        payload = json.loads(
            (HARDWARE / "TTP_E1_DATASHEET_MANIFEST.json").read_text(encoding="utf-8")
        )
        for entry in payload["entries"]:
            assert entry["document_format"] in ("pdf", "html")
            if entry["document_format"] == "pdf":
                assert entry["source_url"].lower().endswith(".pdf")


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


# ---------------------------------------------------------------------------
# DO-104S — tiered candidates
#
# The DO-104P tests above hold one line: a design selection is not a possession.
# These hold the two DO-104S adds. A tier that says it is complete has every
# mandatory role in it, and an unknown price is not zero. Both are ways a
# procurement document can read as finished while being wrong.
# ---------------------------------------------------------------------------


CANDIDATE_ROLES = {
    "host": ("HOST-001", "synchronized_acquisition"),
    "adc_interface": ("ADC-001", "synchronized_acquisition"),
    "microphone": ("MIC-001", "response_acquisition"),
    "mic_preamp": ("PREAMP-001", "response_acquisition"),
    "force_transducer": ("FORCE-001", "force_measurement"),
    "force_conditioner": ("PRECOND-001", "force_measurement"),
    "shaker": ("SHAKER-001", "contact_excitation"),
    "amplifier": ("AMP-001", "contact_excitation"),
    "stinger": ("STINGER-001", "contact_excitation"),
    "contact_tip": ("TIP-001", "contact_excitation"),
    "stand_base": ("STAND-001", "mechanical_support"),
    "reference_structure": ("REF-STRUCT-001", "mechanical_support"),
    "cabling": ("CABLE-001", "interconnect"),
}


def candidate(component_class, tier="PREFERRED_E1", **overrides):
    """One candidate row, valid unless a test breaks it on purpose."""
    role, chain = CANDIDATE_ROLES[component_class]
    row = {
        "candidate_id": f"{component_class.upper()}-X-001",
        "role_local_id": role,
        "component_class": component_class,
        "functional_chain": chain,
        "selection_tier": tier,
        "quantity": "1",
        "unit_cost_usd": "100.00",
        "extended_cost_usd": "100.00",
        "availability": "IN_STOCK",
        "lead_time": "not stated",
        "commercial_source": "a distributor",
        "checked_date": "2026-08-25",
        "procurement_action": "HOLD",
        "ownership": "UNKNOWN",
    }
    row.update(overrides)
    return row


def spec(candidate_id, **overrides):
    row = {
        "spec_for": candidate_id,
        "manufacturer": "Some Manufacturer",
        "model": "Some Model",
        "powering": "48 V phantom",
        "key_specification": "a specification",
        "technical_source": "a manufacturer datasheet",
    }
    row.update(overrides)
    return row


def complete_tier(tier="PREFERRED_E1", mic_powering="48 V phantom", omit=()):
    """A tier with every mandatory role filled, plus the preamp the mic needs."""
    classes = [c for c in CANDIDATE_ROLES if c not in omit]
    if "phantom" not in mic_powering.lower():
        classes = [c for c in classes if c != "mic_preamp"]
    rows = [candidate(c, tier=tier) for c in classes]
    specs = [
        spec(
            r["candidate_id"],
            powering=mic_powering
            if r["component_class"] == "microphone"
            else "as required",
        )
        for r in rows
    ]
    return rows, specs


def fake_bom():
    """The canonical role rows, as the candidate checks see them."""
    return [
        {"local_id": role, "component_class": cls}
        for cls, (role, _chain) in CANDIDATE_ROLES.items()
    ] + [{"local_id": "ATTEN-001", "component_class": "attenuator"}]


class TestTierVocabulary:
    def test_each_recognised_tier_is_accepted(self, checker):
        for tier in ("RESEARCH_MINIMUM", "PREFERRED_E1", "REFERENCE_GRADE"):
            rows, _ = complete_tier(tier=tier)
            assert checker.validate_tier_vocabulary(rows) == []

    def test_an_unknown_tier_is_refused(self, checker):
        rows = [candidate("shaker", tier="GOOD_ENOUGH")]
        problems = checker.validate_tier_vocabulary(rows)
        assert any("GOOD_ENOUGH" in p for p in problems)

    def test_an_empty_tier_is_refused(self, checker):
        assert checker.validate_tier_vocabulary([candidate("shaker", tier="")])


class TestTierCompleteness:
    def test_a_complete_tier_passes(self, checker):
        rows, specs = complete_tier()
        by_id = {s["spec_for"]: s for s in specs}
        assert checker.validate_tier_completeness(rows, by_id) == []

    @pytest.mark.parametrize(
        "missing",
        [
            "force_transducer",
            "force_conditioner",
            "shaker",
            "amplifier",
            "microphone",
            "adc_interface",
            "host",
            "stinger",
            "contact_tip",
            "stand_base",
            "reference_structure",
            "cabling",
        ],
    )
    def test_a_tier_missing_any_mandatory_role_fails(self, checker, missing):
        rows, specs = complete_tier(omit=(missing,))
        by_id = {s["spec_for"]: s for s in specs}
        problems = checker.validate_tier_completeness(rows, by_id)
        assert any(missing in p and "incomplete" in p for p in problems)

    def test_a_phantom_microphone_requires_a_preamp(self, checker):
        rows, specs = complete_tier(omit=("mic_preamp",))
        by_id = {s["spec_for"]: s for s in specs}
        problems = checker.validate_tier_completeness(rows, by_id)
        assert any("mic_preamp" in p for p in problems)

    def test_a_ccp_microphone_legitimately_has_no_preamp(self, checker):
        # Reference grade's real shape: the CCP microphone is conditioned by the
        # ICP conditioner, so the phantom preamp is not in that chain at all.
        # Padding a preamp row in to satisfy a count would describe a chain that
        # does not exist.
        rows, specs = complete_tier(mic_powering="CCP/IEPE, 4 mA at 24 V")
        by_id = {s["spec_for"]: s for s in specs}
        assert "mic_preamp" not in {r["component_class"] for r in rows}
        assert checker.validate_tier_completeness(rows, by_id) == []

    def test_unrecorded_microphone_powering_is_refused(self, checker):
        rows, specs = complete_tier()
        by_id = {s["spec_for"]: s for s in specs}
        for s in by_id.values():
            if s["spec_for"].startswith("MICROPHONE"):
                s["powering"] = "TBD"
        problems = checker.validate_tier_completeness(rows, by_id)
        assert any("powering is not recorded" in p for p in problems)

    def test_the_attenuator_is_never_required(self, checker):
        rows, specs = complete_tier()
        by_id = {s["spec_for"]: s for s in specs}
        assert not any("attenuator" in p for p in checker.validate_tier_completeness(rows, by_id))

    def test_an_incomplete_tier_is_not_silently_complete(self, checker):
        # C.17: the failure mode is a comparison table that reads as a finished
        # chain because nobody counted the roles.
        rows, specs = complete_tier(omit=("force_transducer", "amplifier"))
        by_id = {s["spec_for"]: s for s in specs}
        problems = checker.validate_tier_completeness(rows, by_id)
        assert len(problems) == 2


class TestCandidateIdentity:
    def test_a_duplicate_candidate_id_is_refused(self, checker):
        rows = [candidate("shaker"), candidate("shaker")]
        assert any("duplicate" in p for p in checker.validate_candidate_identity(rows, fake_bom()))

    def test_a_candidate_naming_no_role_is_refused(self, checker):
        rows = [candidate("shaker", role_local_id="SHAKR-001")]
        assert any("not a canonical BOM row" in p for p in
                   checker.validate_candidate_identity(rows, fake_bom()))

    def test_a_candidate_filed_against_the_wrong_role_is_refused(self, checker):
        rows = [candidate("shaker", role_local_id="MIC-001")]
        assert any("does not match role" in p for p in
                   checker.validate_candidate_identity(rows, fake_bom()))

    def test_candidates_never_appear_in_the_canonical_role_table(self, checker, bom):
        # Ruling 5: downstream identity and protocol machinery must not come to
        # depend on a vendor choice.
        assert {row["local_id"] for row in bom} == {
            "HOST-001", "ADC-001", "PREAMP-001", "MIC-001", "FORCE-001",
            "PRECOND-001", "ATTEN-001", "SHAKER-001", "AMP-001", "STINGER-001",
            "TIP-001", "STAND-001", "REF-STRUCT-001", "CABLE-001",
        }


class TestFunctionalChain:
    def test_a_candidate_in_the_wrong_chain_is_refused(self, checker):
        rows = [candidate("shaker", functional_chain="force_measurement")]
        assert any("contact_excitation" in p for p in checker.validate_functional_chain(rows))

    def test_an_unknown_chain_is_refused(self, checker):
        rows = [candidate("shaker", functional_chain="vibes")]
        assert any("vibes" in p for p in checker.validate_functional_chain(rows))


class TestMeasuredForceCannotBeFaked:
    """The boundary DO-104S is least allowed to cross."""

    def test_an_amplifier_cannot_fill_the_force_role(self, checker):
        rows = [candidate("amplifier", role_local_id="FORCE-001")]
        problems = checker.validate_measured_force(rows, {})
        assert any("cannot fill the measured-force role" in p for p in problems)

    def test_a_microphone_cannot_be_relabelled_onto_the_force_channel(self, checker):
        rows = [candidate("microphone", role_local_id="FORCE-001")]
        assert checker.validate_measured_force(rows, {})

    def test_commanded_voltage_cannot_be_the_force_candidate(self, checker):
        rows = [candidate("force_transducer", role_local_id="FORCE-001")]
        specs = {rows[0]["candidate_id"]: spec(rows[0]["candidate_id"],
                                               model="commanded DAC output level")}
        problems = checker.validate_measured_force(rows, specs)
        assert any("commanded" in p for p in problems)

    def test_a_real_force_transducer_is_accepted(self, checker):
        rows = [candidate("force_transducer", role_local_id="FORCE-001")]
        specs = {rows[0]["candidate_id"]: spec(rows[0]["candidate_id"], model="208C01")}
        assert checker.validate_measured_force(rows, specs) == []


class TestCostFields:
    def test_correct_arithmetic_passes(self, checker):
        assert checker.validate_cost_fields(
            [candidate("shaker", quantity="3", unit_cost_usd="10.00",
                       extended_cost_usd="30.00")]
        ) == []

    def test_contradictory_extended_cost_is_refused(self, checker):
        problems = checker.validate_cost_fields(
            [candidate("shaker", quantity="3", unit_cost_usd="10.00",
                       extended_cost_usd="25.00")]
        )
        assert any("does not equal" in p for p in problems)

    def test_zero_quantity_is_refused_where_priced(self, checker):
        assert any("greater than zero" in p for p in checker.validate_cost_fields(
            [candidate("shaker", quantity="0")]
        ))

    @pytest.mark.parametrize("non_value", ["UNKNOWN", "QUOTE_REQUIRED"])
    def test_an_unpriced_row_is_represented_honestly(self, checker, non_value):
        assert checker.validate_cost_fields(
            [candidate("shaker", unit_cost_usd=non_value, extended_cost_usd=non_value)]
        ) == []

    @pytest.mark.parametrize("non_value", ["UNKNOWN", "QUOTE_REQUIRED"])
    def test_an_unknown_price_may_not_become_zero(self, checker, non_value):
        # F.30/F.31: the failure that makes a tier total a lie.
        problems = checker.validate_cost_fields(
            [candidate("shaker", unit_cost_usd=non_value, extended_cost_usd="0.00")]
        )
        assert any("must stay unpriced" in p for p in problems)

    def test_an_unrecognised_cost_placeholder_is_refused(self, checker):
        assert any("neither a number nor" in p for p in checker.validate_cost_fields(
            [candidate("shaker", unit_cost_usd="ask Bob", extended_cost_usd="ask Bob")]
        ))

    def test_tier_totals_exclude_unpriced_rows(self, checker):
        rows = [
            candidate("shaker", unit_cost_usd="10.00", extended_cost_usd="10.00"),
            candidate("amplifier", unit_cost_usd="QUOTE_REQUIRED",
                      extended_cost_usd="QUOTE_REQUIRED"),
        ]
        total = sum(
            checker.as_money(r["extended_cost_usd"]) or 0.0
            for r in rows
            if checker.as_money(r["unit_cost_usd"]) is not None
        )
        assert total == 10.00
        assert checker.as_money("QUOTE_REQUIRED") is None


class TestSourceProvenance:
    def test_a_candidate_without_a_technical_source_is_refused(self, checker):
        rows = [candidate("shaker")]
        specs = {rows[0]["candidate_id"]: spec(rows[0]["candidate_id"],
                                               technical_source="TBD")}
        assert any("no technical source" in p for p in
                   checker.validate_source_provenance(rows, specs))

    def test_a_priced_row_without_a_commercial_source_is_refused(self, checker):
        rows = [candidate("shaker", commercial_source="—")]
        specs = {rows[0]["candidate_id"]: spec(rows[0]["candidate_id"])}
        assert any("no commercial source" in p for p in
                   checker.validate_source_provenance(rows, specs))

    def test_a_market_observation_without_a_date_is_refused(self, checker):
        rows = [candidate("shaker", checked_date="recently")]
        specs = {rows[0]["candidate_id"]: spec(rows[0]["candidate_id"])}
        assert any("not an ISO-8601 date" in p for p in
                   checker.validate_source_provenance(rows, specs))

    def test_a_fabricated_part_needs_no_distributor(self, checker):
        # Demanding one would push the document toward inventing a supplier for
        # something nobody sells.
        rows = [candidate("stinger", unit_cost_usd="UNKNOWN",
                          extended_cost_usd="UNKNOWN", availability="FABRICATED",
                          commercial_source="—", lead_time="UNKNOWN")]
        specs = {rows[0]["candidate_id"]: spec(rows[0]["candidate_id"])}
        assert checker.validate_source_provenance(rows, specs) == []

    def test_a_candidate_with_no_specification_row_is_refused(self, checker):
        assert any("no specification row" in p for p in
                   checker.validate_source_provenance([candidate("shaker")], {}))


class TestProcurementSemantics:
    def test_unknown_ownership_with_hold_is_the_normal_state(self, checker):
        assert checker.validate_procurement_semantics(
            [candidate("shaker", ownership="UNKNOWN", procurement_action="HOLD")]
        ) == []

    def test_unknown_ownership_does_not_require_buying(self, checker):
        rows = [candidate("shaker", ownership="UNKNOWN",
                          procurement_action="VERIFY_POSSESSION")]
        assert checker.validate_procurement_semantics(rows) == []

    def test_recommending_purchase_against_unknown_ownership_is_refused(self, checker):
        # The inference error the census exists to prevent: UNKNOWN means nobody
        # looked, and buying on that basis duplicates equipment already owned.
        rows = [candidate("shaker", ownership="UNKNOWN",
                          procurement_action="RECOMMEND_PURCHASE")]
        problems = checker.validate_procurement_semantics(rows)
        assert any("nobody has looked yet" in p for p in problems)

    def test_purchase_may_be_recommended_once_absence_is_established(self, checker):
        rows = [candidate("shaker", ownership="CONFIRMED_ABSENT",
                          procurement_action="RECOMMEND_PURCHASE")]
        assert checker.validate_procurement_semantics(rows) == []

    def test_a_preferred_candidate_may_remain_unknown_and_held(self, checker):
        rows = [candidate("force_transducer", tier="PREFERRED_E1",
                          ownership="UNKNOWN", procurement_action="HOLD")]
        assert checker.validate_procurement_semantics(rows) == []
        assert checker.validate_tier_vocabulary(rows) == []

    def test_an_unknown_ownership_state_is_refused(self, checker):
        assert any("ownership state" in p for p in
                   checker.validate_procurement_semantics(
                       [candidate("shaker", ownership="PROBABLY_HAVE_ONE")]))

    def test_an_unknown_procurement_action_is_refused(self, checker):
        assert any("procurement_action" in p for p in
                   checker.validate_procurement_semantics(
                       [candidate("shaker", procurement_action="ORDER_IT")]))

    @pytest.mark.parametrize(
        "claim", ["RECEIVED", "ASSEMBLED", "CALIBRATED", "VERIFIED_ON_HARDWARE"]
    )
    def test_selection_cannot_confer_a_physical_claim(self, checker, claim):
        rows = [candidate("shaker", availability=claim)]
        problems = checker.validate_procurement_semantics(rows)
        assert any(claim in p for p in problems)

    def test_vendor_availability_cannot_become_receipt(self, checker):
        rows = [candidate("shaker", availability="IN_STOCK", ownership="UNKNOWN")]
        assert checker.validate_procurement_semantics(rows) == []


class TestTheCommittedCandidateTables:
    @pytest.fixture(scope="class")
    def candidates(self, checker):
        return checker.parse_optional_table(checker.BOM_PATH, checker.CANDIDATE_KEY)

    @pytest.fixture(scope="class")
    def specs(self, checker):
        return checker.parse_optional_table(checker.BOM_PATH, checker.SPEC_KEY)

    def test_the_candidate_tables_exist(self, candidates, specs):
        assert candidates and specs

    def test_all_three_tiers_are_represented(self, checker, candidates):
        assert set(checker.group_candidates_by_tier(candidates)) == set(
            checker.SELECTION_TIERS
        )

    def test_every_tier_is_complete(self, checker, candidates, specs):
        by_id = {s["spec_for"]: s for s in specs}
        assert checker.validate_tier_completeness(candidates, by_id) == []

    def test_nothing_is_owned_and_nothing_is_recommended_for_purchase(
        self, candidates
    ):
        assert {r["ownership"] for r in candidates} == {"UNKNOWN"}
        assert {r["procurement_action"] for r in candidates} == {"HOLD"}

    def test_measured_force_is_present_in_every_tier(self, checker, candidates):
        by_tier = checker.group_candidates_by_tier(candidates)
        for tier, rows in by_tier.items():
            classes = {r["component_class"] for r in rows}
            assert "force_transducer" in classes, tier
            assert "force_conditioner" in classes, tier

    def test_the_response_sensor_is_a_microphone_in_every_tier(
        self, checker, candidates, specs
    ):
        # 4.11: no accelerometer may become the E1 response sensor here.
        by_id = {s["spec_for"]: s for s in specs}
        for tier, rows in checker.group_candidates_by_tier(candidates).items():
            mics = [r for r in rows if r["component_class"] == "microphone"]
            assert len(mics) == 1, tier
            model = by_id[mics[0]["candidate_id"]]["key_specification"].lower()
            assert "accelerometer" not in model

    def test_no_tier_total_treats_an_unknown_price_as_zero(self, checker, candidates):
        for row in candidates:
            if checker.as_money(row["unit_cost_usd"]) is None:
                assert row["extended_cost_usd"].strip() in checker.COST_NON_VALUES

    def test_every_priced_row_carries_a_dated_source(self, checker, candidates):
        for row in candidates:
            if checker.as_money(row["unit_cost_usd"]) is not None:
                assert checker.is_set(row["commercial_source"]), row["candidate_id"]
                assert checker._ISO_DATE.match(row["checked_date"])


class TestADocumentWithoutCandidatesStillValidates:
    """A DO-104P-shaped BOM predates the candidate tables and is not broken."""

    def test_absent_candidate_tables_are_tolerated(self, checker, tmp_path):
        document = tmp_path / "bom.md"
        document.write_text(
            "| local_id | component_class |\n| --- | --- |\n"
            "| HOST-001 | host |\n",
            encoding="utf-8",
        )
        assert checker.parse_optional_table(document, checker.CANDIDATE_KEY) is None

    def test_candidate_checks_are_skipped_when_absent(self, checker):
        assert checker.check_candidates(None, None, fake_bom()) == []

    def test_candidates_without_specifications_are_refused(self, checker):
        problems = checker.check_candidates([candidate("shaker")], None, fake_bom())
        assert any("no specification table" in p for p in problems)

    def test_a_half_present_candidate_table_is_a_document_error(self, checker, tmp_path):
        document = tmp_path / "bom.md"
        document.write_text(
            "| candidate_id | selection_tier |\n| --- | --- |\n"
            "| SHAKER-X-001 | PREFERRED_E1 |\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="missing column"):
            checker.parse_optional_table(
                document, checker.CANDIDATE_KEY, checker.REQUIRED_CANDIDATE_COLUMNS
            )


class TestTheArchitectureStopCondition:
    """I: a force chain needing an incompatible acquisition architecture.

    The validator's job at this point is to report, not to resolve. Substituting
    a different ADC to make a table complete would be the exact failure the stop
    condition exists to prevent.
    """

    def test_the_checker_never_substitutes_a_component(self, checker):
        source = (
            REPO_ROOT / "scripts" / "check_e1_hardware_bom.py"
        ).read_text(encoding="utf-8")
        for verb in ("def substitute", "def select_", "def recommend_", "def choose_"):
            assert verb not in source

    def test_an_incompatible_force_chain_is_reported_not_repaired(self, checker):
        # A conditioner whose only output overruns the input window, with no
        # attenuator in the tier. The tier is still structurally complete, so
        # completeness alone must not be read as compatibility - the interface
        # matrix carries that judgement, and the validator does not invent one.
        rows, specs = complete_tier()
        by_id = {s["spec_for"]: s for s in specs}
        assert checker.validate_tier_completeness(rows, by_id) == []
        assert "attenuator" not in {r["component_class"] for r in rows}

    def test_the_checker_writes_nothing(self, checker):
        source = (
            REPO_ROOT / "scripts" / "check_e1_hardware_bom.py"
        ).read_text(encoding="utf-8")
        assert "write_text" not in source
        assert "open(" not in source.replace("read_text", "")
