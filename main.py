import asyncio
import requests
from telegram import Bot
import time
from datetime import datetime

# 配置
BOT_TOKEN = "你的BOT_TOKEN"
CHAT_ID = "你的CHAT_ID"  # 整数或字符串
CHECK_INTERVAL = 60  # 秒，建议 30-60 秒，避免频繁请求

# Solana DEX Quote API (OKX DEX)
DEX_QUOTE_URL = "https://web3.okx.com/api/v6/dex/aggregator/quote"
SOLANA_CHAIN_INDEX = "501"  # Solana

# CEX 交易对
CEX_PAIRS = ["USDC-USDT", "USDG-USDT", "PYUSD-USDT"]

def get_dex_price(from_token, to_token, amount=100000000):  # amount 为最小单位，例如 100 USDC
    params = {
        "chainIndex": SOLANA_CHAIN_INDEX,
        "fromTokenAddress": from_token,
        "toTokenAddress": to_token,
        "amount": str(amount),
        "swapMode": "exactIn"
    }
    try:
        resp = requests.get(DEX_QUOTE_URL, params=params, timeout=10)
        data = resp.json()
        if data.get("code") == "0" and data.get("data"):
            quote = data["data"][0]
            price = float(quote["toTokenAmount"]) / float(quote["fromTokenAmount"])  # 近似价格
            return round(price, 6)
        return None
    except Exception as e:
        print(f"DEX 请求失败: {e}")
        return None

def get_cex_buy_one(inst_id):  # 如 "USDC-USDT"
    url = f"https://www.okx.com/api/v5/market/books?instId={inst_id}&sz=1"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("code") == "0" and data.get("data"):
            bids = data["data"][0].get("bids", [])
            if bids:
                return float(bids[0][0])  # 买一价
        return None
    except Exception as e:
        print(f"CEX 请求失败: {e}")
        return None

async def monitor_prices(bot: Bot):
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"🕒 **价格监控报告** ({now})\n\n"

        # DEX 价格 (Solana)
        usdg_usdc = get_dex_price("2u1tszSeqZ3qBWF3uNGPFc8TzMk2tdiwknnRMWGWjGWH", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        pyusd_usdc = get_dex_price("2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        
        message += "**OKX DEX (Solana)**\n"
        message += f"USDG/USDC: {usdg_usdc if usdg_usdc else 'N/A'}\n"
        message += f"PYUSD/USDC: {pyusd_usdc if pyusd_usdc else 'N/A'}\n\n"

        # CEX 买一价
        message += "**OKX CEX 买一价**\n"
        for pair in CEX_PAIRS:
            price = get_cex_buy_one(pair)
            message += f"{pair}: {price if price else 'N/A'}\n"

        # 发送消息
        try:
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
            print("报告已发送")
        except Exception as e:
            print(f"发送失败: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    bot = Bot(token=BOT_TOKEN)
    asyncio.run(monitor_prices(bot))
