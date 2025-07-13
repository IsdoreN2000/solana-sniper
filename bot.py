from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env at the very start

import os
import json
import time
import asyncio
import threading
from datetime import datetime, timezone

from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient

from utils import (
    jupiter_swap_sol_to_token,
    sell_token,
    send_alert,
    get_sol_usd_price,
    get_pump_fun_tokens,
    get_moonshot_tokens
)

import websocket

# === Load Wallet from .env ===
phantom_key_raw = os.getenv("PHANTOM_PRIVATE_KEY")
if not phantom_key_raw:
    raise ValueError(
        "❌ PHANTOM_PRIVATE_KEY is missing! Please add it to your .env file as a JSON array, e.g. PHANTOM_PRIVATE_KEY=[12,34,...]"
    )

try:
    private_key_array = json.loads(phantom_key_raw)
    if not isinstance(private_key_array, list):
        raise ValueError("PHANTOM_PRIVATE_KEY must be a JSON array, e.g. [12,34,...]")
except Exception as e:
    raise Exception(
        f"PHANTOM_PRIVATE_KEY is not valid JSON array: {e}\n"
        "Example .env line:\nPHANTOM_PRIVATE_KEY=[12,34,56,...]"
    )

keypair = Keypair.from_bytes(bytes(private_key_array))

# === Global Config ===
seen_tokens = {}
SCAN_INTERVAL = 20  # seconds
TOKEN_HOLD_SECONDS = 420  # 7 minutes

# === Token Safety Filter ===
def token_is_safe(mint_address):
    return True  # Placeholder for your safety logic

# === Auto Buy Logic ===
async def buy_token_async(client, token_address, amount_sol):
    try:
        resp = await jupiter_swap_sol_to_token(client, keypair, token_address, amount_sol)
        seen_tokens[token_address] = {
            "buy_time": time.time(),
            "buy_price_sol": amount_sol,
            "bought": True,
            "sold": False
        }
        send_alert(f"✅ Bought {amount_sol:.4f} SOL of {token_address}\nTx: {resp}")
    except Exception as e:
        send_alert(f"❌ Buy failed for {token_address}: {e}")

# === Auto Sell Logic ===
async def auto_sell_tokens(client):
    current_time = time.time()
    sol_usd = await get_sol_usd_price()
    if not sol_usd:
        return
    for mint, info in list(seen_tokens.items()):
        if info["sold"]:
            continue
        held_seconds = current_time - info["buy_time"]
        # Trigger sell at 2x or after 7 minutes
        should_sell = False
        if held_seconds > TOKEN_HOLD_SECONDS:
            should_sell = True
            reason = "⏱️ Time-based sell"
        else:
            # Here you can add price-check logic to determine 2x
            # But for simplicity we'll only use the timer here
            continue
        if should_sell:
            try:
                resp = await sell_token(client, keypair, mint)
                seen_tokens[mint]["sold"] = True
                send_alert(f"💰 Sold {mint} - {reason}\nTx: {resp}")
            except Exception as e:
                send_alert(f"❌ Sell failed for {mint}: {e}")

# === New Token Scanner ===
async def process_new_tokens_async(client):
    now = int(time.time())
    all_tokens = []
    # Await async token fetchers
    pump_tokens = await get_pump_fun_tokens()
    moonshot_tokens = await get_moonshot_tokens()
    all_tokens.extend(pump_tokens)
    all_tokens.extend(moonshot_tokens)
    eligible = [
        t for t in all_tokens
        if t.get("mint") not in seen_tokens
        and 1 <= (now - int(t.get("created_at", now))) <= 60
        and token_is_safe(t.get("mint"))
    ]
    eligible.sort(key=lambda t: t.get("created_at", 0), reverse=True)
    tokens_to_buy = eligible[:3]

    if not tokens_to_buy:
        print("⚠️ No eligible tokens found in the 1–60s window.")
        return

    sol_usd = await get_sol_usd_price()
    if not sol_usd:
        send_alert("⚠️ Could not fetch SOL/USD price. Skipping buys.")
        return

    amount_sol = 5 / sol_usd  # $5 in SOL
    await asyncio.gather(*(buy_token_async(client, t["mint"], amount_sol) for t in tokens_to_buy))

# === WebSocket for Live New Tokens ===
def on_message(ws, message):
    try:
        data = json.loads(message)
        if data.get("event") == "newToken":
            print("🚀 New token via WebSocket:")
            print(json.dumps(data["data"], indent=2))
    except Exception as e:
        print("WS error:", e)

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

def start_websocket():
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

# === Main ===
async def main_loop():
    print("✅ Sniper Bot Started.")
    send_alert("Sniper Bot Started: Scanning for best tokens in 1–60s window, $5 per buy.")
    start_websocket()
    rpc_url = os.getenv("RPC_URL")
    if not rpc_url:
        raise ValueError("❌ RPC_URL is missing! Please add it to your .env file.")
    async with AsyncClient(rpc_url) as client:
        while True:
            print("🔁 Bot main loop running...")
            try:
                await process_new_tokens_async(client)
                await auto_sell_tokens(client)
                await asyncio.sleep(SCAN_INTERVAL)
            except Exception as e:
                print(f"❌ Exception in loop: {e}")
                send_alert(f"Bot Error: {e}")
                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main_loop())
