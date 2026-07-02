import os
import json
import time
import threading
import requests
import websocket
from datetime import datetime

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

THRESHOLD_HIGH = float(os.environ.get("THRESHOLD_HIGH", "10000"))
THRESHOLD_LOW = float(os.environ.get("THRESHOLD_LOW", "9998"))

# 监控的代币（仅 Solana）
TOKENS = {
    "USDG": "2u1tszSeqZ3qBWF3uNGPFc8TzMk2tdiwknnRMWGWjGWH",
    "PYUSD": "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo"
}

SOLANA_CHAIN_INDEX = "501"
DEX_WS_URL = "wss://wsdex.okx.com/ws/v6/dex"
OKX_API_URL = "https://www.okx.com"

# ============================================================
#  发送 Telegram 消息（同步，使用 requests）
# ============================================================
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"Telegram API 错误: {resp.status_code} - {resp.text}")
        return resp
    except Exception as e:
        print(f"发送 Telegram 消息失败: {e}")
        return None

# ============================================================
#  获取交易所买一价格
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
#  发送提醒
# ============================================================
def send_alert(symbol, amount_usd, trade_info, prices, alert_type):
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
    send_telegram_message(message)

# ============================================================
#  心跳线程（发送应用层 ping）
# ============================================================
def send_ping(ws):
    while True:
        time.sleep(20)
        try:
            ws.send(json.dumps({"op": "ping"}))
            print("发送 ping")
        except Exception as e:
            print(f"发送 ping 失败: {e}")
            break

# ============================================================
#  WebSocket 回调
# ============================================================
def on_message(ws, message):
    try:
        data = json.loads(message)
        if data.get("op") == "pong":
            return
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
                alert_type = None
                if volume >= THRESHOLD_HIGH:
                    alert_type = "high"
                elif volume <= THRESHOLD_LOW:
                    alert_type = "low"
                else:
                    continue
                prices = get_all_prices()
                trade_info = {"amount": amount, "price": price, "tx_hash": tx_hash}
                send_alert(symbol_name, volume, trade_info, prices, alert_type)
    except Exception as e:
        print(f"处理消息错误: {e}")

def on_error(ws, error):
    print(f"WebSocket 错误: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"WebSocket 已关闭: {close_status_code} - {close_msg}")
    time.sleep(5)
    start_websocket()

def on_open(ws):
    # 启动心跳线程
    threading.Thread(target=send_ping, args=(ws,), daemon=True).start()
    # 订阅 Solana 链交易数据
    subscribe_msg = {
        "op": "subscribe",
        "args": [{
            "channel": "dex-market-trades",
            "chainIndex": SOLANA_CHAIN_INDEX
        }]
    }
    ws.send(json.dumps(subscribe_msg))
    print(f"已订阅 Solana 链 (chainIndex: {SOLANA_CHAIN_INDEX})")
    # 发送启动通知（同步）
    send_telegram_message(
        f"🤖 OKX DEX 监控 Bot 启动\n监控 Solana 链 USDG/PYUSD\n阈值: ${THRESHOLD_LOW:,.2f} ~ ${THRESHOLD_HIGH:,.2f}"
    )

def start_websocket():
    ws = websocket.WebSocketApp(
        DEX_WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

if __name__ == "__main__":
    print(f"🤖 OKX DEX 监控 Bot 启动...")
    print(f"阈值范围: ${THRESHOLD_LOW:,.2f} ~ ${THRESHOLD_HIGH:,.2f}")
    start_websocket()
