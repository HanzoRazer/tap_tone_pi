# RMOS Advisory Integration Specification

**Document Version:** 1.0  
**Target System:** Luthier's ToolBox RMOS (runs_v2)  
**Phase:** Phase 3 (Optional Interpretive Analysis)  
**Status:** Specification (not yet implemented)

---

## Purpose

This document defines how Phase 3 Advisory artifacts (defined in `schemas/advisory.schema.json`) integrate with the ToolBox RMOS content-addressed attachment model.

**Key principle:** Advisories are just another attachment kind — no special cases needed.

---

## Storage Invariant

* **Advisory JSON is an immutable blob** stored in the **content-addressed attachments store** (SHA256-sharded)
* The **RunArtifact JSON remains the pointer/index**
* Advisories never mutate measurement artifacts

---

## Advisory Storage Model

### Where the Advisory Lives

Store the advisory JSON as an attachment with:

* `kind = "advisory.v1.json"` (or `"advisory_json"`)
* `sha256 = <sha256 of advisory JSON bytes>`
* `mime = "application/json"`
* `relpath = "derived/advisories/advisory_<advisory_id>.json"` (optional, for export)

### How the Run References It

The RunArtifact's `meta` namespace includes acoustics metadata:

```json
{
  "meta": {
    "acoustics": {
      "phase": 3,
      "advisories": [
        {
          "advisory_id": "adv_20251226_001",
          "sha256": "…64hex…",
          "kind": "advisory.v1.json"
        }
      ]
    }
  }
}
```

Optional: maintain `advisory_ids: []` at top-level if already using that pattern.

---

## RMOS Object Structures

### 1) Advisory JSON (Phase 3 Output)

The `advisory.v1` JSON (defined in `schemas/advisory.schema.json`) is stored as-is, unchanged.

Validates against schema, then stored as immutable blob.

### 2) RunAttachment Entry

Add attachment entry to run JSON:

```json
{
  "sha256": "…64hex…",
  "bytes": 12345,
  "mime": "application/json",
  "kind": "advisory.v1.json",
  "relpath": "derived/advisories/advisory_<advisory_id>.json"
}
```

**Notes:**
* `relpath` is optional but useful for export/reconstruction
* No file paths disclosed
* No shard location exposed

### 3) Append-Only RunAdvisoryLink File (Recommended)

Keep existing append-only link pattern for stable indexing.

**Filename pattern:**
```
run_<run_id>_advisory_<advisory_id>.json
```

**Contents (minimal pointer):**

```json
{
  "run_id": "rmos_run_123",
  "advisory_id": "adv_20251226_001",
  "created_at_utc": "2025-12-26T22:10:00Z",
  "advisory_sha256": "…64hex…",
  "kind": "advisory.v1.json",
  "status": "ACTIVE"
}
```

**Why this file exists:**
* List advisories quickly without re-parsing full run JSON
* Append-only updates (add new advisories later) without mutating historical blobs
* Fast indexing and query support

---

## Import-Time Behavior (ToolBox-Side)

When `import_acoustics_bundle()` or Phase 3 advisory generator produces advisories:

1. **Validate** advisory JSON against `schemas/advisory.schema.json`
2. **Hash** it: compute `advisory_sha256`
3. **Write** advisory blob into content-addressed attachments store
4. **Add** RunAttachment entry on the run:
   * `kind = advisory.v1.json`
   * `sha256 = advisory_sha256`
5. **Write** `run_<run_id>_advisory_<advisory_id>.json` link file (append-only)
6. **Update** `_index.json` for queryability by:
   * `instrument_id`
   * `build_stage`
   * advisory type
   * tags
   * frequency ranges
   * confidence thresholds

---

## Query / API Mapping (Recommended Endpoints)

### List Advisories on a Run

**Endpoint:**
```
GET /api/rmos/acoustics/runs/{run_id}/advisories
```

**Response:**

```json
{
  "run_id": "rmos_run_123",
  "advisories": [
    {
      "advisory_id": "adv_20251226_001",
      "created_at_utc": "2025-12-26T22:10:00Z",
      "sha256": "…64hex…",
      "kind": "advisory.v1.json",
      "bytes": 12345,
      "mime": "application/json",
      "tags": ["wolf", "interpretive"],
      "confidence_max": 0.62
    }
  ]
}
```

**Notes:**
* No path disclosure
* Optional confidence/tag filtering

### Fetch Advisory JSON by ID

**Option A (best):** Resolve by `advisory_id` via index/link → sha → stream blob

```
GET /api/rmos/acoustics/advisories/{advisory_id}
```

**Option B (simplest):** By SHA256 directly

```
GET /api/rmos/acoustics/attachments/{sha256}
```

(You already wanted this for general attachment access)

### Export Run (Includes Advisories)

Zip export should include:

* Run JSON pointer file
* Advisory link files (`run_*_advisory_*.json`)
* Advisory blobs (by SHA256) with relpaths in bundle
* Manifest/index as needed

