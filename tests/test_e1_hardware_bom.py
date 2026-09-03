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
        assert not any(
            "attenuator" in p for p in checker.validate_tier_completeness(rows, by_id)
        )

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
        assert any(
            "duplicate" in p
            for p in checker.validate_candidate_identity(rows, fake_bom())
        )

    def test_a_candidate_naming_no_role_is_refused(self, checker):
        rows = [candidate("shaker", role_local_id="SHAKR-001")]
        assert any(
            "not a canonical BOM row" in p
            for p in checker.validate_candidate_identity(rows, fake_bom())
        )

    def test_a_candidate_filed_against_the_wrong_role_is_refused(self, checker):
        rows = [candidate("shaker", role_local_id="MIC-001")]
        assert any(
            "does not match role" in p
            for p in checker.validate_candidate_identity(rows, fake_bom())
        )

    def test_candidates_never_appear_in_the_canonical_role_table(self, checker, bom):
        # Ruling 5: downstream identity and protocol machinery must not come to
        # depend on a vendor choice.
        assert {row["local_id"] for row in bom} == {
            "HOST-001",
            "ADC-001",
            "PREAMP-001",
            "MIC-001",
            "FORCE-001",
            "PRECOND-001",
            "ATTEN-001",
            "SHAKER-001",
            "AMP-001",
            "STINGER-001",
            "TIP-001",
            "STAND-001",
            "REF-STRUCT-001",
            "CABLE-001",
        }


class TestFunctionalChain:
    def test_a_candidate_in_the_wrong_chain_is_refused(self, checker):
        rows = [candidate("shaker", functional_chain="force_measurement")]
        assert any(
            "contact_excitation" in p for p in checker.validate_functional_chain(rows)
        )

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
        specs = {
            rows[0]["candidate_id"]: spec(
                rows[0]["candidate_id"], model="commanded DAC output level"
            )
        }
        problems = checker.validate_measured_force(rows, specs)
        assert any("commanded" in p for p in problems)

    def test_a_real_force_transducer_is_accepted(self, checker):
        rows = [candidate("force_transducer", role_local_id="FORCE-001")]
        specs = {rows[0]["candidate_id"]: spec(rows[0]["candidate_id"], model="208C01")}
        assert checker.validate_measured_force(rows, specs) == []


