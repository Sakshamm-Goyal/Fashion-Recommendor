# scripts/seed_products.py
"""
Seeds the product vector database with synthetic fashion products.
Generates ~200 diverse items across retailers, categories, and price points.
"""
import os
import sys
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from vector_index import ensure_schema, upsert_products

random.seed(42)

# Fashion catalog data
RETAILERS = [
    "Zara", "H&M", "ASOS", "Nordstrom", "Macy's",
    "Amazon Fashion", "Urban Outfitters", "Revolve"
]

COLORS = [
    "beige", "black", "white", "navy", "olive", "brown",
    "charcoal", "khaki", "cream", "espresso", "burgundy",
    "forest green", "grey", "camel", "ivory"
]

FABRICS = [
    "linen", "cotton", "wool", "denim", "leather", "suede",
    "silk", "poplin", "seersucker", "viscose", "crochet",
    "jersey", "cashmere", "tweed", "chambray"
]

# (category, subcategory) pairs
CATEGORIES = [
    ("outerwear", "blazer"),
    ("outerwear", "overshirt"),
    ("outerwear", "jacket"),
    ("tops", "oxford shirt"),
    ("tops", "dress shirt"),
    ("tops", "tee"),
    ("tops", "polo"),
    ("tops", "knit"),
    ("tops", "sweater"),
    ("bottoms", "chinos"),
    ("bottoms", "jeans"),
    ("bottoms", "trousers"),
    ("footwear", "loafers"),
    ("footwear", "derbies"),
    ("footwear", "sneakers"),
    ("footwear", "boots"),
    ("accessory", "belt"),
    ("accessory", "watch"),
    ("accessory", "bag"),
]

OCCASIONS = ["wedding", "work", "date night", "smart casual", "casual", "business"]


def generate_title(color: str, fabric: str, cat: str, sub: str) -> str:
    """Generates a realistic product title."""
    templates = {
        ("outerwear", "blazer"): f"{color.title()} {fabric.title()} Blazer",
        ("outerwear", "overshirt"): f"{color.title()} {fabric.title()} Overshirt",
        ("outerwear", "jacket"): f"{color.title()} {fabric.title()} Jacket",
        ("tops", "oxford shirt"): f"{color.title()} {fabric.title()} Oxford Shirt",
        ("tops", "dress shirt"): f"{color.title()} {fabric.title()} Dress Shirt",
        ("tops", "tee"): f"{color.title()} {fabric.title()} T-Shirt",
        ("tops", "polo"): f"{color.title()} {fabric.title()} Polo Shirt",
        ("tops", "knit"): f"{color.title()} {fabric.title()} Knit",
        ("tops", "sweater"): f"{color.title()} {fabric.title()} Sweater",
        ("bottoms", "chinos"): f"{color.title()} {fabric.title()} Chinos",
        ("bottoms", "jeans"): f"{color.title()} {fabric.title()} Jeans",
        ("bottoms", "trousers"): f"{color.title()} {fabric.title()} Trousers",
        ("footwear", "loafers"): f"{color.title()} {fabric.title()} Loafers",
        ("footwear", "derbies"): f"{color.title()} {fabric.title()} Derby Shoes",
        ("footwear", "sneakers"): f"{color.title()} {fabric.title()} Sneakers",
        ("footwear", "boots"): f"{color.title()} {fabric.title()} Boots",
        ("accessory", "belt"): f"{color.title()} {fabric.title()} Belt",
        ("accessory", "watch"): f"{color.title()} Watch",
        ("accessory", "bag"): f"{color.title()} {fabric.title()} Bag",
    }

    key = (cat, sub)
    if key in templates:
        return templates[key]
    return f"{color.title()} {fabric.title()} {sub.title()}"


def synthesize_items(n: int = 200) -> list:
    """
    Generates synthetic fashion product data.

    Args:
        n: Number of products to generate

    Returns:
        List of product dicts with all required fields
    """
    items = []

    for i in range(n):
        retailer = random.choice(RETAILERS)
        color = random.choice(COLORS)
        fabric = random.choice(FABRICS)
        cat, sub = random.choice(CATEGORIES)
        occasion = random.choice(OCCASIONS)

        # Price distribution: more items in mid-range
        if random.random() < 0.6:
            price = round(random.uniform(39, 149), 2)
        else:
            price = round(random.uniform(150, 299), 2)

        # Generate unique ID
        cid = f"{retailer[:2].lower()}_{cat[:2]}_{sub[:2]}_{i:04d}"

        # Generate title
        title = generate_title(color, fabric, cat, sub)

        # Metadata
        meta = {
            "category": cat,
            "subcategory": sub,
            "color": color,
            "fabric": fabric,
            "occasion": occasion,
            "sizes": ["S", "M", "L", "XL"] if cat != "footwear" else ["40", "41", "42", "43"],
        }

        # Create searchable embedding text
        embed_text = (
            f"{title}. {cat} {sub}. color {color}. fabric {fabric}. "
            f"for {occasion}. {retailer}. "
            f"Available in sizes {', '.join(meta['sizes'])}."
        )

        items.append({
            "id": cid,
            "retailer": retailer,
            "title": title,
            "price": price,
            "currency": "USD",
            "url": f"https://{retailer.replace(' ', '').lower()}.example.com/p/{cid}",
            "image": f"https://cdn.example.com/images/{cid}.jpg",
            "meta": meta,
            "text_for_embed": embed_text
        })

    return items


def main():
    """Main seeding function."""
    print("=" * 60)
    print("ELARA PRODUCT DATABASE SEEDER")
    print("=" * 60)
    print()

    print("Step 1: Ensuring database schema...")
    ensure_schema()
    print("✓ Schema ready")
    print()

    print("Step 2: Generating synthetic products...")
    items = synthesize_items(200)
    print(f"✓ Generated {len(items)} products")
    print()

    print("Step 3: Creating embeddings and upserting to database...")
    print("(This will call the OpenAI embeddings API)")
    upsert_products(items)
    print("✓ Products seeded successfully")
    print()

    print("=" * 60)
    print("SEEDING COMPLETE")
    print("=" * 60)
    print()
    print(f"Total products in database: {len(items)}")
    print("You can now run the demo with: make demo")


if __name__ == "__main__":
    main()
