import requests
import json
from datetime import datetime, timezone
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.signature import Signature
from jup.ag import JupiterClient

# === Global Utils ===
def send_alert(msg):
    print("🔔", msg)

def get_sol_usd_price():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
        return r.json()["solana"]["usd"]
    except Exception as e:
        print("Error fetching SOL price:", e)
        return None

def get_pump_fun_tokens(limit=10, sort="recent", max_age_minutes=5):
    url = "https://pump.fun/api/graphql"
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://pump.fun",
        "Referer": "https://pump.fun/"
    }
    payload = {
        "operationName": "ExploreProjects",
        "variables": {"sort": sort, "limit": limit},
        "query": """
            query ExploreProjects($sort: ExploreSortOption!, $limit: Int!) {
              exploreProjects(sort: $sort, limit: $limit) {
                id
                name
                marketCap
                createdAt
              }
            }
        """
    }
    try:
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        tokens = res.json()["data"]["exploreProjects"]
        fresh = []
        for t in tokens:
            created_at = datetime.fromisoformat(t["createdAt"].replace("Z", "+00:00"))
            age_mins = (datetime.now(timezone.utc) - created_at).total_seconds() / 60
            if age_mins <= max_age_minutes:
                fresh.append({
                    "mint": t["id"],
                    "name": t["name"],
                    "marketCap": t["marketCap"],
                    "created_at": int(created_at.timestamp())
                })
        return fresh
    except Exception as e:
        print("Pump.fun error:", e)
        return []

def get_moonshot_tokens():
    return []  # placeholder for now

# === Jupiter Buy & Sell ===
async def jupiter_swap_sol_to_token(keypair: Keypair, token_address: str, amount_sol: float):
    async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
        jupiter = JupiterClient(client)
        routes = await jupiter.quote(
            input_mint="So11111111111111111111111111111111111111112",  # SOL
            output_mint=token_address,
            amount=int(amount_sol * 1e9),
            slippage_bps=100
        )
        if not routes:
            raise Exception("No swap route found")
        tx = await jupiter.swap(keypair=keypair, route=routes[0])
        sig = await client.send_raw_transaction(tx.serialize(), opts={"skip_preflight": True})
        return {"result": str(sig.value)}

async def sell_token(keypair: Keypair, token_address: str, min_amount_out: int = 0):
    async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
        jupiter = JupiterClient(client)
        routes = await jupiter.quote(
            input_mint=token_address,
            output_mint="So11111111111111111111111111111111111111112",  # SOL
            amount=0,  # Let Jupiter detect max input from wallet
            slippage_bps=100
        )
        if not routes:
            raise Exception("No swap route found")
        tx = await jupiter.swap(keypair=keypair, route=routes[0])
        sig = await client.send_raw_transaction(tx.serialize(), opts={"skip_preflight": True})
        return {"result": str(sig.value)}