class TestCostFields:
    def test_correct_arithmetic_passes(self, checker):
        assert (
            checker.validate_cost_fields(
                [
                    candidate(
                        "shaker",
                        quantity="3",
                        unit_cost_usd="10.00",
                        extended_cost_usd="30.00",
                    )
                ]
            )
            == []
        )

    def test_contradictory_extended_cost_is_refused(self, checker):
        problems = checker.validate_cost_fields(
            [
                candidate(
                    "shaker",
                    quantity="3",
                    unit_cost_usd="10.00",
                    extended_cost_usd="25.00",
                )
            ]
        )
        assert any("does not equal" in p for p in problems)

    def test_zero_quantity_is_refused_where_priced(self, checker):
        assert any(
            "greater than zero" in p
            for p in checker.validate_cost_fields([candidate("shaker", quantity="0")])
        )

    @pytest.mark.parametrize("non_value", ["UNKNOWN", "QUOTE_REQUIRED"])
    def test_an_unpriced_row_is_represented_honestly(self, checker, non_value):
        assert (
            checker.validate_cost_fields(
                [
                    candidate(
                        "shaker", unit_cost_usd=non_value, extended_cost_usd=non_value
                    )
                ]
            )
            == []
        )

    @pytest.mark.parametrize("non_value", ["UNKNOWN", "QUOTE_REQUIRED"])
    def test_an_unknown_price_may_not_become_zero(self, checker, non_value):
        # F.30/F.31: the failure that makes a tier total a lie.
        problems = checker.validate_cost_fields(
            [candidate("shaker", unit_cost_usd=non_value, extended_cost_usd="0.00")]
        )
        assert any("must stay unpriced" in p for p in problems)

    def test_an_unrecognised_cost_placeholder_is_refused(self, checker):
        assert any(
            "neither a number nor" in p
            for p in checker.validate_cost_fields(
                [
                    candidate(
                        "shaker", unit_cost_usd="ask Bob", extended_cost_usd="ask Bob"
                    )
                ]
            )
        )

    def test_tier_totals_exclude_unpriced_rows(self, checker):
        rows = [
            candidate("shaker", unit_cost_usd="10.00", extended_cost_usd="10.00"),
            candidate(
                "amplifier",
                unit_cost_usd="QUOTE_REQUIRED",
                extended_cost_usd="QUOTE_REQUIRED",
            ),
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
        specs = {
            rows[0]["candidate_id"]: spec(
                rows[0]["candidate_id"], technical_source="TBD"
            )
        }
        assert any(
            "no technical source" in p
            for p in checker.validate_source_provenance(rows, specs)
        )

    def test_a_priced_row_without_a_commercial_source_is_refused(self, checker):
        rows = [candidate("shaker", commercial_source="—")]
        specs = {rows[0]["candidate_id"]: spec(rows[0]["candidate_id"])}
        assert any(
            "no commercial source" in p
            for p in checker.validate_source_provenance(rows, specs)
        )

    def test_a_market_observation_without_a_date_is_refused(self, checker):
        rows = [candidate("shaker", checked_date="recently")]
        specs = {rows[0]["candidate_id"]: spec(rows[0]["candidate_id"])}
        assert any(
            "not an ISO-8601 date" in p
            for p in checker.validate_source_provenance(rows, specs)
        )

    def test_a_fabricated_part_needs_no_distributor(self, checker):
        # Demanding one would push the document toward inventing a supplier for
        # something nobody sells.
        rows = [
            candidate(
                "stinger",
                unit_cost_usd="UNKNOWN",
                extended_cost_usd="UNKNOWN",
                availability="FABRICATED",
                commercial_source="—",
                lead_time="UNKNOWN",
            )
        ]
        specs = {rows[0]["candidate_id"]: spec(rows[0]["candidate_id"])}
        assert checker.validate_source_provenance(rows, specs) == []

    def test_a_candidate_with_no_specification_row_is_refused(self, checker):
        assert any(
            "no specification row" in p
            for p in checker.validate_source_provenance([candidate("shaker")], {})
        )


class TestProcurementSemantics:
    def test_unknown_ownership_with_hold_is_the_normal_state(self, checker):
        assert (
            checker.validate_procurement_semantics(
                [candidate("shaker", ownership="UNKNOWN", procurement_action="HOLD")]
            )
            == []
        )

    def test_unknown_ownership_does_not_require_buying(self, checker):
        rows = [
            candidate(
                "shaker", ownership="UNKNOWN", procurement_action="VERIFY_POSSESSION"
            )
        ]
        assert checker.validate_procurement_semantics(rows) == []

    def test_recommending_purchase_against_unknown_ownership_is_refused(self, checker):
        # The inference error the census exists to prevent: UNKNOWN means nobody
        # looked, and buying on that basis duplicates equipment already owned.
        rows = [
            candidate(
                "shaker", ownership="UNKNOWN", procurement_action="RECOMMEND_PURCHASE"
            )
        ]
        problems = checker.validate_procurement_semantics(rows)
        assert any("nobody has looked yet" in p for p in problems)

    def test_purchase_may_be_recommended_once_absence_is_established(self, checker):
        rows = [
            candidate(
                "shaker",
                ownership="CONFIRMED_ABSENT",
                procurement_action="RECOMMEND_PURCHASE",
            )
        ]
        assert checker.validate_procurement_semantics(rows) == []

    def test_a_preferred_candidate_may_remain_unknown_and_held(self, checker):
        rows = [
            candidate(
                "force_transducer",
                tier="PREFERRED_E1",
                ownership="UNKNOWN",
                procurement_action="HOLD",
            )
        ]
        assert checker.validate_procurement_semantics(rows) == []
        assert checker.validate_tier_vocabulary(rows) == []

    def test_an_unknown_ownership_state_is_refused(self, checker):
        assert any(
            "ownership state" in p
            for p in checker.validate_procurement_semantics(
                [candidate("shaker", ownership="PROBABLY_HAVE_ONE")]
            )
        )

    def test_an_unknown_procurement_action_is_refused(self, checker):
        assert any(
            "procurement_action" in p
            for p in checker.validate_procurement_semantics(
                [candidate("shaker", procurement_action="ORDER_IT")]
            )
        )

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

    def test_every_declared_tier_is_represented(self, checker, candidates):
        assert set(checker.group_candidates_by_tier(candidates)) == set(
            checker.SELECTION_TIERS
        )

    def test_every_tier_is_complete(self, checker, candidates, specs):
        by_id = {s["spec_for"]: s for s in specs}
        assert checker.validate_tier_completeness(candidates, by_id) == []

    def test_only_the_host_is_owned_and_nothing_is_bought(self, candidates):
        # Census pass 2 found one owned role. Everything else stays absent, and
        # no row anywhere recommends a purchase - the census made
        # RECOMMEND_PURCHASE legal without performing it.
        owned = {
            r["role_local_id"]
            for r in candidates
            if r["ownership"] == "CONFIRMED_PRESENT"
        }
        assert owned == {"HOST-001"}
        assert {r["ownership"] for r in candidates} == {
            "CONFIRMED_PRESENT",
            "CONFIRMED_ABSENT",
        }
        assert "RECOMMEND_PURCHASE" not in {r["procurement_action"] for r in candidates}
        assert {r["procurement_action"] for r in candidates} == {"HOLD", "USE_OWNED"}

    def test_measured_force_is_present_in_every_whole_chain_tier(
        self, checker, candidates
    ):
        by_tier = checker.group_candidates_by_tier(candidates)
        for tier, rows in by_tier.items():
            if tier in checker.TIER_CHAIN_SCOPE:
                continue
            classes = {r["component_class"] for r in rows}
            assert "force_transducer" in classes, tier
            assert "force_conditioner" in classes, tier

    def test_the_response_sensor_is_a_microphone_in_every_whole_chain_tier(
        self, checker, candidates, specs
    ):
        # 4.11: no accelerometer may become the E1 response sensor here.
        by_id = {s["spec_for"]: s for s in specs}
        for tier, rows in checker.group_candidates_by_tier(candidates).items():
            if tier in checker.TIER_CHAIN_SCOPE:
                continue
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
            "| local_id | component_class |\n| --- | --- |\n| HOST-001 | host |\n",
            encoding="utf-8",
        )
        assert checker.parse_optional_table(document, checker.CANDIDATE_KEY) is None

    def test_candidate_checks_are_skipped_when_absent(self, checker):
        assert checker.check_candidates(None, None, fake_bom()) == []

    def test_candidates_without_specifications_are_refused(self, checker):
        problems = checker.check_candidates([candidate("shaker")], None, fake_bom())
        assert any("no specification table" in p for p in problems)

    def test_a_half_present_candidate_table_is_a_document_error(
        self, checker, tmp_path
    ):
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
        source = (REPO_ROOT / "scripts" / "check_e1_hardware_bom.py").read_text(
            encoding="utf-8"
        )
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
        source = (REPO_ROOT / "scripts" / "check_e1_hardware_bom.py").read_text(
            encoding="utf-8"
        )
        assert "write_text" not in source
        assert "open(" not in source.replace("read_text", "")


