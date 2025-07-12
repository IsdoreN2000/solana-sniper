import aiohttp
import requests
import time
import json
from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from solana.rpc.types import TxOpts
from solana.keypair import Keypair
from solders.pubkey import Pubkey
from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def jupiter_swap_sol_to_token(keypair, mint_address, amount_sol):
    async with aiohttp.ClientSession() as session:
        # Jupiter Quote API
        quote_url = f"https://quote-api.jup.ag/v6/quote?inputMint=So11111111111111111111111111111111111111112&outputMint={mint_address}&amount={int(amount_sol * 1e9)}&slippageBps=500"
        async with session.get(quote_url) as response:
            quote = await response.json()
            if not quote.get("data"):
                raise Exception("No quote found")
            route = quote["data"][0]

        # Jupiter Swap API
        swap_url = "https://quote-api.jup.ag/v6/swap"
        payload = {
            "userPublicKey": str(keypair.pubkey()),
            "wrapUnwrapSOL": True,
            "feeAccount": None,
            "computeUnitPriceMicroLamports": 0,
            "asLegacyTransaction": True,
            **route
        }
        async with session.post(swap_url, json=payload) as response:
            swap = await response.json()

        tx_raw = swap["swapTransaction"]
        tx_bytes = bytes.fromhex(tx_raw)
        tx = Transaction.deserialize(tx_bytes)
        tx.sign([keypair])

        client = AsyncClient("https://api.mainnet-beta.solana.com")
        txid = await client.send_transaction(tx, keypair, opts=TxOpts(skip_confirmation=False))
        await client.close()

        return {"result": f"https://solscan.io/tx/{txid.value}"}


async def sell_token(keypair, mint_address):
    # This is a placeholder. You need to reverse the input/outputMint in Jupiter swap for actual sell.
    return await jupiter_swap_sol_to_token(keypair, "So11111111111111111111111111111111111111112", 0.01)  # sells token for 0.01 SOL worth


def send_alert(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[ALERT] {message}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, json=data)
    except:
        pass


def get_sol_usd_price():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
        return response.json()["solana"]["usd"]
    except:
        return None


def get_pump_fun_tokens(limit=10, max_age_minutes=5):
    try:
        now = int(time.time())
        url = "https://client-api-2-eta.vercel.app/tokens"  # working proxy of pump.fun
        res = requests.get(url)
        tokens = res.json()
        filtered = []
        for t in tokens:
            age_minutes = (now - int(t["created_at"])) / 60
            if age_minutes <= max_age_minutes:
                filtered.append(t)
            if len(filtered) >= limit:
                break
        return filtered
    except:
        return []


def get_moonshot_tokens():
    try:
        res = requests.get("https://moonshot-api-v1.vercel.app/sol/tokens")
        return res.json()
    except:
        return []
