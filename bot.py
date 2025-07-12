import os
import json
import time
import asyncio
import threading
import requests
import websocket
from datetime import datetime
from dotenv import load_dotenv
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient

# === Load Wallet from .env ===
load_dotenv()
phantom_key_raw = os.getenv("PHANTOM_PRIVATE_KEY")
if not phantom_key_raw:
    raise ValueError("❌ PHANTOM_PRIVATE_KEY environment variable is missing!")

private_key_array = json.loads(phantom_key_raw)
keypair = Keypair.from_bytes(bytes(private_key_array))

# === Global Config ===
seen_tokens = set()
SCAN_INTERVAL = 30  # seconds

# === Alerts ===
def send_alert(msg):
    print("🔔", msg)

# === Get SOL/USD price ===
def get_sol_usd_price():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
        return r.json()["solana"]["usd"]
    except Exception as e:
        print("Error fetching SOL price:", e)
        return None

# === Dummy safety filter ===
def token_is_safe(mint_address):
    return True  # You can add real filters here

# === Placeholder for Jupiter swap ===
async def jupiter_swap_sol_to_token(keypair, token_address, amount_sol):
    raise NotImplementedError("🔧 Jupiter swap logic not yet implemented.")

# === Attempt to buy token ===
async def buy_token_async(token_address, amount_sol):
    try:
        resp = await jupiter_swap_sol_to_token(keypair, token_address, amount_sol)
        send_alert(f"✅ Bought {amount_sol:.6f} SOL of {token_address}\nTx: {resp['result']}")
    except Exception as e:
        send_alert(f"❌ Buy failed for {token_address}: {e}")

# === ✅ Pump.fun Token Fetcher ===
def get_pump_fun_tokens(limit=10, max_age_minutes=5):
    url = "https://pump.fun/token/ALL.json"
    try:
        res = requests.get(url)
        res.raise_for_status()
        all_tokens = res.json()
        now = int(time.time())
        fresh = []

        for token in all_tokens:
            created_at_ts = token.get("created_unix_time", 0)
            age_minutes = (now - created_at_ts) / 60
            if age_minutes <= max_age_minutes:
                fresh.append({
                    "mint": token.get("id"),
                    "name": token.get("name", "Unnamed"),
                    "marketCap": token.get("market_cap", 0),
                    "created_at": created_at_ts
                })

        return sorted(fresh, key=lambda x: x["created_at"], reverse=True)[:limit]
    except Exception as e:
        print("Pump.fun error:", e)
        return []

# === Optional: Moonshot tokens ===
def get_moonshot_tokens():
    return []

# === Main Buying Logic ===
async def process_new_tokens_async():
    now = int(time.time())
    all_tokens = get_pump_fun_tokens(limit=10, max_age_minutes=5)

    eligible_tokens = [
        t for t in all_tokens
        if t["mint"] not in seen_tokens
        and 1 <= (now - int(t["created_at"])) <= 40
        and token_is_safe(t["mint"])
    ]

    eligible_tokens.sort(key=lambda t: t["created_at"], reverse=True)
    tokens_to_buy = eligible_tokens[:4]

    if not tokens_to_buy:
        print("⚠️ No eligible tokens found in the 1–40s window.")
        return

    sol_usd = get_sol_usd_price()
    if not sol_usd:
        send_alert("❌ Could not fetch SOL/USD price. Skipping buys.")
        return

    amount_sol = 5 / sol_usd
    await asyncio.gather(*(buy_token_async(t["mint"], amount_sol) for t in tokens_to_buy))

    for t in tokens_to_buy:
        seen_tokens.add(t["mint"])

# === WebSocket Listener ===
def on_message(ws, message):
    try:
        data = json.loads(message)
        if data.get("event") == "newToken":
            print("🚀 New token vi
