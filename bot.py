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
from utils import JupiterClient, sell_token

# === Load Wallet from .env ===
load_dotenv()
phantom_key_raw = os.getenv("PHANTOM_PRIVATE_KEY")
if not phantom_key_raw:
    raise ValueError("❌ PHANTOM_PRIVATE_KEY environment variable is missing!")

private_key_array = json.loads(phantom_key_raw)
keypair = Keypair.from_bytes(bytes(private_key_array))

# === Global Config ===
seen_tokens = set()
pending_sells = []
SCAN_INTERVAL = 20  # seconds
SELL_DELAY = 7 * 60  # 7 minutes

# === Alerts (you can add Telegram later) ===
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
    return True

# === ✅ Jupiter Swap Logic ===
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
        buy_time = int(time.time())
        pending_sells.append({"mint": token_address, "time": buy_time, "buy_amount": amount_sol})
        send_alert(f"✅ Bought {amount_sol:.6f} SOL of {token_address}\nTx: {resp['result']}")
    except Exception as e:
        send_alert(f" Buy failed for {token_address}: {e}")

# === Pump.fun GraphQL Integration ===
def get_pump_fun_tokens(limit=10, sort="recent", max_age_minutes=5):
    url = "https://pump.fun/api/explore"
    try:
        res = requests.get(url)
        res.raise_for_status()
        tokens = res.json()
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

# === Optional: Moonshot tokens ===
def get_moonshot_tokens():
    return []

# === Check for tokens to sell ===
async def handle_sells():
    now = int(time.time())
    tokens_to_remove = []
    for token in pending_sells:
        token_age = now - token["time"]
        if token_age >= SELL_DELAY:
            try:
                await sell_token(keypair, token["mint"])
                send_alert(f"📤 Sold token after 7min: {token['mint']}")
            except Exception as e:
                send_alert(f"Sell failed for {token['mint']}: {e}")
            tokens_to_remove.append(token)
    for t in tokens_to_remove:
        pending_sells.remove(t)

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
        send_alert(" Could not fetch SOL/USD price. Skipping buys.")
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
            asyncio.run(handle_sells())
            time.sleep(SCAN_INTERVAL)
        except Exception as e:
            print(f" Exception in main loop: {e}")
            send_alert(f"Bot Error: {e}")
            time.sleep(60)
