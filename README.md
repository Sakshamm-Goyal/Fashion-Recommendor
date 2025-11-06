# Elara – AI Personal Stylist

> **Best-in-class AI fashion stylist** that analyzes your wardrobe, detects gaps, and intelligently searches for products across multiple retailers with real-time pricing and affiliate links.

A production-ready AI fashion stylist system that learns your wardrobe, understands your preferences, and intelligently suggests what to wear or buy for any occasion.

**New in v2.0**: Hybrid multi-source product search (Google Shopping, ASOS, Zara, H&M), intelligent wardrobe gap detection, affiliate monetization, and 2025 fashion trends integration.

## System Overview

Elara uses a **production-grade multi-layer pipeline**:

1. **Deterministic Layer**: Wardrobe normalization, weather fetching, trend signals, constraint parsing
2. **LLM Reasoning Layer**: GPT-4o with 2025 fashion trends and wardrobe gap analysis
3. **Agentic Layer**: Hybrid search across 4+ sources (Vector DB, Google Shopping, ASOS, Web Scrapers)
4. **Ranking Layer**: Multi-signal product ranking with 8 weighted factors
5. **Monetization Layer**: Affiliate link conversion and commission tracking

### Key Features

🧠 **Advanced AI Reasoning**
- Wardrobe gap detection with high-impact purchase recommendations
- 2025 fashion trends (Quiet Luxury, Oversized Silhouettes, Dopamine Dressing)
- Color theory intelligence (skin tone matching)
- Three-tier outfit strategy (Wardrobe Hero, Smart Upgrade, Fresh Investment)

🔍 **Hybrid Multi-Source Search**
- **Vector DB**: Semantic search across existing product catalog
- **Google Shopping API**: Real-time products with current pricing
- **ASOS API**: Fashion-specific items with size/stock info
- **Web Scrapers**: Zara & H&M (respectful scraping with rate limiting)

📊 **Multi-Signal Product Ranking**
- Semantic relevance (30%) - Vector similarity to description
- Price fit (20%) - Budget sweet spot alignment
- Availability (15%) - In-stock and shipping speed
- Brand match (10%) - User brand preferences
- Quality signals (10%) - Reviews and ratings
- Trend alignment (5%) - Current fashion trends
- Sustainability (5%) - Eco-friendly fabrics
- Return policy (5%) - Easy returns

💰 **Monetization Ready**
- Affiliate network integration (Rakuten, Impact.com, ShareASale)
- Automatic affiliate link conversion
- Commission rate tracking
- Revenue attribution

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Input                               │
│  (preferences, wardrobe, session details)                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Deterministic Layer                             │
│  • Normalize wardrobe items                                  │
│  • Fetch real-time weather                                   │
│  • Load fashion trend signals                                │
│  • Build context pack                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              LLM Reasoning Layer                             │
│  • OpenAI GPT-4o with Structured Outputs                     │
│  • Markdown instructions + JSON schema                       │
│  • Returns 3 outfit recommendations                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Agentic Layer                                   │
│  • pgvector semantic search                                  │
│  • Parallel product catalog queries                          │
│  • LLM reranking for precision                               │
│  • Enrich with prices, images, buy links                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Scoring Layer                                   │
│  • Deterministic weighted matrix                             │
│  • Weather (25%), Occasion (25%), Color (20%)                │
│  • Fit/Body (15%), Brand/Budget (10%), Trend (5%)            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         Top 3 Scored Outfit Recommendations                  │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Language**: Python 3.9+
- **AI/ML**: OpenAI GPT-4o, text-embedding-3-large
- **Database**: PostgreSQL 16 with pgvector
- **Cache**: Redis 7
- **Infrastructure**: Docker Compose
- **Key Libraries**: Pydantic, psycopg2, openai, requests

## Project Structure

