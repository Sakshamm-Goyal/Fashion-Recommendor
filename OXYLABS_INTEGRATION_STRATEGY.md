# Oxylabs Integration Strategy

## Problem Statement

When Claude Web Search finds product URLs from retailers like Nordstrom, Zara, H&M, etc., we face two issues:

1. **Category Pages vs Product Pages**: Search often returns category/collection pages instead of direct product URLs
2. **Anti-Bot Protection**: Playwright navigation times out due to bot detection (30s timeout on Nord strom)

## Solution: Multi-Stage Pipeline

### Stage 1: Discovery (Claude Web Search + DuckDuckGo)
- **Current Implementation**: `integrations/claude_web_search.py`
- **Purpose**: Find retailer pages (product or category)
- **Strategy**: Site-specific searches using DuckDuckGo
  ```python
  search_patterns = [
      f"{query} site:nordstrom.com/s/",
      f"{query} site:zara.com/us/",
      f"{query} site:hm.com/en_us/",
      f"{query} site:asos.com/us/",
      f"{query} site:macys.com/shop/product/",
  ]
  ```
- **Output**: List of retailer URLs (may be category or product pages)

### Stage 2: HTML Scraping (Oxylabs)
- **Implementation**: `integrations/oxylabs_client.py`
- **Purpose**: Bypass anti-bot protection to get page HTML
- **API Source**: `universal_ecommerce`
- **Usage**:
  ```python
  client = OxylabsClient()
  html = client.scrape_retailer_page(url)
  ```
- **Benefits**:
  - Bypasses Cloudflare/bot detection
  - No timeout issues
  - Gets clean HTML content

### Stage 3: Product Extraction (Playwright/BeautifulSoup)
- **Purpose**: Extract actual product URLs from scraped HTML
- **For Category Pages**: Parse product links from grid/list
- **For Product Pages**: Verify URL is correct product page
- **Output**: List of verified product URLs with titles/prices

### Stage 4: Link Verification (Browser Pool)
- **Current Implementation**: `services/link_verification_agent.py`
- **Purpose**: Final verification of product availability
- **Uses**: 15 concurrent Playwright contexts

## API Limits (Oxylabs Free Trial)
- Up to 2K results
- 10 requests/s
- $1 trial limit

**Conservation Strategy**:
- Only use Oxylabs for pages that Playwright times out on
- Prioritize Nordstrom (most timeouts)
- Cache scraped HTML

## Implementation TODOs

1. **Create HTML Parser Service** (`services/html_product_parser.py`)
   - Parse Nordstrom product grids
   - Parse Zara product listings
   - Parse H&M product cards
   - Extract: product URLs, titles, prices, images

2. **Integrate Oxylabs into Search Flow** (`services/product_search_service.py`)
   - When Claude finds retailer URLs
   - Use Oxylabs to scrape HTML (bypassing bot detection)
   - Parse HTML to extract product URLs
   - Return structured product data

3. **Fallback Logic**
   - Try Playwright first (faster, free)
   - If timeout > 15s, use Oxylabs
   - Cache results to avoid duplicate scrapes

## User's Exact Workflow (from message)

> "get URL from this. open that and give exact url (proper site with product) that single product which we were searching"

Translation:
1. Claude Web Search finds: `nordstrom.com/browse/women/shoes/heels`
2. Oxylabs scrapes that category page → Gets HTML
3. Parse HTML → Extract product URLs like `nordstrom.com/s/product-name/1234567`
4. Return those exact product URLs with metadata

> "claude will not give exact product link it will give some page link, exact page link can be opened by playwright"

Translation:
- Claude/DuckDuckGo finds category pages
- Oxylabs scrapes them (bypassing protection)
- Parse HTML to get exact product links
- Playwright verifies them (browser pool)

## Current Status

✅ Claude Web Search working (finding US retailer pages)
✅ Oxylabs client created (`scrape_retailer_page()`)
✅ Browser pool for verification (15 concurrent)
❌ HTML product parser not implemented
❌ Not integrated into search flow

## Next Steps

1. Create HTML parser for Nordstrom/Zara/H&M
2. Integrate into product search service
3. Test with category pages
4. Measure success rate improvement
