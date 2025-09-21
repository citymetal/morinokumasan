from __future__ import annotations
import hashlib
import hmac
import os
import time
import urllib.parse

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

import db

load_dotenv()

SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")

app = FastAPI(title="Slack Webhook for Scheduling App")


def verify_slack_request(timestamp: str, signature: str, body: bytes) -> None:
    if not SIGNING_SECRET:
        raise HTTPException(status_code=500, detail="Signing secret 未設定")

    # リプレイ攻撃対策（5分）
    try:
        ts = int(timestamp)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timestamp")

    if abs(time.time() - ts) > 60 * 5:
        raise HTTPException(status_code=400, detail="Timestamp out of range")

    basestring = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
    my_sig = "v0=" + hmac.new(
        SIGNING_SECRET.encode("utf-8"),
        basestring,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(my_sig, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")


@app.post("/slack/webhook")
async def slack_webhook(request: Request):
    # Slackは application/x-www-form-urlencoded で payload=... を送る
    raw_body = await request.body()
    signature = request.headers.get("X-Slack-Signature", "")
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
    verify_slack_request(timestamp, signature, raw_body)

    form = urllib.parse.parse_qs(raw_body.decode("utf-8"))
    payload_json = form.get("payload", [None])[0]
    if not payload_json:
        raise HTTPException(status_code=400, detail="No payload")

    import json
    payload = json.loads(payload_json)

    # URL verification（省略）や block_actions のみ想定
    if payload.get("type") != "block_actions":
        return PlainTextResponse("ok")

    user_id = payload.get("user", {}).get("id")
    actions = payload.get("actions", [])
    if not user_id or not actions:
        raise HTTPException(status_code=400, detail="Invalid payload")

    value = actions[0].get("value", "")  # 例: "12:ok" or "12:ng"
    try:
        option_str, status = value.split(":", 1)
        option_id = int(option_str)
        status = status if status in ("ok", "ng") else "ng"
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid action value")

    # DBへ保存（UPSERT）
    db.save_vote(option_id=option_id, user=user_id, status=status)

    # Slack には 200 を即返す（3秒以内）
    return PlainTextResponse("ok")


@app.get("/healthz")
async def healthz():
    return PlainTextResponse("ok")
