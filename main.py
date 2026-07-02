import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import requests
from telegram import Bot

load_dotenv()

WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

tg_bot = Bot(token=TG_BOT_TOKEN)

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

async def send_alert():
    prices = await get_okx_bid_prices()
    alert = f"""🚨 【测试提醒 - 已触发阈值】

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

10000 USDG 可兑换 ≈ 10012.45 USDC
10000 PYUSD 可兑换 ≈ 9997.80 USDC

OKX CEX 买一价:
• USDC/USDT : {prices.get('USDC-USDT')}
• USDG/USDT : {prices.get('USDG-USDT')}
• PYUSD/USDT: {prices.get('PYUSD-USDT')}
"""
    await tg_bot.send_message(chat_id=TG_CHAT_ID, text=alert)
    print("✅ 已发送测试提醒")

async def main():
    print("✅ Bot 启动 - 强制测试模式")
    while True:
        await send_alert()   # 每轮都发提醒，用于测试
        await asyncio.sleep(30)  # 30秒发一次

if __name__ == "__main__":
    asyncio.run(main())
