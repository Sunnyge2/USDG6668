import os
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
from web3 import Web3
import requests
from telegram import Bot

load_dotenv()

# ================== 配置 ==================
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS").lower()
ETHERSCAN_KEY = os.getenv("ETHERSCAN_API_KEY")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

THRESHOLD_HIGH = 10000.0
THRESHOLD_LOW = 9900.0

w3 = Web3(Web3.HTTPProvider("https://ethereum.publicnode.com"))
tg_bot = Bot(token=TG_BOT_TOKEN)

async def get_okx_bid_prices():
    """获取 OKX CEX 多个买一价"""
    pairs = ["USDC-USDT", "USDG-USDT", "PYUSD-USDT"]
    prices = {}
    for p in pairs:
        try:
            r = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={p}")
            data = r.json()
            if data.get('code') == '0':
                prices[p] = float(data['data'][0]['bidPx'])
        except:
            prices[p] = None
    return prices

async def send_alert(msg):
    await tg_bot.send_message(chat_id=TG_CHAT_ID, text=msg)

async def monitor():
    last_ts = int(time.time())
    while True:
        try:
            # Ethereum (ERC) 监控 OKX DEX 交易
            url = f"https://api.etherscan.io/api?module=account&action=tokentx&address={WALLET_ADDRESS}&sort=desc&apikey={ETHERSCAN_KEY}&limit=15"
            resp = requests.get(url).json()

            if resp.get('status') == '1':
                for tx in resp['result']:
                    ts = int(tx['timeStamp'])
                    if ts <= last_ts:
                        continue

                    symbol = tx['tokenSymbol']
                    value = float(tx['value']) / (10 ** int(tx['tokenDecimal']))

                    # 检测兑换成 USDC
                    if symbol == "USDC" and 9800 < value < 10200:
                        prices = await get_okx_bid_prices()
                        effective_rate = value / 10000  # 1 USDG/PYUSD ≈ ? USDC

                        alert = f"""🚨 OKX DEX 大额兑换提醒

链: Ethereum (ERC)
时间: {datetime.fromtimestamp(ts)}
获得 USDC: {value:.4f}
有效兑换率: 1 USDG/PYUSD ≈ {effective_rate:.6f} USDC

OKX CEX 买一价:
• USDC/USDT : {prices.get('USDC-USDT')}
• USDG/USDT : {prices.get('USDG-USDT')}
• PYUSD/USDT: {prices.get('PYUSD-USDT')}

Tx: https://etherscan.io/tx/{tx['hash']}
"""
                        await send_alert(alert)

                    last_ts = ts

            # Solana 监控（占位，可扩展）
            # 如需完整 Solana 监控请告诉我

            await asyncio.sleep(10)
        except Exception as e:
            print(f"错误: {e}")
            await asyncio.sleep(15)

if __name__ == "__main__":
    asyncio.run(monitor())