**Example export structure:**

```
export_rmos_run_123.zip
├── run_rmos_run_123.json
├── run_rmos_run_123_advisory_adv_001.json
├── attachments/
│   ├── aa/bb/ccdd…_audio.wav
│   ├── ee/ff/1122…_analysis.json
│   └── 11/22/3344…_advisory_adv_001.json
└── manifest.json
```

---

## Versioning + Evolution Rules

### Schema Versioning

* Advisory schema version is **explicit**: `schema_version = "advisory.v1"`
* Schema evolution uses new version identifiers (`advisory.v2`, etc.)

### Interpretive Logic Versioning

If you change interpretive logic:

* Bump `tool.algorithm_id` or `tool.tool_version`
* Produce a **new advisory_id** (or same id with new `status=SUPERSEDED` link file)

### Immutability Rules

* **Never overwrite advisory blobs**
* Always produce new advisories when logic/data changes
* Old advisories remain accessible via SHA256

### Status Evolution (Optional)

Link files can track advisory lifecycle:

* `status = "ACTIVE"` — current interpretation
* `status = "SUPERSEDED"` — replaced by newer advisory
* `status = "WITHDRAWN"` — retracted interpretation

---

## Why This Mapping is RMOS-Native

### Preserves RMOS Invariants

* **Run JSON is a pointer** — no inline blobs
* **Attachments are immutable by SHA256** — content-addressed
* **Append-only links** — no historical mutation

### Advisories as First-Class Attachments

* Advisories are "just another attachment kind"
* No special storage system required
* No database dependency
* No path disclosure needed

### Clean One-Way Dependency

* Phase 3 consumes Phase 1/2 artifacts
* Phase 1/2 never depend on Phase 3
* RMOS can operate without Phase 3 code

---

## Index Schema Extensions (Recommended)

Add to `_index.json` for fast advisory queries:

```json
{
  "advisories": [
    {
      "advisory_id": "adv_20251226_001",
      "run_id": "rmos_run_123",
      "instrument_id": "OM-TEST-001",
      "build_stage": "box-closed",
      "created_at_utc": "2025-12-26T22:10:00Z",
      "sha256": "…64hex…",
      "tool_id": "tap_tone_pi.phase3",
      "tool_version": "0.1.0",
      "algorithm_id": "wolf.v1",
      "tags": ["phase3", "wolf", "interpretive"],
      "claim_types": ["wolf_candidate"],
      "confidence_max": 0.62,
      "frequency_ranges_hz": [[182, 196]],
      "status": "ACTIVE"
    }
  ]
}
```

**Query examples enabled:**
* All advisories for instrument X
* All wolf candidates with confidence > 0.6
* All advisories in frequency range 180-200 Hz
* All advisories for build stage "box-closed"
* Timeline of advisories across build stages

---

## Pydantic Models (Future Implementation)

When implementing in ToolBox, define:

### RunAdvisoryLinkV1

```python
from pydantic import BaseModel, Field

class RunAdvisoryLinkV1(BaseModel):
    run_id: str
    advisory_id: str = Field(min_length=8)
    created_at_utc: str  # RFC3339
    advisory_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    kind: str = Field(default="advisory.v1.json")
    status: str = Field(default="ACTIVE")  # ACTIVE | SUPERSEDED | WITHDRAWN
```

### AdvisoryAttachmentRefV1

```python
class AdvisoryAttachmentRefV1(BaseModel):
    advisory_id: str
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    kind: str = Field(default="advisory.v1.json")
```

### RunMetaAcoustics

```python
class RunMetaAcoustics(BaseModel):
    phase: int = Field(ge=1, le=3)
    advisories: list[AdvisoryAttachmentRefV1] = Field(default_factory=list)
```

---

## Implementation Checklist (ToolBox)

Phase 3 advisory support complete when:

- [ ] Advisory JSON validation against `schemas/advisory.schema.json`
- [ ] Content-addressed blob storage for advisories
- [ ] RunAttachment entry creation with correct `kind`
- [ ] RunAdvisoryLink file generation (append-only)
- [ ] Index updates for advisory queries
- [ ] API endpoints: list, fetch, export
- [ ] Advisory status lifecycle support (ACTIVE/SUPERSEDED/WITHDRAWN)
- [ ] Export includes advisory blobs + link files
- [ ] Phase 3 failures never break Phase 1/2 workflows

---

## References

* `schemas/advisory.schema.json` — Advisory contract definition
* `PHASE3.md` — Phase 3 charter and scope
* `PHASE2.md` — Phase 2 measurement observability
* ToolBox RMOS runs_v2 implementation (separate repository)

---

**Status:** Specification ratified, awaiting Phase 2 completion before implementation

**Next Steps:**
1. Complete Phase 2 implementation
2. Implement Pydantic models in ToolBox
3. Extend RMOS import pipeline for advisory ingestion
4. Add advisory query endpoints to ToolBox API
5. Test round-trip: tap_tone_pi → RMOS → export → reimport
