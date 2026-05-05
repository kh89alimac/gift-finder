# Requirements: Gift Finder App

## Problem Statement

The Gift Finder app solves the universal struggle of finding the right gift for someone. It serves a broad audience:
- **Overwhelmed gift buyers** who don't know where to start and waste hours browsing generic results
- **Last-minute shoppers** who need curated, relevant suggestions quickly before an occasion
- **Thoughtful gift-givers** who want personalized, unique ideas tailored to the recipient's specific personality and interests

The core pain point: existing gift discovery is generic and time-consuming. Users want a smart, filtered discovery experience based on who they're buying for.

## Acceptance Criteria

- [ ] **Gift discovery works**: Users can search and browse gifts filtered by recipient profile (age, relationship, interests, occasion, budget) and get relevant, high-quality results
- [ ] **All 3 ingestion sources operational**: Web scrapers (cron-based, modular per-site), Instagram Graph API ingestion, and manual admin entry all write to the unified items table with proper source and status tracking
- [ ] **Admin panel functional**: Admins can manage the review queue, taxonomy (categories/tags), cron schedules, and trigger on-demand ingestion
- [ ] **Wishlists + recommendations live**: Users can save items to wishlists, smart recommendation engine surfaces relevant gifts, and AI natural-language search ("find a gift for a 30-year-old who loves hiking, under $100") returns relevant results

## Scope

### In Scope

- Unified gift items catalog with rich tagging (category, occasion, recipient type, age range, price range, interest tags)
- Gift discovery UI: profile-based filtering, search, browsing by category/occasion
- Three ingestion pipelines writing to unified items table:
  1. Cron-based web scrapers with modular per-site adapters, job queue, dedup, auto-categorization
  2. Instagram Graph API ingestion from hashtags/accounts into review queue
  3. Manual admin entry (image upload, form) and bulk CSV import
- User authentication and accounts
- User wishlists (save, organize, share links)
- Smart recommendation engine (collaborative filtering / content-based)
- AI natural-language search (e.g., OpenAI or Claude API integration)
- Admin panel: review queue, taxonomy management, cron scheduling, on-demand ingestion triggers
- Mobile-friendly responsive web UI
- Multi-language / i18n support (not explicitly out of scope)

### Out of Scope

- Payment processing or in-app checkout (links to external retailers only)
- Social features (friend lists, collaborative wishlists, gift sharing between users)

## Technical Constraints

No hard technical constraints. Free to choose best-fit technologies within the chosen stack.

## Technology Stack

- **Frontend**: Next.js 14 (App Router), React, TypeScript, Tailwind CSS
- **Backend**: FastAPI (Python), async, REST API
- **Database**: PostgreSQL
- **Background Jobs**: Celery or ARQ for scraper job queue and cron scheduling
- **AI Integration**: OpenAI API (or Anthropic Claude API) for natural-language search and auto-categorization
- **Instagram**: Meta Graph API for Instagram ingestion
- **File Storage**: S3-compatible storage (AWS S3 or MinIO) for image uploads
- **Cache**: Redis (job queue broker + caching layer)
- **Infrastructure**: Docker-based deployment

## Dependencies

Greenfield application — built from scratch with no existing systems to integrate with, aside from:
- OpenAI or Anthropic Claude API (AI natural-language search and auto-categorization)
- Meta Instagram Graph API (Instagram content ingestion)
- External retailer URLs (affiliate/product links — no API integration required)

## Configuration

- Stack: Next.js 14 + FastAPI + PostgreSQL
- API Style: REST
- Complexity: Complex
