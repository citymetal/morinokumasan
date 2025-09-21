import os
from typing import List, Tuple, Optional
from slack_sdk import WebClient
from slack_sdk.webhook import WebhookClient
from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse
import json

load_dotenv()

app = FastAPI()

# Slackメッセージ用ブロック生成
def _blocks_for_options(options: List[Tuple[int, str]]):
    blocks = []
    for oid, label in options:
        blocks.extend([
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{label}*"}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "○ 参加"},
                        "style": "primary",
                        "action_id": f"vote|{oid}|yes",
                        "value": f"{oid}"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "× 不可"},
                        "style": "danger",
                        "action_id": f"vote|{oid}|no",
                        "value": f"{oid}"
                    }
                ]
            },
            {"type": "divider"}
        ])
    return blocks

# 候補送信
def send_candidates(text: str, options: List[Tuple[int, str]], channel: Optional[str] = None) -> Optional[str]:
    webhook_url = os.getenv("SLACK_INCOMING_WEBHOOK_URL", "")
    bot_token = os.getenv("SLACK_BOT_TOKEN", "")
    blocks = _blocks_for_options(options)

    if bot_token:
        client = WebClient(token=bot_token)
        resp = client.chat_postMessage(
            channel=channel or os.getenv("SLACK_CHANNEL", "C09FX3UP8H1"),
            text=text,
            blocks=blocks
        )
        print(resp)
        if resp.get("ok"):
            return resp.get("ts")
        return None
    elif webhook_url:
        wh = WebhookClient(webhook_url)
        wh.send(text=text, blocks=blocks)
        return None
    else:
        raise RuntimeError("Slack credentials not provided. Set SLACK_BOT_TOKEN or SLACK_INCOMING_WEBHOOK_URL.")

# 決定通知
def send_final_decision(message: str, channel: Optional[str] = None):
    webhook_url = os.getenv("SLACK_INCOMING_WEBHOOK_URL", "")
    bot_token = os.getenv("SLACK_BOT_TOKEN", "")
    if bot_token:
        client = WebClient(token=bot_token)
        client.chat_postMessage(channel=channel or os.getenv("SLACK_CHANNEL", "C09FX3UP8H1"), text=message)
    elif webhook_url:
        WebhookClient(webhook_url).send(text=message)
    else:
        raise RuntimeError("Slack credentials not provided. Set SLACK_BOT_TOKEN or SLACK_INCOMING_WEBHOOK_URL.")

# Slackのインタラクティブイベント受信
@app.post("/slack/interactivity")
async def slack_interactivity(payload: str = Form(...)):
    print("📦 payload:", payload)
    try:
        data = json.loads(payload)
        print("✅ 受信したインタラクティブイベント:", data)
        return JSONResponse(content={"text": "応答を受け取りました"})
    except Exception as e:
        print("❌ エラー発生:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

# テスト用起動（uvicornでは実行されない）
if __name__ == "__main__":
    options = [(1, "10月1日 10:00"), (2, "10月2日 14:00")]
    send_candidates("候補日を選んでください", options)
