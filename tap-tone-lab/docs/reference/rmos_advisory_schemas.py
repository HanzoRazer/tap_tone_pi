"""
RMOS Advisory Pydantic Schemas (Reference Implementation)

This module defines Pydantic models for ToolBox RMOS advisory integration.

**IMPORTANT**: This file belongs in ToolBox repository, NOT tap-tone-lab.
**Target location**: services/api/app/rmos/acoustics/schemas_advisories.py

This is a REFERENCE IMPLEMENTATION stored here for documentation purposes.
When Phase 2 is complete and Phase 3 implementation begins, copy this to ToolBox.

Purpose:
- Advisory attachment references (pointer to blob by sha256)
- Append-only link file records (run_*_advisory_*.json)
- Index shapes for fast advisory queries
- Helper functions for safe conversions

Dependencies:
- pydantic v2+ (with ConfigDict, Field, field_validator)
- Standard library only (datetime, typing)

Schema versions:
- advisory_attachment_ref.v1
- run_advisory_link.v1
- index_run_advisory_summary.v1
- index_run_record.v1
- index_advisory_lookup.v1
- acoustics_index_additions.v1

Integration flow:
1. Phase 3 code generates advisory JSON (validates against schemas/advisory.schema.json)
2. Advisory stored as content-addressed blob (SHA256)
3. RunAdvisoryLinkV1 written as append-only file
4. Index updated with IndexAdvisoryLookupV1 entry
5. API endpoints query via index, stream blob by SHA256

See: docs/RMOS_ADVISORY_INTEGRATION.md for complete specification
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ---------------------------
# Common helpers
# ---------------------------

_SHA256_RE = r"^[a-f0-9]{64}$"


class _Model(BaseModel):
    """Base model with strict settings."""
    model_config = ConfigDict(extra="forbid", frozen=True)


class Sha256Str(str):
    """Marker type for readability; validation happens in models."""


# ---------------------------
# Advisory attachment ref
# ---------------------------

class AdvisoryAttachmentRefV1(_Model):
    """
    Minimal pointer to an advisory JSON blob stored in the content-addressed
    attachments store (sha256 sharded). No filesystem path disclosure.

    This can appear:
      - in RunArtifact.meta.acoustics.advisories[]
      - in _index.json advisory summaries
      - in API responses
    """
    schema_version: Literal["advisory_attachment_ref.v1"] = "advisory_attachment_ref.v1"

    advisory_id: str = Field(..., min_length=2, description="Stable advisory id (UUID recommended).")
    sha256: str = Field(..., pattern=_SHA256_RE, description="SHA256 of the advisory JSON blob.")
    kind: str = Field(
        default="advisory.v1.json",
        description="Attachment kind. Keep stable for indexing (e.g., advisory.v1.json).",
        min_length=2,
    )
    mime: str = Field(default="application/json", description="MIME type for the advisory blob.")
    bytes: Optional[int] = Field(default=None, ge=0, description="Byte length of the blob if known.")
    created_at_utc: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when the advisory was created (from advisory JSON or link).",
    )
    tags: Optional[List[str]] = Field(default=None, description="Optional tags for query/index.")
    confidence_max: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional quick summary: max confidence across claims.",
    )

    @field_validator("tags")
    @classmethod
    def _dedupe_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if not v:
            return v
        # stable de-dupe while preserving order
        seen = set()
        out: List[str] = []
        for t in v:
            tt = (t or "").strip()
            if not tt or tt in seen:
                continue
            seen.add(tt)
            out.append(tt)
        return out or None


# ---------------------------
# Append-only advisory link file
# ---------------------------

class RunAdvisoryLinkV1(_Model):
    """
    Append-only link record stored alongside run artifacts as:

      run_<run_id>_advisory_<advisory_id>.json

    This enables:
      - fast listing of advisories per run
      - append-only evolution (new advisories added without mutating older blobs)
      - stable mapping from advisory_id -> sha256 -> attachment blob

    It does NOT contain shard paths.
    """
    schema_version: Literal["run_advisory_link.v1"] = "run_advisory_link.v1"

    run_id: str = Field(..., min_length=4, description="RMOS run id.")
    advisory_id: str = Field(..., min_length=2, description="Advisory id (UUID recommended).")
    created_at_utc: datetime = Field(..., description="UTC timestamp when link was created.")

    advisory_sha256: str = Field(..., pattern=_SHA256_RE, description="SHA256 of advisory JSON blob.")
    kind: str = Field(default="advisory.v1.json", min_length=2, description="Attachment kind.")
    mime: str = Field(default="application/json", description="MIME type of advisory blob.")
    bytes: Optional[int] = Field(default=None, ge=0, description="Byte length if known.")

    status: Literal["ACTIVE", "SUPERSEDED", "RETRACTED"] = Field(
        default="ACTIVE",
        description="Lifecycle status for the advisory link (append-only).",
    )

    # Optional quick indexing fields (safe summaries)
    tags: Optional[List[str]] = Field(default=None, description="Optional tags for indexing.")
    confidence_max: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Evidence pointer summaries (optional)
    bundle_sha256: Optional[str] = Field(
        default=None,
        pattern=_SHA256_RE,
        description="Optional: bundle sha256 the advisory was based on (manifest-derived).",
    )
    manifest_sha256: Optional[str] = Field(
        default=None,
        pattern=_SHA256_RE,
        description="Optional: manifest sha256 the advisory was based on.",
    )

    @field_validator("tags")
    @classmethod
    def _dedupe_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if not v:
            return v
        seen = set()
        out: List[str] = []
        for t in v:
            tt = (t or "").strip()
            if not tt or tt in seen:
                continue
            seen.add(tt)
            out.append(tt)
        return out or None


# ---------------------------
# Index shapes (in-memory models)
# ---------------------------

class IndexRunAdvisorySummaryV1(_Model):
    """
    Run-scoped advisory summary for _index.json.
    This is intentionally redundant with link files to accelerate queries.
    """
    schema_version: Literal["index_run_advisory_summary.v1"] = "index_run_advisory_summary.v1"

    advisory_id: str = Field(..., min_length=2)
    sha256: str = Field(..., pattern=_SHA256_RE)
    kind: str = Field(default="advisory.v1.json", min_length=2)
    mime: str = Field(default="application/json")
    bytes: Optional[int] = Field(default=None, ge=0)

    created_at_utc: Optional[datetime] = None
    status: Literal["ACTIVE", "SUPERSEDED", "RETRACTED"] = "ACTIVE"

    tags: Optional[List[str]] = None
    confidence_max: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("tags")
    @classmethod
    def _dedupe_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if not v:
            return v
        seen = set()
        out: List[str] = []
        for t in v:
            tt = (t or "").strip()
            if not tt or tt in seen:
                continue
            seen.add(tt)
            out.append(tt)
        return out or None


class IndexRunRecordV1(_Model):
    """
    Minimal representation of how a run may appear in _index.json.
    You likely already have an index model; this is just the advisory addition.
    """
    schema_version: Literal["index_run_record.v1"] = "index_run_record.v1"

    run_id: str = Field(..., min_length=4)
    created_at_utc: datetime
    mode: str = Field(..., min_length=2)

    # Existing fields would go here...
    # meta: Dict[str, Any] = Field(default_factory=dict)

    # Advisory index addition (Phase 3)
    advisories: Optional[List[IndexRunAdvisorySummaryV1]] = Field(
        default=None,
        description="Optional list of advisories associated with this run.",
    )


class IndexAdvisoryLookupV1(_Model):
    """
    Global advisory lookup entry in _index.json so you can resolve:
      advisory_id -> (run_id, sha256, tags, etc.)
    """
    schema_version: Literal["index_advisory_lookup.v1"] = "index_advisory_lookup.v1"

    advisory_id: str = Field(..., min_length=2)
    run_id: str = Field(..., min_length=4)

    sha256: str = Field(..., pattern=_SHA256_RE)
    kind: str = Field(default="advisory.v1.json", min_length=2)
    mime: str = Field(default="application/json")
    bytes: Optional[int] = Field(default=None, ge=0)

    created_at_utc: Optional[datetime] = None
    status: Literal["ACTIVE", "SUPERSEDED", "RETRACTED"] = "ACTIVE"

    tags: Optional[List[str]] = None
    confidence_max: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    bundle_sha256: Optional[str] = Field(default=None, pattern=_SHA256_RE)
    manifest_sha256: Optional[str] = Field(default=None, pattern=_SHA256_RE)

    @field_validator("tags")
    @classmethod
    def _dedupe_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if not v:
            return v
        seen = set()
        out: List[str] = []
        for t in v:
            tt = (t or "").strip()
            if not tt or tt in seen:
                continue
            seen.add(tt)
            out.append(tt)
        return out or None


class AcousticsIndexAdditionsV1(_Model):
    """
    These are the additions to your existing _index.json shape.
    You do NOT need to replace your index; just add these two top-level arrays.

    Example:
      {
        "schema_version": "...",
        "runs": [...],
        "acoustics": {
          "advisory_lookup": [...],
          "run_advisory_rollup": {...}  # optional future
        }
      }
    """
    schema_version: Literal["acoustics_index_additions.v1"] = "acoustics_index_additions.v1"

    advisory_lookup: List[IndexAdvisoryLookupV1] = Field(
        default_factory=list,
        description="Global lookup table for advisories by advisory_id.",
    )


# ---------------------------
# Convenience: extracting safe summaries (optional helper)
# ---------------------------

def advisory_ref_from_link(link: RunAdvisoryLinkV1) -> AdvisoryAttachmentRefV1:
    """Create a safe attachment ref from a link record (no paths)."""
    return AdvisoryAttachmentRefV1(
        advisory_id=link.advisory_id,
        sha256=link.advisory_sha256,
        kind=link.kind,
        mime=link.mime,
        bytes=link.bytes,
        created_at_utc=link.created_at_utc,
        tags=link.tags,
        confidence_max=link.confidence_max,
    )
