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

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDG = "2u1tszSeqZ3qBWF3uNGPFc8TzMk2tdiwknnRMWGWjGWH"
PYUSD = "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo"

CEX_PAIRS = ["USDC-USDT", "USDG-USDT", "PYUSD-USDT"]

def get_okx_dex_amount_out(from_token, to_token, amount_human=10000):
    decimals = 6
    amount_raw = str(int(amount_human * 10 ** decimals))
    
    params = {
        "chainIndex": SOLANA_CHAIN,
        "fromTokenAddress": from_token,
        "toTokenAddress": to_token,
        "amount": amount_raw,
        "swapMode": "exactIn",
        "directRoute": "true",           # 强制单池路由
        "priceImpactProtectionPercent": "100"  # 关闭价格冲击保护
    }
    try:
        r = requests.get(DEX_URL, params=params, timeout=20).json()
        print(f"OKX DEX Response for {from_token[:8]}: {r.get('code')}")  # 调试日志
        
        if r.get("code") == "0" and r.get("data") and len(r["data"]) > 0:
            quote = r["data"][0]
            to_raw = int(quote.get("toTokenAmount") or quote.get("amountOut", 0))
            to_human = to_raw / (10 ** decimals)
            route = quote.get("dexRouterList", [{}])[0].get("dexName", "Unknown")
            return round(to_human, 4), route
        else:
            error_msg = r.get("msg") or r.get("data") or "No route"
            print(f"OKX Error: {error_msg}")
            return None, error_msg
    except Exception as e:
        print(f"请求异常: {e}")
        return None, str(e)

async def main():
    bot = Bot(token=BOT_TOKEN)
    print("Bot 已启动 - 使用 OKX DEX")

    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"🕒 **OKX DEX 报价报告** ({now})\n\n"

        # USDG → USDC
        usdg_out, usdg_route = get_okx_dex_amount_out(USDG, USDC, 10000)
        # PYUSD → USDC
        pyusd_out, pyusd_route = get_okx_dex_amount_out(PYUSD, USDC, 10000)

        msg += "**10000 个输入在 OKX DEX 可得**\n"
        msg += f"10000 USDG → {usdg_out if usdg_out else 'N/A'} USDC  (路由: {usdg_route})\n"
        msg += f"10000 PYUSD → {pyusd_out if pyusd_out else 'N/A'} USDC  (路由: {pyusd_route})\n\n"

        # CEX 部分保持不变
        msg += "**OKX CEX 买一价**\n"
        for pair in CEX_PAIRS:
            try:
                r = requests.get(f"https://www.okx.com/api/v5/market/books?instId={pair}&sz=1", timeout=10).json()
                bid = float(r["data"][0]["bids"][0][0]) if r.get("data") else None
                msg += f"{pair} 买一: {bid if bid else 'N/A'}\n"
            except:
                msg += f"{pair} 买一: 获取失败\n"

        try:
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
            print("✅ 报告发送成功")
        except Exception as e:
            print(f"❌ 发送失败: {e}")

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
