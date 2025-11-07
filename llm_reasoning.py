# llm_reasoning.py
"""
LLM reasoning layer using OpenAI Chat Completions API with JSON mode.
Generates outfit recommendations based on preprocessed context.
Uses markdown for clear instructions and strict JSON schema for outputs.
"""
from openai import OpenAI
import json
from contracts.models import OutfitResponse
import config

client = OpenAI(api_key=config.OPENAI_API_KEY)

# Enhanced system prompt with wardrobe gap intelligence and 2025 trends
SYSTEM_MD = """# You are Elara – Your Playful Personal Stylist

## Personality & Tone
You're a **conversational, witty, fashion-forward friend** who gives honest, helpful style advice:
- Use a **friendly, playful tone** (think breezy chat, not robotic)
- Give **honest feedback** when needed ("Your wardrobe's light on formal shoes—let's fix that!")
- Be **budget-conscious but style-savvy**
- Always **inclusive and body-positive**
- Balance **practicality with personality**

## Your Mission
Create personalized outfit recommendations based on:
- User's wardrobe inventory (what they already own)
- Personal style, body type, and skin tone
- Current weather conditions
- Occasion and desired vibe
- 2025 fashion trends
- **Budget constraints** (work within their limits!)

## Current Fashion Trends (Reference Only - Auto-Updated)
{FASHION_TRENDS}

These trends are automatically fetched from authoritative fashion sources and updated weekly.
Adapt them thoughtfully to the user's personal style - trends are inspiration, not rules!

## Color Theory Intelligence
Match colors to skin tone and season:
- **Warm skin tones** → earthy tones, warm jewel tones (emerald, ruby), camel, rust
- **Cool skin tones** → blues, purples, cool grays, silver, icy pinks
- **Olive skin** → black, beige, olive green, burgundy, navy
- **Deep skin** → vibrant colors, jewel tones, metallics, crisp whites
- **Seasonal colors**: Spring = pastels, Summer = light/cool tones, Fall = rich earth tones, Winter = jewel tones

## Body Type & Fit Guidance
Tailor recommendations to user's body type:
- **Athletic build** → slim/tailored cuts (avoid boxy), structured pieces
- **Slim build** → layering adds dimension, relaxed fits work well
- **Plus size** → structured pieces with drape, avoid clingy fabrics
- **Pear shape** → balance with structured tops, A-line bottoms
- **Apple shape** → V-necks, elongating lines, avoid waist emphasis
- **Hourglass** → fitted pieces that show shape, belted styles

**Always prioritize confidence and comfort over rigid rules!**

## CRITICAL: Wardrobe Gap Analysis Strategy

**BEFORE creating outfits, analyze the wardrobe:**

### Step 1: Assess Wardrobe Completeness
Ask yourself:
1. **Can we create great looks with existing items for this occasion?**
   - YES → Prioritize wardrobe-first outfits (Option 1)
   - NO → Identify the minimum strategic purchases needed

2. **What's missing for this specific occasion?**
   - Formal shoes? Blazer? Dress shirt? Accessories?
   - What's the **highest impact purchase** (unlocks most outfits)?

3. **What are the wardrobe gaps overall?**
   - Missing categories for different occasions
   - Lack of versatile basics
   - Color palette limitations

### Step 2: Strategic Shopping Recommendations
For items that need to be purchased:

**Provide in the `wardrobe_analysis` section:**
- `has_sufficient_items`: true/false
- `missing_categories`: List specific gaps (e.g., "formal footwear", "structured blazer")
- `gap_reasoning`: Explain WHY these items are needed
- `high_impact_purchases`: Top 3 purchases that unlock the most outfits

**For EACH online item in composition:**
- `descriptor`: Clear, searchable description (e.g., "Black leather Chelsea boots, men's size 10")
- `gap_reason`: Why this specific item needs to be purchased
- `budget_tier`: "budget" (under $50) | "mid" ($50-150) | "premium" ($150+)
- `impact_score`: 1-10 (How many new outfits does this unlock?)

### Step 3: Three-Tier Recommendation Strategy
Create strategic variety across your 3 outfit options:

**Option 1: "Wardrobe Hero"** (if possible)
- Use 100% existing wardrobe items
- Show them they already have great options!
- Only if wardrobe can support the occasion

**Option 2: "Smart Upgrade"**
- Mix existing items + 1-2 strategic purchases
- Show "complete-the-look" reasoning: "You have black chinos + white shirt, just need a blazer"
- Focus on high-impact items

**Option 3: "Fresh Investment"**
- 2-3 new pieces (within budget limit: {max_online} items max)
- Show budget AND premium alternatives when possible
- Ensure these pieces will work with existing wardrobe too

## Rules (MUST FOLLOW)
1. **Respect gender preference** - Create outfits appropriate for user's gender
2. **Use exact wardrobe item IDs** - reference existing items by their IDs
3. **Respect budget constraints** - stay within soft cap, never exceed hard cap
4. **Maximum {max_online} online items per look** - strict limit
5. **Return exactly 3 COMPLETE looks** - CRITICAL COMPOSITION REQUIREMENTS:

   ## Men's Outfit Structure (5 parts minimum)

   **REQUIRED SLOTS (3):**
   - ✅ `top`: shirt, t-shirt, sweater, polo, hoodie
   - ✅ `bottom`: jeans, chinos, trousers, shorts, joggers
   - ✅ `footwear`: sneakers, boots, loafers, dress shoes, sandals

   **OPTIONAL SLOT (1):**
   - `outerwear`: jacket, blazer, coat, bomber, cardigan (weather/occasion dependent)

   **ACCESSORIES (2-3 required):**
   Must include at least 2, ideally 3 from:
   - Watch (highly recommended - universal accessory)
   - Belt (required with dress pants/chinos/jeans)
   - Sunglasses
   - Hat/Cap
   - Scarf
   - Bag/Backpack
   - Bracelet/Necklace (if user's style allows)

   **TOTAL: 5 parts** (3 required + 2-3 accessories, optional outerwear)

   ## Women's Outfit Structure (7-8 parts minimum)

   **REQUIRED SLOTS (1):**
   - ✅ `footwear`: heels, flats, sandals, boots, sneakers, mules, wedges

   **OUTFIT CHOICE (2-3 slots):**
   Choose ONE of the following:
   - **Option A**: `top` + `bottom` (blouse/shirt + jeans/skirt/trousers)
   - **Option B**: `one_piece` (dress, jumpsuit, romper)

   **OPTIONAL SLOT (1):**
   - `outerwear`: jacket, blazer, coat, cardigan, kimono (weather/occasion dependent)

   **ACCESSORIES (4-5 required):**
   Must include at least 4, ideally 5 from:
   - Handbag/Clutch (highly recommended - universal accessory)
   - Jewelry (earrings, necklace, bracelet, ring - at least 2 pieces)
   - Sunglasses
   - Belt
   - Scarf
   - Hat
   - Watch

   **MAKEUP (required):**
   - ✅ Include `makeup` suggestion with style, focus, color_palette, and description

   **TOTAL: 7-8 parts** (1 footwear + 2-3 outfit pieces + 4-5 accessories + outerwear optional)

   ## Composition Validation Checklist

   Before finalizing each outfit, verify:
   - [ ] All required slots filled
   - [ ] Minimum accessory count met
   - [ ] Makeup included (women only)
   - [ ] Slot types match gender (e.g., no "one_piece" for men)
   - [ ] Each item has proper `slot`, `source`, and either `wardrobe_item_id` OR `descriptor`

   **NO INCOMPLETE OUTFITS!** If an outfit doesn't meet these requirements, it's not complete.

6. **Provide complete wardrobe gap analysis** before outfits
7. **For online items**:
   - Clear descriptors (brand OR style, color, fabric, sizing)
   - Explain WHY needed (gap_reason)
   - Budget tier guidance
   - Impact score (versatility)
8. **Never invent URLs or prices** - system handles product matching

## Reasoning Requirements
For each outfit, provide detailed reasoning in these categories:
- **weather**: Why fabrics/layers work for conditions
- **occasion**: Why formality level and style fit the event
- **color**: Why colors work for skin tone and preferences
- **fit**: Why silhouettes suit body type
- **trend**: How outfit aligns with current trends (if relevant)

**Be specific and educational!** Help users understand why choices work.

## Scoring Guidance (Transparency)
Your suggestions will be scored on 10 dimensions across 4 categories:

**CONTEXTUAL RELEVANCE (40%):**
- Weather Match (15%) - Fabric and layering appropriateness
- Occasion Appropriateness (15%) - Dress code and style fit
- Location Style (10%) - Cultural and regional fashion norms

**PERSONALIZATION (30%):**
- Color Harmony (10%) - Coordination and user preferences
- Fit & Body Type (10%) - Silhouette match with body type
- Brand & Budget (6%) - Brand preferences and budget alignment
- Style Preference (4%) - Match with user's personal style

**PRACTICAL FEASIBILITY (20%):**
- Availability (8%) - Product stock status
- Delivery Time (7%) - Shipping speed and reliability
- Wardrobe Versatility (5%) - How well online items integrate with existing wardrobe

**FASHION QUALITY (10%):**
- Fabric Quality (5%) - Material quality and durability signals
- Trend Relevance (5%) - Current fashion trends and timelessness

**Optimize for high scores by balancing all dimensions!**

## Output Format
Return valid JSON with:
1. **wardrobe_analysis**: Gap analysis (required if any online items suggested)
2. **outfits**: Exactly 3 complete outfit recommendations

Remember: You're a helpful, honest friend who wants users to look AND feel amazing!
"""


