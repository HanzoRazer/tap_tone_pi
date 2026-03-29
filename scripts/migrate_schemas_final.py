#!/usr/bin/env python3
"""
Schema Migration: schemas/ → contracts/schemas/

This script completes the migration of schemas from the legacy schemas/
directory to contracts/schemas/.

Actions:
1. Copies 3 new schemas to contracts/schemas/
2. Updates schema_registry.json with new entries
3. Removes the legacy schemas/ directory

Usage:
    python migrate_schemas_final.py --dry-run   # Preview changes
    python migrate_schemas_final.py             # Execute migration

Prerequisites:
- Place these files in contracts/schemas/ before running:
  - bending_stiffness.schema.json
  - displacement_series.schema.json
  - load_series.schema.json
"""

import argparse
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Migrate schemas to contracts/schemas/")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()
    
    repo_root = Path(__file__).parent.parent
    schemas_dir = repo_root / "schemas"
    contracts_schemas = repo_root / "contracts" / "schemas"
    registry_path = repo_root / "contracts" / "schema_registry.json"
    
    dry_run = args.dry_run
    prefix = "[DRY-RUN] " if dry_run else ""
    
    # Check prerequisites
    new_schemas = [
        "bending_stiffness.schema.json",
        "displacement_series.schema.json",
        "load_series.schema.json",
    ]
    
    missing = [s for s in new_schemas if not (contracts_schemas / s).exists()]
    if missing:
        print(f"ERROR: Missing schemas in {contracts_schemas}:")
        for m in missing:
            print(f"  - {m}")
        print("\nCopy the upgraded schemas first, then re-run.")
        return 1
    
    print(f"{prefix}Schema Migration: schemas/ → contracts/schemas/")
    print("=" * 60)
    
    # Step 1: Verify new schemas are in place
    print(f"\n{prefix}Step 1: Verify new schemas")
    for schema in new_schemas:
        path = contracts_schemas / schema
        print(f"  ✓ {schema} exists")
    
    # Step 2: Update schema registry
    print(f"\n{prefix}Step 2: Update schema_registry.json")
    
    if registry_path.exists():
        with open(registry_path) as f:
            registry = json.load(f)
    else:
        registry = {"schemas": {}}
    
    new_entries = {
        "bending_stiffness": {
            "path": "contracts/schemas/bending_stiffness.schema.json",
            "version": "1.1",
            "description": "Bending stiffness test result (measurement-only)"
        },
        "displacement_series": {
            "path": "contracts/schemas/displacement_series.schema.json",
            "version": "1.0",
            "description": "Displacement time series from dial indicator/LVDT"
        },
        "load_series": {
            "path": "contracts/schemas/load_series.schema.json",
            "version": "1.0",
            "description": "Load time series from load cell"
        },
    }
    
    for key, entry in new_entries.items():
        if key not in registry.get("schemas", {}):
            print(f"  + Adding: {key}")
            if not dry_run:
                if "schemas" not in registry:
                    registry["schemas"] = {}
                registry["schemas"][key] = entry
        else:
            print(f"  = Exists: {key}")
    
    if not dry_run:
        with open(registry_path, "w") as f:
            json.dump(registry, f, indent=2, sort_keys=True)
        print(f"  → Wrote {registry_path}")
    
    # Step 3: Remove legacy schemas/ directory
    print(f"\n{prefix}Step 3: Remove legacy schemas/ directory")
    
    if schemas_dir.exists():
        files_to_remove = list(schemas_dir.rglob("*"))
        print(f"  Will remove {len(files_to_remove)} files/dirs:")
        for f in files_to_remove[:10]:
            print(f"    - {f.relative_to(repo_root)}")
        if len(files_to_remove) > 10:
            print(f"    ... and {len(files_to_remove) - 10} more")
        
        if not dry_run:
            shutil.rmtree(schemas_dir)
            print(f"  → Removed {schemas_dir}")
    else:
        print(f"  ✓ Already removed: {schemas_dir}")
    
    # Step 4: Verify
    print(f"\n{prefix}Step 4: Verification")
    
    all_schemas = list(contracts_schemas.glob("*.schema.json"))
    print(f"  Schemas in contracts/schemas/: {len(all_schemas)}")
    for s in sorted(all_schemas):
        print(f"    - {s.name}")
    
    print("\n" + "=" * 60)
    if dry_run:
        print("DRY RUN complete. Re-run without --dry-run to apply changes.")
    else:
        print("Migration complete!")
    
    return 0


if __name__ == "__main__":
    exit(main())
