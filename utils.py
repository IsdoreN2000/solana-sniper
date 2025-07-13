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
if not RPC_URL:
    raise ValueError("❌ RPC_URL is missing! Please add it to your .env file.")

# === Alert function ===
def send_alert(message: str):
    try:
        print("\U0001F514", message)  # Unicode for 🔔 bell emoji
    except UnicodeEncodeError:
        print("[ALERT]", message)

# === Load keypair from .env ===
def load_keypair_from_env():
    key = os.getenv("PHANTOM_PRIVATE_KEY")
    if not key:
        raise ValueError("❌ PHANTOM_PRIVATE_KEY is missing! Please add it to your .env file.")
    try:
        private_key_array = json.loads(key)
        if not isinstance(private_key_array, list):
            raise ValueError("PHANTOM_PRIVATE_KEY must be a JSON array, e.g. [12,34,...]")
        return Keypair.from_bytes(bytes(private_key_array))
    except Exception as e:
        raise ValueError(f"Invalid PHANTOM_PRIVATE_KEY: {e}")

# === Get current SOL/USD price ===
async def get_sol_usd_price():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd") as resp:
                data = await resp.json()
                return data['solana']['usd']
        except Exception as e:
            send_alert(f"Error fetching SOL/USD price: {e}")
            return None

# === Fetch latest tokens from pump.fun ===
async def get_pump_fun_tokens():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://pump.fun/api/latest-tokens") as response:
                return await response.json()
    except Exception as e:
        send_alert(f"Pump.fun error: {e}")
        return []

# === Stub for other platforms ===
async def get_moonshot_tokens():
    return []  # Extend this later with actual logic

# === Dummy Jupiter Swap Logic (replace with real later) ===
async def jupiter_swap_sol_to_token(client: AsyncClient, keypair: Keypair, token_mint: str, sol_amount: float):
    print(f"[SWAP] Buying {token_mint} with {sol_amount} SOL...")
    # Replace with real swap logic
    return "DummyTxSignature"

# === Dummy Sell Logic ===
async def sell_token(client: AsyncClient, keypair: Keypair, token_mint: str):
    print(f"[SELL] Selling token {token_mint}...")
    # Replace with real sell logic
    return "DummySellSignature"

# === Timer Helpers ===
def get_token_age_minutes(created_at_str):
    try:
        created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - created_at).total_seconds() / 60
    except Exception:
        return 999

# === Example usage as a script ===
if __name__ == "__main__":
    async def main():
        keypair = load_keypair_from_env()
        async with AsyncClient(RPC_URL) as client:
            sol_price = await get_sol_usd_price()
            print("SOL/USD:", sol_price)
            tokens = await get_pump_fun_tokens()
            print("Tokens:", tokens[:2])
            # Example swap
            await jupiter_swap_sol_to_token(client, keypair, "TOKEN_MINT_ADDRESS", 0.1)
            # Example sell
            await sell_token(client, keypair, "TOKEN_MINT_ADDRESS")

    asyncio.run(main())
