#!/usr/bin/env python3
"""
Simple script to view seed products in a formatted table.
Run: python view_products.py
"""
from dotenv import load_dotenv
load_dotenv()
from vector_index import get_pg
import json
from tabulate import tabulate

def view_products(limit=20):
    """View products in a formatted table."""
    conn = get_pg()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT id, retailer, title, price, currency, meta
        FROM product_vectors 
        ORDER BY retailer, price 
        LIMIT %s
    ''', (limit,))
    
    rows = cur.fetchall()
    
    # Format data for table
    table_data = []
    for row in rows:
        id_val, retailer, title, price, currency, meta = row
        meta_str = json.dumps(meta) if meta else ""
        table_data.append([
            id_val,
            retailer,
            title[:40] + "..." if len(title) > 40 else title,
            f"${price} {currency}",
            meta.get('category', '') if meta else '',
            meta.get('color', '') if meta else ''
        ])
    
    headers = ["ID", "Retailer", "Title", "Price", "Category", "Color"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # Show count
    cur.execute('SELECT COUNT(*) FROM product_vectors')
    count = cur.fetchone()[0]
    print(f"\nTotal products in database: {count}")
    
    conn.close()

if __name__ == "__main__":
    view_products(limit=30)