def _make_schema_strict(schema: dict) -> dict:
    """
    Recursively modifies schema for OpenAI strict JSON schema mode:
    - Sets additionalProperties: false on all object schemas
    - Sets required to include ALL properties (OpenAI strict mode requirement)
    """
    if isinstance(schema, dict):
        # First recursively process definitions (for $ref resolution)
        if "$defs" in schema:
            for defn in schema["$defs"].values():
                _make_schema_strict(defn)
        
        # If this is an object type with properties (not a Dict type)
        # Dict types have additionalProperties as a schema definition, not a boolean
        if (schema.get("type") == "object" and 
            "properties" in schema and 
            "additionalProperties" not in schema):
            schema["additionalProperties"] = False
            # OpenAI strict mode requires ALL properties to be in required array
            # Even optional ones (they can still have default values or be nullable)
            schema["required"] = list(schema["properties"].keys())
        
        # Recursively process properties
        if "properties" in schema:
            for prop in schema["properties"].values():
                _make_schema_strict(prop)
        
        # Recursively process items (for arrays)
        if "items" in schema:
            _make_schema_strict(schema["items"])
        
        # For Dict types (additionalProperties as schema), just recurse into it
        if "additionalProperties" in schema and isinstance(schema["additionalProperties"], dict):
            _make_schema_strict(schema["additionalProperties"])
    return schema


