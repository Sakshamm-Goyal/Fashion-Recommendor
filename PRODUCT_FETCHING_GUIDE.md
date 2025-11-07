# 🛍️ Product Fetching Guide - Complete Overview

## 📋 Table of Contents
1. [High-Level Flow](#high-level-flow)
2. [Parameters & Inputs](#parameters--inputs)
3. [Product Sources](#product-sources)
4. [Fetching Process](#fetching-process)
5. [Verification Process](#verification-process)
6. [Ranking & Filtering](#ranking--filtering)
7. [Current Configuration](#current-configuration)

---

## High-Level Flow

```
User Request (descriptor: "Black leather oxford shoes, men's size 10")
    ↓
[agentic_layer.py] find_candidates_for_descriptor()
    ↓
[product_search_service.py] search_multi_source()
    ↓
┌─────────────────────────────────────────────────────────┐
│  PARALLEL SEARCH ACROSS MULTIPLE SOURCES                │
│  (All sources run simultaneously for speed)             │
└─────────────────────────────────────────────────────────┘
    ↓
├─→ Claude Web Search (PRIMARY - ACTIVE)
├─→ Oxylabs Google Shopping (PRIMARY - ACTIVE)
├─→ ASOS API (ACTIVE)
├─→ OpenSERP (DISABLED - currently off)
├─→ Visual Scraping (DISABLED)
├─→ Retailed.io (DISABLED - API errors)
└─→ Vector DB (DISABLED - only fake products)
    ↓
[Merge & Deduplicate Results]
    ↓
[Link Verification] (if enabled)
    ↓
[Filter by Price & Retailers]
    ↓
[Rank Products] (multi-signal scoring)
    ↓
[LLM Re-ranking] (GPT-4o-mini picks top 3)
    ↓
Return: List[Product] objects
```

---

## Parameters & Inputs

### Main Search Parameters

**Function:** `search_multi_source(descriptor, budget, filters, retailers_allowlist, k)`

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `descriptor` | `str` | Natural language product description | `"Black leather oxford shoes, men's size 10"` |
| `budget` | `Dict` | Budget constraints | `{"currency": "USD", "soft_cap": 150, "hard_cap": 300}` |
| `filters` | `Dict` | Optional filters | `{"gender": "Men", "color": "Black", "size": "10", "brand": "Nike"}` |
| `retailers_allowlist` | `List[str]` | Allowed retailers | `["Zara", "H&M", "ASOS", "Nordstrom"]` |
| `k` | `int` | Number of results to return | `50` (default) |

### Budget Object Structure
```python
budget = {
    "currency": "USD",      # Currency code
    "soft_cap": 150,        # Preferred max price (sweet spot)
    "hard_cap": 300         # Absolute max price
}
```

### Filters Object Structure
```python
filters = {
    "gender": "Men",        # Gender filter
    "color": "Black",       # Color preference
    "size": "10",           # Size requirement
    "brand": "Nike",        # Brand preference
    "location": "US",       # Geographic location
    "zip_code": "10001"     # ZIP code for delivery
}
```

---

## Product Sources

### 1. **Claude Web Search** (PRIMARY - ACTIVE ✅)
**File:** `integrations/claude_web_search.py`
**Status:** ✅ ENABLED (if `ENABLE_CLAUDE_WEB_SEARCH=true` and valid API key)

**How it works:**
- Uses Claude (Anthropic API) with web search capability
- Claude searches actual retailer websites
- Extracts structured product data (title, price, URL, image, retailer)
- More accurate than scraping because Claude understands context

**Parameters:**
- `query`: Product descriptor
- `max_results`: 20 (default)
- `max_price`: From budget.hard_cap
- `preferred_retailers`: From retailers_allowlist

**Returns:** `List[ProductCandidate]` with verified URLs and prices

**Advantages:**
- High accuracy (Claude understands product pages)
- Real product URLs (not search result pages)
- Includes prices and retailer info

---

### 2. **Oxylabs Google Shopping** (PRIMARY - ACTIVE ✅)
**File:** `integrations/oxylabs_client.py`
**Status:** ✅ ENABLED (if `ENABLE_OXYLABS=true` and credentials valid)

**How it works:**
- Uses Oxylabs Web Scraper API to scrape Google Shopping
- Bypasses anti-bot protection
- Returns Google Shopping results with prices, ratings, retailer info
- Supports US geo-location

**Parameters:**
- `descriptor`: Product search query
- `price_max`: From budget.hard_cap
- `location`: From filters.location (default: "United States")
- `max_results`: 20 (default)
- `prefer_new`: True (prefer new products)
- `prefer_free_delivery`: False

**Returns:** `List[Product]` objects

**API Limits:**
- Free trial: Up to 2K results
- 10 requests/second
- $1 trial limit

**Credentials:**
- Username: `elara_u1y0M`
- Password: `AVFGxj4K3fx8n+i`

---

### 3. **ASOS API** (ACTIVE ✅)
**File:** `integrations/asos_api.py`
**Status:** ✅ ENABLED (if `ENABLE_ASOS_SEARCH=true`)

**How it works:**
- Direct API call to ASOS (fashion retailer)
- Fashion-specific search
- Returns products with size/stock info
- Good for clothing items

**Parameters:**
- `descriptor`: Product search query
- `gender`: From filters.gender
- `max_price`: From budget.hard_cap
- `filters`: Additional filters
- `max_results`: 20 (default)

**Returns:** `List[Product]` objects

**Note:** May have 403 errors (rate limiting)

---

### 4. **OpenSERP** (DISABLED ❌)
**File:** `integrations/openserp_client.py`
**Status:** ❌ DISABLED (currently `enable_openserp = False`)

**How it works:**
- Local scraper running on port 7001
- Searches Google, Bing, DuckDuckGo simultaneously
- FREE - No API costs
- Returns search results (may need link resolution)

**When enabled:**
- Requires OpenSERP server running on `localhost:7001`
- Can use OpenSERP Manager for auto-restart
- Link resolution converts search pages to product pages

---

### 5. **Visual Scraping** (DISABLED ❌)
**File:** `integrations/visual_shopping_scraper.py`
**Status:** ❌ DISABLED (Chromium gets CAPTCHA'd)

**How it works:**
- Uses Playwright + Claude Vision API
- Takes screenshots of Google Shopping
- Claude Vision extracts product info from images
- More robust against HTML structure changes

**Why disabled:** Chromium gets CAPTCHA'd, not working reliably

---

### 6. **Retailed.io** (DISABLED ❌)
**File:** `integrations/retailed_client.py`
**Status:** ❌ DISABLED (API returning 500 errors)

**How it works:**
- API for retailer-specific searches (Nike, Zara, StockX, etc.)
- Good for brand-specific products

**Why disabled:** API returning 500 errors

---

### 7. **Vector Database** (DISABLED ❌)
**File:** `vector_index.py`
**Status:** ❌ DISABLED (only contains fake/synthetic products)

**How it works:**
- Uses pgvector (PostgreSQL with vector search)
- Semantic search using embeddings
- Fast similarity matching

**Why disabled:** Only contains fake products from seed script

---

## Fetching Process

### Step 1: Parallel Search Execution

**File:** `services/product_search_service.py` → `search_multi_source()`

All enabled sources run **in parallel** using `asyncio.gather()`:

```python
tasks = []

# 1. Claude Web Search
if self.claude_web_search_client:
    tasks.append(self._search_claude_web(descriptor, max_price, retailers_allowlist))

# 2. Oxylabs Google Shopping
if self.enable_oxylabs:
    tasks.append(self._search_oxylabs(descriptor, max_price, location))

# 3. ASOS API
if self.enable_asos:
    tasks.append(self._search_asos(descriptor, max_price, filters))

# Execute all in parallel
results = await asyncio.gather(*tasks, return_exceptions=True)
```

**Fail-Fast Pattern:**
- If a source fails with 400/401/403 errors, it's marked as failed
- Subsequent searches skip failed sources
- Prevents wasting time on broken APIs

---

### Step 2: Merge & Deduplicate

**Function:** `_deduplicate_products()`

**Strategy:**
1. **Exact URL match** → Keep product with highest relevance score
2. **Title similarity** (future) → Keep one if >80% similar

**Current implementation:** URL-based deduplication only

---

### Step 3: Link Verification (Optional)

**File:** `services/link_verification_agent.py`
**Status:** ✅ ENABLED (if `ENABLE_LINK_VERIFICATION=true`)

**Who verifies:** `LinkVerificationAgent` using Playwright browser pool

**How it works:**
1. **Check cache first** (Redis) - avoids re-verifying known-good links
2. **Browser verification** for uncached products:
   - Uses browser pool (3 browsers × 5 contexts = 15 concurrent)
   - Navigates to product URL
   - Detects retailer patterns
   - Checks for "Add to Cart" button
   - Verifies NOT out of stock
   - Validates price matches (if provided)
   - Takes screenshot (if enabled)

**Verification Checks:**
- ✅ HTTP status code (200 OK)
- ✅ Add to Cart button exists
- ✅ NOT out of stock
- ✅ Price matches (within 10% variance)

**Performance:**
- Verifies top 30 products by relevance
- 15 concurrent verifications
- ~5-10 seconds for 20 products
- 95-100% link accuracy

**Caching:**
- Redis cache with 1-hour TTL
- Cached verifications skip browser check

---

### Step 4: Filter by Price & Retailers

**Function:** `_apply_filters()`

**Filters applied:**
1. **Price filter:** Skip products above `max_price` (budget.hard_cap)
2. **Retailer filter:** Skip products not in `retailers_allowlist`
   - **Exception:** OpenSERP products (they're search results, not final retailers)

---

### Step 5: Rank Products

**Function:** `_rank_products()`

**Multi-signal scoring (weighted):**

| Signal | Weight | Description |
|--------|--------|-------------|
| **Semantic relevance** | 30% | From search source (relevance_score) |
| **Price fit** | 25% | How well price fits budget sweet spot |
| **Source priority** | 20% | Source reliability score |
| **In-stock availability** | 15% | Product is in stock |
| **Brand preference** | 10% | Matches preferred brands |

**Source Priority Scores:**
```python
source_scores = {
    "openserp": 1.0,              # PRIMARY: Local scraper
    "claude_web_search": 0.98,    # Claude web search (verified URLs)
    "searchapi_shopping": 0.95,   # SearchAPI (deprecated)
    "web_search": 0.90,           # Real products from web search
    "asos": 0.85,                 # Fashion-specific API
    "google_shopping": 0.80,      # LEGACY
    "retailed_io": 0.92,          # Retailer-specific
    "vector_db": 0.70,            # Lower priority
}
```

**Price Fit Scoring:**
- Under soft cap: 80-100% (closer to soft cap = better)
- Between soft/hard cap: Linearly decrease from 80% to 20%
- Over hard cap: 0%

---

### Step 6: LLM Re-ranking

**File:** `agentic_layer.py` → `llm_rerank()`

**Who re-ranks:** GPT-4o-mini (OpenAI)

**How it works:**
1. Takes top 15 products (by multi-signal score)
2. Sends to GPT-4o-mini with:
   - Product descriptor
   - User context (gender, occasion, style, budget)
   - Product candidates (title, retailer, price, source)
3. GPT-4o-mini ranks by:
   - Match quality (40%)
   - Value for money (25%)
   - Versatility (20%)
   - Retailer trust (15%)
4. Returns top 3 product IDs

**Fallback:** If LLM fails, returns top 3 by relevance score

---

## Verification Process

### Link Verification Agent

**File:** `services/link_verification_agent.py`
**Class:** `LinkVerificationAgent`

**Who verifies:**
- Playwright browser instances (managed by browser pool)
- 15 concurrent verifications (3 browsers × 5 contexts)

**What gets verified:**
1. **HTTP Status:** 200 OK
2. **Add to Cart Button:** Exists on page
3. **Stock Status:** NOT out of stock
4. **Price Match:** Actual price matches expected (within 10%)

**Retailer-Specific Patterns:**
- Uses `services/retailer_patterns.py` for retailer detection
- Custom selectors for each retailer (Nordstrom, Zara, ASOS, etc.)
- Universal fallback patterns if retailer not detected

**Performance:**
- Verifies top 30 products (by relevance)
- ~5-10 seconds for 20 products
- 95-100% link accuracy

**Caching:**
- Redis cache (`services/link_cache.py`)
- 1-hour TTL
- Cached verifications skip browser check

---

## Current Configuration

### Active Sources (as of now)

| Source | Status | Priority | Notes |
|--------|--------|----------|-------|
| **Claude Web Search** | ✅ ACTIVE | PRIMARY | Best accuracy, verified URLs |
| **Oxylabs** | ✅ ACTIVE | PRIMARY | Google Shopping via Oxylabs |
| **ASOS API** | ✅ ACTIVE | SECONDARY | Fashion-specific, may have 403 errors |
| **OpenSERP** | ❌ DISABLED | - | Currently `enable_openserp = False` |
| **Visual Scraping** | ❌ DISABLED | - | Chromium gets CAPTCHA'd |
| **Retailed.io** | ❌ DISABLED | - | API returning 500 errors |
| **Vector DB** | ❌ DISABLED | - | Only fake products |

### Verification Settings

```python
ENABLE_LINK_VERIFICATION = True          # Enable link verification
VERIFICATION_CONCURRENCY = 5             # Parallel browser instances
VERIFICATION_TIMEOUT = 5000              # 5 seconds per product
VERIFICATION_CACHE_TTL = 3600            # 1 hour cache TTL
ENABLE_VERIFICATION_SCREENSHOTS = False  # Disable screenshots (saves storage)
```

### Search Limits

```python
k = 50                    # Max products to return
max_results_per_source = 20  # Per source limit
verification_limit = 30   # Top 30 products verified
```

---

## Complete Example Flow

```
User Request:
  descriptor: "Black leather oxford shoes, men's size 10"
  budget: {"currency": "USD", "soft_cap": 150, "hard_cap": 300}
  retailers: ["Zara", "H&M", "ASOS", "Nordstrom"]

↓

[Parallel Search]
├─ Claude Web Search → 8 products
├─ Oxylabs → 12 products
└─ ASOS → 5 products

↓

[Merge] → 25 unique products (deduplicated)

↓

[Link Verification]
├─ Check cache → 5 cached (verified)
└─ Browser verify → 15 products verified
   → 20 total verified products

↓

[Filter]
├─ Price filter → 18 within budget
└─ Retailer filter → 16 in allowlist

↓

[Rank] → Top 15 by multi-signal score

↓

[LLM Re-rank] → Top 3 products selected

↓

Return: 3 Product objects with:
  - Real buy links
  - Verified prices
  - In-stock status
  - Retailer info
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `agentic_layer.py` | Main orchestrator, calls search & re-ranking |
| `services/product_search_service.py` | Hybrid search service, coordinates all sources |
| `integrations/claude_web_search.py` | Claude web search client |
| `integrations/oxylabs_client.py` | Oxylabs Google Shopping client |
| `integrations/asos_api.py` | ASOS API client |
| `services/link_verification_agent.py` | Link verification using Playwright |
| `services/browser_pool.py` | Browser pool management for parallel verification |
| `services/link_cache.py` | Redis cache for verification results |
| `services/retailer_patterns.py` | Retailer-specific selectors and patterns |
| `config.py` | Configuration and feature flags |

---

## Summary

**Who fetches:**
- `HybridProductSearch` service coordinates all sources
- Multiple sources run in parallel (Claude, Oxylabs, ASOS)
- Each source has its own client/integration

**Who verifies:**
- `LinkVerificationAgent` using Playwright browser pool
- 15 concurrent verifications
- Redis cache for performance

**Parameters:**
- `descriptor`: Product description
- `budget`: Soft/hard cap
- `filters`: Gender, color, size, brand, location
- `retailers_allowlist`: Allowed retailers
- `k`: Number of results

**Current active sources:**
1. Claude Web Search (PRIMARY)
2. Oxylabs Google Shopping (PRIMARY)
3. ASOS API (SECONDARY)

**Verification:**
- Enabled by default
- Verifies top 30 products
- 95-100% link accuracy
- 1-hour cache TTL

