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
import os

# === Load from .env ===
RPC_URL = os.getenv("RPC_URL")

# === Load keypair ===
def load_keypair_from_env():
    private_key_array = json.loads(os.getenv("PHANTOM_PRIVATE_KEY"))
    return Keypair.from_bytes(bytes(private_key_array))

# === Alerts ===
def send_alert(message):
    try:
        print("🔔 " + message.encode('ascii', 'ignore').decode('ascii'))
    except Exception:
        print("[Alert]", message)

# === SOL price ===
async def get_sol_usd_price():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd") as resp:
            data = await resp.json()
            return data['solana']['usd']

# === Pump.fun token list ===
async def get_pump_fun_tokens():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://pump.fun/api/latest-tokens") as response:
                return await response.json()
    except Exception as e:
        print("Pump.fun error:", e)
        return []

# === Moonshot logic placeholder ===
async def get_moonshot_tokens():
    return []  # Replace with real logic

# === Dummy Buy ===
async def jupiter_swap_sol_to_token(client: AsyncClient, keypair: Keypair, token_mint: str, sol_amount: float):
    print(f"[SWAP] Buying {token_mint} with {sol_amount} SOL...")
    return "DummyTxSignature"

# === Dummy Sell ===
async def sell_token(client: AsyncClient, keypair: Keypair, token_mint: str):
    print(f"[SELL] Selling token {token_mint}...")
    return "DummySellSignature"
