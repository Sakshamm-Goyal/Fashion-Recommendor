# 🎨 How Elara Works - Simple Explanation

A friendly walkthrough of how the system creates outfit recommendations!

---

## 🎯 The Big Picture

You want outfit recommendations → Elara gives you 3 complete outfits with real products you can buy.

**The journey:** User Input → Context Prep → AI Brain → Product Search → Scoring → Final Outfits

---

## 📋 Step-by-Step Flow

### **Phase 1: Context Preparation** 🔍
**File:** `deterministic_layer.py`

**What happens:**
1. **Get your wardrobe** - Takes your existing clothes (items you own)
2. **Check weather** - Calls OpenWeather API to get temperature, conditions
3. **Load trends** - Gets current fashion trends (updated weekly)
4. **Normalize data** - Cleans up your wardrobe items into a standard format
5. **Build context pack** - Combines everything into one package for the AI

**Example:**
```
Input: "Wedding in Soho, NYC, Oct 5"
↓
Weather API: "20°C, clear sky"
↓
Context Pack: {wardrobe, weather, trends, budget, occasion}
```

**Key Point:** This phase is **deterministic** (no AI) - just gathering facts!

---

### **Phase 2: LLM Reasoning** 🧠
**File:** `llm_reasoning.py`

**What happens:**
1. **Sends context to GPT-4o** - The AI receives your wardrobe, weather, occasion, style
2. **AI analyzes** - Decides:
   - Which items from your wardrobe to use
   - Which items need to be purchased online
   - How to combine them into outfits
3. **Generates 3 outfits** - Creates outfit concepts with:
   - Items from your wardrobe (by ID)
   - Items to buy online (with search descriptions)

**Example LLM Output:**
```json
{
  "outfits": [
    {
      "name": "Wardrobe Hero",
      "composition": [
        {"slot": "top", "source": "wardrobe", "wardrobe_item_id": "item_123"},
        {"slot": "shoes", "source": "online", "descriptor": "Black leather oxford shoes, men's size 10"}
      ]
    }
  ]
}
```

**Key Point:** The AI is creative here - it's making style decisions!

---

### **Phase 3: Product Search** 🛍️
**File:** `agentic_layer.py` + `product_search_service.py`

**What happens:**
For each item marked as "online", the system searches **4 sources in parallel:**

#### **1. Web Search (Primary)** 🌐
**File:** `integrations/web_product_search.py`

