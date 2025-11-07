"""Debug Oxylabs response structure"""
import requests
import json

username = "elara_u1y0M"
password = "AVFGxj4K3fx8n+i"

payload = {
    "source": "google_shopping_search",
    "query": "white sneakers under $150",
    "domain": "com",
    "geo_location": "United States",
    "parse": True,
    "start_page": 1,
    "pages": 1
}

print("Making Oxylabs request...")
response = requests.post(
    "https://realtime.oxylabs.io/v1/queries",
    auth=(username, password),
    headers={"Content-Type": "application/json"},
    json=payload,
    timeout=30
)

print(f"Status: {response.status_code}")
data = response.json()

print(f"\nTop-level keys: {list(data.keys())}")

if 'results' in data and len(data['results']) > 0:
    result = data['results'][0]
    print(f"\nFirst result keys: {list(result.keys())}")

    if 'content' in result:
        content = result['content']
        print(f"\nContent type: {type(content)}")
        print(f"Content keys: {list(content.keys()) if isinstance(content, dict) else 'Not a dict'}")

        # Try different paths to products
        if isinstance(content, dict):
            if 'results' in content:
                print(f"\ncontent['results'] keys: {list(content['results'].keys())}")
                if 'organic' in content['results']:
                    products = content['results']['organic']
                    print(f"\nFound {len(products)} products in content['results']['organic']")
                    if products:
                        print(f"\nFirst product keys: {list(products[0].keys())}")
                        print(f"\nFirst product sample:")
                        print(json.dumps(products[0], indent=2))
            elif 'organic' in content:
                products = content['organic']
                print(f"\nFound {len(products)} products in content['organic']")
                if products:
                    print(f"\nFirst product keys: {list(products[0].keys())}")
                    print(f"\nFirst product sample:")
                    print(json.dumps(products[0], indent=2))
