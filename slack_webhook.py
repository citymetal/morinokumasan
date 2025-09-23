# slack_webhook.py
from __future__ import annotations

import os
import time
import hmac
import hashlib
import json
from typing import Any, Dict, Optional, Tuple

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
from slack_sdk import WebClient

import db  # 既存の db.py を利用（record_vote など）

# -----------------------
# 環境変数のロード
# -----------------------
load_dotenv()
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")

app = FastAPI(title="Slack Webhook for Voting")

# -----------------------
# Slack 署名検証
# -----------------------
def _verify_slack_signature(headers: Dict[str, str], body: bytes) -> None:
    if not SLACK_SIGNING_SECRET:
        # セキュリティのため、本番では必須。未設定なら警告だけ出して通す。
        return
    timestamp = headers.get("X-Slack-Request-Timestamp")
    slack_sig = headers.get("X-Slack-Signature")
    if not timestamp or not slack_sig:
        raise HTTPException(status_code=401, detail="Missing Slack signature headers")
    # リプレイ攻撃対策（5分許容）
    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            raise HTTPException(status_code=401, detail="Stale Slack request")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp")

    basestring = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
    my_sig = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode("utf-8"),
        basestring,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(my_sig, slack_sig):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

# -----------------------
# display_name 解決
# -----------------------
def _resolve_display_name(user_id: str) -> Optional[str]:
    """
    Slackの user_id から display_name を取得（未設定時は real_name -> name にフォールバック）
    """
    if not SLACK_BOT_TOKEN:
        return None
    try:
        client = WebClient(token=SLACK_BOT_TOKEN)
        resp = client.users_info(user=user_id)  # 要 users:read
        user = (resp or {}).get("user", {}) or {}
        profile = user.get("profile", {}) or {}
        return (
            profile.get("display_name")
            or profile.get("real_name")
            or user.get("name")
        )
    except Exception:
        return None

# -----------------------
# アクションペイロードの解析
# -----------------------
def _extract_vote_from_payload(data: Dict[str, Any]) -> Tuple[int, str]:
    """
    payload(JSON) から (option_id, status) を抽出する。
    status は 'ok' or 'ng'
    """
    actions = data.get("actions") or []
    if actions:
        a0 = actions[0]
        # value に JSON を入れているパターン（例: {"option_id": 12, "status": "ok"}）
        val = a0.get("value")
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                oid = int(parsed.get("option_id"))
                status = str(parsed.get("status"))
                if status in ("ok", "ng"):
                    return oid, status
            except Exception:
                pass

        # action_id から推測（例: vote_ok_12 / vote:ng:12 など末尾の数字を option_id に）
        import re
        act_id = str(a0.get("action_id", ""))
        m = re.search(r"(\d+)\s*$", act_id)
        if m:
            oid = int(m.group(1))
            status = "ok" if "ok" in act_id else ("ng" if "ng" in act_id else "")
            if status in ("ok", "ng"):
                return oid, status

        # 選択肢メニュー系（selected_option.value に JSON）
        sel = a0.get("selected_option") or {}
        val = sel.get("value")
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                oid = int(parsed.get("option_id"))
                status = str(parsed.get("status"))
                if status in ("ok", "ng"):
                    return oid, status
            except Exception:
                pass

    raise HTTPException(status_code=400, detail="Could not parse option_id/status from payload")

# -----------------------
# ルーティング
# -----------------------
@app.post("/slack/interactivity")
async def slack_interactivity(request: Request):
    """
    Slackの「インタラクティブコンポーネント（ボタン等）」の受け口
    Content-Type: application/x-www-form-urlencoded
    フィールド: payload=<JSON文字列>
    """
    raw = await request.body()
    _verify_slack_signature(request.headers, raw)

    # フォーム解析
    form = await request.form()
    payload = form.get("payload")
    if not payload:
        raise HTTPException(status_code=400, detail="Missing payload")
    try:
        data = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload JSON")

    # ユーザーID
    user = (data.get("user") or {}) or (data.get("actor") or {})
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing user id")

    # display_name を解決（未設定・失敗時はフォールバック）
    display = _resolve_display_name(user_id)
    user_name = display or user.get("username") or user.get("name") or user_id

    # option_id / status の抽出
    option_id, status = _extract_vote_from_payload(data)

    # 投票を保存（db.py の既存関数を使用）
    db.record_vote(option_id=option_id, user_id=user_id, user_name=user_name, status=status)

    # Slack へは即時 200 を返す（3秒制限）
    return PlainTextResponse("ok")

@app.get("/healthz")
async def healthz():
    return PlainTextResponse("ok")
