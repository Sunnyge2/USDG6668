import os
import json
import time
import asyncio
import threading
import requests
import websocket
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode

# ============================================================
#  配置（从环境变量读取）
# ============================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
THRESHOLD = float(os.environ.get("THRESHOLD", "10000"))

# 代币合约地址
# USDG: https://www.coindesk.com 确认 [reference:2]
# PYUSD: https://paxos.com 确认 [reference:3]
TOKENS = {
    "USDG": {
        "ethereum": "0xe343167631d89b6ffc58b88d6b7fb0228795491d",
        "solana": "2u1tszSeqZ3qBWF3uNGPFc8TzMk2tdiwknnRMWGWjGWH"
    },
    "PYUSD": {
        "ethereum": "0x6c3ea9036406852006290770bedfcaba0e23a0e8",
        "solana": "2b1kV6DkPANxd5ixfnXcPjxmKwqijaYmCZfHsFu24GXo"
    }
}

CHAIN_INDEX = {"ethereum": "1", "solana": "501"}  # 1=Ethereum, 501=Solana [reference:4]

# OKX DEX WebSocket 地址 [reference:5][reference:6]
DEX_WS_URL = "wss://wsdex.okx.com/ws/v6/dex"

# OKX 交易所 API（获取买一价格）
OKX_API_URL = "https://www.okx.com"

# ============================================================
#  初始化 Telegram Bot
# ============================================================
# 在 token 使用前加检查
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    print("❌ 环境变量 TELEGRAM_TOKEN 未设置或为空！")
    print("请在 Railway 的 Variables 中添加 TELEGRAM_TOKEN=你的Token")
    exit(1)   # 直接退出，避免重复报错

CHAT_ID = os.environ.get("CHAT_ID")
if not CHAT_ID:
    print("❌ 环境变量 CHAT_ID 未设置或为空！")
    exit(1)

bot = Bot(token=TELEGRAM_TOKEN)
bot = Bot(token=TELEGRAM_TOKEN)

# ============================================================
#  获取交易所买一价格
# ============================================================
def get_bid_price(symbol):
    """获取指定交易对的买一价格"""
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
    """获取所有需要的买一价格"""
    return {
        "USDC_USDT": get_bid_price("USDC-USDT"),
        "USDG_USDT": get_bid_price("USDG-USDT"),
        "PYUSD_USDT": get_bid_price("PYUSD-USDT")
    }

# ============================================================
#  发送 Telegram 提醒
# ============================================================
async def send_alert(symbol, chain, amount_usd, trade_info, prices):
    """发送大额兑换提醒"""
    # 构建消息
    message = f"""
🚨 **大额兑换提醒** 🚨

**代币**: {symbol}
**链**: {chain}
**兑换金额**: ${amount_usd:,.2f}

📊 **交易所买一价格**:
• USDC/USDT: {prices.get('USDC_USDT', 'N/A')}
• USDG/USDT: {prices.get('USDG_USDT', 'N/A')}
• PYUSD/USDT: {prices.get('PYUSD_USDT', 'N/A')}

📝 **交易详情**:
• 价格: ${trade_info.get('price', 'N/A')}
• 数量: {trade_info.get('amount', 'N/A')}
• 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
• 哈希: {trade_info.get('tx_hash', 'N/A')}
"""
    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)

# ============================================================
#  WebSocket 消息处理
# ============================================================
def on_message(ws, message):
    """处理 WebSocket 推送的消息"""
    try:
        data = json.loads(message)
        
        # 检查是否是交易数据
        # OKX DEX 推送数据结构参考 [reference:7]
        if "data" in data:
            for item in data.get("data", []):
                # 获取交易信息
                chain_idx = item.get("chainIndex", "")
                changed_info = item.get("changedTokenInfo", {})
                token_symbol = changed_info.get("tokenSymbol", "")
                token_address = changed_info.get("tokenContractAddress", "")
                amount = float(changed_info.get("amount", 0))
                price = float(item.get("price", 0))
                volume = float(item.get("volume", 0))  # USD 价值 [reference:8]
                tx_hash = item.get("txHashUrl", "")
                trade_type = item.get("type", "")  # buy / sell [reference:9]

                # 只关注 sell（兑换出去）
                if trade_type.lower() != "sell":
                    continue

                # 检查是否是我们监控的代币
                monitored = False
                symbol_name = None
                for name, addresses in TOKENS.items():
                    for chain, addr in addresses.items():
                        if addr.lower() == token_address.lower():
                            monitored = True
                            symbol_name = name
                            break
                    if monitored:
                        break

                if not monitored:
                    continue

                # 检查是否超过阈值
                if volume >= THRESHOLD:
                    # 映射链索引到链名称
                    chain_map = {"1": "Ethereum", "501": "Solana"}
                    chain_name = chain_map.get(chain_idx, chain_idx)

                    # 获取交易所价格
                    prices = get_all_prices()

                    # 发送提醒（在异步环境中运行）
                    trade_info = {
                        "amount": amount,
                        "price": price,
                        "tx_hash": tx_hash
                    }
                    asyncio.run(send_alert(symbol_name, chain_name, volume, trade_info, prices))

    except Exception as e:
        print(f"处理消息错误: {e}")

def on_error(ws, error):
    print(f"WebSocket 错误: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"WebSocket 已关闭: {close_status_code} - {close_msg}")
    # 5秒后重连
    time.sleep(5)
    start_websocket()

def on_open(ws):
    """WebSocket 连接成功后的订阅"""
    # 订阅 Ethereum 和 Solana 的交易数据
    # 频道: dex-market-trades 或类似 [reference:10][reference:11]
    for chain in ["1", "501"]:
        # 订阅该链上所有代币的交易（或可指定具体代币）
        subscribe_msg = {
            "op": "subscribe",
            "args": [{
                "channel": "dex-market-trades",
                "chainIndex": chain
            }]
        }
        ws.send(json.dumps(subscribe_msg))
        print(f"已订阅链: {chain}")

    # 发送启动通知
    asyncio.run(bot.send_message(
        chat_id=CHAT_ID,
        text="🤖 OKX DEX 监控 Bot 已启动，正在监控 USDG 和 PYUSD 的大额兑换..."
    ))

# ============================================================
#  WebSocket 连接管理
# ============================================================
def start_websocket():
    """启动 WebSocket 连接"""
    ws = websocket.WebSocketApp(
        DEX_WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# ============================================================
#  主程序
# ============================================================
if __name__ == "__main__":
    print(f"🤖 OKX DEX 监控 Bot 启动... 阈值: ${THRESHOLD:,.2f}")
    start_websocket()
