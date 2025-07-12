import os
import time
import json
import requests
import asyncio
import base64
from dotenv import load_dotenv
from solders.keypair import Keypair
from telegram import Bot
from solana.rpc.async_api import AsyncClient
from solders.transaction import Transaction

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

def get_sol_usd_price():
    try:
        res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
        return res.json()["solana"]["usd"]
    except Exception as e:
        print(f"Error fetching SOL price: {e}")
        return None

def get_pumpfun_tokens():
    try:
        res = requests.get("https://pump.fun/api/projects?sort=recent")
        return [
            {
                "mint": p.get("mint"),
                "created_at": p.get("created_at")  # seconds since epoch
            }
            for p in res.json().get("projects", [])
            if p.get("mint") and p.get("created_at")
        ]
    except Exception as e:
        print(f"Pump.fun error: {e}")
        return []

def get_moonshot_tokens():
    try:
        res = requests.get("https://api.moonshot.so/v1/tokens/recent")
        return [
            {
                "mint": t.get("mint"),
                "created_at": int(t.get("launchDate", 0)) // 1000  # convert ms to s
            }
            for t in res.json().get("tokens", [])
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
        quote_resp = requests.get(JUPITER_QUOTE_URL, params=params)
        quote = quote_resp.json()
        if not quote.get("outAmount") or not quote.get("routes"):
            raise Exception(f"Jupiter quote failed: {quote}")

        swap_req = {
            "userPublicKey": str(keypair.pubkey()),
            "route": quote["routes"][0],
            "wrapUnwrapSOL": True,
            "asLegacyTransaction": True
        }
        swap_resp = requests.post(JUPITER_SWAP_URL, json=swap_req)
        swap_data = swap_resp.json()
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

if __name__ == "__main__":
    print("✅ Bot is starting...")  # Log when the bot starts
    send_alert("Sniper Bot Started: scanning for 4 best tokens in 1-40s window, $5 each.")
    while True:
        print("✅ Bot main loop entered.")  # Log each time the main loop starts
        try:
            asyncio.run(process_new_tokens_async())
            time.sleep(SCAN_INTERVAL)
        except Exception as e:
            print(f"❌ Exception in main loop: {e}")
            send_alert(f"Bot Error: {e}")
            time.sleep(60)
