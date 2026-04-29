#!/usr/bin/env python3
"""Test Angel One API endpoints to find working quote endpoint."""

import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

auth_token = os.getenv('ANGEL_ONE_AUTH_TOKEN')
api_key = os.getenv('ANGEL_ONE_API_KEY')

print("=" * 80)
print("Testing Angel One Quote API Endpoints")
print("=" * 80 + "\n")

endpoints = [
    ("https://smartapi.angelbroking.com/rest/secure/quote/", "Official quote endpoint"),
    ("https://smartapi.angelbroking.com/smartapi/quote/", "Alternative smartapi path"),
    ("https://api.angelbroking.com/rest/secure/quote/", "API domain"),
    ("https://smartapi.angelbroking.com/rest/secure/Quote", "Capital Q"),
]

for url, description in endpoints:
    try:
        print(f"📍 {description}")
        print(f"   URL: {url}")
        
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB"
        }
        
        payload = {
            "mode": "LTP",
            "exchangeTokens": {
                "MCX": ["SILVER"]
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ SUCCESS!")
            try:
                data = response.json()
                print(f"   Data: {json.dumps(data, indent=2)[:300]}")
            except:
                print(f"   Response: {response.text[:200]}")
        else:
            print(f"   ❌ Error: {response.status_code}")
            if response.text:
                print(f"   Response: {response.text[:150]}")
        
        print()
        
    except Exception as e:
        print(f"   ❌ Exception: {str(e)[:100]}\n")

print("\n" + "=" * 80)
print("Testing with WebSocket Quote Subscription (Alternative)")
print("=" * 80 + "\n")

# Alternative: Try WebSocket quote subscription
ws_url = "wss://smartapiquote.angelbroking.com/smartquote/"
print(f"WebSocket URL: {ws_url}")
print("(Requires separate WebSocket connection implementation)")
