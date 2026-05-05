"""Pytest configuration and shared fixtures for the Gift Finder test suite.

Strategy
--------
* All tests run against an **in-process SQLite** database (via aiosqlite).
  PostgreSQL-specific constructs (pgvector, TSVECTOR, JSONB, ARRAY, pg_insert ON
  CONFLICT, ENUM types) are shimmed with SQLite-compatible equivalents supplied
  through monkeypatching and import-time overrides below.

* The ``async_session`` fixture yields an ``AsyncSession`` that is rolled back
  after every test, so the DB is always in a clean state without recreating
  schema.

* The ``test_client`` fixture builds an ``httpx.AsyncClient`` wired to the
  FastAPI app with ``get_uow``, ``get_db``, and Redis/OpenAI/S3 dependencies
  overridden.

* All third-party I/O (Redis, OpenAI, S3) is replaced with in-memory fakes.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, String, Text, event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ---------------------------------------------------------------------------
# Override Settings *before* any app import resolves settings at module level.
# ---------------------------------------------------------------------------

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only-32chars!")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# Shim PostgreSQL-only types BEFORE any model imports.
# Models declare their columns at class-body time, so the replacement types
# must be in place before the class body executes.
# ---------------------------------------------------------------------------


def _install_pg_shims() -> None:
    """Replace PostgreSQL-only SQLAlchemy types with SQLite-compatible ones."""
    from sqlalchemy import JSON, String, Text
    from sqlalchemy.types import UserDefinedType

    # --- pgvector ---
    class _FakeVectorType(UserDefinedType):
        """A plain JSON column that stores embedding lists as JSON arrays."""

        cache_ok = True

        def __init__(self, dim: int = 1536):
            self.dim = dim

        def get_col_spec(self, **kwargs):
            return "TEXT"

    fake_pgvector_module = MagicMock()
    fake_pgvector_module.Vector = _FakeVectorType
    sys.modules.setdefault("pgvector", fake_pgvector_module)
    sys.modules.setdefault("pgvector.sqlalchemy", fake_pgvector_module)

    # --- sqlalchemy.dialects.postgresql ---
    # Patch the dialect-specific types used in model column definitions so
    # SQLite create_all doesn't fail on unknown types.
    import sqlalchemy.dialects.postgresql as _pg_dialect

    class _FakeEnum(String):
        """Fake ENUM that compiles to VARCHAR for SQLite."""

        def __init__(self, *args, name=None, create_type=True, values_callable=None, **kwargs):
            super().__init__(length=50)

        # SQLAlchemy calls process_bind_param on inserts.
        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            return str(value.value) if hasattr(value, "value") else str(value)

        def process_result_value(self, value, dialect):
            return value

    class _FakeJSONB(JSON):
        pass

    class _FakeTSVECTOR(Text):
        pass

    class _FakeARRAY(JSON):
        def __init__(self, *args, **kwargs):
            super().__init__()

    from sqlalchemy import TypeDecorator as _TypeDecorator

    class _FakeUUID(_TypeDecorator):
        """UUID stored as a 36-char string in SQLite."""

        impl = String(36)
        cache_ok = True

        def __init__(self, as_uuid: bool = False, **kwargs):
            super().__init__()
            self.as_uuid = as_uuid

        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            return str(value)

        def process_result_value(self, value, dialect):
            if value is None:
                return None
            if self.as_uuid:
                try:
                    return uuid.UUID(str(value))
                except (ValueError, AttributeError):
                    return value
            return value

    # Patch the dialect module attributes in-place.
    _pg_dialect.ENUM = _FakeEnum
    _pg_dialect.JSONB = _FakeJSONB
    _pg_dialect.TSVECTOR = _FakeTSVECTOR
    _pg_dialect.ARRAY = _FakeARRAY
    _pg_dialect.UUID = _FakeUUID

    # Patch ``pg_insert`` to fall back to a plain SQLAlchemy ``insert``.
    # The repositories that use ``pg_insert ... on_conflict_do_update`` will
    # fail on SQLite; those code paths are either guarded by ``mock.patch``
    # in the relevant tests or use the standard ``insert`` fallback below.
    from sqlalchemy import insert as _sa_insert

    class _SafeInsert:
        """Wraps sqlalchemy.insert and silently drops on_conflict_do_update."""

        def __init__(self, table):
            self._stmt = _sa_insert(table)
            self._table = table

        def values(self, *args, **kwargs):
            self._stmt = self._stmt.values(*args, **kwargs)
            return self

        def on_conflict_do_update(self, **kwargs):
            # SQLite doesn't support ON CONFLICT DO UPDATE with a constraint
            # name — just return the INSERT statement as-is (INSERT OR IGNORE
            # would be the closest, but for tests we prefer simple inserts).
            return self._stmt

        def on_conflict_do_nothing(self, **kwargs):
            return self._stmt

        def returning(self, *cols):
            self._stmt = self._stmt.returning(*cols)
            return self

    _pg_dialect.insert = _SafeInsert

    # The models import these via ``from sqlalchemy.dialects.postgresql import ...``
    # which reads the module at import time. We need to patch those name bindings
    # in submodules that have already captured the originals, if any. Since we
    # patch *before* model imports, the above is sufficient.


_install_pg_shims()

# Patch get_settings before it's cached.
from app.core.config import get_settings as _get_settings

_get_settings.cache_clear()

# Now safe to import models (triggers class-body execution with shimmed types).
from app.models.base import Base  # noqa: E402 - after patches

# Import all model modules so Base.metadata is fully populated.
import app.models.catalog  # noqa: F401
import app.models.user  # noqa: F401
import app.models.taxonomy  # noqa: F401
import app.models.ingestion  # noqa: F401
import app.models.admin  # noqa: F401


def _strip_pg_server_defaults() -> None:
    """Remove PostgreSQL-specific server_default expressions from all columns.

    Expressions like ``'{}'::jsonb``, ``'pending_review'::item_status``, and
    ``gen_random_uuid()`` are valid in PostgreSQL but break SQLite's DDL parser.
    We strip them so ``create_all`` succeeds on SQLite; Python-side defaults
    in the tests (factories, explicit values) provide the necessary values.
    """
    import re
    from datetime import timezone as _timezone

    import uuid as _uuid
    from sqlalchemy.sql.schema import ColumnDefault

    _UUID_RE = re.compile(r"gen_random_uuid\(\)")
    _NOW_RE = re.compile(r"\bNOW\s*\(\s*\)", re.I)
    # Matches ``'literal_value'::some_type`` — capture the literal.
    _CAST_RE = re.compile(r"^'(.*?)'::[a-z_\[\]]+$", re.DOTALL)
    # Empty array/JSONB → Python list default.
    _EMPTY_ARRAY_RE = re.compile(r"'\{\}'::(?:jsonb|text\[\]|_text|anyarray)")
    # Patterns to strip without injecting a value:
    _STRIP_PATTERNS = (
        re.compile(r"websearch_to_tsquery"),
    )

    def _utcnow():
        return datetime.now(_timezone.utc)

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if col.server_default is not None:
                try:
                    expr_text = str(col.server_default.arg).strip()
                    if _UUID_RE.search(expr_text):
                        col.server_default = None
                        col.default = ColumnDefault(_uuid.uuid4)
                        continue
                    if _NOW_RE.search(expr_text):
                        col.server_default = None
                        col.default = ColumnDefault(_utcnow)
                        continue
                    if _EMPTY_ARRAY_RE.search(expr_text):
                        col.server_default = None
                        col.default = ColumnDefault(dict)
                        continue
                    # Extract literal from 'value'::type and use it as a Python default.
                    cast_m = _CAST_RE.match(expr_text)
                    if cast_m:
                        literal = cast_m.group(1)
                        col.server_default = None
                        col.default = ColumnDefault(literal)
                        continue
                    for pattern in _STRIP_PATTERNS:
                        if pattern.search(expr_text):
                            col.server_default = None
                            break
                except Exception:
                    col.server_default = None


_strip_pg_server_defaults()


def _fix_sqlite_integer_pks() -> None:
    """In SQLite only INTEGER PRIMARY KEY (spelled exactly) acts as a rowid alias.

    SmallInteger / BigInteger primary keys with autoincrement don't get that
    behaviour, so SQLite raises NOT NULL on insert.  Replace those column types
    with plain Integer so SQLAlchemy emits ``INTEGER`` in the CREATE TABLE DDL.
    """
    from sqlalchemy import BigInteger, Integer, SmallInteger

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if col.primary_key and col.autoincrement is True:
                if isinstance(col.type, (SmallInteger, BigInteger)):
                    col.type = Integer()


_fix_sqlite_integer_pks()

# ---------------------------------------------------------------------------
# Async engine + session factory for tests (SQLite in-memory)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop required by pytest-asyncio with session scope."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    """Create a single shared in-memory SQLite engine for the whole session."""
    eng = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    # SQLite doesn't enforce FK constraints by default.
    @event.listens_for(eng.sync_engine, "connect")
    def _set_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with eng.begin() as conn:
        # Create all tables. Models using PostgreSQL-specific types (ENUM,
        # TSVECTOR, JSONB, ARRAY, Vector) must be patched before this runs.
        await conn.run_sync(Base.metadata.create_all)

    yield eng

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture()
async def async_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield a per-test ``AsyncSession`` that always rolls back on teardown.

    We use ``autobegin=False`` so we can explicitly begin/rollback a transaction
    that spans the entire test body, guaranteeing a clean slate on teardown.
    """
    factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession, autobegin=False
    )
    async with factory() as session:
        await session.begin()
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def session_factory(engine: AsyncEngine):
    """Return an async_sessionmaker that creates sessions against the test engine."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ---------------------------------------------------------------------------
# Mock Redis (in-memory dict)
# ---------------------------------------------------------------------------


class _InMemoryRedis:
    """Minimal fake that covers the operations used by security.py."""

    def __init__(self):
        self._data: dict[str, Any] = {}
        self._sets: dict[str, set] = {}
        self._expiries: dict[str, int] = {}

    async def setex(self, key: str, ttl: int, value: Any) -> None:
        self._data[key] = value
        self._expiries[key] = ttl

    async def get(self, key: str) -> Any:
        return self._data.get(key)

    async def exists(self, key: str) -> int:
        return 1 if key in self._data else 0

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for k in keys:
            if k in self._data:
                del self._data[k]
                deleted += 1
            if k in self._sets:
                del self._sets[k]
        return deleted

    async def sadd(self, key: str, *members: Any) -> int:
        if key not in self._sets:
            self._sets[key] = set()
        before = len(self._sets[key])
        self._sets[key].update(members)
        return len(self._sets[key]) - before

    async def smembers(self, key: str) -> set:
        return self._sets.get(key, set())

    async def expire(self, key: str, ttl: int) -> int:
        self._expiries[key] = ttl
        return 1

    async def ping(self) -> bool:
        return True

    def clear(self):
        self._data.clear()
        self._sets.clear()
        self._expiries.clear()


_redis_instance = _InMemoryRedis()


@pytest.fixture(autouse=True)
def mock_redis():
    """Auto-use: replace the global Redis client with an in-memory fake."""
    _redis_instance.clear()
    with patch("app.core.redis.get_redis", return_value=_redis_instance), \
         patch("app.core.security.get_redis", return_value=_redis_instance):
        yield _redis_instance


# ---------------------------------------------------------------------------
# Mock OpenAI
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_openai(mocker):
    """Mock ``embed_texts`` and ``extract_gift_filters`` in the openai_client module."""
    dummy_embedding = [0.1] * 1536

    mock_embed = mocker.patch(
        "app.integrations.openai_client.embed_texts",
        new_callable=AsyncMock,
        return_value=[dummy_embedding],
    )
    mocker.patch(
        "app.integrations.openai_client.embed_one",
        new_callable=AsyncMock,
        return_value=dummy_embedding,
    )
    # Also patch the references captured at import time in consuming modules.
    mocker.patch(
        "app.services.search_service.embed_one",
        new_callable=AsyncMock,
        return_value=dummy_embedding,
    )
    mocker.patch(
        "app.workers.tasks.embed.embed_one",
        new_callable=AsyncMock,
        return_value=dummy_embedding,
    )

    from app.integrations.openai_client import GiftFilterExtraction

    _extraction = GiftFilterExtraction(
        interest_keywords=["tech", "gadgets"],
        occasion_keywords=["birthday"],
        recipient_keywords=["him"],
        price_min=20.0,
        price_max=100.0,
        cleaned_query="tech gadgets",
    )
    mocker.patch(
        "app.integrations.openai_client.extract_gift_filters",
        new_callable=AsyncMock,
        return_value=_extraction,
    )
    # Return the service-level mock so assertions on mock_openai["extract"]
    # see actual calls (the service imports extract_gift_filters at load time).
    mock_extract = mocker.patch(
        "app.services.search_service.extract_gift_filters",
        new_callable=AsyncMock,
        return_value=_extraction,
    )

    from app.integrations.openai_client import CategorizationSuggestion

    _suggest_mock = CategorizationSuggestion(
        interest_slugs=["tech"],
        occasion_slugs=["birthday"],
        recipient_slugs=["him"],
        confidence=0.9,
    )
    mocker.patch(
        "app.integrations.openai_client.suggest_tags_for_item",
        new_callable=AsyncMock,
        return_value=_suggest_mock,
    )
    # Also patch the reference captured by the scraper orchestrator at import time.
    mocker.patch(
        "app.services.scraper_orchestrator.suggest_tags_for_item",
        new_callable=AsyncMock,
        return_value=_suggest_mock,
    )

    return {"embed": mock_embed, "extract": mock_extract}


# ---------------------------------------------------------------------------
# Mock S3
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_s3(mocker):
    """Replace S3 upload functions with stubs that return fake URLs."""
    mock_upload = mocker.patch(
        "app.integrations.s3_client.upload_file",
        new_callable=AsyncMock,
        return_value="https://s3.example.com/test-key",
    )
    mock_presign = mocker.patch(
        "app.integrations.s3_client.generate_presigned_url",
        new_callable=AsyncMock,
        return_value="https://s3.example.com/presigned/test-key",
    )
    mock_upload_image = mocker.patch(
        "app.integrations.s3_client.upload_image",
        new_callable=AsyncMock,
        return_value=("https://s3.example.com/items/test.jpg", "image/jpeg"),
    )
    # Also patch manual_ingestion_service's direct import
    mocker.patch(
        "app.services.manual_ingestion_service.upload_image",
        new_callable=AsyncMock,
        return_value=("https://s3.example.com/items/test.jpg", "image/jpeg"),
    )
    return {
        "upload": mock_upload,
        "presign": mock_presign,
        "upload_image": mock_upload_image,
    }


# ---------------------------------------------------------------------------
# Unit-of-Work fixture bound to test session
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def uow(async_session: AsyncSession):
    """A UnitOfWork whose session is the test session (no auto-commit)."""
    from app.repositories.unit_of_work import UnitOfWork
    from app.repositories.items import ItemRepository
    from app.repositories.wishlists import WishlistRepository
    from app.repositories.tags import TagRepository
    from app.repositories.scraper_jobs import ScraperJobRepository
    from app.repositories.instagram import InstagramQueueRepository
    from app.repositories.recommendations import RecommendationRepository

    unit = UnitOfWork.__new__(UnitOfWork)
    unit.session = async_session
    unit.items = ItemRepository(async_session)
    unit.wishlists = WishlistRepository(async_session)
    unit.tags = TagRepository(async_session)
    unit.scraper_jobs = ScraperJobRepository(async_session)
    unit.instagram = InstagramQueueRepository(async_session)
    unit.recommendations = RecommendationRepository(async_session)
    unit._committed = False
    return unit


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def user_factory(async_session: AsyncSession):
    """Create User rows directly in the test session."""
    from app.models.user import User
    from app.models.enums import UserRole
    from app.core.security import hash_password

    created: list[User] = []

    async def _make(
        email: str | None = None,
        password: str = "Secret1Pass",
        role: UserRole = UserRole.USER,
        **kwargs,
    ) -> User:
        user = User(
            email=email or f"user-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password(password),
            role=role,
            **kwargs,
        )
        async_session.add(user)
        await async_session.flush()
        created.append(user)
        return user

    yield _make


@pytest_asyncio.fixture()
async def admin_factory(user_factory):
    """Convenience: create a User with role=ADMIN."""
    from app.models.enums import UserRole

    async def _make(email: str | None = None, **kwargs) -> Any:
        return await user_factory(email=email, role=UserRole.ADMIN, **kwargs)

    return _make


@pytest_asyncio.fixture()
async def tag_type_factory(async_session: AsyncSession):
    """Create TagType rows."""
    from app.models.taxonomy import TagType

    async def _make(name: str | None = None, **kwargs) -> TagType:
        tt = TagType(
            name=name or f"type-{uuid.uuid4().hex[:6]}",
            is_filterable=True,
            sort_order=0,
            **kwargs,
        )
        async_session.add(tt)
        await async_session.flush()
        return tt

    return _make


@pytest_asyncio.fixture()
async def tag_factory(async_session: AsyncSession, tag_type_factory):
    """Create Tag rows."""
    from app.models.taxonomy import Tag

    async def _make(
        slug: str | None = None,
        name: str | None = None,
        tag_type_id: int | None = None,
        **kwargs,
    ) -> Tag:
        if tag_type_id is None:
            tt = await tag_type_factory()
            tag_type_id = tt.id
        slug = slug or f"tag-{uuid.uuid4().hex[:6]}"
        tag = Tag(
            tag_type_id=tag_type_id,
            name=name or slug,
            slug=slug,
            is_active=True,
            sort_order=0,
            **kwargs,
        )
        async_session.add(tag)
        await async_session.flush()
        return tag

    return _make


@pytest_asyncio.fixture()
async def item_factory(async_session: AsyncSession):
    """Create Item rows."""
    from app.models.catalog import Item
    from app.models.enums import ItemSource, ItemStatus

    async def _make(
        title: str | None = None,
        status: ItemStatus = ItemStatus.ACTIVE,
        price: Decimal | None = Decimal("29.99"),
        published_at: datetime | None = None,
        **kwargs,
    ) -> Item:
        item = Item(
            title=title or f"Item {uuid.uuid4().hex[:6]}",
            status=status,
            price=price,
            currency="USD",
            source=kwargs.pop("source", ItemSource.MANUAL),
            published_at=published_at or datetime.now(timezone.utc),
            **kwargs,
        )
        async_session.add(item)
        await async_session.flush()
        return item

    return _make


@pytest_asyncio.fixture()
async def wishlist_factory(async_session: AsyncSession, user_factory):
    """Create Wishlist rows."""
    from app.models.user import Wishlist

    async def _make(
        user_id: uuid.UUID | None = None,
        name: str | None = None,
        is_public: bool = False,
        **kwargs,
    ) -> Wishlist:
        if user_id is None:
            u = await user_factory()
            user_id = u.id
        wl = Wishlist(
            user_id=user_id,
            name=name or f"Wishlist {uuid.uuid4().hex[:6]}",
            is_public=is_public,
            **kwargs,
        )
        async_session.add(wl)
        await async_session.flush()
        return wl

    return _make


@pytest_asyncio.fixture()
async def scraper_site_factory(async_session: AsyncSession):
    """Create ScraperSite rows."""
    from app.models.catalog import ScraperSite

    async def _make(
        name: str | None = None,
        is_active: bool = True,
        **kwargs,
    ) -> ScraperSite:
        site = ScraperSite(
            name=name or f"site-{uuid.uuid4().hex[:6]}",
            base_url="https://example.com",
            adapter_class="app.adapters.generic_html.GenericHTMLAdapter",
            is_active=is_active,
            **kwargs,
        )
        async_session.add(site)
        await async_session.flush()
        return site

    return _make


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _make_auth_headers(user_id: uuid.UUID, role: str) -> dict[str, str]:
    from app.core.security import create_access_token

    token = create_access_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_headers(user_factory):
    """Return a callable: ``auth_headers(user) -> dict``."""

    def _make(user) -> dict[str, str]:
        return _make_auth_headers(user.id, user.role.value)

    return _make


@pytest.fixture()
def admin_headers():
    """Return a callable: ``admin_headers(admin_user) -> dict``."""

    def _make(user) -> dict[str, str]:
        return _make_auth_headers(user.id, user.role.value)

    return _make


# ---------------------------------------------------------------------------
# FastAPI TestClient + AsyncClient
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app():
    """Build the FastAPI application once per session.

    The lifespan calls ``ping_redis`` and ``dispose_engine`` / ``close_redis``
    on startup/shutdown. We stub those so no real infrastructure is needed.
    """
    from app.main import create_app as _create_app
    return _create_app()


@pytest_asyncio.fixture()
async def test_client(
    app,
    async_session: AsyncSession,
    engine: AsyncEngine,
    mock_redis,
) -> AsyncIterator[AsyncClient]:
    """Yield an ``httpx.AsyncClient`` with injected test session and fakes."""
    from app.dependencies import get_uow, get_db
    from app.repositories.unit_of_work import UnitOfWork
    from app.repositories.items import ItemRepository
    from app.repositories.wishlists import WishlistRepository
    from app.repositories.tags import TagRepository
    from app.repositories.scraper_jobs import ScraperJobRepository
    from app.repositories.instagram import InstagramQueueRepository
    from app.repositories.recommendations import RecommendationRepository

    # Build a UoW bound to the test session (so HTTP calls see the same data
    # that fixtures wrote).
    async def _override_uow():
        unit = UnitOfWork.__new__(UnitOfWork)
        unit.session = async_session
        unit.items = ItemRepository(async_session)
        unit.wishlists = WishlistRepository(async_session)
        unit.tags = TagRepository(async_session)
        unit.scraper_jobs = ScraperJobRepository(async_session)
        unit.instagram = InstagramQueueRepository(async_session)
        unit.recommendations = RecommendationRepository(async_session)
        unit._committed = False
        yield unit

    async def _override_db():
        yield async_session

    app.dependency_overrides[get_uow] = _override_uow
    app.dependency_overrides[get_db] = _override_db

    # Patch lifespan infrastructure so no real Redis/DB connections are opened.
    with patch("app.main.ping_redis", new_callable=AsyncMock, return_value=True), \
         patch("app.main.dispose_engine", new_callable=AsyncMock), \
         patch("app.main.close_redis", new_callable=AsyncMock):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client

    app.dependency_overrides.clear()
