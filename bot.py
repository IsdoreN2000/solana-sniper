import os
import time
import json
import requests
import asyncio
import base64
import threading
from dotenv import load_dotenv
from solders.keypair import Keypair
from telegram import Bot
from solana.rpc.async_api import AsyncClient
from solders.transaction import Transaction
import websocket

# === Load Environment Variables ===
def get_env_var(name, required=True):
    value = os.getenv(name)
    if required and (value is None or value.strip() == ""):
        raise Exception(f"Missing required environment variable: {name}")
    return value

load_dotenv()

raw_key = get_env_var("PHANTOM_PRIVATE_KEY")
try:
    PRIVATE_KEY = json.loads(raw_key)
except Exception as e:
    raise Exception(f"PHANTOM_PRIVATE_KEY is not valid JSON: {e}")

TELEGRAM_TOKEN = get_env_var("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = get_env_var("TELEGRAM_CHAT_ID")

keypair = Keypair.from_bytes(bytes(PRIVATE_KEY))
wallet = keypair.pubkey()
tg_bot = Bot(token=TELEGRAM_TOKEN)

SCAN_INTERVAL = 120  # seconds
seen_tokens = set()

JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"
SOL_MINT = "So11111111111111111111111111111111111111112"

def send_alert(message):
    try:
        asyncio.run(tg_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message))
    except Exception as e:
        print(f"Telegram Error: {e}")

def fetch_platform_data(url, platform_name, params=None, method="GET", json_data=None, retries=3, delay=2):
    for attempt in range(1, retries + 1):
        try:
            if method == "GET":
                response = requests.get(url, params=params, timeout=10)
            elif method == "POST":
                response = requests.post(url, json=json_data, timeout=10)
            else:
                raise ValueError("Unsupported HTTP method")
            response.raise_for_status()
            if response.text.strip():
                try:
                    return response.json()
                except ValueError as json_err:
                    print(f"{platform_name} JSON decode error: {json_err}")
                    print("Response text:", response.text)
                    return {}
            else:
                print(f"{platform_name} error: Empty response body")
                return {}
        except requests.exceptions.HTTPError as http_err:
            print(f"{platform_name} HTTP error: {http_err}")
            print("Response text:", response.text)
        except requests.exceptions.RequestException as req_err:
            print(f"{platform_name} request error: {req_err}")
        except Exception as e:
            print(f"{platform_name} unexpected error: {e}")

        if attempt < retries:
            print(f"Retrying {platform_name} in {delay} seconds... (Attempt {attempt + 1}/{retries})")
            time.sleep(delay)
    return {}

def get_sol_usd_price():
    data = fetch_platform_data(
        "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
        "CoinGecko"
    )
    try:
        return data["solana"]["usd"]
    except Exception as e:
        print(f"Error fetching SOL price: {e}")
        return None

def get_pumpfun_tokens():
    data = fetch_platform_data(
        "https://pump.fun/api/projects?sort=recent",
        "Pump.fun"
    )
    try:
        return [
            {
                "mint": p.get("mint"),
                "created_at": p.get("created_at")
            }
            for p in data.get("projects", [])
            if p.get("mint") and p.get("created_at")
        ]
    except Exception as e:
        print(f"Pump.fun error: {e}")
        return []

def get_moonshot_tokens():
    data = fetch_platform_data(
        "https://api.moonshot.so/v1/tokens/recent",
        "Moonshot"
    )
    try:
        return [
            {
                "mint": t.get("mint"),
                "created_at": int(t.get("launchDate", 0)) // 1000
            }
            for t in data.get("tokens", [])
            if t.get("mint") and t.get("launchDate")
        ]
    except Exception as e:
        print(f"Moonshot error: {e}")
        return []

def token_is_safe(token_address):
    # TODO: Integrate honeypot or blacklist checker here
    return True

async def jupiter_swap_sol_to_token(
    keypair: Keypair,
    destination_token_mint: str,
    amount_sol: float,
    slippage_bps: int = 100
):
    async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
        amount_lamports = int(amount_sol * 1_000_000_000)
        params = {
            "inputMint": SOL_MINT,
            "outputMint": destination_token_mint,
            "amount": str(amount_lamports),
            "slippageBps": str(slippage_bps),
            "swapMode": "ExactIn"
        }
        quote = fetch_platform_data(JUPITER_QUOTE_URL, "Jupiter Quote", params=params)
        if not quote.get("outAmount") or not quote.get("routes"):
            raise Exception(f"Jupiter quote failed: {quote}")

        swap_req = {
            "userPublicKey": str(keypair.pubkey()),
            "route": quote["routes"][0],
            "wrapUnwrapSOL": True,
            "asLegacyTransaction": True
        }
        swap_data = fetch_platform_data(JUPITER_SWAP_URL, "Jupiter Swap", method="POST", json_data=swap_req)
        if "swapTransaction" not in swap_data:
            raise Exception(f"Jupiter swap failed: {swap_data}")

        txn_bytes = base64.b64decode(swap_data["swapTransaction"])
        txn = Transaction.deserialize(txn_bytes)
        txn.sign(keypair)
        send_resp = await client.send_transaction(txn, keypair)
        return send_resp

async def buy_token_async(token_address, amount_sol):
    try:
        resp = await jupiter_swap_sol_to_token(keypair, token_address, amount_sol)
        send_alert(f"Bought {amount_sol:.6f} SOL of {token_address}\nTx: {resp['result']}")
    except Exception as e:
        send_alert(f"Buy failed for {token_address}: {e}")

async def process_new_tokens_async():
    now = int(time.time())
    sources = [get_pumpfun_tokens, get_moonshot_tokens]
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
        print("No eligible tokens found in the 1-40s window.")
        return

    sol_usd = get_sol_usd_price()
    if not sol_usd:
        send_alert("Could not fetch SOL/USD price. Skipping buys.")
        return

    amount_sol = 5 / sol_usd  # $5 in SOL

    await asyncio.gather(*(buy_token_async(t["mint"], amount_sol) for t in tokens_to_buy))

    for t in tokens_to_buy:
        seen_tokens.add(t["mint"])

# === WebSocket Integration for PumpPortal ===
def on_message(ws, message):
    try:
        data = json.loads(message)
        if data.get("event") == "newToken":
            print("🚀 New token detected!")
            print(json.dumps(data["data"], indent=2))
            # 👇 Optionally, trigger your buy logic here
            # Example:
            # token_address = data["data"].get("mint")
            # if token_address:
            #     asyncio.run(buy_token_async(token_address, amount_sol))
    except Exception as e:
        print("Error parsing WebSocket message:", e)

def on_error(ws, error):
    print("WebSocket error:", error)

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed:", close_msg)

def on_open(ws):
    print("✅ WebSocket connection opened")
    ws.send(json.dumps({
        "event": "subscribeNewToken",
        "filters": {}  # You can filter by creator, market cap, etc.
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
    # Run it in a thread so your bot can do other things too
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()

if __name__ == "__main__":
    print("✅ Bot is starting...")  # Log when the bot starts
    send_alert("Sniper Bot Started: scanning for 4 best tokens in 1-40s window, $5 each.")

    # Start the PumpPortal WebSocket listener in a background thread
    start_pumpportal_ws()

    while True:
        print("✅ Bot main loop entered.")  # Log each time the main loop starts
        try:
            asyncio.run(process_new_tokens_async())
            time.sleep(SCAN_INTERVAL)
        except Exception as e:
            print(f"❌ Exception in main loop: {e}")
            send_alert(f"Bot Error: {e}")
            time.sleep(60)
