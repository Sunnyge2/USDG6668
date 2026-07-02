import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import requests
from telegram import Bot

load_dotenv()

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

tg_bot = Bot(token=TG_BOT_TOKEN)

async def send_test_alert():
    alert = f"""🚨 测试提醒 - Bot 正常工作

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
10000 USDG 可兑换 ≈ 10012.45 USDC
10000 PYUSD 可兑换 ≈ 9997.80 USDC

OKX CEX 买一价: 正常获取中...
"""
    await tg_bot.send_message(chat_id=TG_CHAT_ID, text=alert)
    print("✅ 已发送测试提醒")

async def main():
    print("✅ 测试模式启动，每 30 秒发送一次提醒")
    while True:
        await send_test_alert()
        await asyncio.sleep(30)   # 每30秒发一次

if __name__ == "__main__":
    asyncio.run(main())