class TestDocumentationAgreesWithItself:
    """The documents are read by a human making a spending decision.

    A recommendation that names one product in the rationale and another in the
    BOM is worse than no recommendation, because the disagreement is invisible
    until someone has bought the wrong thing.
    """

    @pytest.fixture(scope="class")
    def docs(self):
        return {
            name: (HARDWARE / name).read_text(encoding="utf-8")
            for name in (
                "TTP_E1_HARDWARE_BOM.md",
                "TTP_E1_HARDWARE_SELECTION_RATIONALE.md",
                "TTP_E1_PROCUREMENT_STATUS.md",
                "TTP_E1_INTERFACE_MATRIX.md",
                "TTP_HARDWARE_STACK.md",
            )
        }

    @pytest.fixture(scope="class")
    def preferred_models(self, checker):
        specs = checker.parse_optional_table(checker.BOM_PATH, checker.SPEC_KEY)
        candidates = checker.parse_optional_table(
            checker.BOM_PATH, checker.CANDIDATE_KEY
        )
        preferred = {
            row["candidate_id"]
            for row in candidates
            if row["selection_tier"] == "PREFERRED_E1"
        }
        return {
            s["model"]
            for s in specs
            if s["spec_for"] in preferred
            and s["manufacturer"].lower()
            not in ("fabricated", "assorted", "custom build")
        }

    def test_the_rationale_names_the_same_products_as_the_bom(
        self, docs, preferred_models
    ):
        rationale = docs["TTP_E1_HARDWARE_SELECTION_RATIONALE.md"]
        for model in preferred_models:
            assert model in rationale, (
                f"{model} is preferred in the BOM but absent from the rationale"
            )

    def test_the_procurement_recommendation_names_the_same_products(
        self, docs, preferred_models
    ):
        procurement = docs["TTP_E1_PROCUREMENT_STATUS.md"]
        for model in preferred_models:
            assert model in procurement, (
                f"{model} is preferred but absent from the procurement recommendation"
            )

    def test_the_interface_matrix_covers_every_preferred_chain(self, checker, docs):
        candidates = checker.parse_optional_table(
            checker.BOM_PATH, checker.CANDIDATE_KEY
        )
        chains = {
            row["functional_chain"]
            for row in candidates
            if row["selection_tier"] == "PREFERRED_E1"
        }
        matrix = docs["TTP_E1_INTERFACE_MATRIX.md"].lower()
        # Each chain must be resolved somewhere in the matrix, by the words the
        # matrix actually uses for it.
        words = {
            "force_measurement": "force chain — resolved",
            "contact_excitation": "excitation chain — resolved",
            "response_acquisition": "response chain — resolved",
            "synchronized_acquisition": "synchronization — the determination",
            "mechanical_support": "mechanical — resolved",
            "interconnect": "cabling — enumerated",
        }
        for chain in chains:
            assert words[chain] in matrix, (
                f"{chain} is not resolved in the interface matrix"
            )

    def test_the_ownership_census_and_the_recommendation_agree(self, docs):
        # Both tables in the procurement document carry an Ownership column, and
        # every row of both must agree. If one says a role is absent while the
        # other still says nobody looked, a reader has two answers to the only
        # question that gates a purchase.
        procurement = docs["TTP_E1_PROCUREMENT_STATUS.md"]
        ownership_cells = []
        for line in procurement.splitlines():
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            for cell in cells:
                if cell in ("UNKNOWN", "CONFIRMED_PRESENT", "CONFIRMED_ABSENT"):
                    ownership_cells.append(cell)
        assert ownership_cells, "no ownership cells found — the tables moved"
        # Both tables must show the same one-owned / rest-absent split. If they
        # ever differ, a reader has two answers to "do we have it?"
        assert set(ownership_cells) == {"CONFIRMED_PRESENT", "CONFIRMED_ABSENT"}
        assert ownership_cells.count("CONFIRMED_PRESENT") == 2

    def test_nothing_is_actioned_beyond_hold(self, docs):
        # HOLD is the only action this order may leave behind. RECOMMEND_PURCHASE
        # may appear in the vocabulary table that defines it, but never in a row
        # that assigns it to a component.
        procurement = docs["TTP_E1_PROCUREMENT_STATUS.md"]
        for line in procurement.splitlines():
            if not line.startswith("|") or "RECOMMEND_PURCHASE" not in line:
                continue
            # A definition row names the action and explains it; an assignment
            # row names a component id alongside it.
            assert "-001" not in line, f"a component is actioned for purchase: {line}"

    def test_the_stack_spec_claims_no_e1_validation(self, docs):
        stack = docs["TTP_HARDWARE_STACK.md"]
        assert "Neither 2A nor 2B is validated hardware" in stack
        for claim in ("VERIFIED_ON_HARDWARE", "has been calibrated", "E1 confirmed"):
            assert claim not in stack

    def test_no_document_claims_the_chain_was_measured(self, docs):
        # The gate verdict is a paper compatibility finding. If any document
        # starts describing it as a measurement, that is the failure this whole
        # order is shaped to prevent.
        for name, text in docs.items():
            lowered = text.lower()
            for claim in (
                "measured noise floor of the assembled",
                "e1 has established",
                "verified on hardware",
            ):
                assert claim not in lowered, f"{name} claims {claim!r}"

    def test_the_gate_verdict_is_stated_with_its_limits(self, docs):
        matrix = docs["TTP_E1_INTERFACE_MATRIX.md"]
        assert "Architecture gate — verdict" in matrix
        assert "The gate passes" in matrix
        # and immediately says what passing does not mean
        assert "What passing does not mean" in matrix
        assert "It does not mean the chain works" in matrix


