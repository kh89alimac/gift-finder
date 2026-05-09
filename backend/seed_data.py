"""Seed the database with sample gift items."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.catalog import Item
from app.models.enums import ItemSource, ItemStatus

SAMPLE_ITEMS = [
    {
        "title": "Leather Journal Notebook",
        "description": "Handcrafted genuine leather journal with 200 pages of premium paper. Perfect for writers and thinkers.",
        "price": Decimal("45.99"),
        "currency": "USD",
        "image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400",
        "product_url": "https://example.com/leather-journal",
        "brand": "Artisan Craft Co.",
        "retailer": "Amazon",
    },
    {
        "title": "Wireless Noise-Cancelling Headphones",
        "description": "Premium over-ear headphones with 30-hour battery life and active noise cancellation.",
        "price": Decimal("149.99"),
        "currency": "USD",
        "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400",
        "product_url": "https://example.com/headphones",
        "brand": "SoundWave",
        "retailer": "Best Buy",
    },
    {
        "title": "Succulent Plant Collection",
        "description": "Set of 6 assorted succulents in cute ceramic pots. Low maintenance and beautiful.",
        "price": Decimal("34.99"),
        "currency": "USD",
        "image_url": "https://images.unsplash.com/photo-1459156212016-c812468e2115?w=400",
        "product_url": "https://example.com/succulents",
        "brand": "Green Thumb",
        "retailer": "Etsy",
    },
    {
        "title": "Cozy Knit Throw Blanket",
        "description": "Ultra-soft chunky knit blanket, 50x60 inches. Available in multiple colors.",
        "price": Decimal("59.99"),
        "currency": "USD",
        "image_url": "https://images.unsplash.com/photo-1580301762395-21ce84d00bc6?w=400",
        "product_url": "https://example.com/blanket",
        "brand": "Cozy Home",
        "retailer": "Amazon",
    },
    {
        "title": "Personalised Star Map Print",
        "description": "Custom star map showing the night sky on any date and location. Framed and ready to hang.",
        "price": Decimal("49.00"),
        "currency": "USD",
        "image_url": "https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?w=400",
        "product_url": "https://example.com/star-map",
        "brand": "Night Sky Prints",
        "retailer": "Etsy",
    },
    {
        "title": "Gourmet Hot Sauce Collection",
        "description": "Set of 6 small-batch artisan hot sauces ranging from mild to extra hot. Great for foodies.",
        "price": Decimal("38.00"),
        "currency": "USD",
        "image_url": "https://images.unsplash.com/photo-1563245372-f21724e3856d?w=400",
        "product_url": "https://example.com/hot-sauce",
        "brand": "Fire & Spice",
        "retailer": "Etsy",
    },
    {
        "title": "Portable Espresso Maker",
        "description": "Manual handheld espresso machine — no electricity needed. Perfect for travel and camping.",
        "price": Decimal("69.95"),
        "currency": "USD",
        "image_url": "https://images.unsplash.com/photo-1510591509098-f4fdc6d0ff04?w=400",
        "product_url": "https://example.com/espresso",
        "brand": "BrewGo",
        "retailer": "Amazon",
    },
    {
        "title": "Scented Soy Candle Set",
        "description": "Set of 4 hand-poured soy wax candles in calming scents: lavender, vanilla, cedar, and citrus.",
        "price": Decimal("42.00"),
        "currency": "USD",
        "image_url": "https://images.unsplash.com/photo-1603905860209-aa5b47cf2d97?w=400",
        "product_url": "https://example.com/candles",
        "brand": "Calm Wick",
        "retailer": "Etsy",
    },
    {
        "title": "Adventure Scratch Map",
        "description": "Scratch-off world map poster to reveal colourful countries as you travel. 24x17 inches.",
        "price": Decimal("25.99"),
        "currency": "USD",
        "image_url": "https://images.unsplash.com/photo-1524661135-423995f22d0b?w=400",
        "product_url": "https://example.com/scratch-map",
        "brand": "Wander & Co.",
        "retailer": "Amazon",
    },
    {
        "title": "Bamboo Cutting Board Set",
        "description": "Set of 3 eco-friendly bamboo cutting boards with juice grooves. Dishwasher safe.",
        "price": Decimal("32.99"),
        "currency": "USD",
        "image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=400",
        "product_url": "https://example.com/cutting-boards",
        "brand": "EcoKitchen",
        "retailer": "Amazon",
    },
]


async def seed():
    engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        now = datetime.now(timezone.utc)
        for data in SAMPLE_ITEMS:
            item = Item(
                **data,
                source=ItemSource.MANUAL,
                status=ItemStatus.ACTIVE,
                published_at=now,
            )
            session.add(item)
        await session.commit()
        print(f"Seeded {len(SAMPLE_ITEMS)} gift items successfully.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
