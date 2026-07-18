#!/usr/bin/env python3
"""
Schema Migration Script — Consolidates schemas/ into contracts/schemas/.

This script:
1. Verifies all schemas in schemas/ have equivalents in contracts/schemas/
2. Identifies any missing schemas that need migration
3. Deletes the schemas/ directory (after backup)
4. Updates references in code

Run with --dry-run to preview changes without modifying anything.

Usage:
    python scripts/migrate_schemas.py --dry-run   # Preview changes
    python scripts/migrate_schemas.py             # Execute migration
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def find_project_root() -> Path:
    """Find project root by looking for pyproject.toml."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not find project root")


def load_schema(path: Path) -> dict:
    """Load and parse a JSON schema file."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Invalid JSON in {path}: {e}")
        return {}


def compare_schemas(old: Path, new: Path) -> tuple[bool, str]:
    """
    Compare two schema files.

    Returns (identical, diff_description).
    """
    if not old.exists():
        return False, "Old file does not exist"
    if not new.exists():
        return False, "New file does not exist"

    old_data = load_schema(old)
    new_data = load_schema(new)

    if old_data == new_data:
        return True, "Identical"

    # Check key differences
    old_keys = set(old_data.get("properties", {}).keys())
    new_keys = set(new_data.get("properties", {}).keys())

    added = new_keys - old_keys
    removed = old_keys - new_keys

    diffs = []
    if added:
        diffs.append(f"Added: {', '.join(sorted(added))}")
    if removed:
        diffs.append(f"Removed: {', '.join(sorted(removed))}")

    if not diffs:
        diffs.append("Content differs (same structure)")

    return False, "; ".join(diffs)


def find_schema_references(root: Path) -> list[tuple[Path, int, str]]:
    """
    Find code references to schemas/ directory.

    Returns list of (file, line_number, line_content).
    """
    references = []

    for ext in ["*.py", "*.yml", "*.yaml", "*.md"]:
        for filepath in root.rglob(ext):
            # Skip the schemas directory itself
            if "schemas" in filepath.parts and filepath.suffix == ".json":
                continue

            try:
                with open(filepath, "r") as f:
                    for i, line in enumerate(f, 1):
                        # Look for schemas/ but not contracts/schemas/
                        if "schemas/" in line and "contracts/schemas/" not in line:
                            references.append((filepath, i, line.strip()))
            except (UnicodeDecodeError, PermissionError):
                continue

    return references


def main():
    parser = argparse.ArgumentParser(
        description="Migrate schemas/ to contracts/schemas/"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without modifying"
    )
    args = parser.parse_args()

    root = find_project_root()
    old_schemas = root / "schemas"
    new_schemas = root / "contracts" / "schemas"

    print("=" * 60)
    print("Schema Migration: schemas/ → contracts/schemas/")
    print("=" * 60)
    print()

    # Check directories exist
    if not old_schemas.exists():
        print("✓ Old schemas/ directory already deleted")
        return 0

    if not new_schemas.exists():
        print("✗ ERROR: contracts/schemas/ does not exist!")
        return 1

    # Find all schema files
    old_schema_files = list(old_schemas.rglob("*.json"))
    new_schema_files = list(new_schemas.rglob("*.json"))

    print(f"Found {len(old_schema_files)} schema files in schemas/")
    print(f"Found {len(new_schema_files)} schema files in contracts/schemas/")
    print()

    # Compare schemas
    print("Schema comparison:")
    print("-" * 40)

    needs_migration = []
    for old_file in old_schema_files:
        rel_path = old_file.relative_to(old_schemas)
        new_file = new_schemas / rel_path

        if not new_file.exists():
            # Check if it's in the root of new_schemas
            alt_new_file = new_schemas / old_file.name
            if alt_new_file.exists():
                new_file = alt_new_file

        if new_file.exists():
            identical, diff = compare_schemas(old_file, new_file)
            if identical:
                print(f"  ✓ {rel_path} — identical")
            else:
                print(f"  ⚠ {rel_path} — {diff}")
        else:
            print(f"  ✗ {rel_path} — MISSING in contracts/schemas/")
            needs_migration.append(old_file)

    print()

    # Find code references
    print("Code references to schemas/ (need updating):")
    print("-" * 40)

    references = find_schema_references(root)

    if references:
        for filepath, line_num, content in references[:20]:  # Limit output
            rel_path = filepath.relative_to(root)
            print(f"  {rel_path}:{line_num}")
            print(f"    {content[:80]}...")

        if len(references) > 20:
            print(f"  ... and {len(references) - 20} more")
    else:
        print("  ✓ No references found")

    print()

    # Migration actions
    if needs_migration:
        print("BLOCKED: The following schemas need migration first:")
        for f in needs_migration:
            print(f"  - {f.relative_to(old_schemas)}")
        print()
        print("Copy these files to contracts/schemas/ and re-run.")
        return 1

    if args.dry_run:
        print("DRY RUN: Would perform the following actions:")
        print(f"  1. Create backup: {old_schemas}.bak")
        print(f"  2. Delete: {old_schemas}")
        print(f"  3. Update {len(references)} code references")
        return 0

    # Execute migration
    print("Executing migration...")

    # Backup
    backup_path = root / "schemas.bak"
    if backup_path.exists():
        shutil.rmtree(backup_path)
    shutil.copytree(old_schemas, backup_path)
    print(f"  ✓ Backup created: {backup_path}")

    # Delete old schemas
    shutil.rmtree(old_schemas)
    print(f"  ✓ Deleted: {old_schemas}")

    # Note about references
    if references:
        print()
        print(f"NOTE: {len(references)} code references need manual update:")
        print("  Replace 'schemas/' with 'contracts/schemas/' in these files.")

    print()
    print("Migration complete!")
    print()
    print("Next steps:")
    print("  1. Update any remaining code references")
    print("  2. Run tests: make test")
    print("  3. Commit changes")
    print("  4. Delete backup: rm -rf schemas.bak")

    return 0


if __name__ == "__main__":
    sys.exit(main())