class TestOwnershipBackedActions:
    """Actions asserting possession must be backed by an observation.

    Both directions are guarded, and the second one only became reachable when
    census pass 2 found an owned item: you may not recommend buying what you
    have not established you lack, and you may not plan to use what you do not
    have.
    """

    def test_use_owned_requires_confirmed_present(self, checker):
        rows = [
            candidate(
                "host", ownership="CONFIRMED_ABSENT", procurement_action="USE_OWNED"
            )
        ]
        problems = checker.validate_procurement_semantics(rows)
        assert any("requires CONFIRMED_PRESENT" in p for p in problems)

    def test_use_owned_is_accepted_when_owned(self, checker):
        rows = [
            candidate(
                "host", ownership="CONFIRMED_PRESENT", procurement_action="USE_OWNED"
            )
        ]
        assert checker.validate_procurement_semantics(rows) == []

    def test_no_purchase_required_requires_confirmed_present(self, checker):
        rows = [
            candidate(
                "host", ownership="UNKNOWN", procurement_action="NO_PURCHASE_REQUIRED"
            )
        ]
        assert checker.validate_procurement_semantics(rows)

    def test_recommend_purchase_still_requires_confirmed_absent(self, checker):
        # The original rule survives the vocabulary extension.
        rows = [
            candidate(
                "shaker",
                ownership="CONFIRMED_PRESENT",
                procurement_action="RECOMMEND_PURCHASE",
            )
        ]
        problems = checker.validate_procurement_semantics(rows)
        assert any("requires CONFIRMED_ABSENT" in p for p in problems)

    def test_owning_something_does_not_action_it(self, checker):
        # OWNED does not imply any procurement action at all. HOLD stays legal.
        rows = [
            candidate("host", ownership="CONFIRMED_PRESENT", procurement_action="HOLD")
        ]
        assert checker.validate_procurement_semantics(rows) == []

    def test_owning_something_does_not_select_it(self, checker):
        # The Pi is owned and the human ruling is SELECTION_DEFERRED. Possession
        # must not have promoted the canonical role row.
        bom = checker.parse_table(checker.BOM_PATH, "local_id")
        host = next(r for r in bom if r["local_id"] == "HOST-001")
        assert host["status"] == "SELECTED"  # design selection, unchanged
        assert checker.rung(host["status"]) < checker.rung("ORDERED")


# ---------------------------------------------------------------------------
# DO-108P — the commercial excitation tier
#
# DO-104S added tiers that are each a complete rig. DO-108P adds one that is
# deliberately not: the excitation stage of a commercial TTP, scoped to the
# contact-excitation chain and carrying no force channel at all.
#
# Two failures are worth holding here. A scoped tier could be read as an
# incomplete rig and quietly "finished" by someone adding a force transducer to
# it — which would invent a measurement the commercial path does not make. And a
# manufacturer value could drift from the document it came from, which is how a
# requirement ends up sized against a number nobody published.
# ---------------------------------------------------------------------------


class TestScopedTiers:
    def test_a_whole_chain_tier_owes_every_mandatory_role(self, checker):
        assert checker.mandatory_roles_for("PREFERRED_E1") == (
            checker.MANDATORY_ROLE_CLASSES
        )

    def test_a_scoped_tier_owes_only_its_own_chains_roles(self, checker):
        owed = checker.mandatory_roles_for("COMMERCIAL_PROTOTYPE")
        assert set(owed) == {"shaker", "amplifier", "stinger", "contact_tip"}
        # The point of the exemption: it does not owe a force chain.
        assert "force_transducer" not in owed
        assert "force_conditioner" not in owed

    def test_a_scoped_tier_still_fails_if_it_drops_its_own_role(self, checker):
        rows = [
            candidate(cls, tier="COMMERCIAL_PROTOTYPE")
            for cls in ("shaker", "stinger", "contact_tip")
        ]
        specs = {r["candidate_id"]: spec(r["candidate_id"]) for r in rows}
        problems = checker.validate_tier_completeness(rows, specs)
        assert any("amplifier" in p and "incomplete" in p for p in problems)

    def test_a_scoped_tier_complete_within_its_scope_passes(self, checker):
        rows = [
            candidate(cls, tier="COMMERCIAL_PROTOTYPE")
            for cls in ("shaker", "amplifier", "stinger", "contact_tip")
        ]
        specs = {r["candidate_id"]: spec(r["candidate_id"]) for r in rows}
        assert checker.validate_tier_completeness(rows, specs) == []

    def test_a_force_transducer_cannot_be_filed_into_the_commercial_tier(self, checker):
        # The failure this rule exists for: the commercial path acquiring a
        # force channel by accretion, so that it reads as a complete rig at a
        # commodity price. Its defining property is that it measures no force.
        rows = [candidate("force_transducer", tier="COMMERCIAL_PROTOTYPE")]
        problems = checker.validate_tier_scope(rows)
        assert any("scoped to contact_excitation" in p for p in problems)

    def test_a_response_candidate_cannot_be_filed_into_the_commercial_tier(
        self, checker
    ):
        rows = [candidate("microphone", tier="COMMERCIAL_PROTOTYPE")]
        assert checker.validate_tier_scope(rows)

    def test_scope_validation_leaves_whole_chain_tiers_alone(self, checker):
        rows, _ = complete_tier(tier="PREFERRED_E1")
        assert checker.validate_tier_scope(rows) == []

    def test_an_excitation_candidate_is_in_scope(self, checker):
        rows = [candidate("shaker", tier="COMMERCIAL_PROTOTYPE")]
        assert checker.validate_tier_scope(rows) == []


