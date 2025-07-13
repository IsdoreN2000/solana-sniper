# === utils.py (rewritten to use only solders, no solana-py) ===
import os
import json
import base64
import aiohttp
import asyncio
from datetime import datetime, timezone

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.rpc.requests import GetTokenAccountsByOwner
from solana.rpc.async_api import AsyncClient  # still needed for network communication
from solana.rpc.types import TxOpts

# === Constants ===
RPC_URL = os.getenv("RPC_URL")

# === Alert function ===
def send_alert(message: str):
    try:
        print("\U0001F514", message)  # Unicode for 🔔 bell emoji
    except UnicodeEncodeError:
        print("[ALERT]", message)

# === Load keypair from .env ===
def load_keypair_from_env():
    private_key_array = json.loads(os.getenv("PHANTOM_PRIVATE_KEY"))
    return Keypair.from_bytes(bytes(private_key_array))

# === Get current SOL/USD price ===
async def get_sol_usd_price():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd") as resp:
            data = await resp.json()
            return data['solana']['usd']

# === Fetch latest tokens from pump.fun ===
async def get_pump_fun_tokens():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://pump.fun/api/latest-tokens") as response:
                return await response.json()
    except Exception as e:
        print("Pump.fun error:", e)
        return []

# === Stub for other platforms ===
async def get_moonshot_tokens():
    return []  # Extend this later with actual logic

# === Dummy Jupiter Swap Logic (replace with real later) ===
async def jupiter_swap_sol_to_token(client: AsyncClient, keypair: Keypair, token_mint: str, sol_amount: float):
    print(f"[SWAP] Buying {token_mint} with {sol_amount} SOL...")
    return "DummyTxSignature"

# === Dummy Sell Logic ===
async def sell_token(client: AsyncClient, keypair: Keypair, token_mint: str):
    print(f"[SELL] Selling token {token_mint}...")
    return "DummySellSignature"

# === Timer Helpers ===
def get_token_age_minutes(created_at_str):
    try:
        created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - created_at).total_seconds() / 60
    except Exception:
        return 999

# === Async Client Setup ===
client = AsyncClient(RPC_URL)
