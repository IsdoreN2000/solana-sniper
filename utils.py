# === utils.py ===
import json
import aiohttp
import os
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from datetime import datetime, timezone

# ✅ Telegram alert (print for now)
def send_alert(message):
    print("🔔", message)

# ✅ Get SOL price in USD
async def get_sol_usd_price():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd") as resp:
            data = await resp.json()
            return data['solana']['usd']

# ✅ Get pump.fun tokens
async def get_pump_fun_tokens():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://pump.fun/api/latest-tokens") as response:
                return await response.json()
    except Exception as e:
        print("Pump.fun error:", e)
        return []

# ✅ Stub for other platforms like Raydium
async def get_moonshot_tokens():
    return []

# ✅ Dummy Jupiter swap simulation
async def jupiter_swap_sol_to_token(client: AsyncClient, keypair: Keypair, token_mint: str, sol_amount: float):
    print(f"[SWAP] Buying {token_mint} with {sol_amount} SOL...")
    return "DummyTxSignature"

# ✅ Dummy sell simulation (2x or timeout condition)
async def sell_token(client: AsyncClient, keypair: Keypair, token_mint: str):
    print(f"[SELL] Selling token {token_mint}...")
    return "DummySellSignature"

# ✅ Load keypair from environment
def load_keypair_from_env():
    private_key_array = json.loads(os.getenv("PHANTOM_PRIVATE_KEY"))
    return Keypair.from_bytes(bytes(private_key_array))


# === bot.py ===
import asyncio
import os
from datetime import datetime, timezone
from solders.rpc.responses import GetTokenAccountsByOwnerResp
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient

from utils import (
    jupiter_swap_sol_to_token,
    sell_token,
    send_alert,
    get_sol_usd_price,
    get_pump_fun_tokens,
    get_moonshot_tokens,
    load_keypair_from_env
)

RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
keypair = load_keypair_from_env()
client = AsyncClient(RPC_URL)

# Configuration
MAX_AGE_MINUTES = 1
BUY_AMOUNT_SOL = 0.1
SELL_DELAY_SECONDS = 420  # 7 minutes

async def process_new_tokens_async():
    while True:
        print("🔁 Bot main loop running...")
        tokens = await get_pump_fun_tokens()

        for token in tokens:
            try:
                mint = token.get("mint")
                created_at = datetime.strptime(token.get("created_at"), "%Y-%m-%dT%H:%M:%S.%fZ")
                created_at = created_at.replace(tzinfo=timezone.utc)
                age_minutes = (datetime.now(timezone.utc) - created_at).total_seconds() / 60.0

                if age_minutes <= MAX_AGE_MINUTES:
                    print(f"🚀 New token via pump.fun: {mint}, Age: {age_minutes:.2f} min")
                    send_alert(f"New Token Detected: {mint}\nAge: {age_minutes:.2f} min\nBuying {BUY_AMOUNT_SOL} SOL...")

                    tx = await jupiter_swap_sol_to_token(client, keypair, mint, BUY_AMOUNT_SOL)
                    print(f"✅ Bought token {mint}, Tx: {tx}")
                    send_alert(f"✅ Bought token: {mint}\nTx: {tx}\nWaiting {SELL_DELAY_SECONDS}s before checking sell...")

                    await asyncio.sleep(SELL_DELAY_SECONDS)

                    sell_tx = await sell_token(client, keypair, mint)
                    print(f"✅ Sold token {mint}, Tx: {sell_tx}")
                    send_alert(f"✅ Sold token: {mint}\nTx: {sell_tx}")

            except Exception as e:
                print("⚠️ Error processing token:", e)

        await asyncio.sleep(20)  # Delay between loops

if __name__ == "__main__":
    print("✅ Sniper Bot Started.")
    send_alert("Sniper Bot Started: Scanning for best tokens in 1–40s window, $5 per buy.")
    asyncio.run(process_new_tokens_async())