class TestTheCommittedCommercialTier:
    @pytest.fixture(scope="class")
    def candidates(self, checker):
        rows = checker.parse_optional_table(checker.BOM_PATH, checker.CANDIDATE_KEY)
        return [r for r in rows if r["selection_tier"] == "COMMERCIAL_PROTOTYPE"]

    @pytest.fixture(scope="class")
    def specs(self, checker):
        rows = checker.parse_optional_table(checker.BOM_PATH, checker.SPEC_KEY)
        return {r["spec_for"]: r for r in rows}

    @pytest.fixture(scope="class")
    def manifest(self):
        return json.loads(
            (HARDWARE / "TTP_E1_DATASHEET_MANIFEST.json").read_text(encoding="utf-8")
        )

    def test_all_three_exciter_candidates_are_registered(self, candidates, specs):
        models = {
            specs[r["candidate_id"]]["model"]
            for r in candidates
            if r["component_class"] == "shaker"
        }
        assert models == {"DAEX25CT-4", "DAEX25FHE-4", "EX 30 S, Art. No. 4532"}

    def test_the_candidates_use_the_existing_role_namespace(self, candidates):
        # Ruling 1: no competing EXC-* authority. Every commercial candidate
        # fills an existing canonical role row.
        assert {r["role_local_id"] for r in candidates} == {
            "SHAKER-001",
            "AMP-001",
            "STINGER-001",
            "TIP-001",
        }

    def test_the_tier_carries_no_force_chain(self, candidates):
        classes = {r["component_class"] for r in candidates}
        assert "force_transducer" not in classes
        assert "force_conditioner" not in classes

    def test_nothing_is_selected_owned_or_bought(self, candidates):
        assert {r["ownership"] for r in candidates} == {"CONFIRMED_ABSENT"}
        assert {r["procurement_action"] for r in candidates} == {"HOLD"}

    def test_the_tier_is_unpriced_rather_than_cheap(self, checker, candidates):
        for row in candidates:
            assert checker.as_money(row["unit_cost_usd"]) is None
            assert row["unit_cost_usd"].strip() in checker.COST_NON_VALUES
            assert row["extended_cost_usd"].strip() == row["unit_cost_usd"].strip()

    @pytest.mark.parametrize(
        "model, values",
        [
            (
                "DAEX25CT-4",
                (
                    "Re 3.6 ohms",
                    "Fs 306 Hz",
                    "Mms 1.29 g",
                    "BL 1.54 Tm",
                    "10 W RMS",
                    "4 ohms nominal",
                ),
            ),
            (
                "DAEX25FHE-4",
                (
                    "Re 4.3 ohms",
                    "Fs 224 Hz",
                    "Mms 1.61 g",
                    "BL 3.63 Tm",
                    "24 W RMS",
                    "4 ohms nominal",
                ),
            ),
        ],
    )
    def test_the_dayton_values_are_the_datasheet_values(self, specs, model, values):
        row = next(s for s in specs.values() if s["model"] == model)
        for value in values:
            assert value in row["key_specification"], f"{model}: {value}"

    def test_the_dayton_panel_response_caveat_survives(self, specs):
        # Both sheets qualify their response curve as a foam-core panel
        # measurement that depends on the driven surface. Dropping that turns a
        # comparison aid into a claim about a soundboard.
        rows = [s for s in specs.values() if s["model"].startswith("DAEX25")]
        assert len(rows) == 2
        for row in rows:
            assert "foam-core" in row["key_specification"]

    def test_the_visaton_gaps_stay_explicit_and_are_never_zero(self, specs):
        row = next(s for s in specs.values() if s["model"].startswith("EX 30 S"))
        assert "not published" in row["key_specification"]
        for absent in ("BL", "Mms", "Fs", "Re", "Qts", "Cms"):
            assert absent in row["key_specification"]
        assert "not derived here" in row["key_specification"]

    def test_the_visaton_load_is_not_rewritten_to_match_the_daytons(self, specs):
        # The candidates genuinely differ: 4 ohm Daytons, an 8 ohm Visaton. The
        # requirement covers both rather than the odd one out being restated.
        row = next(s for s in specs.values() if s["model"].startswith("EX 30 S"))
        assert "8 ohms nominal" in row["key_specification"]

    def test_the_amplifier_is_a_family_not_a_selection(self, specs):
        row = specs["AMP-CP-001"]
        assert "reference family, not a selection" in row["model"]
        assert "TPA3116D2" in row["model"]

    def test_the_amplifier_control_surface_is_recorded(self, specs):
        key = specs["AMP-CP-001"]["key_specification"]
        for feature in ("PLIMIT", "MUTE", "SDZ", "FAULTZ", "4.5-26 V"):
            assert feature in key

    def test_every_manufacturer_candidate_rests_on_a_retrieved_document(
        self, checker, candidates, specs, manifest
    ):
        covered = {
            cid
            for entry in manifest["entries"]
            for cid in entry.get("covers_candidates", []) or []
        }
        for row in candidates:
            cid = row["candidate_id"]
            if specs[cid]["manufacturer"].strip().lower() == "fabricated":
                continue
            assert cid in covered, cid

    def test_those_documents_carry_real_retrieved_digests(self, manifest):
        entries = [
            e
            for e in manifest["entries"]
            if any(
                cid.endswith("-CP-001")
                or cid.endswith("-CP-002")
                or cid.endswith("-CP-003")
                for cid in e.get("covers_candidates", []) or []
            )
        ]
        assert len(entries) == 4
        for entry in entries:
            assert len(entry["sha256"]) == 64
            assert int(entry["byte_length"]) > 0
            assert entry["retrieved_utc"].endswith("Z")
            # Manufacturer-hosted, not a distributor page.
            assert entry["source_url"].startswith("https://")
            assert "parts-express" not in entry["source_url"]

    def test_the_datasheet_checker_would_notice_an_uncovered_candidate(
        self, checker, manifest
    ):
        # Coverage used to be required for the preferred tier only. The
        # commercial tier's numbers are quoted straight into a requirement
        # document, so an uncovered candidate there is the same failure.
        rows = [candidate("shaker", tier="COMMERCIAL_PROTOTYPE")]
        specs = [spec(rows[0]["candidate_id"], manufacturer="Dayton Audio")]
        problems = checker.check_candidate_datasheets({"entries": []}, rows, specs)
        assert any("COMMERCIAL_PROTOTYPE candidate" in p for p in problems)

    def test_a_fabricated_commercial_part_needs_no_datasheet(self, checker):
        rows = [candidate("stinger", tier="COMMERCIAL_PROTOTYPE")]
        specs = [spec(rows[0]["candidate_id"], manufacturer="fabricated")]
        assert checker.check_candidate_datasheets({"entries": []}, rows, specs) == []


