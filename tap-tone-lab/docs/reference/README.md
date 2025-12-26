# RMOS Reference Implementations

This directory contains **reference implementations** for ToolBox RMOS integration.

**IMPORTANT**: These files belong in the **ToolBox repository**, not tap-tone-lab.

## Purpose

These reference implementations are stored here for:
- Documentation of the integration contract
- Version control alongside schema definitions
- Reference when implementing Phase 3 in ToolBox
- Ensuring consistency between tap-tone-lab contracts and ToolBox implementation

## Files

### `rmos_advisory_schemas.py`

**Target location in ToolBox:**
```
services/api/app/rmos/acoustics/schemas_advisories.py
```

**Purpose:**
- Pydantic v2 models for advisory integration
- Advisory attachment references (content-addressed pointers)
- Append-only link file structures
- Index shape additions for fast queries
- Helper functions for safe conversions

**Dependencies:**
- pydantic v2+ (ConfigDict, Field, field_validator)
- Standard library (datetime, typing)

**Schema versions defined:**
- `advisory_attachment_ref.v1` — Minimal pointer to advisory blob
- `run_advisory_link.v1` — Append-only link file
- `index_run_advisory_summary.v1` — Run-scoped advisory summary
- `index_run_record.v1` — Run record with advisory additions
- `index_advisory_lookup.v1` — Global advisory lookup
- `acoustics_index_additions.v1` — Index additions for acoustics

## Usage

When implementing Phase 3 in ToolBox:

1. Copy `rmos_advisory_schemas.py` to target location in ToolBox
2. Implement index update functions using these models
3. Implement API endpoints using these models
4. Validate advisory JSON against `schemas/advisory.schema.json` before storage
5. Use content-addressed blob storage (SHA256 sharding)

## Integration Workflow

```
Phase 3 code → Advisory JSON
             ↓
         Validate (schemas/advisory.schema.json)
             ↓
         Hash (SHA256)
             ↓
         Store blob (content-addressed)
             ↓
         Create RunAdvisoryLinkV1
             ↓
         Update _index.json (IndexAdvisoryLookupV1)
             ↓
         API endpoints query via index
```

## API Endpoints (to be implemented in ToolBox)

### List advisories on a run
```
GET /api/rmos/acoustics/runs/{run_id}/advisories
```

Returns: List of `AdvisoryAttachmentRefV1` (no path disclosure)

### Fetch advisory JSON by ID
```
GET /api/rmos/acoustics/advisories/{advisory_id}
```

Resolves: `advisory_id` → `IndexAdvisoryLookupV1` → `sha256` → stream blob

### Fetch attachment by SHA256
```
GET /api/rmos/acoustics/attachments/{sha256}
```

Direct content-addressed blob retrieval.

## See Also

- `docs/RMOS_ADVISORY_INTEGRATION.md` — Complete integration specification
- `schemas/advisory.schema.json` — Advisory JSON contract
- `PHASE3.md` — Phase 3 charter and scope
