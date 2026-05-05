"""Manual ingestion service: admin item entry + CSV bulk import + image upload."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.safe_http import validate_display_url
from app.integrations.s3_client import upload_image, validate_image
from app.models.catalog import Item, ItemTag
from app.models.enums import ItemSource, ItemStatus
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.ingestion import CsvImportResult, CsvImportRowError, ImageUploadResponse
from app.schemas.items import ItemManualIn, ItemManualUpdate

log = get_logger(__name__)

REQUIRED_CSV_COLUMNS = {"title"}
OPTIONAL_CSV_COLUMNS = {
    "description",
    "price",
    "currency",
    "image_url",
    "product_url",
    "brand",
    "retailer",
    "tag_slugs",  # comma-separated
    "publish",
}


class ManualIngestionService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ---------------------------------------------------- create item
    async def create_item(
        self, data: ItemManualIn, admin_user_id: uuid.UUID
    ) -> Item:
        item = Item(
            title=data.title,
            description=data.description,
            price=data.price,
            currency=data.currency,
            image_url=str(data.image_url) if data.image_url else None,
            product_url=str(data.product_url) if data.product_url else None,
            brand=data.brand,
            retailer=data.retailer,
            source=ItemSource.MANUAL,
            status=ItemStatus.ACTIVE if data.publish else ItemStatus.PENDING_REVIEW,
            reviewed_by=admin_user_id if data.publish else None,
            reviewed_at=datetime.now(timezone.utc) if data.publish else None,
            published_at=datetime.now(timezone.utc) if data.publish else None,
        )
        self.uow.session.add(item)
        await self.uow.session.flush()

        for tid in data.tag_ids:
            self.uow.session.add(ItemTag(item_id=item.id, tag_id=tid))
        await self.uow.session.flush()
        return item

    # ----------------------------------------------------- update item
    async def update_item(
        self,
        item_id: uuid.UUID,
        data: ItemManualUpdate,
        admin_user_id: uuid.UUID,
    ) -> Item:
        item = await self.uow.items.get_by_id(item_id)
        if item is None:
            raise NotFoundError(f"Item {item_id} not found")

        changes: dict[str, Any] = data.model_dump(exclude_unset=True, exclude={"tag_ids"})
        if data.image_url is not None:
            changes["image_url"] = str(data.image_url)
        if data.product_url is not None:
            changes["product_url"] = str(data.product_url)
        if data.status is not None:
            changes["reviewed_by"] = admin_user_id
            changes["reviewed_at"] = datetime.now(timezone.utc)
            if data.status == ItemStatus.ACTIVE and item.published_at is None:
                changes["published_at"] = datetime.now(timezone.utc)

        if changes:
            await self.uow.items.update(item, **changes)

        # Replace tags atomically if provided.
        if data.tag_ids is not None:
            from sqlalchemy import delete

            await self.uow.session.execute(
                delete(ItemTag).where(ItemTag.item_id == item_id)
            )
            for tid in data.tag_ids:
                self.uow.session.add(ItemTag(item_id=item.id, tag_id=tid))
        await self.uow.session.flush()
        return item

    # --------------------------------------------------- image upload
    async def upload_image(
        self,
        item_id: uuid.UUID,
        file_bytes: bytes,
        admin_user_id: uuid.UUID,
        *,
        filename: str | None = None,
    ) -> ImageUploadResponse:
        item = await self.uow.items.get_by_id(item_id)
        if item is None:
            raise NotFoundError(f"Item {item_id} not found")

        ext = "jpg"
        if filename and "." in filename:
            ext_candidate = filename.rsplit(".", 1)[1].lower()
            if ext_candidate in {"jpg", "jpeg", "png", "gif", "webp"}:
                ext = "jpeg" if ext_candidate == "jpg" else ext_candidate

        validate_image(file_bytes)
        key = f"items/{item_id}/{uuid.uuid4().hex}.{ext}"
        url, _mime = await upload_image(key, file_bytes)

        await self.uow.items.update(item, image_url=url, image_s3_key=key)
        return ImageUploadResponse(item_id=item_id, image_url=url, image_s3_key=key)

    # ---------------------------------------------------- CSV import
    async def import_csv(
        self,
        file_content: bytes,
        admin_user_id: uuid.UUID,
    ) -> CsvImportResult:
        try:
            text = file_content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError(f"CSV must be UTF-8: {exc}") from exc

        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise ValidationError("CSV is empty")
        cols = {c.strip().lower() for c in reader.fieldnames}
        missing = REQUIRED_CSV_COLUMNS - cols
        if missing:
            raise ValidationError(
                f"CSV is missing required columns: {sorted(missing)}",
                details={"required": sorted(REQUIRED_CSV_COLUMNS)},
            )

        total = 0
        inserted = 0
        updated = 0
        skipped = 0
        errors: list[CsvImportRowError] = []

        # Pre-load tag slug -> id map once instead of per row.
        from sqlalchemy import select

        from app.models.taxonomy import Tag

        slug_map: dict[str, int] = {}
        all_tags = await self.uow.session.execute(select(Tag.id, Tag.slug))
        for tid, slug in all_tags.all():
            slug_map[slug] = tid

        for i, row in enumerate(reader, start=2):  # row 1 is the header
            total += 1
            row_errors: list[str] = []

            normalized = {
                (k or "").strip().lower(): (v.strip() if v else "")
                for k, v in row.items()
            }
            title = normalized.get("title")
            if not title:
                row_errors.append("title is required")

            price = _parse_decimal(normalized.get("price"))
            currency = (normalized.get("currency") or "USD").upper()[:3]
            if len(currency) != 3:
                row_errors.append("currency must be 3 letters")
            publish = (normalized.get("publish") or "").lower() in {"1", "true", "yes"}

            tag_slugs = [
                s.strip().lower()
                for s in (normalized.get("tag_slugs") or "").split(",")
                if s.strip()
            ]
            unknown_slugs = [s for s in tag_slugs if s not in slug_map]
            if unknown_slugs:
                row_errors.append(f"unknown tag slugs: {unknown_slugs}")

            if row_errors:
                skipped += 1
                errors.append(CsvImportRowError(row_number=i, errors=row_errors))
                continue

            try:
                tag_ids = [slug_map[s] for s in tag_slugs]
                # Strip any non-http(s) URLs from imported rows — same guard
                # as the scraper pipeline so we can't be fed a CSV with
                # ``javascript:`` payloads as image/product URLs.
                image_url = validate_display_url(
                    normalized.get("image_url") or None
                )
                product_url = validate_display_url(
                    normalized.get("product_url") or None
                )
                # Use a SAVEPOINT so a per-row failure doesn't poison the
                # whole transaction. We commit on success of the savepoint;
                # on failure we roll back to the savepoint and the outer
                # transaction stays usable.
                async with self.uow.session.begin_nested():
                    item = Item(
                        title=title[:500] if title else "",
                        description=normalized.get("description") or None,
                        price=price,
                        currency=currency,
                        image_url=image_url,
                        product_url=product_url,
                        brand=normalized.get("brand") or None,
                        retailer=normalized.get("retailer") or None,
                        source=ItemSource.CSV_IMPORT,
                        status=(
                            ItemStatus.ACTIVE if publish else ItemStatus.PENDING_REVIEW
                        ),
                        reviewed_by=admin_user_id if publish else None,
                        reviewed_at=datetime.now(timezone.utc) if publish else None,
                        published_at=datetime.now(timezone.utc) if publish else None,
                    )
                    self.uow.session.add(item)
                    await self.uow.session.flush()
                    for tid in tag_ids:
                        self.uow.session.add(ItemTag(item_id=item.id, tag_id=tid))
                inserted += 1
            except Exception as exc:  # DB-level failure for this row
                skipped += 1
                errors.append(CsvImportRowError(row_number=i, errors=[str(exc)]))

        return CsvImportResult(
            total_rows=total,
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            errors=errors,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_decimal(text: str | None) -> Decimal | None:
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None
