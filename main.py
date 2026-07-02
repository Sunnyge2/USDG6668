import asyncio
import os
import requests
from telegram import Bot
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
INTERVAL = int(os.getenv("INTERVAL", "60"))

DEX_URL = "https://web3.okx.com/api/v6/dex/aggregator/quote"
SOLANA_CHAIN = "501"

CEX_PAIRS = ["USDC-USDT", "USDG-USDT", "PYUSD-USDT"]

async def main():
    bot = Bot(token=BOT_TOKEN)
    print("Bot started...")

    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"🕒 **OKX 价格监控** ({now})\n\n"

        # === DEX (Solana) ===
        try:
            # USDG/USDC
            r1 = requests.get(DEX_URL, params={
                "chainIndex": SOLANA_CHAIN,
                "fromTokenAddress": "2u1tszSeqZ3qBWF3uNGPFc8TzMk2tdiwknnRMWGWjGWH",  # USDG
                "toTokenAddress": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",    # USDC
                "amount": "100000000",
                "swapMode": "exactIn"
            }, timeout=15).json()
            usdg_price = round(float(r1["data"][0]["toTokenAmount"]) / float(r1["data"][0]["fromTokenAmount"]), 6) if r1.get("data") else None

            # PYUSD/USDC
            r2 = requests.get(DEX_URL, params={
                "chainIndex": SOLANA_CHAIN,
                "fromTokenAddress": "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo",  # PYUSD
                "toTokenAddress": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "amount": "100000000",
                "swapMode": "exactIn"
            }, timeout=15).json()
            pyusd_price = round(float(r2["data"][0]["toTokenAmount"]) / float(r2["data"][0]["fromTokenAmount"]), 6) if r2.get("data") else None

            msg += "**OKX DEX (Solana)**\n"
            msg += f"USDG/USDC ≈ {usdg_price}\n"
            msg += f"PYUSD/USDC ≈ {pyusd_price}\n\n"
        except Exception as e:
            msg += f"DEX 获取失败: {e}\n\n"

        # === CEX 买一价 ===
        msg += "**OKX CEX 买一价**\n"
        for pair in CEX_PAIRS:
            try:
                r = requests.get(f"https://www.okx.com/api/v5/market/books?instId={pair}&sz=1", timeout=10).json()
                bid = float(r["data"][0]["bids"][0][0]) if r.get("data") else None
                msg += f"{pair}: {bid}\n"
            except:
                msg += f"{pair}: 获取失败\n"

        try:
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
            print("✅ 报告发送成功")
        except Exception as e:
            print(f"❌ 发送失败: {e}")

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