# ---------------------------------------------------------------------------
# DO-108P — the commercial excitation documents
#
# The candidate registry above feeds four documents and one gate. What these
# hold is the way a requirements document fills itself in: a TBD_MEASURE quietly
# becoming a number, an enclosure survey reading complete on rows nobody
# measured, a gate opening because the work was ready rather than the evidence -
# and the one that would matter most, a force appearing in a chain that has no
# force channel.
# ---------------------------------------------------------------------------


def flat(text: str) -> str:
    """Collapse whitespace, so a prose assertion survives a line rewrap.

    These documents are hard-wrapped. A sentence assertion that failed because
    the sentence moved across a line boundary would be a test about formatting,
    which is not what any of these are checking.
    """
    return " ".join(text.split())


def amplifier_document(*rows: tuple[str, str]) -> str:
    """An Output range section, for testing what the checker does with it."""
    body = "\n".join(f"| {prop} | {value} |" for prop, value in rows)
    return "\n".join(
        [
            "# Requirements",
            "",
            "## Load compatibility",
            "",
            "| Property | Value |",
            "| --- | --- |",
            "| Nominal load | 4 and 8 ohm |",
            "",
            "## Output range",
            "",
            "| Property | Value |",
            "| --- | --- |",
            body,
            "",
            "## Gain",
            "",
            "nothing here",
        ]
    )


def envelope_document(status: str, *rows: tuple[str, str]) -> str:
    body = "\n".join(
        f"| {name} | {value} | measurement | pending |" for name, value in rows
    )
    return "\n".join(
        [
            f"**survey_status:** `{status}`",
            "",
            "| Parameter | Value | Method | Evidence |",
            "| --- | --- | --- | --- |",
            body,
        ]
    )


class TestTheExcitationDocumentsExist:
    @pytest.mark.parametrize(
        "name",
        [
            "TTP_COMMERCIAL_EXCITATION_ARCHITECTURE.md",
            "TTP_EXCITATION_AMPLIFIER_REQUIREMENTS.md",
            "TTP_EXCITATION_PCB_ENVELOPE.md",
            "TTP_EXCITER_POWER_CHARACTERIZATION_PROTOCOL.md",
        ],
    )
    def test_document_present(self, name):
        assert (HARDWARE / name).exists()

    def test_the_gate_adr_follows_the_repository_convention(self, checker):
        # docs/ADR-NNNN-topic.md, not a new docs/decisions/ directory.
        assert checker.PCB_GATE_PATH.exists()
        assert checker.PCB_GATE_PATH.parent.name == "docs"
        assert not (REPO_ROOT / "docs" / "decisions").exists()

    def test_the_committed_documents_validate(self, checker):
        candidates = checker.parse_optional_table(
            checker.BOM_PATH, checker.CANDIDATE_KEY
        )
        specs = checker.parse_optional_table(checker.BOM_PATH, checker.SPEC_KEY)
        assert checker.check_excitation_documents(candidates, specs) == []


class TestTheProductionChain:
    def test_the_committed_architecture_puts_the_amplifier_inside_the_chain(
        self, checker
    ):
        text = checker.ARCHITECTURE_PATH.read_text(encoding="utf-8")
        assert checker.validate_excitation_architecture(text) == []

    def test_a_chain_without_an_amplifier_is_refused(self, checker):
        text = "\n".join(
            [
                "DAC",
                "ELECTRODYNAMIC EXCITER",
                "controlled waveform emission",
                "controlled physical excitation",
                "measured dynamic input force",
            ]
        )
        problems = checker.validate_excitation_architecture(text)
        assert any("INTERNAL POWER AMPLIFIER" in p for p in problems)

    def test_an_exciter_driven_before_the_amplifier_is_refused(self, checker):
        # The ordering is the architectural claim, not decoration.
        text = "\n".join(
            [
                "DAC",
                "ELECTRODYNAMIC EXCITER",
                "INTERNAL POWER AMPLIFIER",
                "controlled waveform emission",
                "controlled physical excitation",
                "measured dynamic input force",
            ]
        )
        problems = checker.validate_excitation_architecture(text)
        assert any("DAC -> amplifier -> exciter" in p for p in problems)

    def test_the_capability_states_are_recorded_locally(self, checker):
        # Ruling 4: recorded here rather than by importing a fragment of the
        # unmerged capability-census document.
        text = checker.ARCHITECTURE_PATH.read_text(encoding="utf-8")
        assert "controlled waveform emission     = implemented" in text
        assert "external physical transducer required" in text
        assert "absent from the commercial path" in text
        assert not (REPO_ROOT / "docs" / "ANALYZER_CAPABILITY_MATRIX.md").exists()

    def test_the_product_does_not_require_a_standalone_amplifier(self, checker):
        text = flat(checker.ARCHITECTURE_PATH.read_text(encoding="utf-8"))
        assert "does not presume a standalone external amplifier" in text

    def test_the_microphone_stays_the_zero_added_mass_baseline(self, checker):
        text = flat(checker.ARCHITECTURE_PATH.read_text(encoding="utf-8"))
        assert "adds no attached mass" in text
        assert "microphone remains the baseline response sensor" in text


