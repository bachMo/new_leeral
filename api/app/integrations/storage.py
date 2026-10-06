import asyncio
import hashlib
import hmac
import time
import uuid
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Protocol
from urllib.parse import quote, urlencode

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import PROJECT_ROOT, Settings, get_settings
from app.core.errors import AppError, ErrorCode

GUEST_PREFIX = "tmp"
ACCOUNT_PREFIX = "users"


def owner_prefix(user_id: uuid.UUID, *, is_guest: bool) -> str:
    return f"{GUEST_PREFIX if is_guest else ACCOUNT_PREFIX}/{user_id}"


def promoted_key(key: str, user_id: uuid.UUID) -> str:
    parts = PurePosixPath(key).parts
    if len(parts) > 2 and parts[0] == GUEST_PREFIX:
        return str(PurePosixPath(ACCOUNT_PREFIX, str(user_id), *parts[2:]))
    return key


class FileStorage(Protocol):
    async def put(self, key: str, content: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def move(self, source: str, destination: str) -> None: ...

    async def delete(self, keys: list[str]) -> None: ...

    async def delete_prefix(self, prefix: str) -> None: ...

    def signed_url(self, key: str, *, filename: str | None = None) -> str: ...


class R2Storage:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.r2_bucket
        self._ttl = settings.signed_url_ttl_seconds
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id.get_secret_value(),
            aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
            region_name="auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    async def put(self, key: str, content: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )

    async def get(self, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.get_object, Bucket=self._bucket, Key=key
            )
        except ClientError as exc:
            raise AppError(ErrorCode.NOT_FOUND, detail=f"storage object {key}") from exc
        body = response["Body"]
        return await asyncio.to_thread(body.read)

    async def move(self, source: str, destination: str) -> None:
        if source == destination:
            return
        try:
            await asyncio.to_thread(
                self._client.copy_object,
                Bucket=self._bucket,
                Key=destination,
                CopySource={"Bucket": self._bucket, "Key": source},
            )
        except ClientError:
            if await self._exists(destination):
                return
            raise
        await self.delete([source])

    async def _exists(self, key: str) -> bool:
        try:
            await asyncio.to_thread(self._client.head_object, Bucket=self._bucket, Key=key)
        except ClientError:
            return False
        return True

    async def delete(self, keys: list[str]) -> None:
        for start in range(0, len(keys), 1000):
            batch = keys[start : start + 1000]
            await asyncio.to_thread(
                self._client.delete_objects,
                Bucket=self._bucket,
                Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
            )

    async def delete_prefix(self, prefix: str) -> None:
        paginator = self._client.get_paginator("list_objects_v2")

        def list_keys() -> list[str]:
            keys: list[str] = []
            for page in paginator.paginate(Bucket=self._bucket, Prefix=f"{prefix.rstrip('/')}/"):
                keys.extend(item["Key"] for item in page.get("Contents", []))
            return keys

        keys = await asyncio.to_thread(list_keys)
        if keys:
            await self.delete(keys)

    def signed_url(self, key: str, *, filename: str | None = None) -> str:
        params: dict[str, str] = {"Bucket": self._bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f"inline; filename*=UTF-8''{quote(filename)}"
        url: str = self._client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=self._ttl
        )
        return url


class LocalStorage:
    def __init__(self, settings: Settings) -> None:
        self._root = (PROJECT_ROOT / settings.local_storage_path).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._base_url = f"{settings.public_base_url.rstrip('/')}/v1/files"
        self._secret = settings.jwt_secret.get_secret_value().encode()
        self._ttl = settings.signed_url_ttl_seconds

    def path_for(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise AppError(ErrorCode.NOT_FOUND, detail="invalid storage key")
        return path

    async def put(self, key: str, content: bytes, content_type: str) -> None:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, content)

    async def get(self, key: str) -> bytes:
        path = self.path_for(key)
        if not path.is_file():
            raise AppError(ErrorCode.NOT_FOUND, detail=f"storage object {key}")
        return await asyncio.to_thread(path.read_bytes)

    async def move(self, source: str, destination: str) -> None:
        origin = self.path_for(source)
        target = self.path_for(destination)
        if source == destination or (not origin.exists() and target.exists()):
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(origin.replace, target)

    async def delete(self, keys: list[str]) -> None:
        for key in keys:
            self.path_for(key).unlink(missing_ok=True)

    async def delete_prefix(self, prefix: str) -> None:
        directory = self.path_for(prefix)
        if directory.is_dir():
            for path in sorted(directory.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                else:
                    path.rmdir()
            directory.rmdir()

    def signed_url(self, key: str, *, filename: str | None = None) -> str:
        expires = int(time.time()) + self._ttl
        query = {"expires": str(expires), "signature": self.signature(key, expires)}
        return f"{self._base_url}/{quote(key)}?{urlencode(query)}"

    def signature(self, key: str, expires: int) -> str:
        message = f"{key}:{expires}".encode()
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()

    def verify(self, key: str, expires: int, signature: str) -> bool:
        if expires < time.time():
            return False
        return hmac.compare_digest(self.signature(key, expires), signature)


@lru_cache
def get_storage() -> FileStorage:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorage(settings)
    return R2Storage(settings)
