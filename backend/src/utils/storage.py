from abc import ABC, abstractmethod

import structlog

logger = structlog.get_logger()


class StorageProvider(ABC):
    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str) -> str: ...

    @abstractmethod
    async def download(self, key: str) -> bytes: ...


class NullStorage(StorageProvider):
    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        return ""

    async def download(self, key: str) -> bytes:
        return b""


class R2Storage(StorageProvider):
    def __init__(
        self,
        account_id: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        public_url: str = "",
    ):
        import boto3

        self._bucket = bucket
        self._public_url = public_url
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        import asyncio

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            ),
        )
        if self._public_url:
            return f"{self._public_url}/{key}"
        return key

    async def download(self, key: str) -> bytes:
        import asyncio

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.get_object(Bucket=self._bucket, Key=key),
        )
        return response["Body"].read()


def create_storage(
    account_id: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    public_url: str = "",
) -> StorageProvider:
    if account_id and access_key and secret_key:
        return R2Storage(
            account_id=account_id,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            public_url=public_url,
        )
    return NullStorage()
