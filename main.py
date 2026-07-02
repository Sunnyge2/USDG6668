import asyncio
import os
import requests
import time
import hmac
import hashlib
import base64
from telegram import Bot
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
INTERVAL = int(os.getenv("INTERVAL", "60"))

# OKX 配置
OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_API_SECRET = os.getenv("OKX_API_SECRET")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE")

DEX_URL = "https://web3.okx.com/api/v6/dex/aggregator/quote"

SOLANA_CHAIN = "501"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDG = "2u1tszSeqZ3qBWF3uNGPFc8TzMk2tdiwknnRMWGWjGWH"
PYUSD = "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo"

CEX_PAIRS = ["USDC-USDT", "USDG-USDT", "PYUSD-USDT"]

def get_okx_signature(method, request_path):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method + request_path
    mac = hmac.new(OKX_API_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
    signature = base64.b64encode(mac.digest()).decode('utf-8')
    return timestamp, signature

def get_okx_dex_amount_out(from_token, to_token, amount_human=10000):
    decimals = 6
    amount_raw = str(int(amount_human * 10**decimals))
    
    params = {
        "chainIndex": SOLANA_CHAIN,
        "fromTokenAddress": from_token,
        "toTokenAddress": to_token,
        "amount": amount_raw,
        "swapMode": "exactIn",
        "directRoute": "true",
        "priceImpactProtectionPercent": "100"
    }
    
    # 构造用于签名的完整 path
    query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    request_path = f"/api/v6/dex/aggregator/quote?{query_string}"
    
    timestamp, signature = get_okx_signature("GET", request_path)
    
    headers = {
        "OK-ACCESS-KEY": OKX_API_KEY,
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": OKX_PASSPHRASE,
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.get(DEX_URL, params=params, headers=headers, timeout=20)
        r = resp.json()
        
        if r.get("code") == "0" and r.get("data"):
            quote = r["data"][0]
            to_amount = int(quote.get("toTokenAmount") or 0) / (10 ** decimals)
            route = quote.get("dexRouterList", [{}])[0].get("dexName", "OKX")
            return round(to_amount, 4), route
        else:
            return None, r.get("msg", f"Code:{r.get('code')}")
    except Exception as e:
        return None, str(e)

async def main():
    bot = Bot(token=BOT_TOKEN)
    print("Bot 启动 - OKX DEX 签名版 v2")

    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"🕒 **OKX DEX 报价报告** ({now})\n\n"

        usdg_out, usdg_info = get_okx_dex_amount_out(USDG, USDC, 10000)
        pyusd_out, pyusd_info = get_okx_dex_amount_out(PYUSD, USDC, 10000)

        msg += "**10000 个输入可得**\n"
        msg += f"10000 USDG → {usdg_out if usdg_out else 'N/A'} USDC  ({usdg_info})\n"
        msg += f"10000 PYUSD → {pyusd_out if pyusd_out else 'N/A'} USDC  ({pyusd_info})\n\n"

        msg += "**OKX CEX 买一价**\n"
        for pair in CEX_PAIRS:
            try:
                r = requests.get(f"https://www.okx.com/api/v5/market/books?instId={pair}&sz=1", timeout=10).json()
                bid = float(r["data"][0]["bids"][0][0]) if r.get("data") else None
                msg += f"{pair}: {bid if bid else 'N/A'}\n"
            except:
                msg += f"{pair}: 失败\n"

        try:
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
            print("✅ 发送成功")
        except Exception as e:
            print(f"发送失败: {e}")

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
