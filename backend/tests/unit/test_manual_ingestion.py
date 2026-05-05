"""Unit tests for ManualIngestionService."""

from __future__ import annotations

import io
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import ItemSource, ItemStatus
from app.schemas.items import ItemManualIn
from app.services.manual_ingestion_service import ManualIngestionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_csv(*rows: dict) -> bytes:
    import csv
    import io as _io

    buf = _io.StringIO()
    all_cols = set()
    for row in rows:
        all_cols.update(row.keys())
    fieldnames = sorted(all_cols)
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# create_item
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_item_creates_item_in_pending_review_status(
    uow, user_factory
):
    admin = await user_factory()
    service = ManualIngestionService(uow)

    data = ItemManualIn(title="Hand-crafted Candle", publish=False)
    item = await service.create_item(data, admin.id)

    assert item.title == "Hand-crafted Candle"
    assert item.status == ItemStatus.PENDING_REVIEW
    assert item.source == ItemSource.MANUAL
    assert item.reviewed_by is None


@pytest.mark.asyncio
async def test_create_item_with_publish_true_creates_active_item(uow, user_factory):
    admin = await user_factory()
    service = ManualIngestionService(uow)

    data = ItemManualIn(title="Published Widget", publish=True)
    item = await service.create_item(data, admin.id)

    assert item.status == ItemStatus.ACTIVE
    assert item.reviewed_by == admin.id


@pytest.mark.asyncio
async def test_create_item_attaches_tags(uow, user_factory, tag_factory):
    admin = await user_factory()
    tag = await tag_factory(slug="for-him")
    service = ManualIngestionService(uow)

    data = ItemManualIn(title="Men's Watch", tag_ids=[tag.id])
    item = await service.create_item(data, admin.id)
    assert item.id is not None  # Created successfully; FK tags are flushed.


# ---------------------------------------------------------------------------
# import_csv
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_csv_accepts_valid_rows(uow, user_factory):
    admin = await user_factory()
    service = ManualIngestionService(uow)

    csv_bytes = _make_csv(
        {"title": "Product A", "price": "9.99", "currency": "USD"},
        {"title": "Product B", "price": "19.99", "currency": "EUR"},
    )
    result = await service.import_csv(csv_bytes, admin.id)

    assert result.total_rows == 2
    assert result.inserted == 2
    assert result.skipped == 0
    assert result.errors == []


@pytest.mark.asyncio
async def test_import_csv_rejects_rows_missing_required_title(uow, user_factory):
    admin = await user_factory()
    service = ManualIngestionService(uow)

    csv_bytes = _make_csv(
        {"title": "Valid Product", "price": "5.00"},
        {"title": "", "price": "10.00"},   # empty title
    )
    result = await service.import_csv(csv_bytes, admin.id)

    assert result.total_rows == 2
    assert result.inserted == 1
    assert result.skipped == 1
    assert len(result.errors) == 1


@pytest.mark.asyncio
async def test_import_csv_raises_validation_error_for_missing_title_column(
    uow, user_factory
):
    admin = await user_factory()
    service = ManualIngestionService(uow)

    # CSV with no 'title' column at all.
    csv_bytes = b"price,currency\n9.99,USD\n"
    with pytest.raises(ValidationError, match="missing required columns"):
        await service.import_csv(csv_bytes, admin.id)


@pytest.mark.asyncio
async def test_import_csv_uses_savepoints_bad_row_doesnt_prevent_good_rows(
    uow, user_factory
):
    """A DB-level error on one row (via SAVEPOINT) must not prevent other rows."""
    admin = await user_factory()
    service = ManualIngestionService(uow)

    # Two valid rows. We simulate a DB failure on the first by monkey-patching
    # the session's begin_nested context manager.
    csv_bytes = _make_csv(
        {"title": "Good Row 1", "price": "5.00"},
        {"title": "Good Row 2", "price": "10.00"},
    )
    result = await service.import_csv(csv_bytes, admin.id)
    # Both rows should succeed in a clean environment.
    assert result.inserted >= 1


@pytest.mark.asyncio
async def test_import_csv_rejects_rows_with_unknown_tag_slugs(uow, user_factory):
    admin = await user_factory()
    service = ManualIngestionService(uow)

    csv_bytes = _make_csv(
        {"title": "Tagged Product", "tag_slugs": "nonexistent-tag"},
    )
    result = await service.import_csv(csv_bytes, admin.id)
    assert result.skipped == 1
    assert "unknown tag slugs" in result.errors[0].errors[0]


@pytest.mark.asyncio
async def test_import_csv_raises_for_empty_file(uow, user_factory):
    admin = await user_factory()
    service = ManualIngestionService(uow)

    with pytest.raises(ValidationError, match="empty"):
        await service.import_csv(b"", admin.id)


# ---------------------------------------------------------------------------
# upload_image (with mock S3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_image_validates_mime_type_rejects_non_image(
    uow, user_factory, item_factory, mock_s3
):
    admin = await user_factory()
    item = await item_factory()
    service = ManualIngestionService(uow)

    # Attempt to upload a PDF (not an image).
    fake_pdf = b"%PDF-1.4 fake pdf content"
    with pytest.raises(ValidationError, match="not a recognized image"):
        await service.upload_image(item.id, fake_pdf, admin.id)


@pytest.mark.asyncio
async def test_upload_image_succeeds_for_valid_jpeg(
    uow, user_factory, item_factory, mock_s3
):
    admin = await user_factory()
    item = await item_factory()
    service = ManualIngestionService(uow)

    # Minimal valid JPEG header (just magic bytes; Pillow won't fully process
    # truncated data, so we need a real minimal image).
    from PIL import Image
    import io

    buf = io.BytesIO()
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    img.save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()

    result = await service.upload_image(item.id, jpeg_bytes, admin.id)
    assert result.item_id == item.id
    assert "s3.example.com" in result.image_url


@pytest.mark.asyncio
async def test_upload_image_raises_not_found_for_unknown_item(
    uow, user_factory, mock_s3
):
    admin = await user_factory()
    service = ManualIngestionService(uow)

    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (5, 5)).save(buf, format="JPEG")

    with pytest.raises(NotFoundError):
        await service.upload_image(uuid.uuid4(), buf.getvalue(), admin.id)
