import asyncio
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.signature import Signature
import base64
import time

# You may need this if not defined elsewhere
from jup_ag import JupiterClient  # or replace with your own Jupiter client logic


async def sell_token(keypair: Keypair, token_mint: str, min_amount_out: float = 0):
    """
    Swap token back to SOL using Jupiter Aggregator
    """
    try:
        async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
            jupiter = JupiterClient(client)
            
            # Step 1: Get quote route
            routes = await jupiter.quote(
                input_mint=token_mint,
                output_mint="So11111111111111111111111111111111111111112",  # SOL
                amount=1000000,  # You can dynamically get balance to replace this
                slippage_bps=100,
            )
            if not routes:
                print(f"❌ No routes found for selling token {token_mint}")
                return None

            # Step 2: Execute swap
            route = routes[0]
            tx = await jupiter.swap(keypair=keypair, route=route)
            sig = await client.send_raw_transaction(tx.serialize(), opts={"skip_preflight": True})

            print(f"✅ Sold token {token_mint}\n📦 Tx: {sig.value}")
            return sig.value

    except Exception as e:
        print(f"❌ Error while selling {token_mint}: {e}")
        return None
