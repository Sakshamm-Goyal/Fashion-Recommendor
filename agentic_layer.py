# agentic_layer.py
"""
Enhanced Agentic layer for intelligent product matching and retrieval.

Uses hybrid search across multiple sources:
- Vector DB (existing catalog)
- Google Shopping API (real-time)
- ASOS API (fashion-specific)
# - Affiliate networks (disabled for now)

Reranks results using LLM.
"""
import asyncio
from typing import Dict, List
import config
from services.product_search_service import search_products_hybrid
from services.ranking_engine import rank_products
# from integrations.affiliate_manager import convert_to_affiliate_link
from contracts.models import Product
from openai import OpenAI
import json

client = OpenAI(api_key=config.OPENAI_API_KEY)

RERANK_PROMPT = """You are an expert fashion merchandiser with deep knowledge of style, fit, quality, and value.

**Task**: Rank these product candidates by how well they match the descriptor.

**Descriptor**: "{desc}"

**User Context**:
- Gender: {gender}
- Occasion: {occasion}
- Style preferences: {style_prefs}
- Budget range: ${soft_cap} - ${hard_cap}

**Ranking Criteria** (in order of importance):
1. **Match Quality** (40%) - How closely does the product match the descriptor?
   - Style accuracy (formal vs casual, cut, silhouette)
   - Material/fabric match
   - Color accuracy

2. **Value for Money** (25%) - Best quality within budget
   - Prefer items at or below soft cap (${soft_cap})
   - Consider brand reputation vs price
   - Quality signals (if available)

3. **Versatility** (20%) - Can this work with other wardrobe items?
   - Classic/timeless vs trendy
   - Color versatility
   - Multi-occasion potential

4. **Retailer Trust** (15%) - Reliable retailers with good return policies
   - Prefer: Nordstrom, Macy's, J.Crew, Everlane > Unknown retailers
   - Major department stores > obscure websites

**Product Candidates**:
{candidates}

**Output**: Return a JSON object with:
- "top_picks": Array of top 3 product IDs in ranked order
- "reasoning": Brief explanation why the #1 pick is best (1 sentence)

Example:
{{
  "top_picks": ["chatgpt-123", "asos-456", "vector-789"],
  "reasoning": "Best match for formal style at excellent price point from trusted retailer"
}}

Return ONLY valid JSON, no additional text.
"""


async def find_candidates_for_descriptor(
    desc: str,
    budget: Dict,
    retailers: List[str],
    filters: Dict = None
) -> List[Product]:
    """
    Searches for product candidates using HYBRID multi-source search.

    NEW: Uses hybrid search service to query:
    - Vector DB (existing products)
    - Google Shopping API (real-time)
    - ASOS API (fashion-specific)
    - Future: Web scrapers

    Args:
        desc: Natural language description of the desired item
        budget: Budget dict with soft_cap and hard_cap
        retailers: List of allowed retailer names
        filters: Optional filters (gender, color, size, brand)

    Returns:
        List of Product objects from multiple sources
    """
    # Use new hybrid search service
    products = await search_products_hybrid(
        descriptor=desc,
        budget=budget,
        filters=filters or {},
        retailers_allowlist=retailers,
        k=50  # Get top 50 candidates
    )

    return products


async def llm_rerank(descriptor: str, candidates: List[Product], ctx: Dict = None) -> List[str]:
    """
    Uses a lightweight LLM to rerank product candidates with rich context.

    Args:
        descriptor: The original item description
        candidates: List of Product objects
        ctx: Context dict with user preferences, occasion, budget

    Returns:
        List of top product IDs in ranked order
    """
    if not candidates:
        return []

    # Extract context or use defaults
    if ctx:
        gender = ctx.get("session", {}).get("gender", "unisex")
        occasion = ctx.get("session", {}).get("occasion", "casual")
        style_prefs = ", ".join(ctx.get("user_profile", {}).get("style_keywords", ["classic", "versatile"]))
        soft_cap = ctx.get("constraints", {}).get("budget", {}).get("soft_cap", 150)
        hard_cap = ctx.get("constraints", {}).get("budget", {}).get("hard_cap", 300)
    else:
        gender, occasion, style_prefs = "unisex", "casual", "classic"
        soft_cap, hard_cap = 150, 300

    # Build candidate snippet (limit to top 15 for better choices)
    snippet = "\n".join([
        f"- {c.id}: {c.title} | {c.retailer} | ${c.price} {c.currency} | Source: {c.source}"
        for c in candidates[:15]
    ])

    text = RERANK_PROMPT.format(
        desc=descriptor,
        gender=gender,
        occasion=occasion,
        style_prefs=style_prefs,
        soft_cap=soft_cap,
        hard_cap=hard_cap,
        candidates=snippet
    )

    try:
        resp = client.chat.completions.create(
            model=config.OPENAI_MINI_MODEL,
            messages=[{"role": "user", "content": text}],
            response_format={"type": "json_object"}
            # Note: temperature removed - json_object mode only supports default (1.0)
        )

        content = resp.choices[0].message.content
        parsed = json.loads(content)
        ids = parsed.get("top_picks") or parsed.get("ids") or []

        # Log reasoning if available
        reasoning = parsed.get("reasoning")
        if reasoning:
            print(f"  [Rerank] {descriptor[:50]}... → {reasoning}")

        return ids if isinstance(ids, list) else []

    except Exception as e:
        print(f"  [Rerank] Error: {e} - falling back to top candidates")
        # Fallback: return top 3 by vector similarity
        return [c.id for c in candidates[:3]]


