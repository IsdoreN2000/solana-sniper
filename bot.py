import os
import json
import asyncio
import websockets
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from datetime import datetime, timezone

# === Config ===
RPC_URL = os.getenv("RPC_URL")
PHANTOM_PRIVATE_KEY = os.getenv("PHANTOM_PRIVATE_KEY")

if not RPC_URL:
    raise ValueError("❌ RPC_URL is missing! Please add it to your .env file.")
if not PHANTOM_PRIVATE_KEY:
    raise ValueError("❌ PHANTOM_PRIVATE_KEY is missing! Please add it to your .env file.")

keypair = Keypair.from_bytes(bytes(json.loads(PHANTOM_PRIVATE_KEY)))

# === Alert function ===
def send_alert(message: str):
    try:
        print("\U0001F514", message)
    except UnicodeEncodeError:
        print("[ALERT]", message)

# === Mock buy function (replace with your real logic) ===
async def buy_token(client, keypair, mint_address, amount_sol=0.01):
    print(f"[MOCK BUY] Would buy {amount_sol} SOL of token {mint_address}")
    send_alert(f"🚀 Would buy {amount_sol} SOL of token {mint_address}")
    # Replace with your real swap logic here

# === Handle new token event ===
async def handle_new_token(token_data, client):
    print("🚀 New token event:", json.dumps(token_data, indent=2))
    mint_address = token_data.get("mint") or token_data.get("address")  # Adjust key as needed
    if mint_address:
        await buy_token(client, keypair, mint_address)
    else:
        print("No mint address found in token data.")

# === WebSocket listener ===
async def listen_for_new_tokens():
    uri = "wss://pumpportal.fun/api/data"
    async with websockets.connect(uri) as websocket:
        payload = {
            "event": "subscribeNewToken",
            "filters": {}
        }
        await websocket.send(json.dumps(payload))
        print("✅ Subscribed to new token events.")

        async with AsyncClient(RPC_URL) as client:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data.get("event") == "newToken":
                        await handle_new_token(data["data"], client)
                except Exception as e:
                    print("Error parsing message:", e)

if __name__ == "__main__":
    asyncio.run(listen_for_new_tokens())

