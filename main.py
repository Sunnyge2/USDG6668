import os
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
import requests
from telegram import Bot

load_dotenv()

WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

if not WALLET_ADDRESS or not TG_BOT_TOKEN or not TG_CHAT_ID:
    raise ValueError("❌ 请在 Variables 中设置 WALLET_ADDRESS、TG_BOT_TOKEN、TG_CHAT_ID")

THRESHOLD_HIGH = 10000.0
THRESHOLD_LOW = 9999.0

tg_bot = Bot(token=TG_BOT_TOKEN)

print("✅ SOL链 OKX DEX 监控 Bot 已启动")

async def get_okx_prices():
    pairs = ["USDC-USDT", "USDG-USDT", "PYUSD-USDT"]
    prices = {}
    for p in pairs:
        try:
            r = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={p}")
            data = r.json()
            if data.get('code') == '0':
                prices[p] = float(data['data'][0]['bidPx'])
        except:
            prices[p] = "N/A"
    return prices

async def send_alert(msg):
    await tg_bot.send_message(chat_id=TG_CHAT_ID, text=msg)

async def monitor():
    while True:
        try:
            # Solana 交易监控（简化版）
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [WALLET_ADDRESS, {"limit": 10}]
            }
            resp = requests.post("https://api.mainnet-beta.solana.com", json=payload).json()

            # 这里可扩展解析具体 swap 金额（目前用示例）
            # 实际运行时我会帮你加上 Jupiter / OKX DEX swap 解析

            prices = await get_okx_prices()
            usdc_amount = 10012.34   # ← 实际应从交易解析获得

            if usdc_amount > THRESHOLD_HIGH or usdc_amount < THRESHOLD_LOW:
                alert = f"""🚨 SOL链 OKX DEX 兑换提醒

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
当前 10000 USDG/PYUSD 可兑换 **{usdc_amount:.2f} USDC**

OKX CEX 买一价:
• USDC/USDT : {prices.get('USDC-USDT')}
• USDG/USDT : {prices.get('USDG-USDT')}
• PYUSD/USDT: {prices.get('PYUSD-USDT')}
"""
                await send_alert(alert)

            await asyncio.sleep(8)
        except Exception as e:
            print(f"错误: {e}")
            await asyncio.sleep(15)

if __name__ == "__main__":
    asyncio.run(monitor())
