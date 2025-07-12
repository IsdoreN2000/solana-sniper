import os
import json
import time
import asyncio
import threading
import requests
import websocket
from datetime import datetime, timezone
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
keypair = Keypair.from_secret_key(bytes(private_key_array))

# === Global Config ===
seen_tokens = set()
held_tokens = {}  # mint_address -> buy_timestamp
SCAN_INTERVAL = 20  # seconds

# === Alerts (you can replace with Telegram)
def send_alert(msg):
    print("🔔", msg)

# === Get current SOL/USD price ===
def get_sol_usd_price():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
        return r.json()["solana"]["usd"]
    except Exception as e:
        print("Error fetching SOL price:", e)
        return None

# === Validate Token ===
def token_is_safe(mint_address):
    return True  # Dummy filter

# === Dummy Jupiter Swap Logic (replace with real implementation)
async def jupiter_swap_sol_to_token(keypair, token_address, amount_sol):
    # Replace this stub with actual JupiterClient logic
    print(f"[MOCK] Buying {amount_sol:.4f} SOL of {token_address}")
    return {"result": "MOCK_TX_HASH_BUY"}

async def jupiter_swap_token_to_sol(keypair, token_address):
    # Replace this stub with actual JupiterClient logic
    print(f"[MOCK] Selling all of {token_address}")
    return {"result": "MOCK_TX_HASH_SELL"}

# === Buy Token ===
async def buy_token_async(token_address, amount_sol):
    try:
        resp = await jupiter_swap_sol_to_token(keypair, token_address, amount_sol)
        send_alert(f"✅ Bought {amount_sol:.6f} SOL of {token_address}\nTx: {resp['result']}")
        seen_tokens.add(token_address)
        held_tokens[token_address] = int(time.time())
    except Exception as e:
        send_alert(f"Buy failed for {token_address}: {e}")

# === Auto Sell Token ===
async def auto_sell_tokens():
    current_time = int(time.time())
    to_sell = []
    for token, buy_time in held_tokens.items():
        held_duration = current_time - buy_time
        if held_duration >= 420:  # 7 minutes
            to_sell.append(token)

    for token in to_sell:
        try:
            resp = await jupiter_swap_token_to_sol(keypair, token)
            send_alert(f"✅ Sold {token} after 7 mins.\nTx: {resp['result']}")
            del held_tokens[token]
        except Exception as e:
            send_alert(f"Sell failed for {token}: {e}")

# === Pump.fun GraphQL Integration ===
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

# === Optional: Add other sources
def get_moonshot_tokens():
    return []  # stub

# === Main Buying Logic ===
async def process_new_tokens_async():
    now = int(time.time())
    sources = [
        lambda: get_pump_fun_tokens(limit=10, max_age_minutes=5),
        get_moonshot_tokens
    ]
    all_tokens = []
    for source in sources:
        all_tokens.extend(source())
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
    amount_sol = 5 / sol_usd  # $5 in SOL
    await asyncio.gather(*(buy_token_async(t["mint"], amount_sol) for t in tokens_to_buy))

# === WebSocket Listener (optional)
def on_message(ws, message):
    try:
        data = json.loads(message)
        if data.get("event") == "newToken":
            print("🚀 New token via WebSocket:")
            print(json.dumps(data["data"], indent=2))
    except Exception as e:
        print("Error in WS message:", e)

def on_error(ws, error):
    print("WebSocket error:", error)

def on_close(ws, code, msg):
    print("WebSocket closed:", msg)

def on_open(ws):
    print("✅ WebSocket opened")
    ws.send(json.dumps({
        "event": "subscribeNewToken",
        "filters": {}
    }))

def start_pumpportal_ws():
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp(
        "wss://pumpportal.fun/api/data",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()

# === Main Loop ===
if __name__ == "__main__":
    print("✅ Sniper Bot Started.")
    send_alert("Sniper Bot Started: Scanning for best tokens in 1–40s window, $5 per buy.")
    start_pumpportal_ws()
    while True:
        print("🔁 Bot main loop running...")
        try:
            asyncio.run(process_new_tokens_async())
            asyncio.run(auto_sell_tokens())
        except Exception as e:
            print(f"Exception in main loop: {e}")
            send_alert(f"Bot Error: {e}")
        time.sleep(SCAN_INTERVAL)
