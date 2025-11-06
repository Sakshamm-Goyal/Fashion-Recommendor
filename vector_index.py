# vector_index.py
"""
Vector index for product search using pgvector and OpenAI embeddings.
Provides semantic search over fashion product catalogs.
"""
from typing import List, Dict
import psycopg2
import psycopg2.extras
from openai import OpenAI
import config

client = OpenAI(api_key=config.OPENAI_API_KEY)

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS product_vectors(
  id TEXT PRIMARY KEY,
  retailer TEXT,
  title TEXT,
  price NUMERIC,
  currency TEXT,
  url TEXT,
  image TEXT,
  meta JSONB,
  embedding VECTOR(1536)  -- Using text-embedding-3-large with dimension reduction to 1536
);

DROP INDEX IF EXISTS idx_product_vectors_embedding;

CREATE INDEX idx_product_vectors_embedding
  ON product_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
"""


def get_pg():
    """
    Returns a new Postgres connection.
    """
    return psycopg2.connect(config.PG_DSN)


def ensure_schema():
    """
    Creates the pgvector table and index if they don't exist.
    Safe to call multiple times (idempotent).
    Drops and recreates the index if it exists to handle schema changes.
    """
    with get_pg() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
        conn.commit()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generates embeddings for a list of texts using OpenAI's embedding model.

    Args:
        texts: List of strings to embed

    Returns:
        List of embedding vectors (each is a list of floats)
    """
    if not texts:
        return []

    out = client.embeddings.create(
        model=config.OPENAI_EMBED_MODEL,
        input=texts,
        dimensions=1536  # Use dimension reduction for compatibility with pgvector index limits
    )
    return [d.embedding for d in out.data]


def upsert_products(items: List[Dict]):
    """
    Inserts or updates products in the vector database.
    Generates embeddings for each item's text_for_embed field.

    Args:
        items: List of dicts with keys:
            - id, title, retailer, price, currency, url, image, meta, text_for_embed
    """
    if not items:
        return

    # Generate embeddings in batch
    embs = embed_texts([x["text_for_embed"] for x in items])

    with get_pg() as conn, conn.cursor() as cur:
        for x, e in zip(items, embs):
            cur.execute("""
              INSERT INTO product_vectors(id, retailer, title, price, currency, url, image, meta, embedding)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
              ON CONFLICT (id) DO UPDATE SET
                retailer=EXCLUDED.retailer,
                title=EXCLUDED.title,
                price=EXCLUDED.price,
                currency=EXCLUDED.currency,
                url=EXCLUDED.url,
                image=EXCLUDED.image,
                meta=EXCLUDED.meta,
                embedding=EXCLUDED.embedding
            """, (
                x["id"],
                x["retailer"],
                x["title"],
                x["price"],
                x["currency"],
                x["url"],
                x["image"],
                psycopg2.extras.Json(x.get("meta", {})),
                e
            ))


def search_products(
    descriptor: str,
    price_max: float,
    retailers: List[str],
    k: int = 50
) -> List[Dict]:
    """
    Hybrid semantic + metadata search for products.

    Args:
        descriptor: Natural language description of the desired item
        price_max: Maximum price filter
        retailers: List of allowed retailer names
        k: Number of results to return

    Returns:
        List of product dicts with similarity scores
    """
    # Generate query embedding
    q = embed_texts([descriptor])[0]

    with get_pg() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
          SELECT
            id,
            retailer,
            title,
            price,
            currency,
            url,
            image,
            meta,
            1 - (embedding <=> %s::vector) AS score
          FROM product_vectors
          WHERE retailer = ANY(%s) AND price <= %s
          ORDER BY embedding <=> %s::vector
          LIMIT %s
        """, (q, retailers, price_max, q, k))
        return list(cur.fetchall())
