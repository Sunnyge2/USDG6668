import os
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
import requests
from telegram import Bot

load_dotenv()

WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
if not WALLET_ADDRESS:
    raise ValueError("❌ WALLET_ADDRESS 未设置")

WALLET_ADDRESS = WALLET_ADDRESS.lower().strip()
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

THRESHOLD_HIGH = 10000.0
THRESHOLD_LOW = 9999.0

tg_bot = Bot(token=TG_BOT_TOKEN)

print("✅ SOL链 OKX DEX 监控 Bot 已启动")

async def get_okx_bid_prices():
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

async def send_alert(usdg_usdc, pyusd_usdc):
    prices = await get_okx_bid_prices()
    alert = f"""🚨 SOL链 OKX DEX 兑换提醒

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

10000 USDG 可兑换 ≈ {usdg_usdc:.4f} USDC
10000 PYUSD 可兑换 ≈ {pyusd_usdc:.4f} USDC

OKX CEX 买一价:
• USDC/USDT : {prices.get('USDC-USDT')}
• USDG/USDT : {prices.get('USDG-USDT')}
• PYUSD/USDT: {prices.get('PYUSD-USDT')}
"""
    await tg_bot.send_message(chat_id=TG_CHAT_ID, text=alert)

async def monitor():
    while True:
        try:
            # 这里实际应解析真实 swap 交易
            # 目前用示例数据，后面可替换为真实解析
            usdg_to_usdc = 10005.23   # ← 替换为实际计算的 10000 USDG 兑换 USDC 数量
            pyusd_to_usdc = 9998.45   # ← 替换为实际计算的 10000 PYUSD 兑换 USDC 数量

            if (usdg_to_usdc > THRESHOLD_HIGH or usdg_to_usdc < THRESHOLD_LOW) or \
               (pyusd_to_usdc > THRESHOLD_HIGH or pyusd_to_usdc < THRESHOLD_LOW):
                await send_alert(usdg_to_usdc, pyusd_to_usdc)

            await asyncio.sleep(8)
        except Exception as e:
            print(f"错误: {e}")
            await asyncio.sleep(15)

if __name__ == "__main__":
    asyncio.run(monitor())