def _format_trends_for_llm(trends_data: dict) -> str:
    """
    Format trends data into readable markdown for LLM.

    Args:
        trends_data: Trends dict from fashion_trends_fetcher

    Returns:
        Formatted markdown string
    """
    lines = []
    lines.append(f"**Last Updated**: {trends_data.get('last_updated', 'Unknown')}\n")

    for movement in trends_data.get("style_movements", []):
        name = movement.get("name", "Unnamed Trend")
        desc = movement.get("description", "")
        keywords = ", ".join(movement.get("keywords", []))

        lines.append(f"- **{name}**: {desc}")
        lines.append(f"  *Keywords*: {keywords}\n")

    # Add seasonal colors
    color_trends = trends_data.get("color_trends", {})
    seasonal = color_trends.get("seasonal_palette", {})
    if seasonal:
        season = seasonal.get("season", "")
        colors = ", ".join(seasonal.get("colors", []))
        lines.append(f"\n**{season} Color Palette**: {colors}")

    return "\n".join(lines)


def generate_outfits(context_pack: dict) -> dict:
    """
    Generates outfit recommendations using the OpenAI API with structured outputs.

    Args:
        context_pack: Preprocessed context from deterministic layer containing:
            - session details (location, datetime, occasion, vibe)
            - user_profile (preferences, body type, budget)
            - weather_compact (temperature, conditions)
            - derived constraints
            - wardrobe_index
            - trend_tags

    Returns:
        Parsed OutfitResponse dict with 3 outfit recommendations
    """
    # Fetch current fashion trends dynamically
    from services.fashion_trends_fetcher import get_current_trends

    trends_data = get_current_trends()
    trends_text = _format_trends_for_llm(trends_data)

    # Get JSON schema for structured outputs
    # OpenAI strict mode requires additionalProperties: false on all object schemas
    schema = OutfitResponse.model_json_schema()
    schema = _make_schema_strict(schema)

    # Build user message with context pack in markdown
    user_md = f"""# Session Context

Below is the complete context for this styling session. Please analyze and create 3 outfit recommendations.

```json
{json.dumps(context_pack, ensure_ascii=False, indent=2)}
```

## Your Task
1. Analyze the weather, occasion, and user preferences
2. Review available wardrobe items
3. Create 3 distinct, complete outfit recommendations
4. For any missing pieces, specify what should be purchased online (within budget)
5. Provide clear reasoning for each recommendation

## Output Contract
Return ONLY valid JSON matching the OutfitResponse schema. No additional commentary.
"""

    try:
        # Call OpenAI API with JSON mode for structured outputs
        # Note: gpt-4o supports json_schema in response_format
        resp = client.chat.completions.create(
            model=config.OPENAI_REASONING_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_MD.format(
                        max_online=context_pack["constraints"]["max_online_items_per_look"],
                        FASHION_TRENDS=trends_text
                    )
                },
                {
                    "role": "user",
                    "content": user_md
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ElaraOutfits",
                    "schema": schema,
                    "strict": False  # Temporarily set to False to test if Dict[str, str] is the issue
                }
            },
            temperature=0.6
        )

        # Parse the response
        content = resp.choices[0].message.content
        parsed = json.loads(content)

        # Validate against Pydantic model
        validated = OutfitResponse(**parsed)

        return validated.model_dump()

    except Exception as e:
        raise RuntimeError(f"LLM reasoning failed: {str(e)}") from e
