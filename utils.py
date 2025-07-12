# === utils.py ===
import json
import base64
import aiohttp
import asyncio
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from datetime import datetime, timezone

# Send alert (placeholder: replace with actual Telegram alert logic)
def send_alert(message):
    print("🔔", message)

# Get SOL price in USD
async def get_sol_usd_price():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd") as resp:
            data = await resp.json()
            return data['solana']['usd']

# Get pump.fun tokens (mocked or real endpoint depending on backend update)
async def get_pump_fun_tokens():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://pump.fun/api/latest-tokens") as response:
                return await response.json()
    except Exception as e:
        print("Pump.fun error:", e)
        return []

# Get moonshot tokens (stub logic for other platforms like Raydium)
async def get_moonshot_tokens():
    return []  # Replace with real moonshot logic if available

# Dummy Jupiter swap function (placeholder)
async def jupiter_swap_sol_to_token(client: AsyncClient, keypair: Keypair, token_mint: str, sol_amount: float):
    print(f"[SWAP] Buying {token_mint} with {sol_amount} SOL...")
    return "DummyTxSignature"

# Dummy sell logic with 2x or timeout sell conditions
async def sell_token(client: AsyncClient, keypair: Keypair, token_mint: str):
    print(f"[SELL] Selling token {token_mint}...")
    return "DummySellSignature"

# Decode wallet private key from string
def load_keypair_from_env():
    import os
    private_key_array = json.loads(os.getenv("PHANTOM_PRIVATE_KEY"))
    return Keypair.from_bytes(bytes(private_key_array))