```
elara_stylist/
├── config.py                    # Configuration and environment variables
├── contracts/
│   └── models.py                # Pydantic schemas (Product, OutfitResponse, WardrobeGapAnalysis)
├── services/                    # Core business logic
│   ├── deterministic_layer.py   # Constraint parsing and context building
│   ├── product_search_service.py  # Hybrid multi-source search
│   ├── ranking_engine.py        # Multi-signal product ranking
│   └── wardrobe_analyzer.py     # Gap detection and analysis
├── integrations/                # External API integrations
│   ├── google_shopping.py       # Google Shopping API client
│   ├── asos_api.py              # ASOS API client
│   ├── affiliate_manager.py     # Affiliate link conversion
│   └── web_scrapers.py          # Zara & H&M scrapers
├── llm_reasoning.py             # OpenAI GPT-4o reasoning with structured outputs
├── vector_index.py              # pgvector product search
├── agentic_layer.py             # Product matching and enrichment
├── scoring_matrix.py            # Deterministic scoring system
├── main.py                      # Main orchestrator
├── infra/
│   ├── cache.py                 # Redis caching
│   ├── logging.py               # Structured logging
│   └── secrets.py               # Secrets management
├── scripts/
│   ├── seed_products.py         # Database seeding script
│   └── smoke_demo.py            # End-to-end demo
├── docker-compose.yml           # Infrastructure setup
├── requirements.txt             # Python dependencies
└── Makefile                     # Convenience commands
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.9+
- OpenAI API key
- OpenWeather API key (optional, uses fallback if not provided)

### Setup

1. **Clone and navigate to the directory**:
   ```bash
   cd /path/to/Elara-Joining
   ```

2. **Copy environment file**:
   ```bash
   cp .env.sample .env
   ```

3. **Edit `.env` and add your API keys**:
   ```
   OPENAI_API_KEY=your_openai_key_here
   OPENWEATHER_API_KEY=your_weather_key_here
   ```

4. **Start infrastructure** (Postgres + Redis):
   ```bash
   make up
   ```

5. **Create Python virtual environment and install dependencies**:
   ```bash
   make install
   ```

6. **Activate virtual environment**:
   ```bash
   source .venv/bin/activate  # On macOS/Linux
   # OR
   .\.venv\Scripts\Activate.ps1  # On Windows PowerShell
   ```

7. **Seed product database** (~200 synthetic products):
   ```bash
   make seed
   ```

8. **Run the demo**:
   ```bash
   make demo
   ```

### Manual Run

```bash
source .venv/bin/activate
python main.py
```

## API Key Configuration

### Required (Free Tier Available)

**OpenAI API**
- Get key at: [platform.openai.com](https://platform.openai.com/)
- Add to `.env`:
  ```bash
  OPENAI_API_KEY=sk-proj-your_key_here
  ```

### Optional (Recommended for Production)

**Google Shopping API** (Free: 100 queries/day)
- Setup: [Google Cloud Console](https://console.cloud.google.com/)
- Create Custom Search Engine: [programmablesearchengine.google.com](https://programmablesearchengine.google.com/)
- Add to `.env`:
  ```bash
  GOOGLE_SHOPPING_API_KEY=your_api_key
  GOOGLE_SHOPPING_CX=your_search_engine_id
  ```

**OpenWeather API** (Free: 1000 calls/day)
- Get key: [openweathermap.org](https://openweathermap.org/api)
- Add to `.env`:
  ```bash
  OPENWEATHER_API_KEY=your_key_here
  ```

**Affiliate Networks** (For Monetization)
- **Rakuten**: [rakutenadvertising.com](https://rakutenadvertising.com/) (Nordstrom, Macy's)
- **Impact.com**: [impact.com](https://impact.com/) (Nike, Adidas)
- **ShareASale**: [shareasale.com](https://www.shareasale.com/) (Urban Outfitters, Revolve)

Add affiliate keys to `.env`:
```bash
RAKUTEN_API_KEY=your_key
RAKUTEN_ACCOUNT_ID=your_account_id
IMPACT_API_KEY=your_key
IMPACT_ACCOUNT_ID=your_account_id
SHARESALE_AFFILIATE_ID=your_id
```

## Makefile Commands

### Infrastructure
```bash
make up      # Start Docker services (Postgres + Redis)
make down    # Stop and remove Docker services
make logs    # View Docker logs
make install # Create venv and install dependencies
make seed    # Seed product database
make demo    # Run end-to-end demo
```

### Testing
```bash
make test         # Check configuration
make test-all     # Run all tests
make test-trends  # Test fashion trends
make test-gaps    # Test wardrobe gap analysis
make test-search  # Test product search
make test-e2e     # Test end-to-end pipeline
make quick-demo   # Run interactive demo
```

## Input Schema

```python
{
  "user_profile": {
    "gender": "Men|Women|Non-binary|Unisex",
    "skin_tone": "Olive|Fair|Deep",
    "brand_prefs": ["Zara", "H&M"],
    "color_prefs": ["Black", "Beige"],
    "body_type": "Athletic|Slim|Plus|Pear",
    "fit_pref": "Slim|Relaxed|Oversized",
    "style_pref": "Minimalist|Streetwear|Classic",
    "budget": {"currency": "USD", "soft_cap": 150, "hard_cap": 300}
  },
  "session": {
    "location": "City, Country",
    "datetime_local_iso": "2025-10-05T18:00:00",
    "occasion": "Wedding|Work|Date|Casual",
    "vibe": "Chill|Formal|Edgy"
  },
  "wardrobe": [/* array of wardrobe items */],
  "limits": {
    "max_online_items_per_look": 3,
    "retailers_allowlist": ["Zara", "H&M", "ASOS", ...]
  }
}
```

## Output Schema

```python
{
  "recommendations": [
    {
      "look": "Outfit Name",
      "score": 8.75,
      "summary": "Brief description...",
      "items": [
        {
          "slot": "top|bottom|outerwear|footwear|accessory",
          "source": "wardrobe|RetailerName",
          "name": "Product Name",
          "price": {"value": 89.99, "currency": "USD"},
          "image": "https://...",
          "buy_link": "https://..."
        }
      ],
      "reasoning": {
        "weather": "Explanation...",
        "occasion": "Explanation...",
        ...
      },
      "tags": ["casual", "summer", "neutral"]
    }
  ],
  "context_hash": "abc123..."
}
```

## Scoring Matrix

Outfits are scored using a deterministic weighted system:

| Dimension           | Weight | Criteria                                    |
|---------------------|--------|---------------------------------------------|
| Weather             | 25%    | Fabric, layering, temperature appropriateness |
| Occasion            | 25%    | Formality level, event type match           |
| Color Compatibility | 20%    | Skin tone complement, user preferences      |
| Fit & Body Type     | 15%    | Silhouette appropriateness                  |
| Brand & Budget      | 10%    | Brand preferences, budget compliance        |
| Trend Alignment     | 5%     | Current fashion trend matches               |

**Final Score** = Weighted sum (0–10 scale)

## Key Features

### 1. Structured Outputs
Uses OpenAI's JSON Schema mode for guaranteed valid responses.

### 2. Vector Search
pgvector with text-embedding-3-large for semantic product matching.

### 3. Caching
Redis caching for:
- Weather data (6h TTL)
- Product searches (24h TTL)
- LLM outputs (by context hash, 24h TTL)

### 4. Parallel Processing
Async/await for concurrent product searches across retailers.

### 5. LLM Reranking
Lightweight GPT-4o-mini reranks vector search results for precision.

### 6. Deterministic Scoring
All scoring is auditable and explainable, not hidden in LLM weights.

## Production Considerations

### Security
- PII scrubbing in logs
- Secrets via environment variables
- Encrypted wardrobe images (planned)

### Observability
- Structured logging with request IDs
- Token usage tracking
- Latency monitoring hooks

### Performance
- P95 latency target: < 2.8s (with cache) / < 6s (cold)
- Single LLM reasoning call
- Parallel product searches
- Aggressive caching strategy

### Cost Optimization
- GPT-4o for reasoning (~$5-10/1000 requests)
- GPT-4o-mini for reranking (~$0.15/1000 requests)
- Embedding caching reduces API calls by ~80%

## Development Roadmap

### Phase 1 (MVP) ✅
- Three-layer pipeline
- Structured outputs
- Vector search
- Deterministic scoring

### Phase 2 (Current - v2.0) ✅
- ✅ Hybrid multi-source product search
- ✅ Google Shopping API integration
- ✅ ASOS API integration
- ✅ Web scrapers (Zara, H&M)
- ✅ Intelligent wardrobe gap detection
- ✅ Multi-signal product ranking
- ✅ Affiliate monetization
- ✅ 2025 fashion trends
- ⏳ Product catalog sync pipeline (pending)

### Phase 3 (Next)
- User feedback loop (likes/dislikes)
- A/B testing framework
- Wardrobe auto-tagging from photos (GPT-4o vision)
- Multi-language support
- Real-time inventory tracking

### Phase 4 (Future)
- Influencer mode (style-inspired recommendations)
- Shopping cart integration
- Mobile app (iOS + Android)
- Voice/chat interface
- Virtual try-on (AR)
- Social sharing
- Community features

## Troubleshooting

### Docker Issues
```bash
# Reset everything
make down
docker system prune -a
make up
```

### Python Dependencies
```bash
# Reinstall
rm -rf .venv
make install
```

### Database Connection
```bash
# Check Postgres is running
docker ps | grep elara_pg

