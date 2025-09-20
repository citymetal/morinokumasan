#ライブラリインポート
import streamlit as st
import pandas as pd
import json
import os
import datetime

from typing import List, Tuple, Optional
from slack_sdk import WebClient
from slack_sdk.webhook import WebhookClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse

# ======================================
# Streamlit UI Part
# ======================================
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
        candidates.append(datetime.datetime.combine(date_val, time_val).strftime('%Y/%m/%d(%a) %H:%M'))
    
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

    st.button("この内容でSlackに投票を投稿", type="primary")

#2つ目のタブの中身の設定
with tab2:
    meeting_id = st.text_input("会議URL")
    st.button("この内容でSlackに確定を通知", type="primary")