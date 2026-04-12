
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

AUTH_TOKEN = "Bearer eyJhbGciOiJIUzUxMiJ9.eyJ1c2VybmFtZSI6IkFBQ0U2NDgzNzkiLCJyb2xlcyI6MCwidXNlcnR5cGUiOiJVU0VSIiwidG9rZW4iOiJleUpoYkdjaU9pSlNVekkxTmlJc0luUjVjQ0k2SWtwWFZDSjkuZXlKMWMyVnlYM1I1Y0dVaU9pSmpiR2xsYm5RaUxDSjBiMnRsYmw5MGVYQmxJam9pZEhKaFpHVmZZV05qWlhOelgzUnZhMlZ1SWl3aVoyMWZhV1FpT2pNc0luTnZkWEpqWlNJNklqTWlMQ0prWlhacFkyVmZhV1FpT2lJek5EVmxOak5tTmkxaU1ESTBMVE5pWmpBdFlUZGpPQzFrTXpGbFpUVmlNamRoWTJZaUxDSnJhV1FpT2lKMGNtRmtaVjlyWlhsZmRqSWlMQ0p2Ylc1bGJXRnVZV2RsY21sa0lqb3pMQ0p3Y205a2RXTjBjeUk2ZXlKa1pXMWhkQ0k2ZXlKemRHRjBkWE1pT2lKaFkzUnBkbVVpZlN3aWJXWWlPbnNpYzNSaGRIVnpJam9pWVdOMGFYWmxJbjE5TENKcGMzTWlPaUowY21Ga1pWOXNiMmRwYmw5elpYSjJhV05sSWl3aWMzVmlJam9pUVVGRFJUWTBPRE0zT1NJc0ltVjRjQ0k2TVRjM01qYzJNRFUxTlN3aWJtSm1Jam94TnpjeU5qY3pPVGMxTENKcFlYUWlPakUzTnpJMk56TTVOelVzSW1wMGFTSTZJbVU1WVRGaVpHUmlMVEJpTmpNdE5ETmtNUzA1WmpVMkxUTm1OREU0Wm1JelltTmpZU0lzSWxSdmEyVnVJam9pSW4wLkxRa2YxMUlLNnY4MkFmODlzV0t5TmdfdEEzWjFRRGdmUGZKLW9fR05taVZsdlZ6UjJRQk55WkhEbWFLT08zVExWaWViWWU3WUgwYmFnYW9HZjJMRURYcEFLSjdFOFdzcVRnR0lDSlZ1MjNaMWxwSDE1ekdiUHNtaXJDR1RCRm5rT2ZWX3hDRWV0M05wTk9yRWp0akRzNlc0VVhXZkJWSzZGWGtqSWtfa0RlSSIsIkFQSS1LRVkiOiJaenRiWVdRciIsIlgtT0xELUFQSS1LRVkiOmZhbHNlLCJpYXQiOjE3NzI2NzQxNTUsImV4cCI6MTc3MjczNTQwMH0.B2KrGW3la7Yzk_DA5x_LifQJKx4F5fggEIbp0GOelfJrquKg2X53oTjhHPHVZMqb9BU0fwm2X16wOl4YTkaPqw"
API_KEY = "ZztbYWQr"
CLIENT_CODE = "AACE648379"
FEED_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJ1c2VybmFtZSI6IkFBQ0U2NDgzNzkiLCJpYXQiOjE3NzI2NzQxNTUsImV4cCI6MTc3Mjc2MDU1NX0.1b5rq5_U4afBucBCxhGHY2e1IkJv5CrwTMo9gXwrrx4ju7HmdMfkQnuFXN3YF4mGSbWBrkrvrnyk0o9MbOBYVw"

sws = SmartWebSocketV2(AUTH_TOKEN, API_KEY, CLIENT_CODE, FEED_TOKEN)

# runs when websocket opens
def on_open(ws):
    print("Connected")

    token_list = [
        {
            "exchangeType": 5,   # 5 = MCX
            "tokens": ["25163"]  # example instrument token
        }
    ]

    sws.subscribe("mw", token_list)

# receives market data
def on_data(ws, message):
    print("Tick:", message)

def on_error(ws, error):
    print("Error:", error)

def on_close(ws):
    print("Closed")

sws.on_open = on_open
sws.on_data = on_data
sws.on_error = on_error
sws.on_close = on_close

sws.connect()