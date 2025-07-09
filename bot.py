import os
import time
import json
import requests
from dotenv import load_dotenv
from solana.keypair import Keypair
from solana.rpc.api import Client
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer
from solana.publickey import PublicKey
from solana.rpc.types import TxOpts
from telegram import Bot

# === Load environment variables ===
load_dotenv()

try:
    PRIVATE_KEY = json.loads(os.getenv("PRIVATE_KEY"))
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    MAIN_WITHDRAW_WALLET = os.getenv("MAIN_WITHDRAW_WALLET")
    assert all([PRIVATE_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, MAIN_WITHDRAW_WALLET])
except Exception as e:
    raise Exception("Environment variable error: " + str(e))

# === Solana Setup ===
keypair = Keypair.from_secret_key(bytes(PRIVATE_KEY))
wallet = keypair.public_key
client = Client("https://api.mainnet-beta.solana.com")

# === Telegram Setup ===
tg_bot = Bot(token=TELEGRAM_TOKEN)

# === Config ===
BUY_AMOUNT_SOL = 0.01
SCAN_INTERVAL = 120  # every 2 minutes
PROFIT_TARGET_MULTIPLIER = 1.8
SNIPER_WALLETS = [
    "SniperWallet1Here",  # replace with real sniper wallets
    "SniperWallet2Here"
]

# === Helpers ===
def send_alert(message):
    try:
        tg_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        print(f"Telegram Error: {e}")

def get_pumpfun_tokens():
    try:
        res = requests.get("https://pump.fun/api/projects?sort=recent")
        return res.json().get("projects", [])[:10]
    except Exception as e:
        print(f"Pump.fun error: {e}")
        return []

def token_is_safe(token_address):
    # TODO: Integrate honeypot or blacklist checker here
    return True

def buy_token(token_address):
    # TODO: Integrate Jupiter swap API for actual buy
    print(f"[BUY] Token: {token_address}")
    send_alert(f"Buying token: {token_address}")

def sell_token(token_address):
    # TODO: Integrate Jupiter swap API for actual sell
    print(f"[SELL] Token: {token_address}")
    send_alert(f"Selling token: {token_address}")

def withdraw_profits():
    try:
        balance = client.get_balance(wallet)["result"]["value"]
        lamports = int(balance * 0.9)
        if lamports < 5000:
            print("Insufficient balance to withdraw.")
            return

        tx = Transaction().add(
            transfer(
                TransferParams(
                    from_pubkey=wallet,
                    to_pubkey=PublicKey(MAIN_WITHDRAW_WALLET),
                    lamports=lamports
                )
            )
        )
        result = client.send_transaction(tx, keypair, opts=TxOpts(skip_preflight=True))
        send_alert(f"Withdrawn: https://solscan.io/tx/{result['result']}")
    except Exception as e:
        print(f"[Withdraw error]: {e}")

def process_new_tokens():
    tokens = get_pumpfun_tokens()
    for token in tokens:
        token_address = token.get("mint")
        if not token_address:
            continue

        if not token_is_safe(token_address):
            print(f"[SKIP] Unsafe token: {token_address}")
            continue

        buy_token(token_address)
        time.sleep(30)  # hold briefly
        sell_token(token_address)
        withdraw_profits()

def copy_trade_snipers():
    for sniper in SNIPER_WALLETS:
        # TODO: Add wallet tracking and copy-trading logic if needed
        pass

# === Main Loop ===
if __name__ == "__main__":
    send_alert("Sniper Bot Started.")
    while True:
        try:
            process_new_tokens()
            copy_trade_snipers()
            time.sleep(SCAN_INTERVAL)
        except Exception as e:
            send_alert(f"Bot Error: {e}")
            time.sleep(60)
