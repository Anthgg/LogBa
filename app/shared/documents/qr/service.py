"""Backend QR Code Generation Service."""

import base64
import io
import json
from typing import Any, Dict

import qrcode


class DocumentQRService:
    """Generates standard QR codes as Base64 Data URI PNG strings for direct HTML embedding."""

    @staticmethod
    def generate_qr_data_uri(payload: Dict[str, Any]) -> str:
        """Encodes structured JSON payload into a PNG QR code data URI."""
        # Sanitize payload: never include credentials, tokens or secrets
        safe_payload = {
            "document_type": payload.get("document_type", ""),
            "display_code": payload.get("display_code", ""),
            "version": payload.get("version", 1),
            "snapshot_hash": payload.get("snapshot_hash", ""),
            "generated_at": payload.get("generated_at", ""),
        }
        raw_json = json.dumps(safe_payload, sort_keys=True, separators=(",", ":"))

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(raw_json)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64_str = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64_str}"
