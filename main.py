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

OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_API_SECRET = os.getenv("OKX_API_SECRET")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE")

PRICE_URL = "https://web3.okx.com/api/v6/dex/index/current-price"

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDG = "2u1tszSeqZ3qBWF3uNGPFc8TzMk2tdiwknnRMWGWjGWH"
PYUSD = "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo"

CEX_PAIRS = ["USDC-USDT", "USDG-USDT", "PYUSD-USDT"]

def get_signature(method, request_path, body=""):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method + request_path + body
    mac = hmac.new(OKX_API_SECRET.encode(), message.encode(), hashlib.sha256)
    return timestamp, base64.b64encode(mac.digest()).decode()

def get_token_price(token_address):
    body = [{
        "chainIndex": "501",
        "tokenContractAddress": token_address
    }]
    body_str = str(body).replace("'", '"')  # 转成 JSON 字符串格式
    
    request_path = "/api/v6/dex/index/current-price"
    timestamp, signature = get_signature("POST", request_path, body_str)
    
    headers = {
        "OK-ACCESS-KEY": OKX_API_KEY,
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": OKX_PASSPHRASE,
        "Content-Type": "application/json"
    }
    
    try:
        r = requests.post(PRICE_URL, json=body, headers=headers, timeout=20).json()
        if r.get("code") == "0" and r.get("data"):
            return float(r["data"][0]["price"])
        else:
            return None
    except:
        return None

async def main():
    bot = Bot(token=BOT_TOKEN)
    print("Bot 启动 - 使用 current-price 接口")

    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"🕒 **OKX DEX 报价报告** ({now})\n\n"

        usdg_price = get_token_price(USDG)
        pyusd_price = get_token_price(PYUSD)
        usdc_price = get_token_price(USDC) or 1.0

        usdg_out = round(10000 * (usdg_price or 0) / usdc_price, 4) if usdg_price else None
        pyusd_out = round(10000 * (pyusd_price or 0) / usdc_price, 4) if pyusd_price else None

        msg += "**10000 个输入可得 USDC（估算）**\n"
        msg += f"10000 USDG → {usdg_out if usdg_out else 'N/A'} USDC  (USDG价格: {usdg_price})\n"
        msg += f"10000 PYUSD → {pyusd_out if pyusd_out else 'N/A'} USDC  (PYUSD价格: {pyusd_price})\n\n"

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
