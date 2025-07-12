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
from utils import jupiter_swap_sol_to_token, sell_token, send_alert, get_sol_usd_price, get_pump_fun_tokens, get_moonshot_tokens

# === Load Wallet from .env ===
load_dotenv()
phantom_key_raw = os.getenv("PHANTOM_PRIVATE_KEY")
if not phantom_key_raw:
    raise ValueError("❌ PHANTOM_PRIVATE_KEY environment variable is missing!")

private_key_array = json.loads(phantom_key_raw)
keypair = Keypair.from_bytes(bytes(private_key_array))

# === Global Config ===
seen_tokens = set()
bought_tokens = {}
SCAN_INTERVAL = 20  # scan every 20s

# === Validate Token ===
def token_is_safe(mint_address):
    return True  # Replace with real safety check

# === Buy Token ===
async def buy_token_async(token_address, amount_sol):
    try:
        resp = await jupiter_swap_sol_to_token(keypair, token_address, amount_sol)
        send_alert(f"✅ Bought {amount_sol:.6f} SOL of {token_address}\nTx: {resp['result']}")
        bought_tokens[token_address] = {
            "timestamp": int(time.time()),
            "amount": amount_sol,
            "bought_for_usd": amount_sol * get_sol_usd_price()
        }
    except Exception as e:
        send_alert(f"Buy failed for {token_address}: {e}")

# === Auto Sell Token ===
async def check_and_sell_tokens():
    sol_usd = get_sol_usd_price()
    now = int(time.time())
    for mint, info in list(bought_tokens.items()):
        try:
            bought_for = info["bought_for_usd"]
            age = now - info["timestamp"]
            current_value = await sell_token(keypair, mint, dry_run=True)
            if current_value >= 2 * bought_for:
                result = await sell_token(keypair, mint)
                send_alert(f"🚀 Sold {mint} for 2× profit\nTx: {result}")
                del bought_tokens[mint]
            elif age >= 420:
                result = await sell_token(keypair, mint)
                send_alert(f"⏰ Sold {mint} after 7 min\nTx: {result}")
                del bought_tokens[mint]
        except Exception as e:
            send_alert(f"Sell check failed for {mint}: {e}")

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
    amount_sol = 5 / sol_usd
    await asyncio.gather(*(buy_token_async(t["mint"], amount_sol) for t in tokens_to_buy))
    for t in tokens_to_buy:
        seen_tokens.add(t["mint"])

# === WebSocket Listener ===
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
            asyncio.run(check_and_sell_tokens())
            time.sleep(SCAN_INTERVAL)
        except Exception as e:
            print(f"Exception in main loop: {e}")
            sen
