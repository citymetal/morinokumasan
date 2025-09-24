from slack_client import get_user_display_name
import sqlite3
import datetime as dt

DB_NAME = "schedule.db"

def init_db():
    """データベースを初期化し、全テーブルを作成する"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # ★修正点1: meetingsテーブルにchannel_idを追加
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            channel_id TEXT NOT NULL, -- 投票先のSlackチャンネルID
            created_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            meeting_id INTEGER,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            option_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            status TEXT NOT NULL, -- 'ok' or 'ng'
            created_at TEXT NOT NULL,
            FOREIGN KEY (option_id) REFERENCES options(id),
            UNIQUE (option_id, user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS final_selection (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            option_id INTEGER NOT NULL,
            decided_at TEXT NOT NULL,
            meeting_id INTEGER NOT NULL, 
            FOREIGN KEY (option_id) REFERENCES options(id),
            FOREIGN KEY (meeting_id) REFERENCES meetings(id),
            UNIQUE(meeting_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# --- 会議の作成 ---
# ★修正点1: channel_id を受け取るように変更
def create_meeting(title: str, channel_id: str) -> int:
    """新しい会議を作成し、そのIDを返す"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = dt.datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO meetings (title, channel_id, created_at) VALUES (?, ?, ?)",
        (title, channel_id, now)
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id
    
# --- 候補の追加と表示 ---
def add_option(text: str, meeting_id: int) -> int:
    """候補をDBに追加する"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = dt.datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO options (text, created_at, meeting_id) VALUES (?, ?, ?)",
        (text, now, meeting_id)
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def list_options(meeting_id: int) -> list:
    """指定された会議の候補をすべて取得する"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, text FROM options WHERE meeting_id = ? ORDER BY created_at",
        (meeting_id,)
    )
    options = cursor.fetchall()
    conn.close()
    return options

# --- 投票の記録 ---
def record_vote(option_id: int, user_id: str, user_name: str, status: str):
    """投票を記録する（同じ人が再度投票したら更新）"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = dt.datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO votes (option_id, user_id, user_name, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(option_id, user_id) DO UPDATE SET
        status = excluded.status, created_at = excluded.created_at
    """, (option_id, user_id, user_name, status, now))
    conn.commit()
    conn.close()

# --- 集計 ---
def tally_votes(meeting_id: int) -> list:
    """【人数集計用】各候補のOK/NG票を数える"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            o.id,
            o.text,
            SUM(CASE WHEN v.status = 'ok' THEN 1 ELSE 0 END) as ok_count,
            SUM(CASE WHEN v.status = 'ng' THEN 1 ELSE 0 END) as ng_count
        FROM options o
        LEFT JOIN votes v ON o.id = v.option_id
        WHERE o.meeting_id = ?
        GROUP BY o.id, o.text
        ORDER BY ok_count DESC, ng_count ASC
    """, (meeting_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ★新機能: 要件④を満たすための新しい関数
def get_vote_details(meeting_id: int) -> dict:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    options = list_options(meeting_id)
    details = {}
    for option_id, option_text in options:
        cursor.execute("""
            SELECT user_id, status FROM votes
            WHERE option_id = ?
        """, (option_id,))
        votes = cursor.fetchall()
        details[option_text] = {
            'ok_users': [get_user_display_name(v['user_id']) for v in votes if v['status'] == 'ok'],
            'ng_users': [get_user_display_name(v['user_id']) for v in votes if v['status'] == 'ng']
        }
    conn.close()
    return details
def set_final_selection(option_id: int, meeting_id: int):
    # ... (変更なし)
    pass
def get_final_selection(meeting_id: int):
    # ... (変更なし)
    pass
