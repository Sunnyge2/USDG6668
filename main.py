import asyncio
import os
import requests
import time
import hmac
import hashlib
import base64
from telegram import Bot
from datetime import datetime

# ================== 配置 ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
INTERVAL = int(os.getenv("INTERVAL", "60"))

# OKX API Key（必须填！）
OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_API_SECRET = os.getenv("OKX_API_SECRET")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE")

DEX_URL = "https://web3.okx.com/api/v6/dex/aggregator/quote"
SOLANA_CHAIN = "501"

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDG = "2u1tszSeqZ3qBWF3uNGPFc8TzMk2tdiwknnRMWGWjGWH"
PYUSD = "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo"

CEX_PAIRS = ["USDC-USDT", "USDG-USDT", "PYUSD-USDT"]

def get_okx_signature(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    msg = timestamp + method + path + body
    mac = hmac.new(OKX_API_SECRET.encode(), msg.encode(), hashlib.sha256)
    signature = base64.b64encode(mac.digest()).decode()
    return timestamp, signature

def get_okx_dex_amount_out(from_token, to_token, amount_human=10000):
    decimals = 6
    amount_raw = str(int(amount_human * 10 ** decimals))
    
    params = {
        "chainIndex": SOLANA_CHAIN,
        "fromTokenAddress": from_token,
        "toTokenAddress": to_token,
        "amount": amount_raw,
        "swapMode": "exactIn",
        "directRoute": "true",
        "priceImpactProtectionPercent": "100"
    }
    
    # 构造带签名的请求
    path = "/api/v6/dex/aggregator/quote?" + "&".join([f"{k}={v}" for k,v in params.items()])
    timestamp, signature = get_okx_signature("GET", path)
    
    headers = {
        "OK-ACCESS-KEY": OKX_API_KEY,
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": OKX_PASSPHRASE,
        "Content-Type": "application/json"
    }
    
    try:
        r = requests.get(DEX_URL, params=params, headers=headers, timeout=20).json()
        if r.get("code") == "0" and r.get("data"):
            quote = r["data"][0]
            to_raw = int(quote.get("toTokenAmount") or 0)
            to_human = to_raw / (10 ** decimals)
            route = quote.get("dexRouterList", [{}])[0].get("dexName", "OKX")
            return round(to_human, 4), route
        else:
            return None, r.get("msg", "No route")
    except Exception as e:
        return None, str(e)

async def main():
    bot = Bot(token=BOT_TOKEN)
    print("Bot 已启动 - OKX DEX 已带签名")

    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"🕒 **OKX DEX 报价报告** ({now})\n\n"

        usdg_out, usdg_route = get_okx_dex_amount_out(USDG, USDC, 10000)
        pyusd_out, pyusd_route = get_okx_dex_amount_out(PYUSD, USDC, 10000)

        msg += "**10000 个输入在 OKX DEX 可得**\n"
        msg += f"10000 USDG → {usdg_out if usdg_out else 'N/A'} USDC  ({usdg_route})\n"
        msg += f"10000 PYUSD → {pyusd_out if pyusd_out else 'N/A'} USDC  ({pyusd_route})\n\n"

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
            print("✅ 发送成功")
        except Exception as e:
            print(f"发送失败: {e}")

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
