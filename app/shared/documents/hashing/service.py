"""Canonical Snapshot Serialization and Two-Stage SHA-256 Hashing Service."""

import hashlib
import json
from typing import Any, Dict


class CanonicalSnapshotService:
    """Provides deterministic JSON serialization and cryptographic SHA-256 hashing."""

    @staticmethod
    def canonical_json(data: Dict[str, Any]) -> str:
        """Serializes dictionary to deterministic canonical JSON."""
        # Strip transient render-time fields before snapshot hashing to avoid circular dependency
        clean_data = {
            k: v for k, v in data.items() if k not in ("snapshot_hash", "qr_data_uri", "pdf_hash")
        }
        return json.dumps(clean_data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def compute_snapshot_hash(cls, context_dict: Dict[str, Any]) -> str:
        """Computes SHA-256 hash of the canonical JSON snapshot."""
        canonical_str = cls.canonical_json(context_dict)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_pdf_hash(pdf_bytes: bytes) -> str:
        """Computes SHA-256 hash of final PDF bytes."""
        return hashlib.sha256(pdf_bytes).hexdigest()