def pick_first_by_ids(ids: List[str], candidates: List[Product]) -> List[Product]:
    """
    Returns products in the order specified by IDs.
    """
    index = {c.id: c for c in candidates}
    return [index[i] for i in ids if i in index]


async def fetch_buy_links(llm_output: dict, ctx: dict) -> dict:
    """
    Main agentic function: enriches LLM output with actual product matches.

    For each composition item marked as 'online', this function:
    1. Searches the product catalog
    2. Reranks results using LLM
    3. Attaches the best match with price, image, and buy link

    Args:
        llm_output: Output from llm_reasoning.generate_outfits
        ctx: Context pack from deterministic layer

    Returns:
        Enriched dict with final_recommendations and scored outfits
    """
    retailers = ctx["constraints"]["retailers_allowlist"]
    budget = ctx["constraints"]["budget"]

    tasks = []
    plan = []

    # Phase 1: Collect all online items and prepare search tasks
    for outfit in llm_output["outfits"]:
        enriched_items = []
        for comp in outfit["composition"]:
            if comp["source"] == "online":
                # Queue async product search
                tasks.append(find_candidates_for_descriptor(
                    comp["descriptor"],
                    budget,
                    retailers
                ))
                plan.append((outfit, comp))
            else:
                # Wardrobe items pass through unchanged
                enriched_items.append({**comp, "product": None})

        outfit["_pending_online"] = enriched_items

    # Phase 2: Execute searches sequentially to prevent OpenSERP overload
    # NOTE: Changed from parallel to sequential because 12 parallel searches
    # overwhelm OpenSERP even with per-client rate limiting
    results = []
    if tasks:
        for i, task in enumerate(tasks):
            print(f"[ProductMatch] Searching {i+1}/{len(tasks)}...")
            result = await task
            results.append(result)
            # Small delay between searches to give OpenSERP breathing room
            if i < len(tasks) - 1:
                await asyncio.sleep(0.5)

    # Phase 3: Rerank and attach products
    idx = 0
    for (outfit, comp) in plan:
        candidates = results[idx]
        idx += 1

        print(f"[ProductMatch] '{comp['descriptor']}' -> {len(candidates)} candidates found")

        # Rerank candidates with full context for better evaluation
        ids = await llm_rerank(comp["descriptor"], candidates, ctx) if candidates else []
        picks = pick_first_by_ids(ids, candidates) or candidates[:1]

        print(f"[ProductMatch] After reranking: {len(picks)} products selected")

        # Attach best match
        # NOTE: Affiliate link enrichment commented out for now
        if picks:
            product = picks[0]
            # # Try to convert to affiliate link
            # affiliate_link, commission_rate = convert_to_affiliate_link(
            #     product.url,
            #     product.retailer
            # )
            # if affiliate_link:
            #     product.affiliate_link = affiliate_link
            #     product.commission_rate = commission_rate

            comp["product"] = product
        else:
            comp["product"] = None

        outfit["_pending_online"].append(comp)

    # Phase 4: Stitch together final recommendations
    final = {"final_recommendations": []}

    for outfit in llm_output["outfits"]:
        items = []

        for comp in outfit["_pending_online"]:
            if comp["source"] == "wardrobe":
                items.append({
                    "item_type": "wardrobe",  # Clear distinction: from user's wardrobe
                    "slot": comp["slot"],
                    "source": "wardrobe",
                    "wardrobe_item_id": comp["wardrobe_item_id"]
                })
            else:
                p = comp.get("product")
                if p:
                    # Use original URL (affiliate links disabled for now)
                    buy_link = p.url
                    # buy_link = p.affiliate_link if p.affiliate_link else p.url

                    items.append({
                        "item_type": "purchase",  # Clear distinction: needs to be purchased
                        "slot": comp["slot"],
                        "source": p.retailer,
                        "retailer": p.retailer,  # Explicit retailer field for clarity
                        "name": p.title,
                        "price": {"value": float(p.price), "currency": p.currency} if p.price is not None else None,
                        "image": p.image,
                        "buy_link": buy_link,
                        "match_explainer": comp.get("descriptor", ""),
                        "brand": p.brand,
                        # "affiliate_commission": p.commission_rate  # Disabled for now
                    })
                else:
                    # Product search failed - log warning
                    print(f"⚠️  [Incomplete Outfit] No product found for {comp.get('slot', 'unknown slot')}: '{comp.get('descriptor', 'no description')}'")
                    print(f"   This item will be missing from the '{outfit['name']}' outfit")

        # Validate outfit completeness (minimum requirements)
        slots = {item.get("slot") for item in items}
        has_top = any(s in slots for s in ["top", "dress", "jumpsuit"])
        has_bottom = "bottom" in slots or any(s in slots for s in ["dress", "jumpsuit"])  # Dress counts as bottom
        has_footwear = "footwear" in slots

        min_items = 3  # Minimum: top + bottom + footwear
        is_complete = has_top and has_bottom and has_footwear and len(items) >= min_items

        if not is_complete:
            print(f"⚠️  [Incomplete Outfit Warning] '{outfit['name']}' is missing key items:")
            if not has_top:
                print(f"   - Missing: Top/Dress")
            if not has_bottom:
                print(f"   - Missing: Bottom/Pants")
            if not has_footwear:
                print(f"   - Missing: Footwear")
            if len(items) < min_items:
                print(f"   - Only {len(items)} items (minimum: {min_items})")

        final["final_recommendations"].append({
            "look": outfit["name"],
            "items": items
        })

        # Clean up temporary field
        del outfit["_pending_online"]

    # Also return outfits for scoring
    final["outfits"] = llm_output["outfits"]

    return final
