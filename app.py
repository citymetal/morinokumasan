#ライブラリインポート
import streamlit as st
import pandas as pd
import json
import os
import datetime
import sqlite3

from typing import List, Tuple, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse

## TASさんファイルのインポート
import slack_client

## がうらさんファイルのインポート
import db

## しんしんさんファイルのインポート
import slack_webhook

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
            slack_client.send_candidates(
                text=title,
                options=db.list_options(meeting_id),  # DBに保存した候補を渡すのがベター
                channel=channel_id if channel_id else None
            )
            st.success(f"✅ Slackに投票を投稿しました！（meeting_id={meeting_id}）")
        except Exception as e:
            st.error(f"❌ エラーが発生しました: {e}")

#2つ目のタブの中身の設定
with tab2:
    st.header("投票結果の確認")
    meeting_id = st.text_input("会議URL（または会議ID）")

    st.subheader("現在の投票状況")

    if meeting_id:
        try:
            results = db.tally_votes(int(meeting_id))  # 集計結果を取得
            if results:
                df = pd.DataFrame(
                    [(text, ok, ng) for _, text, ok, ng in results],
                    columns=["候補日時", "参加", "不参加"]
                )
                st.dataframe(df.set_index("候補日時"))

                # 詳細も表示するならこちら
                details = db.get_vote_details(int(meeting_id))
                st.subheader("投票詳細（誰が参加/不参加か）")
                st.json(details)

                st.subheader("確定候補の選択")
                
                df = pd.DataFrame(
                    [(text, ok, ng) for _, text, ok, ng in results],
                    columns=["候補日時", "参加", "不参加"]
                )
                
                df.set_index("候補日時", inplace=True)  # インデックスを候補日時に変更

                option_texts = df.index.tolist()  # これで候補日時のリストになる

                final_candidate = st.radio(
                    "最終確定する日程を選択してください。",
                    options=option_texts,
                    index=None
                )

                if final_candidate:
                    st.info(f"確定日程: **{final_candidate}**")

                if st.button("この内容でSlackに確定を通知", type="primary"):
                    try:
                        slack_client.send_final_decision(
                            f"📣 会議日程が決定しました：*{final_candidate}* です！",
                            channel=channel_id
                        )
                        st.success("Slackに確定日程を通知しました！")
                    except Exception as e:
                        st.error(f"Slack通知でエラー: {e}")

            else:
                st.info("まだ投票結果がありません。")

        except Exception as e:
            st.error(f"❌ 投票状況の取得に失敗しました: {e}")
    else:
        st.info("会議IDを入力してください。")
