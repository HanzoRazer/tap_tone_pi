#!/usr/bin/env python3
"""
Schema Migration: schemas/ → contracts/schemas/

Completes the migration by:
1. Updating schema_registry.json with new entries
2. Updating import references across the codebase
3. Removing the legacy schemas/ directory

Usage:
    python migrate_schemas_final.py --dry-run   # Preview changes
    python migrate_schemas_final.py             # Execute migration
"""

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import List, Tuple


def find_repo_root() -> Path:
    """Find repository root by looking for pyproject.toml or .git."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return current.parent  # Fallback: assume scripts/ is one level down


def update_schema_registry(registry_path: Path, dry_run: bool) -> List[str]:
    """Add new schema entries to registry."""

    new_entries = {
        "bending_stiffness": {
            "path": "contracts/schemas/bending_stiffness.schema.json",
            "schema_id": "bending_stiffness",
            "version": "1.1",
            "description": "Bending stiffness test result (measurement-only)",
        },
        "displacement_series": {
            "path": "contracts/schemas/displacement_series.schema.json",
            "schema_id": "displacement_series",
            "version": "1.0",
            "description": "Displacement time series from dial indicator/LVDT",
        },
        "load_series": {
            "path": "contracts/schemas/load_series.schema.json",
            "schema_id": "load_series",
            "version": "1.0",
            "description": "Load time series from load cell",
        },
    }

    if registry_path.exists():
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    else:
        registry = {"schemas": {}}

    if "schemas" not in registry:
        registry["schemas"] = {}

    added = []
    for key, entry in new_entries.items():
        if key not in registry["schemas"]:
            added.append(key)
            if not dry_run:
                registry["schemas"][key] = entry

    if added and not dry_run:
        # Sort schemas alphabetically
        registry["schemas"] = dict(sorted(registry["schemas"].items()))
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2)
            f.write("\n")

    return added


def find_import_references(repo_root: Path) -> List[Tuple[Path, int, str]]:
    """Find files referencing the old schemas/ path."""

    patterns = [
        r"schemas/bending_stiffness",
        r"schemas/measurement/",
        r"from tap_tone_pi.contracts import schemas  # ",
        r"from schemas\.",
        r"import schemas",
        r'"schemas/',
        r"'schemas/",
    ]

    combined_pattern = re.compile("|".join(patterns))

    matches = []

    # Search Python and JSON files
    for ext in ["*.py", "*.json", "*.md", "*.yml", "*.yaml"]:
        for filepath in repo_root.rglob(ext):
            # Skip virtual envs, caches, and the migration script itself
            if any(
                skip in str(filepath)
                for skip in [
                    "venv",
                    ".venv",
                    "__pycache__",
                    ".git",
                    "node_modules",
                    "migrate_schemas_final.py",
                ]
            ):
                continue

            try:
                content = filepath.read_text(encoding="utf-8")
                for i, line in enumerate(content.splitlines(), 1):
                    if combined_pattern.search(line):
                        matches.append((filepath, i, line.strip()))
            except (UnicodeDecodeError, PermissionError):
                continue

    return matches


def update_references(repo_root: Path, dry_run: bool) -> List[Tuple[Path, int]]:
    """Update import references from schemas/ to contracts/schemas/."""

    replacements = [
        # Python imports
        (
            r"from schemas\.measurement\.displacement_series",
            "from tap_tone_pi.contracts.schemas.displacement_series",
        ),
        (
            r"from schemas\.measurement\.load_series",
            "from tap_tone_pi.contracts.schemas.load_series",
        ),
        (r"from schemas\.measurement\.", "from tap_tone_pi.contracts.schemas."),
        (
            r"from schemas\.bending_stiffness",
            "from tap_tone_pi.contracts.schemas.bending_stiffness",
        ),
        (
            r"from tap_tone_pi.contracts import schemas  # ",
            "from tap_tone_pi.contracts import schemas  # ",
        ),
        # Path strings
        (
            r'"schemas/measurement/displacement_series\.schema\.json"',
            '"contracts/schemas/displacement_series.schema.json"',
        ),
        (
            r'"schemas/measurement/load_series\.schema\.json"',
            '"contracts/schemas/load_series.schema.json"',
        ),
        (
            r'"schemas/measurement/(\w+)\.schema\.json"',
            r'"contracts/schemas/\1.schema.json"',
        ),
        (
            r'"schemas/bending_stiffness\.schema\.json"',
            '"contracts/schemas/bending_stiffness.schema.json"',
        ),
        # Single quotes
        (
            r"'schemas/measurement/displacement_series\.schema\.json'",
            "'contracts/schemas/displacement_series.schema.json'",
        ),
        (
            r"'schemas/measurement/load_series\.schema\.json'",
            "'contracts/schemas/load_series.schema.json'",
        ),
        (
            r"'schemas/measurement/(\w+)\.schema\.json'",
            r"'contracts/schemas/\1.schema.json'",
        ),
        (
            r"'schemas/bending_stiffness\.schema\.json'",
            "'contracts/schemas/bending_stiffness.schema.json'",
        ),
    ]

    updated_files = []

    for ext in ["*.py", "*.json", "*.md"]:
        for filepath in repo_root.rglob(ext):
            if any(
                skip in str(filepath)
                for skip in ["venv", ".venv", "__pycache__", ".git", "node_modules"]
            ):
                continue

            try:
                content = filepath.read_text(encoding="utf-8")
                original = content

                for pattern, replacement in replacements:
                    content = re.sub(pattern, replacement, content)

                if content != original:
                    changes = sum(
                        1
                        for a, b in zip(original.splitlines(), content.splitlines())
                        if a != b
                    )
                    updated_files.append((filepath, changes))

                    if not dry_run:
                        filepath.write_text(content, encoding="utf-8")

            except (UnicodeDecodeError, PermissionError):
                continue

    return updated_files


def remove_schemas_dir(schemas_dir: Path, dry_run: bool) -> List[Path]:
    """Remove legacy schemas/ directory."""

    if not schemas_dir.exists():
        return []

    files = list(schemas_dir.rglob("*"))

    if not dry_run:
        shutil.rmtree(schemas_dir)

    return files


def main():
    parser = argparse.ArgumentParser(
        description="Migrate schemas/ to contracts/schemas/"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without modifying files"
    )
    args = parser.parse_args()

    dry_run = args.dry_run
    prefix = "[DRY-RUN] " if dry_run else ""

    repo_root = find_repo_root()
    schemas_dir = repo_root / "schemas"
    contracts_schemas = repo_root / "contracts" / "schemas"
    registry_path = repo_root / "contracts" / "schema_registry.json"

    print(f"\n{prefix}Schema Migration: schemas/ → contracts/schemas/")
    print("=" * 70)
    print(f"Repository root: {repo_root}")

    # Verify new schemas exist
    print(f"\n{prefix}Step 1: Verify new schemas in contracts/schemas/")
    required = [
        "bending_stiffness.schema.json",
        "displacement_series.schema.json",
        "load_series.schema.json",
    ]

    missing = [s for s in required if not (contracts_schemas / s).exists()]
    if missing:
        print("  ERROR: Missing schemas:")
        for m in missing:
            print(f"    ✗ {m}")
        print("\n  Copy these to contracts/schemas/ first.")
        return 1

    for s in required:
        print(f"  ✓ {s}")

    # Update schema registry
    print(f"\n{prefix}Step 2: Update schema_registry.json")
    added = update_schema_registry(registry_path, dry_run)
    if added:
        for key in added:
            print(f"  + Adding: {key}")
        if not dry_run:
            print(f"  → Updated {registry_path.relative_to(repo_root)}")
    else:
        print("  = All entries already present")

    # Find and show references
    print(f"\n{prefix}Step 3: Find references to old schemas/ path")
    refs = find_import_references(repo_root)
    if refs:
        print(f"  Found {len(refs)} reference(s):")
        for filepath, line_num, line in refs[:15]:
            rel_path = filepath.relative_to(repo_root)
            print(f"    {rel_path}:{line_num}")
            print(f"      {line[:70]}{'...' if len(line) > 70 else ''}")
        if len(refs) > 15:
            print(f"    ... and {len(refs) - 15} more")
    else:
        print("  No references found")

    # Update references
    print(f"\n{prefix}Step 4: Update import references")
    updated = update_references(repo_root, dry_run)
    if updated:
        for filepath, changes in updated:
            rel_path = filepath.relative_to(repo_root)
            print(f"  {'→' if not dry_run else '~'} {rel_path} ({changes} change(s))")
    else:
        print("  No files needed updating")

    # Remove old directory
    print(f"\n{prefix}Step 5: Remove legacy schemas/ directory")
    if schemas_dir.exists():
        removed = remove_schemas_dir(schemas_dir, dry_run)
        print(
            f"  {'Removed' if not dry_run else 'Will remove'} {len(removed)} files/directories"
        )
        if not dry_run:
            print(f"  → Deleted {schemas_dir.relative_to(repo_root)}/")
    else:
        print("  ✓ Already removed")

    # Summary
    print("\n" + "=" * 70)
    print(f"{prefix}Migration Summary:")
    print(f"  • Schema registry entries added: {len(added)}")
    print(f"  • Files with references found: {len(refs)}")
    print(f"  • Files updated: {len(updated)}")
    print(
        f"  • Legacy directory removed: {'Yes' if not dry_run and schemas_dir.exists() else 'N/A'}"
    )

    if dry_run:
        print(f"\n{prefix}Re-run without --dry-run to apply changes.")
    else:
        print("\n✓ Migration complete!")
        print("\nNext steps:")
        print(
            "  git add contracts/schemas/*.schema.json contracts/schema_registry.json"
        )
        print("  git rm -rf schemas/")
        print(
            "  git commit -m 'chore: Complete schema migration to contracts/schemas/'"
        )

    return 0


if __name__ == "__main__":
    exit(main())
