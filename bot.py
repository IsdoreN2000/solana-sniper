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

# === Custom utils ===
from utils import sell_token  # Uses JupiterClient passed in

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
SELL_AFTER_SECONDS = 420  # 7 minutes
TARGET_MULTIPLIER = 2.0

# === Alerts ===
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

# === Dummy Safety Check ===
def token_is_safe(mint_address):
    return True

# === Buy Token ===
async def buy_token_async(jupiter, token_address, amount_sol):
    try:
        async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
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
        seen_tokens[token_address] = {
            "buy_time": time.time(),
            "buy_amount": amount_sol,
            "buy_price": await get_token_price_usd(token_address),
            "tx": sig.value
        }
        send_alert(f"✅ Bought {amount_sol:.6f} SOL of {token_address}\nTx: {sig.value}")
    except Exception as e:
        send_alert(f"❌ Buy failed for {token_address}: {e}")

# === Track and Sell Logic ===
async def get_token_price_usd(mint):
    try:
        url = f"https://price.jup.ag/v4/price?ids={mint}"
        r = requests.get(url)
        return r.json()["data"][mint]["price"]
    except:
        return 0

async def check_sells(jupiter):
    current_time = time.time()
    for token, meta in list(seen_tokens.items()):
        if "sold" in meta:
            continue
        try:
            now_price = await get_token_price_usd(token)
            if now_price == 0:
                continue
            bought_at = meta["buy_price"]
            if now_price >= bought_at * TARGET_MULTIPLIER or current_time - meta["buy_time"] > SELL_AFTER_SECONDS:
                amount = meta["buy_amount"]
                lamports = int(amount * 1e9)
                sig = await sell_token(jupiter, keypair, token, lamports)
                meta["sold"] = True
                if sig:
                    send_alert(f"✅ Auto-sold {token} at {now_price:.4f} (bought {bought_at:.4f})\nTx: {sig}")
        except Exception as e:
            print(f"Sell error for {token}: {e}")

# === Pump.fun API ===
def get_pump_fun_tokens(limit=10, sort="recent", max_age_minutes=5):
    url = "https://pump.fun/api/projects?sort=recent"
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

# === Main Loop ===
async def main_loop(jupiter):
    while True:
        print("🔁 Bot main loop running...")
        try:
            all_tokens = get_pump_fun_tokens(limit=10, max_age_minutes=5)
            now = int(time.time())
            new_tokens = [t for t in all_tokens if t["mint"] not in seen_tokens and 1 <= (now - int(t["created_at"])) <= 40 and token_is_safe(t["mint"])]
            new_tokens.sort(key=lambda t: t["created_at"], reverse=True)
            tokens_to_buy = new_tokens[:4]

            sol_usd = get_sol_usd_price()
            if not sol_usd:
                send_alert("❌ Could not fetch SOL/USD price. Skipping buys.")
                continue
            amount_sol = 5 / sol_usd
            await asyncio.gather(*(buy_token_async(jupiter, t["mint"], amount_sol) for t in tokens_to_buy))
            await check_sells(jupiter)
        except Exception as e:
            send_alert(f"⚠️ Bot error: {e}")
        await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    print("✅ Sniper Bot Started.")
    send_alert("Sniper Bot Started: Scanning for best tokens in 1–40s window, $5 per buy.")

    try:
        from utils import JupiterClient
        async def run():
            async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
                jupiter = JupiterClient(client)
                await main_loop(jupiter)
        asyncio.run(run())
    except Exception as e:
        print("Startup error:", e)
