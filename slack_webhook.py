from __future__ import annotations
import hashlib
import hmac
import os
import time
import urllib.parse
import json

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

import db  # ← db.py をそのまま利用

load_dotenv()

SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")

app = FastAPI(title="Slack Webhook for Scheduling App")


def verify_slack_request(timestamp: str, signature: str, body: bytes) -> None:
    if not SIGNING_SECRET:
        raise HTTPException(status_code=500, detail="Signing secret 未設定")

    # リプレイ攻撃対策（±5分）
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
    """
    SlackのインタラクティブなBlock Actionsを受け取り、
    例: action.value = "12:ok" / "12:ng" を votes にUPSERTする。
    """
    raw_body = await request.body()

    # 署名検証
    signature = request.headers.get("X-Slack-Signature", "")
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
    verify_slack_request(timestamp, signature, raw_body)

    # Slackは application/x-www-form-urlencoded で payload=... を送る
    form = urllib.parse.parse_qs(raw_body.decode("utf-8"))
    payload_json = form.get("payload", [None])[0]
    if not payload_json:
        raise HTTPException(status_code=400, detail="No payload")

    payload = json.loads(payload_json)

    # URL verification などは素通し。ここでは block_actions のみ想定
    if payload.get("type") != "block_actions":
        return PlainTextResponse("ok")

    # ユーザー情報（user_id と user_nameの両方を確保）
    user = payload.get("user", {}) or {}
    user_id = user.get("id")
    # payloadの仕様差異に備えて複数キーをフォールバック
    user_name = user.get("username") or user.get("name") or user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid payload: no user")

    # 最初のアクションだけを見る（必要に応じて複数対応可）
    actions = payload.get("actions", [])
    if not actions:
        raise HTTPException(status_code=400, detail="Invalid payload: no actions")

    value = actions[0].get("value", "")  # 例: "12:ok" or "12:ng"
    try:
        option_str, status = value.split(":", 1)
        option_id = int(option_str)
        status = status if status in ("ok", "ng") else "ng"
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid action value")

    # --- DBへ保存（db.pyのAPIに合わせる）---
    # db.pyの関数は record_vote(option_id, user_id, user_name, status)
    db.record_vote(option_id=option_id, user_id=user_id, user_name=user_name, status=status)

    # Slackには素早く200を返す（3秒以内）
    return PlainTextResponse("ok")


@app.get("/healthz")
async def healthz():
    return PlainTextResponse("ok")

from slack_client import router as slack_client_router
app.include_router(slack_client_router)

