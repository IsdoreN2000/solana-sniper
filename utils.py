# === utils.py ===
import json
import os
import aiohttp
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts

# Send alert (placeholder: replace with Telegram if needed)
def send_alert(message):
    print("\ud83d\udd14", message)

# Get SOL/USD price
def load_keypair_from_env():
    private_key_array = json.loads(os.getenv("PHANTOM_PRIVATE_KEY"))
    return Keypair.from_bytes(bytes(private_key_array))

async def get_sol_usd_price():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd") as resp:
            data = await resp.json()
            return data['solana']['usd']

# Dummy buy (replace with real Jupiter buy logic)
async def jupiter_swap_sol_to_token(client: AsyncClient, keypair: Keypair, token_mint: str, sol_amount: float):
    print(f"[BUY] Buying {token_mint} with {sol_amount} SOL...")
    return "DummyBuySignature"

# Dummy sell (replace with real Jupiter sell logic)
async def sell_token(client: AsyncClient, keypair: Keypair, token_mint: str):
    print(f"[SELL] Selling token {token_mint}...")
    return "DummySellSignature"

# Get pump.fun tokens
def format_token_data(data):
    formatted = []
    for token in data:
        formatted.append({
            "mint": token.get("mint"),
            "name": token.get("name"),
            "created_at": token.get("created_at", "")
        })
    return formatted

async def get_pump_fun_tokens():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://pump.fun/api/latest-tokens") as response:
                data = await response.json()
                return format_token_data(data)
    except Exception as e:
        print("Pump.fun error:", e)
        return []

async def get_moonshot_tokens():
    return []  # Placeholder for Raydium, Jupiter trending, etc.
