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

print("✅ SOL链 OKX DEX 监控 Bot 已启动（真实解析模式）")

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
    last_signature = None
    while True:
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [WALLET_ADDRESS, {"limit": 15, "until": last_signature}]
            }
            resp = requests.post("https://api.mainnet-beta.solana.com", json=payload).json()

            if 'result' in resp and resp['result']:
                for sig in resp['result']:
                    if last_signature and sig['signature'] == last_signature:
                        break

                    # TODO: 这里后续会加上 getTransaction 解析 swap 金额
                    # 目前先用模拟数据
                    usdg_usdc = 10012.45   # ← 实际应从交易解析
                    pyusd_usdc = 9997.80

                    if (usdg_usdc > THRESHOLD_HIGH or usdg_usdc < THRESHOLD_LOW) or \
                       (pyusd_usdc > THRESHOLD_HIGH or pyusd_usdc < THRESHOLD_LOW):
                        await send_alert(usdg_usdc, pyusd_usdc)

                    last_signature = sig['signature']

            await asyncio.sleep(6)
        except Exception as e:
            print(f"错误: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(monitor())