class TestTheEnclosureEnvelope:
    def test_the_committed_survey_records_that_nobody_has_looked(self, checker):
        text = checker.ENVELOPE_PATH.read_text(encoding="utf-8")
        status = checker.header_field(text, "survey_status")
        assert status == "ENCLOSURE_EXISTENCE_NOT_VERIFIED"
        assert checker.validate_pcb_envelope(text, status) == []

    def test_the_statuses_are_an_evidence_ladder_not_a_switch(self, checker):
        # The census distinction, applied to a case: nobody looked, someone
        # looked and found none, one exists but is unmeasured, measured. Each
        # is cleared by something different, so none may absorb another.
        assert checker.ENVELOPE_STATUSES == (
            "ENCLOSURE_EXISTENCE_NOT_VERIFIED",
            "ENCLOSURE_NOT_AVAILABLE_FOR_MEASUREMENT",
            "NOT_PERFORMED",
            "PERFORMED",
        )

    def test_absence_is_not_inferred_from_an_unbuilt_analyzer(self, checker):
        # The correction this state exists for. An unbuilt Analyzer establishes
        # that no Analyzer was built, not that no case is on a shelf - an empty
        # project box does not depend on the ADC arriving, and the census's ten
        # categories never covered one.
        text = flat(checker.ENVELOPE_PATH.read_text(encoding="utf-8"))
        assert "does not establish absence" in text
        assert "Nobody has looked for an enclosure" in text

    def test_an_unverified_enclosure_cannot_carry_a_measured_dimension(self, checker):
        text = envelope_document(
            "ENCLOSURE_EXISTENCE_NOT_VERIFIED", ("usable width", "42 mm")
        )
        problems = checker.validate_pcb_envelope(
            text, "ENCLOSURE_EXISTENCE_NOT_VERIFIED"
        )
        assert any("nothing has been measured" in p for p in problems)

    def test_finding_a_case_does_not_open_the_layout_gate(self, checker):
        # Looking on a shelf resolves the status and supplies no dimension and
        # no drive requirement, which are what the gate actually needs.
        gate = checker.PCB_GATE_PATH.read_text(encoding="utf-8")
        assert checker.validate_pcb_gate(gate, "NOT_PERFORMED", "NOT_EXECUTED") == []
        problems = checker.validate_pcb_gate(
            "**gate_verdict:** `READY_FOR_SCHEMATIC`", "NOT_PERFORMED", "EXECUTED"
        )
        assert problems

    def test_an_unknown_status_is_refused(self, checker):
        text = envelope_document("PROBABLY_FINE", ("usable width", "TBD"))
        problems = checker.validate_pcb_envelope(text, "PROBABLY_FINE")
        assert any("unknown envelope survey_status" in p for p in problems)

    def test_a_performed_survey_with_any_tbd_is_refused(self, checker):
        text = envelope_document(
            "PERFORMED", ("usable width", "42 mm"), ("max height", "TBD")
        )
        problems = checker.validate_pcb_envelope(text, "PERFORMED")
        assert any("still TBD" in p for p in problems)

    def test_a_fully_measured_survey_is_accepted(self, checker):
        text = envelope_document(
            "PERFORMED", ("usable width", "42 mm"), ("max height", "12 mm")
        )
        assert checker.validate_pcb_envelope(text, "PERFORMED") == []

    def test_an_absent_enclosure_cannot_carry_a_measured_dimension(self, checker):
        # A measurement of something that does not exist.
        text = envelope_document(
            "ENCLOSURE_NOT_AVAILABLE_FOR_MEASUREMENT", ("usable width", "42 mm")
        )
        problems = checker.validate_pcb_envelope(
            text, "ENCLOSURE_NOT_AVAILABLE_FOR_MEASUREMENT"
        )
        assert any("nothing has been measured" in p for p in problems)

    def test_every_committed_dimension_is_still_tbd(self, checker):
        rows = checker.parse_table(checker.ENVELOPE_PATH, "Parameter")
        assert rows
        for row in rows:
            assert not checker.is_set(row["Value"]), row["Parameter"]


class TestAmplifierPowerIsNotInherited:
    def test_the_committed_output_range_is_entirely_unmeasured(self, checker):
        text = checker.AMPLIFIER_PATH.read_text(encoding="utf-8")
        assert (
            checker.validate_amplifier_requirements(text, "NOT_EXECUTED", set()) == []
        )

    def test_a_number_appearing_before_the_bench_runs_is_refused(self, checker):
        text = amplifier_document(("Required continuous output power", "1.5 W"))
        problems = checker.validate_amplifier_requirements(text, "NOT_EXECUTED", set())
        assert any("needs a measurement" in p for p in problems)

    def test_the_same_number_is_accepted_once_the_bench_has_run(self, checker):
        text = amplifier_document(("Required continuous output power", "1.5 W"))
        assert checker.validate_amplifier_requirements(text, "EXECUTED", set()) == []

    def test_an_exciter_rated_power_may_not_become_the_requirement(self, checker):
        # EXC-006, and the rule the whole requirements document is built around:
        # 24 W is what the DAEX25FHE-4 tolerates, not what a plate needs.
        text = amplifier_document(("Required continuous output power", "24 W"))
        problems = checker.validate_amplifier_requirements(
            text, "EXECUTED", {10.0, 24.0}
        )
        assert any(
            "tolerates is not what the amplifier must deliver" in p for p in problems
        )

    def test_a_measured_figure_unrelated_to_any_rating_passes(self, checker):
        text = amplifier_document(("Required continuous output power", "1.5 W"))
        assert (
            checker.validate_amplifier_requirements(text, "EXECUTED", {10.0, 24.0})
            == []
        )

    def test_the_ratings_are_read_from_the_committed_candidates(self, checker):
        candidates = checker.parse_optional_table(
            checker.BOM_PATH, checker.CANDIDATE_KEY
        )
        specs = checker.parse_optional_table(checker.BOM_PATH, checker.SPEC_KEY)
        ratings = checker.exciter_rated_powers(
            candidates, {s["spec_for"]: s for s in specs}
        )
        assert {10.0, 24.0} <= ratings

    def test_both_candidate_loads_are_covered(self, checker):
        # The VISATON is 8 ohm and the Daytons are 4. The requirement covers
        # both rather than restating the odd one out.
        text = checker.AMPLIFIER_PATH.read_text(encoding="utf-8")
        assert "**4 Ω and 8 Ω both required**" in text

    def test_one_excitation_channel_is_stated_in_both_documents(self, checker):
        # A stereo reference part does not make the architecture two-channel.
        amplifier = checker.AMPLIFIER_PATH.read_text(encoding="utf-8")
        architecture = checker.ARCHITECTURE_PATH.read_text(encoding="utf-8")
        assert "mono excitation path" in amplifier
        assert "**1** excitation channel" in amplifier
        assert "one exciter" in amplifier
        assert "drives one exciter" in amplifier or "one exciter" in architecture

    def test_the_amplifier_family_is_never_written_as_a_selection(self, checker):
        text = checker.AMPLIFIER_PATH.read_text(encoding="utf-8")
        assert "**Selection status:** `CANDIDATE`" in text
        assert "Selected amplifier = TPA3116D2" not in text
        assert "candidate, not a selection" in text


