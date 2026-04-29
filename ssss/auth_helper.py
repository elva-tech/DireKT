#!/usr/bin/env python3
"""
Angel One SmartAPI - Authentication Helper
===========================================
Helper script to generate and validate Angel One SmartAPI authentication tokens.
"""

import os
import json
import requests
import pyotp
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

load_dotenv()


def generate_totp() -> str:
    """Generate TOTP token from secret."""
    totp_secret = os.getenv('ANGEL_ONE_TOTP_SECRET')
    if not totp_secret:
        log.error("TOTP_SECRET not found in .env")
        return None
    
    try:
        totp = pyotp.TOTP(totp_secret)
        token = totp.now()
        log.info(f"✅ TOTP generated: {token}")
        return token
    except Exception as e:
        log.error(f"Error generating TOTP: {e}")
        return None


def authenticate_smartapi() -> bool:
    """Authenticate with Angel One SmartAPI and save tokens."""
    
    # Load credentials
    client_id = os.getenv('ANGEL_ONE_CLIENT_ID')
    client_secret = os.getenv('ANGEL_ONE_CLIENT_SECRET')
    api_key = os.getenv('ANGEL_ONE_API_KEY')
    password = os.getenv('ANGEL_ONE_PASSWORD')
    
    if not all([client_id, client_secret, api_key, password]):
        log.error("❌ Missing required credentials in .env")
        return False
    
    # Generate TOTP
    totp = generate_totp()
    if not totp:
        return False
    
    # Prepare payload
    payload = {
        'clientcode': client_id,
        'password': password,
        'totp': totp
    }
    
    # Try authentication endpoints
    endpoints = [
        "https://smartapi.angelbroking.com/rest/secure/login",
        "https://smartapi.angelbroking.com/rest/secure/Login",
        "https://api.angelbroking.com/rest/secure/login",
    ]
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
        'X-UserType': 'USER',
        'X-SourceID': 'WEB'
    }
    
    for endpoint in endpoints:
        try:
            log.info(f"\n🔐 Attempting authentication at: {endpoint}")
            
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            log.info(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                log.info(f"Response: {json.dumps(data, indent=2)}")
                
                if data.get('status') and data.get('data'):
                    auth_token = data['data'].get('jwtToken')
                    feed_token = data['data'].get('feedToken')
                    
                    log.info("\n✅ AUTHENTICATION SUCCESSFUL!")
                    log.info(f"\nSave these tokens to your .env file:")
                    log.info(f"ANGEL_ONE_AUTH_TOKEN={auth_token}")
                    log.info(f"ANGEL_ONE_FEED_TOKEN={feed_token}")
                    
                    # Optionally save to .env
                    save_response = input("\nSave tokens to .env? (y/n): ").lower()
                    if save_response == 'y':
                        with open('.env', 'a') as f:
                            f.write(f"\nANGEL_ONE_AUTH_TOKEN={auth_token}\n")
                            f.write(f"ANGEL_ONE_FEED_TOKEN={feed_token}\n")
                        log.info("✅ Tokens saved to .env")
                    
                    return True
                else:
                    log.warning(f"Status False in response: {data.get('message')}")
            else:
                log.warning(f"Status {response.status_code}: {response.text[:200]}")
        
        except Exception as e:
            log.warning(f"Error with {endpoint}: {e}")
            continue
    
    log.error("\n❌ All authentication attempts failed")
    log.error("\nTroubleshooting:")
    log.error("1. Verify credentials are correct in .env")
    log.error("2. Ensure TOTP secret is valid")
    log.error("3. Check Angel One account status")
    log.error("4. Verify API key is enabled")
    return False


def test_quote_fetch(auth_token: str) -> bool:
    """Test fetching a quote with the auth token."""
    try:
        log.info("\n📊 Testing quote fetch...")
        
        headers = {
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json',
            'X-UserType': 'USER',
            'X-SourceID': 'WEB'
        }
        
        payload = {
            'mode': 'LTP',
            'exchangeTokens': {
                'MCX': {
                    'SILVER': ['all']
                }
            }
        }
        
        response = requests.post(
            "https://smartapi.angelbroking.com/rest/secure/quote",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            log.info(f"✅ Quote fetch successful!")
            log.info(f"Response: {json.dumps(data, indent=2)[:500]}...")
            return True
        else:
            log.warning(f"Quote fetch failed: {response.status_code}")
            log.warning(f"Response: {response.text[:200]}")
            return False
        
    except Exception as e:
        log.error(f"Error fetching quote: {e}")
        return False


def main():
    """Run authentication helper."""
    log.info("="*70)
    log.info("🔐 ANGEL ONE SmartAPI - AUTHENTICATION HELPER")
    log.info("="*70)
    
    # Step 1: Generate TOTP
    log.info("\n📱 Step 1: Generating TOTP...")
    totp = generate_totp()
    if not totp:
        return
    
    # Step 2: Authenticate
    log.info("\n🔐 Step 2: Authenticating with SmartAPI...")
    if not authenticate_smartapi():
        return
    
    # Step 3: Test quote fetch (if tokens were saved)
    auth_token = os.getenv('ANGEL_ONE_AUTH_TOKEN')
    if auth_token:
        log.info("\n✅ Step 3: Testing quote fetch...")
        test_quote_fetch(auth_token)
    
    log.info("\n" + "="*70)
    log.info("✅ AUTHENTICATION SETUP COMPLETE")
    log.info("="*70)
    log.info("\nYou can now run the trading bot:")
    log.info("  python3 trading_bot.py")


if __name__ == "__main__":
    main()
