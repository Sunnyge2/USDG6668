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

# Token 地址
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDG = "2u1tszSeqZ3qBWF3uNGPFc8TzMk2tdiwknnRMWGWjGWH"
PYUSD = "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo"

CEX_PAIRS = ["USDC-USDT", "USDG-USDT", "PYUSD-USDT"]

def get_dex_amount_out(from_token, to_token, amount_human):
    """amount_human = 用户输入的数量，例如 10000"""
    # 大多数稳定币是 6 decimals
    decimals = 6
    amount_raw = int(amount_human * (10 ** decimals))
    
    params = {
        "chainIndex": SOLANA_CHAIN,
        "fromTokenAddress": from_token,
        "toTokenAddress": to_token,
        "amount": str(amount_raw),
        "swapMode": "exactIn"
    }
    try:
        r = requests.get(DEX_URL, params=params, timeout=15).json()
        if r.get("code") == "0" and r.get("data"):
            quote = r["data"][0]
            to_amount_raw = int(quote["toTokenAmount"])
            to_amount_human = to_amount_raw / (10 ** decimals)
            return round(to_amount_human, 4)
        else:
            print(f"API Error: {r.get('msg')}")
            return None
    except Exception as e:
        print(f"请求异常: {e}")
        return None

async def main():
    bot = Bot(token=BOT_TOKEN)
    print("Bot 已启动，正在监控...")

    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"🕒 **OKX 价格监控报告** ({now})\n\n"

        # === DEX 查询（10000 USDG 能换多少 USDC）===
        usdg_out = get_dex_amount_out(USDG, USDC, 10000)
        pyusd_out = get_dex_amount_out(PYUSD, USDC, 10000)

        msg += "**OKX DEX (Solana) - 10000 个输入可得**\n"
        msg += f"10000 USDG → {usdg_out if usdg_out else 'N/A'} USDC\n"
        msg += f"10000 PYUSD → {pyusd_out if pyusd_out else 'N/A'} USDC\n\n"

        # === CEX 买一价 ===
        msg += "**OKX CEX 买一价**\n"
        for pair in CEX_PAIRS:
            try:
                r = requests.get(f"https://www.okx.com/api/v5/market/books?instId={pair}&sz=1", timeout=10).json()
                if r.get("code") == "0" and r.get("data"):
                    bid = float(r["data"][0]["bids"][0][0])
                    msg += f"{pair} 买一: {bid}\n"
                else:
                    msg += f"{pair} 买一: 获取失败\n"
            except:
                msg += f"{pair} 买一: 异常\n"

        try:
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
            print("✅ 报告发送成功")
        except Exception as e:
            print(f"❌ 发送失败: {e}")

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
