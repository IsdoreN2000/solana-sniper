import os
import time
import json
import logging
import requests
from solana.rpc.api import Client
from telegram import Bot

# === HARD-CODED CONFIGURATION ===
TELEGRAM_BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN_HERE'  # <-- Replace with your bot token
TELEGRAM_CHAT_ID = 'YOUR_TELEGRAM_CHAT_ID_HERE'      # <-- Replace with your chat ID
WALLET_ADDRESS = 'EQAat1kZaKhmYadJvEow5HD3YrEdCEmndCNRGVkkVdd9'

BUY_AMOUNT_USDC = 5
MAX_BUYS_PER_CYCLE = 4
SCAN_INTERVAL = 15  # seconds

SEEN_FILE = "seen_tokens.json"

# === LOGGING SETUP ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# === INIT ===
solana_client = Client("https://api.mainnet-beta.solana.com")
bot = Bot(token=TELEGRAM_BOT_TOKEN)

PUMP_FUN_URL = "https://pump.fun/api/launchpad/launches"

# === PERSISTENCE HELPERS ===
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

# === FUNCTION: Get New Tokens ===
def get_new_tokens():
    try:
        res = requests.get(PUMP_FUN_URL, timeout=10)
        res.raise_for_status()
        data = res.json()
        tokens = data.get("tokens", [])
        return tokens
    except Exception as e:
        logging.error(f"Error fetching tokens: {e}")
        return []

# === FUNCTION: Simulate Buy ===
def simulate_buy(token):
    token_name = token.get("name", "unknown")
    mint = token.get("mint", "unknown")
    message = f"📈 New token sniped: {token_name}\nMint: `{mint}`\nBuying ${BUY_AMOUNT_USDC}..."
    logging.info(message)
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Telegram send error: {e}")
    time.sleep(3)
    logging.info(f"✅ Simulated buy complete for {token_name}")

# === MAIN LOOP ===
def main():
    logging.info("🚀 Solana Sniper Bot started.")
    seen = load_seen()
    logging.info(f"Loaded {len(seen)} previously seen tokens.")

    try:
        while True:
            tokens = get_new_tokens()
            new_buys = 0

            for token in tokens:
                mint = token.get("mint")
                if mint and mint not in seen:
                    simulate_buy(token)
                    seen.add(mint)
                    new_buys += 1
                    if new_buys >= MAX_BUYS_PER_CYCLE:
                        break

            save_seen(seen)
            logging.info(f"⏳ Waiting {SCAN_INTERVAL}s before next scan...\n")
            time.sleep(SCAN_INTERVAL)
    except KeyboardInterrupt:
        logging.info("🛑 Shutting down. Saving seen tokens.")
        save_seen(seen)

if __name__ == "__main__":
    main()