**How it works:**
- Uses **GPT-4o with web browsing** capability
- Searches actual retailer websites (Nordstrom, Macy's, ASOS, Zara)
- Extracts real product URLs, prices, images
- Validates URLs are real (rejects fake/example.com URLs)

**Example:**
```
Query: "Black leather oxford shoes, men's size 10"
↓
GPT-4o searches web → Finds Nordstrom product page
↓
Returns: Product with real URL, price $150, image, retailer name
```

#### **2. Google Shopping API** 🔎
**File:** `integrations/google_shopping.py`

**How it works:**
- Calls Google Custom Search API
- Searches across Google Shopping index
- Returns products with prices, ratings, retailer info
- Free tier: 100 searches/day

**Example:**
```
Query: "Black leather oxford shoes"
↓
Google API call → Returns 10 products
↓
Extracts: Title, price, URL, retailer, image
```

#### **3. ASOS API** 👔
**File:** `integrations/asos_api.py`

**How it works:**
- Direct API call to ASOS (fashion retailer)
- Fashion-specific search
- Returns products with size/stock info
- Good for clothing items

#### **4. Vector Database** 📊
**File:** `vector_index.py`

**How it works:**
- Uses **pgvector** (PostgreSQL with vector search)
- Products stored with **embeddings** (AI-generated number arrays)
- Semantic search: Finds similar products by meaning, not just keywords
- Fast similarity matching

**Example:**
```
Query: "Black leather oxford shoes"
↓
Convert to embedding vector
↓
Find similar vectors in database
↓
Return matching products
```

**Key Point:** All 4 sources run **in parallel** (async) for speed!

---

### **Product Merging & Ranking** 🎯

**What happens:**
1. **Merge results** - Combines products from all 4 sources
2. **Deduplicate** - Removes duplicate URLs
3. **Filter** - Removes items over budget, wrong retailers
4. **Rank** - Scores each product on:
   - Match quality (30%)
   - Price fit (25%)
   - Source reliability (20%)
   - In-stock status (15%)
   - Brand preference (10%)

**Then:**
5. **LLM Re-ranking** - GPT-4o-mini reviews top 50 and picks best 3
6. **Affiliate links** - Converts product URLs to affiliate links (for commission)

---

### **Phase 4: Scoring** 📊
**File:** `scoring_matrix.py`

**What happens:**
Scores each outfit on 6 factors:

1. **Weather Appropriateness (20%)** - Is it suitable for the temperature?
2. **Occasion Fit (25%)** - Does it match the event (formal, casual)?
3. **Color Harmony (15%)** - Do colors work together?
4. **Budget Efficiency (20%)** - Good value for money?
5. **Trend Alignment (10%)** - Matches current fashion?
6. **Wardrobe Utilization (10%)** - Uses your existing items?

**Final Score:** 0-10 (higher = better)

---

## 🔄 Complete Example Flow

```
User Input:
"I need an outfit for a wedding in NYC on Oct 5, budget $150-300"

↓ PHASE 1: Context Prep
- Weather: 20°C, clear
- Wardrobe: 2 items (brown sweater, navy chinos)
- Occasion: Wedding
- Budget: $150 soft, $300 hard

↓ PHASE 2: LLM Reasoning
GPT-4o creates:
- Outfit 1: Use wardrobe sweater + chinos, buy shoes online
- Outfit 2: Use chinos, buy shirt + blazer online
- Outfit 3: All new items

↓ PHASE 3: Product Search (for "online" items)
Searching for: "Black leather oxford shoes, men's"

Parallel searches:
├─ Web Search → 6 products (Nordstrom, Macy's)
├─ Google Shopping → 8 products
├─ ASOS API → 5 products
└─ Vector DB → 3 products

Merged: 22 unique products
Filtered: 18 within budget
Ranked: Top 3 selected

↓ PHASE 4: Scoring
Outfit 1: 8.2/10 (great wardrobe use, good value)
Outfit 2: 7.7/10
Outfit 3: 8.7/10 (best style match)

↓ FINAL OUTPUT
Returns top 3 outfits with:
- Real product links
- Prices
- Images
- Scores
- Reasoning
```

---

## 🧠 How LLM is Used

### **1. Outfit Generation (GPT-4o)**
- **What:** Creates outfit concepts
- **Input:** Context pack (wardrobe, weather, occasion, style)
- **Output:** 3 outfit compositions with wardrobe IDs + online descriptions
- **Why GPT-4o:** Needs creativity and style understanding

### **2. Web Product Search (GPT-4o)**
- **What:** Searches real websites for products
- **Input:** Product description ("Black leather oxford shoes")
- **Output:** Real product URLs, prices, images
- **Why GPT-4o:** Has web browsing capability to find actual products

### **3. Product Re-ranking (GPT-4o-mini)**
- **What:** Picks best products from candidates
- **Input:** 50 product candidates + description
- **Output:** Top 3 products with reasoning
- **Why GPT-4o-mini:** Cheaper, still good at ranking

---

## 🔍 Product Search Deep Dive

### **Google Shopping API:**
```
1. Build search query: "Black leather oxford shoes men's size 10 $150-300"
2. Call Google API: https://www.googleapis.com/custom-search/v1
3. Parse response: Extract title, price, URL, retailer
4. Return Product objects
```

### **Web Search (GPT-4o):**
```
1. Create prompt: "Search for Black leather oxford shoes on Nordstrom, Macy's..."
2. GPT-4o uses web browsing tool to visit retailer sites
3. Extract product data from pages
4. Validate URLs are real (not fake)
5. Return Product objects
```

### **Vector DB:**
```
1. Convert query to embedding: [0.123, -0.456, ...] (1536 numbers)
2. Search database: Find products with similar embeddings
3. Use cosine similarity: Calculate how similar vectors are
4. Return top matches
```

---

## ⚡ Performance

- **Phase 1:** ~1-2 seconds (weather, normalization)
- **Phase 2:** ~8-12 seconds (LLM outfit generation)
- **Phase 3:** ~15-25 seconds (parallel product search)
- **Phase 4:** ~1 second (scoring)

**Total:** ~25-40 seconds for complete outfit recommendations

---

## 💡 Key Design Decisions

1. **Parallel Search** - All 4 sources search simultaneously (faster)
2. **Fail-Safe** - If one source fails, others still work
3. **URL Validation** - Rejects fake URLs, only real products
4. **Wardrobe-First** - AI tries to use your existing items first
5. **Multi-Signal Ranking** - Considers price, match, source quality, not just relevance

---

## 🎯 Summary

**Simple Version:**
1. Gather info (weather, wardrobe, occasion)
2. AI creates outfit ideas
3. Search 4 places for products to buy
4. Pick best products
5. Score outfits
6. Return top 3

**The Magic:**
- AI makes style decisions
- Searches find real products you can buy
- Everything happens in parallel for speed
- System is robust (if one thing fails, others work)


