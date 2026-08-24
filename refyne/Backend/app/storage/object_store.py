import abc
import os
from io import BytesIO


class ObjectStore(abc.ABC):
    """Abstract interface for object storage."""

    @abc.abstractmethod
    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload data to storage. Returns the storage key."""

    @abc.abstractmethod
    def download(self, key: str) -> bytes:
        """Download data from storage by key."""

    @abc.abstractmethod
    def delete(self, key: str) -> None:
        """Delete an object from storage by key."""

    @abc.abstractmethod
    def exists(self, key: str) -> bool:
        """Check if an object exists in storage."""


class LocalObjectStore(ObjectStore):
    """Local filesystem object store for development."""

    def __init__(self, base_dir: str = "data/objects"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_path(self, key: str) -> str:
        return os.path.join(self.base_dir, key)

    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._get_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return key

    def download(self, key: str) -> bytes:
        path = self._get_path(key)
        with open(path, "rb") as f:
            return f.read()

    def delete(self, key: str) -> None:
        path = self._get_path(key)
        if os.path.exists(path):
            os.remove(path)

    def exists(self, key: str) -> bool:
        return os.path.exists(self._get_path(key))


class MinIOObjectStore(ObjectStore):
    """MinIO/S3-compatible object store."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = False):
        from minio import Minio
        self.bucket = bucket
        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)

    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.client.put_object(
            self.bucket,
            key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return key

    def download(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete(self, key: str) -> None:
        self.client.remove_object(self.bucket, key)

    def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except Exception:
            return False


_store_instance: ObjectStore | None = None


def get_object_store() -> ObjectStore:
    """Get the configured object store instance."""
    global _store_instance
    if _store_instance is None:
        backend = os.environ.get("OBJECT_STORE_BACKEND", "local")
        if backend == "minio":
            _store_instance = MinIOObjectStore(
                endpoint=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
                access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
                secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
                bucket=os.environ.get("MINIO_BUCKET", "refyne"),
                secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
            )
        else:
            base_dir = os.environ.get("OBJECT_STORAGE_PATH", "data/objects")
            _store_instance = LocalObjectStore(base_dir=base_dir)
    return _store_instance
