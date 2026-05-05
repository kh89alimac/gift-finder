"""S3 client for image uploads.

We use ``aioboto3`` so uploads don't block the event loop. Before upload we
strip EXIF metadata via Pillow — phone photos routinely contain GPS coords
and we never want those leaking to public CDN URLs.
"""

from __future__ import annotations

import io
from typing import Any

import aioboto3  # type: ignore[import-untyped]
from PIL import Image

from app.core.config import settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.core.logging import get_logger

# Pillow refuses to decode anything beyond ``Image.MAX_IMAGE_PIXELS`` — set it
# globally so any code path that opens an image is protected against
# decompression-bomb attacks.
Image.MAX_IMAGE_PIXELS = 24_000_000  # ~24 megapixels max

log = get_logger(__name__)

# Magic-byte signatures we accept. Browsers can lie about Content-Type, so we
# verify the actual bytes match a known image format.
_IMAGE_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",  # WebP also has WEBP at offset 8
}

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def detect_image_mime(data: bytes) -> str | None:
    """Return the detected mime type from magic bytes, or None.

    For RIFF/WebP we additionally check the secondary marker.
    """
    for magic, mime in _IMAGE_MAGIC.items():
        if data.startswith(magic):
            if magic == b"RIFF" and len(data) >= 12 and data[8:12] != b"WEBP":
                continue
            return mime
    return None


def strip_exif(data: bytes) -> tuple[bytes, str]:
    """Re-encode ``data`` without any metadata.

    Returns ``(cleaned_bytes, content_type)`` — content type is derived from
    the format we *write* (always JPEG or PNG) rather than ``img.format``,
    which can be misleading after polyglot uploads.

    Also enforces a 24-megapixel cap as defence against decompression-bomb
    attacks: a tiny PNG/GIF can decode to gigabytes of pixel data.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            # Check dimensions before ``load()`` actually decompresses pixels.
            w, h = img.size
            if w * h > 24_000_000:
                raise ValueError(
                    f"Image too large: {w}x{h} = {w * h} pixels (max 24MP)"
                )

            img.load()  # Now safe to load.

            # Force output to one of two safe formats only — never propagate
            # exotic input formats (TIFF, BMP, …) or trust ``img.format``.
            output_format = "JPEG"
            if img.mode in ("RGBA", "P", "LA"):
                output_format = "PNG"

            # JPEG can't carry alpha — flatten if needed.
            if output_format == "JPEG" and img.mode != "RGB":
                img = img.convert("RGB")

            out = io.BytesIO()
            img.save(out, format=output_format)
            return out.getvalue(), f"image/{output_format.lower()}"
    except Exception as exc:
        # Any decode failure is a validation error, not an internal one.
        raise ValidationError(f"Image could not be processed: {exc}") from exc


def validate_image(data: bytes) -> str:
    """Validate size + magic bytes; return the detected mime type."""
    if len(data) == 0:
        raise ValidationError("Empty file")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationError(
            f"Image exceeds maximum size of {MAX_IMAGE_BYTES // (1024 * 1024)} MB"
        )
    mime = detect_image_mime(data)
    if mime is None:
        raise ValidationError("File is not a recognized image format")
    return mime


# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------


def _session() -> aioboto3.Session:
    return aioboto3.Session(
        aws_access_key_id=(
            settings.AWS_ACCESS_KEY_ID.get_secret_value()
            if settings.AWS_ACCESS_KEY_ID
            else None
        ),
        aws_secret_access_key=(
            settings.AWS_SECRET_ACCESS_KEY.get_secret_value()
            if settings.AWS_SECRET_ACCESS_KEY
            else None
        ),
        region_name=settings.S3_REGION,
    )


async def upload_file(
    key: str,
    data: bytes,
    content_type: str,
    *,
    bucket: str | None = None,
    cache_control: str = "public, max-age=31536000",
) -> str:
    """Upload bytes to S3. Returns the public/CDN URL.

    Caller is responsible for choosing a unique ``key`` (we don't auto-generate
    here so tests can assert specific keys).
    """
    target_bucket = bucket or settings.S3_BUCKET
    extra: dict[str, Any] = {
        "ContentType": content_type,
        "CacheControl": cache_control,
    }

    session = _session()
    try:
        async with session.client(
            "s3", endpoint_url=settings.S3_ENDPOINT_URL
        ) as s3:
            await s3.put_object(
                Bucket=target_bucket,
                Key=key,
                Body=data,
                **extra,
            )
    except Exception as exc:
        log.error("s3.upload.failed", key=key, error=str(exc))
        raise ExternalServiceError(f"S3 upload failed: {exc}") from exc

    if settings.CDN_BASE_URL:
        return f"{settings.CDN_BASE_URL.rstrip('/')}/{key}"
    if settings.S3_ENDPOINT_URL:
        return f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{target_bucket}/{key}"
    return f"https://{target_bucket}.s3.{settings.S3_REGION}.amazonaws.com/{key}"


async def generate_presigned_url(
    key: str, *, expiry: int = 3600, bucket: str | None = None
) -> str:
    """Generate a temporary GET URL for a private object."""
    target_bucket = bucket or settings.S3_BUCKET
    session = _session()
    async with session.client(
        "s3", endpoint_url=settings.S3_ENDPOINT_URL
    ) as s3:
        return await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": target_bucket, "Key": key},
            ExpiresIn=expiry,
        )


async def upload_image(key: str, raw: bytes) -> tuple[str, str]:
    """Validate, strip EXIF, and upload an image. Returns ``(url, mime)``.

    The mime returned reflects what we actually *wrote* to S3 (JPEG/PNG),
    not what the upload claimed — see :func:`strip_exif`.
    """
    validate_image(raw)
    cleaned, mime = strip_exif(raw)
    url = await upload_file(key, cleaned, mime)
    return url, mime
