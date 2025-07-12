# utils.py

from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient

# ✅ This is a placeholder for JupiterClient.
# Make sure to pass your initialized JupiterClient instance when calling sell_token.

async def sell_token(jupiter, keypair: Keypair, token_mint: str, token_amount: int):
    """
    Sell a token for SOL using Jupiter aggregator.
    
    Args:
        jupiter: An instance of JupiterClient already initialized.
        keypair: The wallet keypair.
        token_mint: The SPL token mint address to sell.
        token_amount: The amount to sell (in base units, e.g., lamports).

    Returns:
        Transaction signature if successful, None otherwise.
    """
    try:
        async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
            routes = await jupiter.quote(
                input_mint=token_mint,
                output_mint="So11111111111111111111111111111111111111112",  # SOL
                amount=token_amount,
                slippage_bps=100
            )

            if not routes:
                print(f"❌ No swap route found for {token_mint}")
                return None

            tx = await jupiter.swap(
                keypair=keypair,
                route=routes[0]
            )

            sig = await client.send_raw_transaction(
                tx.serialize(), opts={"skip_preflight": True}
            )

            print(f"✅ Sold token {token_mint}\n📦 Tx: {sig.value}")
            return sig.value

    except Exception as e:
        print(f"❌ Error selling token {token_mint}: {e}")
        return None
