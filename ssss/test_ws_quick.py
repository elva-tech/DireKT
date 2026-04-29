#!/usr/bin/env python3
"""Quick WebSocket test"""

import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
import os
load_dotenv()

from angel_one_websocket import AngelOneWebSocketClient
import time

api_key = os.getenv('ANGEL_ONE_API_KEY')
client_id = os.getenv('ANGEL_ONE_CLIENT_ID')
auth_token = os.getenv('ANGEL_ONE_AUTH_TOKEN')

print('Testing WebSocket...')
print(f'Auth token: {auth_token[:20]}...')

client = AngelOneWebSocketClient(auth_token, api_key, client_id)

calls = []
def on_q(q):
    calls.append(q)
    print(f'Quote: {q.symbol} = {q.ltp}')

client.set_quote_callback(on_q)
client.connect()

time.sleep(15)
client.disconnect()

if calls:
    print(f'✅ Got {len(calls)} quotes')
else:
    print('⏳ No quotes (may need plan upgrade)')
