import os
import json
import time
import asyncio
import requests
import websocket
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

# ============================================================
#  配置（从环境变量读取）
# ============================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    print("❌ 环境变量 TELEGRAM_TOKEN 未设置或为空！")
    exit(1)

CHAT_ID = os.environ.get("CHAT_ID")
if not CHAT_ID:
    print("❌ 环境变量 CHAT_ID 未设置或为空！")
    exit(1)

# 阈值（单位：USDC）
THRESHOLD_HIGH = float(os.environ.get("THRESHOLD_HIGH", "10000"))
THRESHOLD_LOW = float(os.environ.get("THRESHOLD_LOW", "9998"))

# 监控的代币（仅 Solana）
TOKENS = {
    "USDG": "2u1tszSeqZ3qBWF3uNGPFc8TzMk2tdiwknnRMWGWjGWH",
    "PYUSD": "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo"
}

SOLANA_CHAIN_INDEX = "501"

# OKX DEX WebSocket 地址
DEX_WS_URL = "wss://wsdex.okx.com/ws/v6/dex"

# OKX 交易所 API
OKX_API_URL = "https://www.okx.com"

# ============================================================
#  初始化 Telegram Bot（增加连接池）
# ============================================================
request = HTTPXRequest(connection_pool_size=8)
bot = Bot(token=TELEGRAM_TOKEN, request=request)

# ============================================================
#  获取买一价格（REST API）
# ============================================================
def get_bid_price(symbol):
    url = f"{OKX_API_URL}/api/v5/market/books"
    params = {"instId": symbol, "sz": "1"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("code") == "0":
            bids = data.get("data", [{}])[0].get("bids", [])
            if bids:
                return float(bids[0][0])
    except Exception as e:
        print(f"获取价格失败 {symbol}: {e}")
    return None

def get_all_prices():
    return {
        "USDC_USDT": get_bid_price("USDC-USDT"),
        "USDG_USDT": get_bid_price("USDG-USDT"),
        "PYUSD_USDT": get_bid_price("PYUSD-USDT")
    }

# ============================================================
#  发送 Telegram 提醒（异步）
# ============================================================
async def send_alert(symbol, amount_usd, trade_info, prices, alert_type):
    alert_emoji = "🚨" if alert_type == "high" else "⚠️"
    alert_text = "超过上限" if alert_type == "high" else "低于下限"
    message = f"""
{alert_emoji} **大额兑换提醒 ({alert_text})** {alert_emoji}

**代币**: {symbol}
**链**: Solana
**兑换金额**: ${amount_usd:,.2f}
**阈值范围**: ${THRESHOLD_LOW:,.2f} ~ ${THRESHOLD_HIGH:,.2f}

📊 **OKX 交易所买一价格**:
• USDC/USDT: {prices.get('USDC_USDT', 'N/A')}
• USDG/USDT: {prices.get('USDG_USDT', 'N/A')}
• PYUSD/USDT: {prices.get('PYUSD_USDT', 'N/A')}

📝 **交易详情**:
• 价格: ${trade_info.get('price', 'N/A')}
• 数量: {trade_info.get('amount', 'N/A')}
• 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
• 哈希: {trade_info.get('tx_hash', 'N/A')}
"""
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        print(f"发送消息失败: {e}")

# ============================================================
#  WebSocket 回调函数
# ============================================================
def on_message(ws, message):
    try:
        data = json.loads(message)
        if "data" in data:
            for item in data.get("data", []):
                chain_idx = item.get("chainIndex", "")
                if chain_idx != SOLANA_CHAIN_INDEX:
                    continue

                changed_info = item.get("changedTokenInfo", {})
                token_address = changed_info.get("tokenContractAddress", "")
                amount = float(changed_info.get("amount", 0))
                price = float(item.get("price", 0))
                volume = float(item.get("volume", 0))
                tx_hash = item.get("txHashUrl", "")
                trade_type = item.get("type", "")

                if trade_type.lower() != "sell":
                    continue

                symbol_name = None
                for name, addr in TOKENS.items():
                    if addr.lower() == token_address.lower():
                        symbol_name = name
                        break
                if not symbol_name:
                    continue

                # 判断是否超出阈值范围
                alert_type = None
                if volume >= THRESHOLD_HIGH:
                    alert_type = "high"
                elif volume <= THRESHOLD_LOW:
                    alert_type = "low"
                else:
                    continue

                prices = get_all_prices()
                trade_info = {"amount": amount, "price": price, "tx_hash": tx_hash}
                # 使用 asyncio.create_task 异步发送，不阻塞
                asyncio.create_task(send_alert(symbol_name, volume, trade_info, prices, alert_type))
    except Exception as e:
        print(f"处理消息错误: {e}")

def on_error(ws, error):
    print(f"WebSocket 错误: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"WebSocket 已关闭: {close_status_code} - {close_msg}")
    time.sleep(5)
    # 重连
    start_websocket()

def on_open(ws):
    subscribe_msg = {
        "op": "subscribe",
        "args": [{
            "channel": "dex-market-trades",
            "chainIndex": SOLANA_CHAIN_INDEX
        }]
    }
    ws.send(json.dumps(subscribe_msg))
    print(f"已订阅 Solana 链 (chainIndex: {SOLANA_CHAIN_INDEX})")

    # 发送启动通知（同步方式，因为 on_open 在非异步环境中）
    try:
        # 用 asyncio.run 只执行一次，不影响后续事件循环
        asyncio.run(bot.send_message(
            chat_id=CHAT_ID,
            text=f"🤖 OKX DEX 监控 Bot 启动\n监控 Solana 链 USDG/PYUSD\n阈值: ${THRESHOLD_LOW:,.2f} ~ ${THRESHOLD_HIGH:,.2f}"
        ))
    except Exception as e:
        print(f"启动通知失败: {e}")

# ============================================================
#  启动 WebSocket（关键：启用自动心跳）
# ============================================================
def start_websocket():
    ws = websocket.WebSocketApp(
        DEX_WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        # 以下两个参数是修复 4004 错误的关键
        ping_interval=20,   # 每 20 秒自动发送 Ping 帧
        ping_timeout=10     # 等待 Pong 响应的超时时间（秒）
    )
    ws.run_forever()

# ============================================================
#  主程序
# ============================================================
if __name__ == "__main__":
    print(f"🤖 OKX DEX 监控 Bot 启动...")
    print(f"阈值范围: ${THRESHOLD_LOW:,.2f} ~ ${THRESHOLD_HIGH:,.2f}")
    start_websocket()
