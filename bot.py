import os
import json
import time
import asyncio
import threading
import requests
import websocket
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient

# === Load Wallet from .env ===
load_dotenv()
phantom_key_raw = os.getenv("PHANTOM_PRIVATE_KEY")
if not phantom_key_raw:
    raise ValueError("❌ PHANTOM_PRIVATE_KEY environment variable is missing!")

private_key_array = json.loads(phantom_key_raw)
keypair = Keypair.from_bytes(bytes(private_key_array))

# === Global Config ===
seen_tokens = {}
SCAN_INTERVAL = 20  # seconds
BUY_AMOUNT_USD = 5
SELL_MULTIPLIER = 2  # Sell at 2x
SELL_TIMEOUT = 420  # Sell after 7 minutes (420 seconds)

# === Alerts ===
def send_alert(msg):
    print("\n🔔", msg)

# === Get current SOL/USD price ===
def get_sol_usd_price():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
        return r.json()["solana"]["usd"]
    except Exception as e:
        print("Error fetching SOL price:", e)
        return None

# === Dummy token safety filter ===
def token_is_safe(mint_address):
    return True

# === Jupiter Swap Logic Placeholder ===
class JupiterClient:
    def __init__(self, client):
        self.client = client

    async def quote(self, input_mint, output_mint, amount, slippage_bps):
        return [{}]  # Dummy route

    async def swap(self, keypair, route):
        class DummyTx:
            def serialize(self):
                return b"fake_tx"
        return DummyTx()

async def jupiter_swap_sol_to_token(keypair, token_address, amount_sol):
    async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
        jupiter = JupiterClient(client)
        routes = await jupiter.quote(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint=token_address,
            amount=int(amount_sol * 1e9),
            slippage_bps=100
        )
        if not routes:
            raise Exception("No route found")
        tx = await jupiter.swap(keypair=keypair, route=routes[0])
        sig = await client.send_raw_transaction(tx.serialize(), opts={"skip_preflight": True})
        return {"result": str(sig.value)}

# === Buy Token ===
async def buy_token_async(token_address, amount_sol):
    try:
        resp = await jupiter_swap_sol_to_token(keypair, token_address, amount_sol)
        send_alert(f"✅ Bought {amount_sol:.6f} SOL of {token_address}\nTx: {resp['result']}")
        seen_tokens[token_address] = {
            "buy_time": time.time(),
            "buy_price": amount_sol
        }
    except Exception as e:
        send_alert(f"Buy failed for {token_address}: {e}")

# === Auto-sell Logic ===
async def auto_sell_tokens():
    now = time.time()
    tokens_to_sell = []
    for token, info in seen_tokens.items():
        held_time = now - info["buy_time"]
        if held_time >= SELL_TIMEOUT:
            tokens_to_sell.append(token)
            continue
        if token_is_safe(token) and held_time >= 60:
            tokens_to_sell.append(token)
    for token in tokens_to_sell:
        try:
            # Dummy sell logic
            send_alert(f"💰 Selling token {token} after holding {int(now - seen_tokens[token]['buy_time'])}s")
            seen_tokens.pop(token)
        except Exception as e:
            send_alert(f"❌ Sell failed for {token}: {e}")

# === Pump.fun API ===
def get_pump_fun_tokens(limit=10, sort="recent", max_age_minutes=5):
    url = "https://pump.fun/api/graphql"
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://pump.fun",
        "Referer": "https://pump.fun/"
    }
    payload = {
        "operationName": "ExploreProjects",
        "variables": {"sort": sort, "limit": limit},
        "query": """
            query ExploreProjects($sort: ExploreSortOption!, $limit: Int!) {
              exploreProjects(sort: $sort, limit: $limit) {
                id
                name
                marketCap
                createdAt
              }
            }
        """
    }
    try:
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        tokens = res.json()["data"]["exploreProjects"]
        fresh = []
        for t in tokens:
            created_at = datetime.fromisoformat(t["createdAt"].replace("Z", "+00:00"))
            age_minutes = (datetime.now(timezone.utc) - created_at).total_seconds() / 60
            if age_minutes <= max_age_minutes:
                fresh.append({
                    "mint": t["id"],
                    "name": t["name"],
                    "marketCap": t["marketCap"],
                    "created_at": int(created_at.timestamp())
                })
        return fresh
    except Exception as e:
        print("Pump.fun error:", e)
        return []

# === Token Sources ===
def get_all_sources():
    return get_pump_fun_tokens(limit=10, max_age_minutes=5)

# === Main Token Processing ===
async def process_new_tokens_async():
    now = int(time.time())
    all_tokens = get_all_sources()
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
        send_alert("Could not fetch SOL/USD price. Skipping buys.")
        return
    amount_sol = BUY_AMOUNT_USD / sol_usd
    await asyncio.gather(*(buy_token_async(t["mint"], amount_sol) for t in tokens_to_buy))

# === Main Loop ===
if __name__ == "__main__":
    print("✅ Sniper Bot Started.")
    send_alert("Sniper Bot Started: Scanning for best tokens in 1–40s window, $5 per buy.")
    while True:
        print("🔁 Bot main loop running...")
        try:
            asyncio.run(process_new_tokens_async())
            asyncio.run(auto_sell_tokens())
        except Exception as e:
            print(f"❌ Exception in main loop: {e}")
            send_alert(f"Bot Error: {e}")
        time.sleep(SCAN_INTERVAL)
