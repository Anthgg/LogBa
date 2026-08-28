from typing import BinaryIO, Protocol


class ObjectStorageProtocol(Protocol):
    """Boundary contract for the object storage and evidence management service (Target: F030)."""

    def upload_file(self, bucket: str, path: str, file_obj: BinaryIO, content_type: str) -> str: ...

    def get_signed_url(self, bucket: str, path: str, expires_in_seconds: int = 3600) -> str: ...
