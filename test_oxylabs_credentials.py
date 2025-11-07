"""Quick test of Oxylabs credentials"""
import requests
import json

# Test credentials
username = "elara_u1y0M"
password = "AVFGxj4K3fx8n+i"

# Simple test query
payload = {
    "source": "google_shopping",
    "query": "shoes",
    "domain": "com",
    "geo_location": "United States",
    "parse": True
}

print(f"Testing Oxylabs credentials...")
print(f"Username: {username}")
print(f"API: https://realtime.oxylabs.io/v1/queries")
print()

try:
    response = requests.post(
        "https://realtime.oxylabs.io/v1/queries",
        auth=(username, password),
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=30
    )

    print(f"Status code: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")
    print()

    if response.status_code == 200:
        data = response.json()
        print("SUCCESS - Credentials work!")
        print(f"Response keys: {list(data.keys())}")
    else:
        print(f"FAILED - HTTP {response.status_code}")
        print(f"Response body: {response.text[:500]}")

except requests.exceptions.Timeout:
    print("TIMEOUT - Request took longer than 30 seconds")
    print("This suggests the API is unreachable or very slow")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
