"""Grant-readiness boundary guards (DO-102, §8).

Proves by inspection of the source tree that ``tap_tone_pi.grant_readiness``
stays an evidence-support layer: it consumes what the measurement pipeline
produced and adds no signal processing, no capture, no advisory logic, and no
dependency on a downstream system.

These are structural tests. They read the package's own imports and call sites
rather than trusting a docstring.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "tap_tone_pi" / "grant_readiness"
SCRIPTS = (
    REPO_ROOT / "scripts" / "nsf_ttp_audit.py",
    REPO_ROOT / "scripts" / "nsf_ttp_repeatability.py",
    REPO_ROOT / "scripts" / "nsf_ttp_build_pitch_source.py",
    REPO_ROOT / "scripts" / "ttp_hardware_campaign.py",
    REPO_ROOT / "scripts" / "ttp_hardware_campaign_check.py",
)

PACKAGE_FILES = sorted(PACKAGE_DIR.glob("*.py"))
ALL_FILES = [*PACKAGE_FILES, *SCRIPTS]

# inventory.py exists to *name* other parts of the repository — module paths,
# test paths, schema filenames. Textual checks that look for those names would
# fire on it by design, so it is excluded from them and covered instead by
# TestInventoryIsDeclarationOnly, which is the stronger claim: it names things
# and does nothing else.
NAMING_ONLY = {"inventory.py"}
CODE_FILES = [p for p in PACKAGE_FILES if p.name not in NAMING_ONLY]
CODE_AND_SCRIPTS = [*CODE_FILES, *SCRIPTS]

# Modules the grant layer may not reach for. Signal processing and capture are
# excluded because DO-102 authorizes no new DSP; the downstream systems are
# excluded because evidence must not depend on an interpreter of it.
FORBIDDEN_IMPORT_PREFIXES = (
    "numpy",
    "scipy",
    "sounddevice",
    "matplotlib",
    "PyQt6",
    "tap_tone_pi.capture",
    "tap_tone_pi.signal_gen",
    "tap_tone_pi.transfer_function",
    "tap_tone_pi.phase2",
    "tap_tone_pi.wolf",
    "tap_tone_pi.agent",
    "tap_tone_pi.agentic",
    "tap_tone_pi.server",
    "tap_tone_pi.gui",
    "analyzer",
    "luthiers_toolbox",
    "mb_sound",
)

# The only tap_tone_pi module outside the package the grant layer reads. It is
# the DO-085 delegation and nothing else.
PERMITTED_EXTERNAL_IMPORTS = {"tap_tone_pi.core.statistics"}


def module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def source_of(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestPackageIsPopulated:
    def test_package_files_were_found(self):
        # Guards the rest of this module against silently testing nothing.
        assert len(PACKAGE_FILES) >= 8
        assert all(path.exists() for path in SCRIPTS)


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.name)
class TestForbiddenImports:
    def test_no_forbidden_import(self, path):
        for imported in module_imports(path):
            for forbidden in FORBIDDEN_IMPORT_PREFIXES:
                assert not (
                    imported == forbidden or imported.startswith(forbidden + ".")
                ), f"{path.name} imports {imported}"

    def test_declares_instrument_class(self, path):
        head = "\n".join(source_of(path).splitlines()[:5])
        assert "# INSTRUMENT CLASS: MEASUREMENT" in head


class TestNoSignalProcessing:
    """DO-102 authorizes no new signal-processing utilities."""

    @pytest.mark.parametrize("path", CODE_AND_SCRIPTS, ids=lambda p: p.name)
    def test_no_dsp_call_sites(self, path):
        source = source_of(path).lower()
        for marker in (
            "np.fft",
            "rfft",
            "find_peaks",
            "welch",
            "windows.hann",
            "spectrogram",
            "coherence(",
        ):
            assert marker not in source, f"{path.name} contains {marker}"

    @pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.name)
    def test_no_capture_call_sites(self, path):
        source = source_of(path).lower()
        for marker in (
            "inputstream",
            "sd.rec",
            "query_devices",
            "read_wav",
            "write_wav",
        ):
            assert marker not in source, f"{path.name} contains {marker}"


class TestDelegationIsNarrow:
    def test_only_do085_statistics_is_imported_from_elsewhere(self):
        external: set[str] = set()
        for path in PACKAGE_FILES:
            for imported in module_imports(path):
                if imported.startswith("tap_tone_pi.") and not imported.startswith(
                    "tap_tone_pi.grant_readiness"
                ):
                    external.add(imported)
        assert external == PERMITTED_EXTERNAL_IMPORTS

    def test_statistics_module_delegates_rather_than_recomputes(self):
        source = source_of(PACKAGE_DIR / "statistics.py")
        assert "from tap_tone_pi.core.statistics import compute_repeatability" in source
        assert "compute_repeatability(numbers)" in source

    def test_do085_gate_is_not_imported(self):
        # The study cross-references DO-085 evidence by identifier. It does not
        # import the record, and so cannot inherit its acceptance gate.
        for path in PACKAGE_FILES:
            assert "tap_tone_pi.core.repeatability" not in module_imports(path)


class TestCampaignAddsNoSignalProcessing:
    """DO-103 §15 authorizes no new DSP, and the campaign layer adds none.

    The campaign groups and compares runs that the Phase 2 path already
    produced. It reaches those results through the Stage 3 ingestion module,
    which reads the persisted document as a document — so the strongest
    structural claim available is that the campaign module never reaches the
    Phase 2 package or any array library at all, and these tests assert it
    directly rather than trusting the docstring that says so.
    """

    @pytest.fixture(scope="class")
    def campaign_source(self) -> str:
        return source_of(PACKAGE_DIR / "hardware_campaign.py")

    def test_the_campaign_module_exists(self):
        assert (PACKAGE_DIR / "hardware_campaign.py").exists()

    def test_it_reads_phase2_results_through_the_ingestion_module(self):
        imports = module_imports(PACKAGE_DIR / "hardware_campaign.py")
        assert "tap_tone_pi.grant_readiness.phase2_experiment" in imports

    def test_it_reaches_no_measurement_package(self, campaign_source):
        imports = module_imports(PACKAGE_DIR / "hardware_campaign.py")
        for imported in imports:
            assert imported.startswith(
                (
                    "tap_tone_pi.grant_readiness",
                    "typing",
                    "hashlib",
                    "datetime",
                    "__future__",
                )
            ), f"hardware_campaign imports {imported}"

    def test_it_computes_no_transfer_function(self, campaign_source):
        lowered = campaign_source.lower()
        for marker in ("h_mag", "h_phase", "freqs_hz", "fft", "window"):
            assert marker not in lowered, f"hardware_campaign contains {marker}"

    def test_it_defines_no_acceptance_figure(self):
        # DO-103 §4.6 and §4.7 forbid a reciprocity tolerance and a mass-response
        # threshold. Prose that rules one out is fine and is what the module is
        # full of; a *binding* named for one is not, so this reads the module's
        # own definitions rather than its words.
        tree = ast.parse(
            (PACKAGE_DIR / "hardware_campaign.py").read_text(encoding="utf-8")
        )
        # "limitation" is deliberately absent from this list: stating what the
        # evidence cannot support is the opposite of an acceptance figure.
        forbidden = ("threshold", "tolerance", "acceptable", "verdict", "passes")
        defined: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                defined.append(node.id)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                defined.append(node.name)
            elif isinstance(node, ast.arg):
                defined.append(node.arg)
        for name in defined:
            assert not any(marker in name.lower() for marker in forbidden), (
                f"hardware_campaign defines {name}"
            )

    def test_the_check_script_writes_nothing(self):
        # It reports a failing campaign; it never repairs one, because an
        # automatic fix would change evidence to match a claim.
        source = source_of(REPO_ROOT / "scripts" / "ttp_hardware_campaign_check.py")
        assert "write_text(" not in source
        assert "mkdir(" not in source


class TestNoAdvisoryLogic:
    @pytest.mark.parametrize("path", PACKAGE_FILES, ids=lambda p: p.name)
    def test_no_recommendation_vocabulary(self, path):
        source = source_of(path).lower()
        for marker in (
            "def recommend",
            "def advise",
            "def suggest",
            "recommendation",
            "should_adjust",
            "tone_quality",
            "grade(",
        ):
            assert marker not in source, f"{path.name} contains {marker}"

    def test_no_acceptance_threshold_is_defined(self):
        # DO-102 §4.11 sets no target repeatability. A threshold constant in
        # this package would be one, whatever it was called.
        for path in PACKAGE_FILES:
            source = source_of(path)
            for marker in (
                "ACCEPTANCE_THRESHOLD",
                "MAX_CV_PCT",
                "TARGET_CV",
                "PASS_THRESHOLD",
            ):
                assert marker not in source, f"{path.name} defines {marker}"


class TestDoesNotAlterMeasurement:
    def test_package_writes_nothing_under_measurement_directories(self):
        for path in PACKAGE_FILES:
            source = source_of(path)
            # The package builds records and strings; only the scripts write
            # files, and only under an explicit output directory.
            assert "write_text(" not in source
            assert "open(" not in source

    def test_scripts_write_only_under_an_output_directory(self):
        for path in SCRIPTS:
            source = source_of(path)
            if "write_text(" in source:
                assert "output_dir" in source

    def test_no_code_module_names_a_measurement_output_directory(self):
        for path in CODE_FILES:
            assert "runs_phase2" not in source_of(path)


class TestInventoryIsDeclarationOnly:
    """inventory.py may name anything; it may not *do* anything."""

    @pytest.fixture(scope="class")
    def tree(self) -> ast.Module:
        path = PACKAGE_DIR / "inventory.py"
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_defines_no_functions_or_classes(self, tree):
        for node in tree.body:
            assert not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )

    def test_imports_only_the_contract_vocabulary(self, tree):
        assert module_imports(PACKAGE_DIR / "inventory.py") == {
            "__future__",
            "tap_tone_pi.grant_readiness.contracts",
        }

    def test_the_module_body_is_only_declarations(self, tree):
        # Docstring, imports, and assignments — nothing that executes. This is
        # the claim the earlier substring check was reaching for; asked of the
        # AST it cannot be tripped by the word "imports" inside a prose note.
        for node in tree.body:
            assert isinstance(
                node,
                (ast.Expr, ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign),
            ), type(node).__name__
            if isinstance(node, ast.Expr):
                assert isinstance(node.value, ast.Constant)

    def test_it_names_other_subsystems_as_evidence_strings(self, tree):
        # The names it carries are data. A path like the viewer-pack schema
        # appears as a string constant, never as an import or a call.
        constants = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert "contracts/viewer_pack_v1.schema.json" in constants

        # The only calls in the module are constructions of the evidence
        # record itself. Nothing is invoked, resolved, or read.
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert called == {"CapabilityEvidenceV1"}


class TestContractsAreAdditive:
    """The grant layer authors its own contracts and alters nobody else's.

    DO-102 proved that by asserting the package never mentioned an existing
    measurement schema. DO-103 §5.1 brings the Phase 2 transfer-function result
    into the evidence chain, so the package now *reads* that contract and names
    it in order to recognise a document. The claim below is unchanged in
    substance — no existing schema is authored, emitted, or altered here — but
    "never mentions it" was a proxy for that claim, and it stopped being the
    right one once ingestion was authorized. The substantive guards are
    untouched: ``tap_tone_pi.phase2`` remains a forbidden import, and no DSP or
    capture call site is permitted.
    """

    def test_existing_schemas_are_untouched_by_this_package(self):
        for path in CODE_FILES:
            source = source_of(path)
            for existing in (
                "viewer_pack_v1",
                "guided_lab_session_v1",
                "measurement_workflow_contract_v1",
            ):
                assert existing not in source

    def test_the_phase2_contract_is_named_only_where_it_is_read(self):
        for path in CODE_FILES:
            if path.name == "phase2_experiment.py":
                continue
            assert "phase2_ods_snapshot" not in source_of(path), path.name

    def test_the_phase2_contract_is_recognised_not_authored(self):
        # It appears exactly once, as the identity the ingestion path matches a
        # document against. A second occurrence would most likely be this
        # package emitting the contract, which is the thing being ruled out.
        source = source_of(PACKAGE_DIR / "phase2_experiment.py")
        assert 'PHASE2_SCHEMA_VERSION = "phase2_ods_snapshot_v2"' in source, (
            "the Phase 2 contract identity is not declared where it is read"
        )
        assert source.count("phase2_ods_snapshot") == 1

    def test_the_phase2_path_reads_and_does_not_reanalyze(self):
        source = source_of(PACKAGE_DIR / "phase2_experiment.py")
        for marker in (
            "import numpy",
            "import scipy",
            "tap_tone_pi.phase2",
            "scripts.",
        ):
            assert marker not in source, f"phase2_experiment.py reaches for {marker}"

    def test_only_the_two_new_schemas_are_referenced(self):
        source = source_of(PACKAGE_DIR / "contracts.py")
        assert 'AUDIT_SCHEMA_VERSION = "nsf_grant_readiness_audit_v1"' in source
        assert (
            'STUDY_SCHEMA_VERSION = "ttp_preliminary_repeatability_study_v1"' in source
        )


class TestNoCliNamespace:
    def test_unified_cli_is_not_modified(self):
        source = (REPO_ROOT / "tap_tone_pi" / "cli" / "main.py").read_text(
            encoding="utf-8"
        )
        assert "grant_readiness" not in source
        assert "nsf" not in source.lower().replace("nsf_", "")

    def test_no_entry_point_was_added(self):
        source = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "nsf" not in source.lower()
