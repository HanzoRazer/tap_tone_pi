# INSTRUMENT CLASS: MEASUREMENT
"""Tests for the Laboratory Manual contracts and registry (DO-97).

Covers contract construction, deterministic serialization, manifest loading,
lookup and filtering, path safety, packaged-resource access, and the registry
invariants from the dev order.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from tap_tone_pi.acoustic_lab import (
    SCHEMA_VERSION,
    LaboratoryManualEntryV1,
    LaboratoryManualManifestV1,
    ManualContractError,
    ManualDocumentMissingError,
    ManualEntryNotFoundError,
    ManualRegistryError,
    ManualStatus,
    filter_manual_entries,
    get_manual_entry,
    list_manual_entries,
    load_laboratory_manual_manifest,
    parse_manual_status,
    read_manual_entry_text,
    resolve_manual_entry_path,
    resolve_manual_entry_resource,
    validate_manual_manifest,
)
from tap_tone_pi.acoustic_lab import manual_contracts, manual_registry


def _entry(doc_id: str = "d1", **kw) -> LaboratoryManualEntryV1:
    base = dict(
        doc_id=doc_id,
        title="A Procedure",
        path=f"{doc_id}.md",
        section="Setup",
        status="approved",
        revision="1.0",
    )
    base.update(kw)
    return LaboratoryManualEntryV1(**base)


class TestEntryConstruction:
    def test_valid_entry(self):
        e = _entry(applies_to=("phase2", "bending"), status=ManualStatus.PROVISIONAL)
        assert e.doc_id == "d1"
        assert e.status is ManualStatus.PROVISIONAL
        assert e.applies_to == ("phase2", "bending")
        assert e.superseded_by is None

    def test_status_coerced_from_string(self):
        assert _entry(status="deferred").status is ManualStatus.DEFERRED

    def test_backslash_path_normalized_to_posix(self):
        assert _entry(path="sub\\a.md").path == "sub/a.md"

    def test_whitespace_stripped(self):
        assert _entry(doc_id="  d1  ").doc_id == "d1"

    @pytest.mark.parametrize("field", ["doc_id", "title", "section", "revision"])
    def test_empty_identity_field_rejected(self, field):
        with pytest.raises(ManualContractError):
            _entry(**{field: "   "})

    def test_unknown_status_rejected(self):
        with pytest.raises(ManualContractError, match="status must be one of"):
            _entry(status="best")

    def test_self_supersession_rejected(self):
        # Self-reference is only reachable once status is 'superseded'; a
        # non-superseded entry declaring superseded_by is rejected earlier.
        with pytest.raises(ManualContractError, match="cannot supersede itself"):
            _entry(status="superseded", superseded_by="d1")


class TestPathSafety:
    @pytest.mark.parametrize(
        "bad_path",
        [
            "/etc/passwd",
            "../secret.md",
            "a/../../b.md",
            "C:/x.md",
            "sub/../../y.md",
            "",
            "   ",
            "..",
        ],
    )
    def test_unsafe_paths_rejected(self, bad_path):
        with pytest.raises(ManualContractError):
            _entry(path=bad_path)

    def test_nested_relative_path_allowed(self):
        assert _entry(path="setup/tap/a.md").path == "setup/tap/a.md"


class TestSerialization:
    def test_entry_to_dict_key_order_and_content(self):
        e = _entry(applies_to=("phase2",), superseded_by=None)
        d = e.to_dict()
        assert list(d) == [
            "doc_id",
            "title",
            "path",
            "section",
            "status",
            "revision",
            "applies_to",
            "superseded_by",
        ]
        assert d["status"] == "approved"
        assert d["applies_to"] == ["phase2"]

    def test_entry_roundtrip(self):
        e = _entry(applies_to=("a", "b"))
        assert LaboratoryManualEntryV1.from_dict(e.to_dict()) == e

    def test_manifest_roundtrip_preserves_order(self):
        entries = tuple(_entry(f"d{i}", title=f"T{i}") for i in range(5))
        m = LaboratoryManualManifestV1(manual_revision="2.1", entries=entries)
        restored = LaboratoryManualManifestV1.from_dict(m.to_dict())
        assert restored == m
        assert [e.doc_id for e in restored.entries] == [f"d{i}" for i in range(5)]

    def test_manifest_json_roundtrip(self):
        m = LaboratoryManualManifestV1(manual_revision="1.0", entries=(_entry(),))
        restored = LaboratoryManualManifestV1.from_dict(
            json.loads(json.dumps(m.to_dict()))
        )
        assert restored == m

    def test_from_dict_rejects_unknown_entry_field(self):
        d = _entry().to_dict()
        d["extra"] = 1
        with pytest.raises(ManualContractError, match="unknown entry field"):
            LaboratoryManualEntryV1.from_dict(d)

    def test_from_dict_rejects_missing_required_field(self):
        d = _entry().to_dict()
        del d["title"]
        with pytest.raises(ManualContractError, match="missing required field"):
            LaboratoryManualEntryV1.from_dict(d)


class TestManifestInvariants:
    def test_duplicate_doc_id_rejected(self):
        with pytest.raises(ManualContractError, match="duplicate doc_id"):
            LaboratoryManualManifestV1(
                manual_revision="1.0",
                entries=(_entry("dup"), _entry("dup", path="other.md")),
            )

    def test_unsupported_schema_version_rejected(self):
        with pytest.raises(
            ManualContractError, match="unsupported manifest schema_version"
        ):
            LaboratoryManualManifestV1(manual_revision="1.0", schema_version="v99")

    def test_dangling_supersession_rejected(self):
        with pytest.raises(ManualContractError, match="superseded by unknown"):
            LaboratoryManualManifestV1(
                manual_revision="1.0",
                entries=(_entry("old", status="superseded", superseded_by="ghost"),),
            )

    def test_valid_supersession_chain_accepted(self):
        m = LaboratoryManualManifestV1(
            manual_revision="1.0",
            entries=(
                _entry("old", status="superseded", superseded_by="new"),
                _entry("new", path="new.md"),
            ),
        )
        assert len(m.entries) == 2


class TestFilteringAndLookup:
    @pytest.fixture
    def manifest(self):
        return LaboratoryManualManifestV1(
            manual_revision="1.0",
            entries=(
                _entry("a", section="Setup", status="approved"),
                _entry("b", section="Setup", status="provisional", path="b.md"),
                _entry("c", section="Damping", status="approved", path="c.md"),
            ),
        )

    def test_list_returns_authored_order(self, manifest):
        assert [e.doc_id for e in list_manual_entries(manifest)] == ["a", "b", "c"]

    def test_get_by_id(self, manifest):
        assert get_manual_entry("b", manifest).section == "Setup"

    def test_get_missing_raises(self, manifest):
        with pytest.raises(ManualEntryNotFoundError):
            get_manual_entry("zzz", manifest)

    def test_filter_by_section(self, manifest):
        assert [e.doc_id for e in filter_manual_entries(manifest, section="Setup")] == [
            "a",
            "b",
        ]

    def test_filter_by_status(self, manifest):
        got = filter_manual_entries(manifest, status="approved")
        assert [e.doc_id for e in got] == ["a", "c"]

    def test_filter_combined(self, manifest):
        got = filter_manual_entries(
            manifest, section="Setup", status=ManualStatus.APPROVED
        )
        assert [e.doc_id for e in got] == ["a"]

    def test_filter_unknown_status_raises(self, manifest):
        with pytest.raises(ManualContractError):
            filter_manual_entries(manifest, status="optimal")

    def test_no_filters_returns_all(self, manifest):
        assert len(filter_manual_entries(manifest)) == 3


class TestPackagedManifest:
    """Exercises the real packaged resource via importlib.resources."""

    def test_packaged_manifest_loads(self):
        m = load_laboratory_manual_manifest()
        assert m.schema_version == SCHEMA_VERSION

    def test_packaged_manifest_is_empty_by_design(self):
        # DO-97 ships an empty manifest; a consolidated manual does not yet exist.
        assert list_manual_entries(load_laboratory_manual_manifest()) == ()

    def test_validate_packaged_manifest_ok(self):
        report = validate_manual_manifest()
        assert report.ok
        assert report.entry_count == 0

    def test_manifest_reachable_via_installed_resource_mechanism(self):
        # Access through importlib.resources — the same path an installed build
        # uses — not a source-tree file read. This is what makes the packaging
        # acceptance criterion meaningful.
        from importlib import resources

        root = resources.files("tap_tone_pi.acoustic_lab") / "manual"
        assert (root / "manual_manifest.json").is_file()
        assert (root / "README.md").is_file()


class TestRegistryErrorHandling:
    def test_malformed_json_raises_registry_error(self, tmp_path):
        (tmp_path / "manual_manifest.json").write_text("{ not json", encoding="utf-8")
        with mock.patch.object(manual_registry, "_manual_root", return_value=tmp_path):
            with pytest.raises(ManualRegistryError, match="not valid JSON"):
                load_laboratory_manual_manifest()

    def test_missing_manifest_raises_registry_error(self, tmp_path):
        with mock.patch.object(manual_registry, "_manual_root", return_value=tmp_path):
            with pytest.raises(ManualRegistryError, match="missing from the packaged"):
                load_laboratory_manual_manifest()

    def test_missing_registered_file_raises(self):
        # An entry whose file is not in the package must fail loudly, not silently.
        manifest = LaboratoryManualManifestV1(
            manual_revision="1.0", entries=(_entry("ghost", path="ghost.md"),)
        )
        with pytest.raises(ManualDocumentMissingError):
            resolve_manual_entry_path("ghost", manifest)

    def test_read_missing_file_raises(self):
        manifest = LaboratoryManualManifestV1(
            manual_revision="1.0", entries=(_entry("ghost", path="ghost.md"),)
        )
        with pytest.raises(ManualDocumentMissingError):
            read_manual_entry_text("ghost", manifest)

    def test_validate_reports_missing_files_without_raising(self):
        manifest = LaboratoryManualManifestV1(
            manual_revision="1.0", entries=(_entry("ghost", path="ghost.md"),)
        )
        report = validate_manual_manifest(manifest)
        assert not report.ok
        assert "ghost" in report.problems[0]


class TestBoundary:
    """The manual registry must not reach into measurement execution."""

    def test_registry_does_not_import_measurement_execution(self):
        import ast

        src = Path(manual_registry.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)

        forbidden = (
            "tap_tone_pi.capture",
            "tap_tone_pi.calibration",
            "tap_tone_pi.phase2",
            "tap_tone_pi.cli",
            "tap_tone_pi.server",
        )
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)

        for mod in imported:
            assert not mod.startswith(forbidden), f"registry imports {mod}"

    def test_acoustic_lab_core_does_not_import_gui(self):
        # Importing the Laboratory core must not drag in PyQt6.
        import importlib
        import sys

        for name in (
            "tap_tone_pi.acoustic_lab.manual_contracts",
            "tap_tone_pi.acoustic_lab.manual_registry",
        ):
            sys.modules.pop(name, None)
        importlib.import_module("tap_tone_pi.acoustic_lab")

        core_files = {
            "manual_contracts",
            "manual_registry",
            "__init__",
        }
        for name, mod in list(sys.modules.items()):
            if name.startswith("tap_tone_pi.acoustic_lab") and getattr(
                mod, "__file__", None
            ):
                stem = Path(mod.__file__).stem
                if stem in core_files:
                    src = Path(mod.__file__).read_text(encoding="utf-8")
                    assert "PyQt" not in src, f"{name} references PyQt"


# --- DO-97G corrective regressions -----------------------------------------


class TestAppliesToRejectsScalarText:
    """applies_to is a sequence of tags, never scalar text (DO-97G §6.2)."""

    def test_string_applies_to_rejected(self):  # C-01
        with pytest.raises(ManualContractError, match="applies_to must be a sequence"):
            _entry(applies_to="workflow")

    def test_bytes_applies_to_rejected(self):  # C-02
        with pytest.raises(ManualContractError, match="applies_to must be a sequence"):
            _entry(applies_to=b"workflow")

    def test_bytearray_applies_to_rejected(self):
        with pytest.raises(ManualContractError, match="applies_to must be a sequence"):
            _entry(applies_to=bytearray(b"workflow"))

    @pytest.mark.parametrize("value", [("a", "b"), ["a", "b"]])
    def test_tuple_and_list_normalize(self, value):  # C-03
        assert _entry(applies_to=value).applies_to == ("a", "b")

    def test_empty_tag_rejected(self):  # C-04
        with pytest.raises(ManualContractError):
            _entry(applies_to=["ok", "  "])

    def test_non_string_tag_rejected(self):
        with pytest.raises(ManualContractError):
            _entry(applies_to=["ok", 3])


class TestSupersessionConsistency:
    """Entry- and manifest-level supersession invariants (DO-97G §6.1)."""

    def test_superseded_without_replacement_rejected(self):  # C-05
        with pytest.raises(ManualContractError, match="names no replacement"):
            _entry(status="superseded")

    @pytest.mark.parametrize("status", ["approved", "provisional", "deferred"])
    def test_non_superseded_with_replacement_rejected(self, status):  # C-06
        with pytest.raises(ManualContractError, match="not 'superseded'"):
            _entry(status=status, superseded_by="other")

    def test_self_supersession_rejected(self):  # C-07
        with pytest.raises(ManualContractError, match="cannot supersede itself"):
            _entry("a", status="superseded", superseded_by="a")

    def test_unknown_replacement_rejected(self):  # C-08
        with pytest.raises(ManualContractError, match="superseded by unknown"):
            LaboratoryManualManifestV1(
                manual_revision="1.0",
                entries=(_entry("a", status="superseded", superseded_by="ghost"),),
            )

    def test_two_entry_cycle_rejected(self):  # C-09
        with pytest.raises(ManualContractError, match="supersession cycle detected"):
            LaboratoryManualManifestV1(
                manual_revision="1.0",
                entries=(
                    _entry("a", status="superseded", superseded_by="b", path="a.md"),
                    _entry("b", status="superseded", superseded_by="a", path="b.md"),
                ),
            )

    def test_three_entry_cycle_rejected(self):  # C-10
        with pytest.raises(ManualContractError, match="supersession cycle detected"):
            LaboratoryManualManifestV1(
                manual_revision="1.0",
                entries=(
                    _entry("a", status="superseded", superseded_by="b", path="a.md"),
                    _entry("b", status="superseded", superseded_by="c", path="b.md"),
                    _entry("c", status="superseded", superseded_by="a", path="c.md"),
                ),
            )

    def test_valid_acyclic_chain_accepted(self):  # C-11
        m = LaboratoryManualManifestV1(
            manual_revision="1.0",
            entries=(
                _entry("a", status="superseded", superseded_by="b", path="a.md"),
                _entry("b", status="superseded", superseded_by="c", path="b.md"),
                _entry("c", status="approved", path="c.md"),
            ),
        )
        assert [e.doc_id for e in m.entries] == ["a", "b", "c"]


class TestPublicStatusParser:
    """parse_manual_status is the public, contract-owned normalization API."""

    def test_accepts_enum_and_valid_string(self):
        assert parse_manual_status(ManualStatus.APPROVED) is ManualStatus.APPROVED
        assert parse_manual_status("provisional") is ManualStatus.PROVISIONAL

    def test_rejects_invalid_vocabulary(self):
        with pytest.raises(ManualContractError, match="status must be one of"):
            parse_manual_status("optimal")


class _FakeFile:
    """A non-filesystem Traversable file (no native pathlib.Path)."""

    def __init__(self, text: str) -> None:
        self._text = text

    def is_dir(self) -> bool:
        return False

    def is_file(self) -> bool:
        return True

    def read_text(self, encoding: str = "utf-8") -> str:
        return self._text


class _FakeMissing:
    def is_dir(self) -> bool:
        return False

    def is_file(self) -> bool:
        return False

    def __truediv__(self, name: str) -> "_FakeMissing":
        return self


class _FakeDir:
    """A non-filesystem Traversable directory backed by a name->child map."""

    def __init__(self, children: dict) -> None:
        self._children = children

    def is_dir(self) -> bool:
        return True

    def is_file(self) -> bool:
        return False

    def __truediv__(self, name):
        return self._children.get(name, _FakeMissing())


class TestTraversableResourceAccess:
    """Resource access must be truthful for non-filesystem Traversables."""

    def _manifest(self, doc_id="a", path="a.md"):
        return LaboratoryManualManifestV1(
            manual_revision="1.0", entries=(_entry(doc_id, path=path),)
        )

    def test_registry_does_not_depend_on_private_coerce_status(self):
        # The private helper must not exist as a cross-module interface.
        assert not hasattr(manual_contracts, "_coerce_status")
        src = Path(manual_registry.__file__).read_text(encoding="utf-8")
        assert "_coerce_status" not in src

    def test_nested_valid_resource_readable(self):  # R-01
        root = _FakeDir({"setup": _FakeDir({"tap.md": _FakeFile("# nested")})})
        manifest = self._manifest("n", "setup/tap.md")
        with mock.patch.object(manual_registry, "_manual_root", return_value=root):
            assert read_manual_entry_text("n", manifest) == "# nested"

    def test_fake_traversable_text_readable(self):  # R-04
        root = _FakeDir({"a.md": _FakeFile("# hi")})
        with mock.patch.object(manual_registry, "_manual_root", return_value=root):
            assert read_manual_entry_text("a", self._manifest()) == "# hi"
            resource = resolve_manual_entry_resource("a", self._manifest())
            assert resource.read_text() == "# hi"

    def test_missing_resource_raises(self):  # R-02
        root = _FakeDir({})
        with mock.patch.object(manual_registry, "_manual_root", return_value=root):
            with pytest.raises(ManualDocumentMissingError):
                read_manual_entry_text("a", self._manifest())

    def test_directory_resource_rejected(self):  # R-03
        root = _FakeDir({"a.md": _FakeDir({})})
        with mock.patch.object(manual_registry, "_manual_root", return_value=root):
            with pytest.raises(ManualRegistryError, match="is a directory"):
                resolve_manual_entry_resource("a", self._manifest())

    def test_native_path_api_rejects_non_filesystem_resource(self):  # R-05
        root = _FakeDir({"a.md": _FakeFile("# hi")})
        with mock.patch.object(manual_registry, "_manual_root", return_value=root):
            with pytest.raises(
                ManualRegistryError, match="not backed by a filesystem path"
            ):
                resolve_manual_entry_path("a", self._manifest())

    def test_unsafe_path_declarations_still_rejected(self):
        # Contract rejects traversal before the registry ever resolves it.
        for bad in ["../escape.md", "/abs.md", "C:/x.md"]:
            with pytest.raises(ManualContractError):
                _entry(path=bad)

    def test_filesystem_backed_path_api_returns_real_path(self, tmp_path):
        (tmp_path / "a.md").write_text("# real", encoding="utf-8")
        with mock.patch.object(manual_registry, "_manual_root", return_value=tmp_path):
            got = resolve_manual_entry_path("a", self._manifest())
            assert got == (tmp_path / "a.md")
            assert got.read_text(encoding="utf-8") == "# real"