# Connect manually
docker exec -it elara_pg psql -U elara -d elara
```

### Redis Connection
```bash
# Check Redis is running
docker exec -it elara_redis redis-cli ping
```

## Testing

**See [TESTING.md](./TESTING.md) for comprehensive testing guide.**

### Quick Test Commands

```bash
# Check configuration
python scripts/test_pipeline.py --config

# Test individual components
python scripts/test_pipeline.py --trends    # Fashion trends
python scripts/test_pipeline.py --gaps      # Wardrobe analysis
python scripts/test_pipeline.py --search    # Product search
python scripts/test_pipeline.py --e2e       # Full pipeline

# Run all tests
python scripts/test_pipeline.py --all

# Interactive demo
python scripts/quick_demo.py
```

### Test Scripts

- **`scripts/test_pipeline.py`**: Comprehensive test suite for all components
  - Fashion trends fetcher
  - Wardrobe gap analyzer
  - Hybrid product search
  - Multi-signal ranking
  - End-to-end outfit generation

- **`scripts/quick_demo.py`**: Interactive demo with menu system
  - Fashion Trends Intelligence
  - Wardrobe Gap Analysis
  - Hybrid Product Search
  - AI Outfit Generation

### Contract Tests
All LLM outputs are validated against Pydantic schemas with strict JSON mode.

## Contributing

This is a private project for the founding team. See internal docs for contribution guidelines.

## License

Proprietary - All rights reserved.

## Team

- **Founder**: Mehul Agarwal
- **Founding Engineers**: Harpreet, Saksham

## Contact

For questions or issues, contact the team via internal channels.

---

**Built with Claude Code** 🤖
# Fashion-Recommendor
