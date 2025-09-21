#ライブラリインポート
import streamlit as st
import pandas as pd
import json
import os
import datetime
import sqlite3

from typing import List, Tuple, Optional
from slack_sdk import WebClient
from slack_sdk.webhook import WebhookClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse

#関数のインポート
## がうらさんファイルのインポート
import db

# ======================================
# DB Part
# ======================================
DB_NAME = "schedule.db"

# ======================================
# Streamlit UI Part
# ======================================
db.init_db()
st.title("📅 Slack連携 日程調整アプリ")
tab1, tab2 = st.tabs(["投票の作成", "結果の確認・確定"])

#1つ目のタブの中身の設定
with tab1:
    st.header("新しい投票を作成")
    channel_id = st.text_input("投稿先のチャンネルID")
    st.info("""
    **チャンネルIDの取得方法:**
    1. Slackでチャンネル名を右クリック → 2. 「リンクをコピー」
    3. リンク末尾の `C` から始まる文字列を貼り付け
    """)
    title = st.text_input("投票タイトル", "次回のミーティング日程")
    
    st.subheader("候補日時を選択")
    
    #候補日時の選択処理
    if 'num_candidates' not in st.session_state:
        st.session_state.num_candidates = 2

    candidates = []
    for i in range(st.session_state.num_candidates):
        st.markdown('<style> hr { margin-top: 1px; margin-bottom: 1px; } </style>', unsafe_allow_html=True)
        st.markdown(f"**候補 {i+1}**")
        col1, col2 = st.columns(2)
        with col1:
            date_val = st.date_input("日付", datetime.date.today() + datetime.timedelta(days=i), key=f"date_{i}")
        with col2:
            time_val = st.time_input("時刻", datetime.time(10, 0), key=f"time_{i}", step=datetime.timedelta(minutes=30))
        candidates.append((i, datetime.datetime.combine(date_val, time_val).strftime('%Y/%m/%d(%a) %H:%M')))
    
    col_add, col_del = st.columns(2)
    with col_add:
        if st.button("＋ 候補を追加"):
            st.session_state.num_candidates += 1
            st.rerun()
    with col_del:
        if st.session_state.num_candidates > 2:
            if st.button("－ 最後の候補を削除"):
                st.session_state.num_candidates -= 1
                st.rerun()

    if st.button("この内容でSlackに投票を投稿", type="primary"):
        try:
            # DBに会議を登録
            meeting_id = db.create_meeting(title, channel_id)

            # 各候補をDBに保存
            for _, cand_text in candidates:
                db.add_option(cand_text, meeting_id)

             # 保存された候補を確認表示
            st.subheader("保存された候補一覧（DB確認用）")
            saved_options = db.list_options(meeting_id)
            for oid, text in saved_options:
                st.write(f"- ID={oid}, 候補日時={text}")

            # Slack送信
            send_candidates(
                text=title,
                options=candidates,
                channel=channel_id if channel_id else None
            )
            st.success(f"✅ Slackに投票を投稿しました！（meeting_id={meeting_id}）")
        except Exception as e:
            st.error(f"❌ エラーが発生しました: {e}")

#2つ目のタブの中身の設定
with tab2:
    st.header("投票結果の確認")
    meeting_id = st.text_input("会議URL")

    st.subheader("現在の投票状況（ダミーデータ）")

    dummy_results = {
        "2025/09/22(月) 10:00": {
            "参加": 3,
            "不参加": 1
        },
        "2025/09/23(火) 15:30": {
            "参加": 5,
            "不参加": 0
        },
        "2025/09/24(水) 11:00": {
            "参加": 2,
            "不参加": 3
        }
    }
    
    df = pd.DataFrame.from_dict(dummy_results, orient='index')
    df.index.name = "候補日時"
    st.dataframe(df)

    st.subheader("確定候補の選択")
    final_candidate = st.radio(
        "最終確定する日程を選択してください。",
        options=list(dummy_results.keys()),
        index=None
    )
    
    if final_candidate:
        st.info(f"確定日程: **{final_candidate}**")

    st.button("この内容でSlackに確定を通知", type="primary")