class TestNoForceEntersTheCommercialPath:
    def test_the_committed_documents_state_no_force_in_newtons(self, checker):
        texts = {
            path.name: path.read_text(encoding="utf-8")
            for path in checker.EXCITATION_DOCUMENTS
        }
        assert checker.validate_no_specimen_force_claim(texts) == []

    def test_a_bare_newton_figure_is_refused(self, checker):
        problems = checker.validate_no_specimen_force_claim(
            {"doc.md": "The exciter delivers 1.8 N into the plate."}
        )
        assert any("measures no force" in p for p in problems)

    def test_the_same_figure_is_accepted_as_a_motor_force_scale(self, checker):
        assert (
            checker.validate_no_specimen_force_claim(
                {"doc.md": "The motor-force scale is 1.8 N at this current."}
            )
            == []
        )

    def test_the_amplifier_requirements_prohibit_recording_an_input_force(
        self, checker
    ):
        text = checker.AMPLIFIER_PATH.read_text(encoding="utf-8")
        assert "prohibited — no force channel exists" in text

    def test_the_protocol_never_claims_a_calibrated_force(self, checker):
        text = checker.DRIVE_PROTOCOL_PATH.read_text(encoding="utf-8").lower()
        for claim in (
            "calibrated force",
            "measured input force",
            "force channel exists",
        ):
            assert claim not in text
        assert "there is no force channel" in text


class TestTheProtocolRecordsWhatItMustIdentify:
    @pytest.fixture(scope="class")
    def protocol(self, checker):
        return checker.DRIVE_PROTOCOL_PATH.read_text(encoding="utf-8")

    def test_it_is_recorded_as_unexecuted(self, checker, protocol):
        assert checker.header_field(protocol, "execution_status") == "NOT_EXECUTED"

    @pytest.mark.parametrize(
        "identity",
        ["exciter identity", "stinger identity", "tip identity", "amplifier gain"],
    )
    def test_every_energized_step_records_identity(self, protocol, identity):
        assert identity in protocol

    def test_masses_are_measured_rather_than_targeted(self, protocol):
        assert "measured, not target" in protocol

    def test_electrical_and_response_quantities_are_recorded_separately(self, protocol):
        assert "drive-side electrical, measured" in protocol
        assert "response-side, measured" in protocol
        # And the derived one is labelled as derived rather than measured.
        assert "marked derived" in protocol

    def test_the_stinger_contact_question_is_asked_with_the_amplifier_off(
        self, protocol
    ):
        assert "Plate contact, amplifier off" in protocol

    def test_the_emi_interaction_is_a_numbered_step(self, protocol):
        assert "EMI interaction with the ADC and microphone" in protocol

    def test_the_bl_comparison_is_left_empirical(self, protocol):
        assert "empirical questions, not datasheet conclusions" in protocol


class TestThePcbGate:
    @pytest.fixture(scope="class")
    def gate(self, checker):
        return checker.PCB_GATE_PATH.read_text(encoding="utf-8")

    def test_the_committed_gate_is_blocked(self, checker, gate):
        assert checker.header_field(gate, "gate_verdict") == "BLOCKED"

    def test_blocked_is_legal_with_nothing_measured(self, checker, gate):
        assert (
            checker.validate_pcb_gate(
                gate, "ENCLOSURE_EXISTENCE_NOT_VERIFIED", "NOT_EXECUTED"
            )
            == []
        )

    def test_the_gate_cannot_open_without_an_envelope(self, checker):
        text = "**gate_verdict:** `READY_FOR_SCHEMATIC`"
        problems = checker.validate_pcb_gate(text, "NOT_PERFORMED", "EXECUTED")
        assert any("a layout needs an envelope" in p for p in problems)

    def test_the_gate_cannot_open_without_a_measured_drive(self, checker):
        text = "**gate_verdict:** `READY_FOR_SCHEMATIC`"
        problems = checker.validate_pcb_gate(text, "PERFORMED", "NOT_EXECUTED")
        assert any("unmeasured requirement" in p for p in problems)

    def test_the_gate_opens_when_both_inputs_exist(self, checker):
        text = "**gate_verdict:** `READY_FOR_SCHEMATIC`"
        assert checker.validate_pcb_gate(text, "PERFORMED", "EXECUTED") == []

    def test_an_unknown_verdict_is_refused(self, checker):
        problems = checker.validate_pcb_gate(
            "**gate_verdict:** `PROBABLY_FINE`", "PERFORMED", "EXECUTED"
        )
        assert any("unknown PCB gate verdict" in p for p in problems)

    def test_a_closed_gate_is_recorded_as_the_expected_outcome(self, gate):
        assert "normal outcome, not a failure" in gate

    def test_no_schematic_or_layout_was_produced(self):
        # The order's hard boundary. Nothing this order touched may be a board.
        # Scoped to the directories DO-108P wrote in rather than the whole repo,
        # which would spend a minute walking .git, build/ and the run archives.
        suffixes = {".kicad_pcb", ".kicad_sch", ".kicad_pro", ".gbr", ".brd", ".sch"}
        for directory in ("docs", "scripts", "contracts"):
            found = [
                path.name
                for path in (REPO_ROOT / directory).rglob("*")
                if path.suffix in suffixes
            ]
            assert found == [], f"{directory}: {found}"
