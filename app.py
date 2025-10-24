import os
from flask import Flask, request, jsonify, render_template, make_response
import psycopg2
from psycopg2.extras import DictCursor
import secrets
import re
from datetime import datetime

app = Flask(__name__)

# Neonデータベース接続設定（環境変数から読み込み）
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/dbname")
TABLE_NAME = "posts-2b6a83"

# データベース接続関数
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# テーブル作成関数
def create_table():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id SERIAL PRIMARY KEY,
                token VARCHAR(64) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        cursor.close()
        conn.close()
        print("Table created or already exists.")
    except Exception as e:
        print(f"Error creating table: {e}")
        raise

# アプリケーション起動時にテーブルを作成
create_table()

# トークン生成関数
def generate_token():
    return secrets.token_hex(32)

# トークン取得関数
def get_token():
    token = request.cookies.get("token")
    if not token:
        token = generate_token()
    return token

# 検索関数（部分一致、ひらがな⇄カタカナ、半角⇄全角、大文字⇄小文字を吸収）
def search_posts(token, query):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        # カタカナ⇄ひらがな変換
        def kana_convert(s):
            return re.sub(r'[ァ-ヴ]', lambda m: chr(ord(m.group(0)) - 0x60), s)

        # 全角⇄半角変換
        def width_convert(s):
            return re.sub(r'[Ａ-Ｚａ-ｚ０-９]', lambda m: chr(ord(m.group(0)) - 0xFEE0), s)

        # 大文字⇄小文字変換
        def case_convert(s):
            return s.lower()

        # 検索クエリ生成
        converted_query = f"%{kana_convert(width_convert(case_convert(query)))}%"
        cursor.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE token = %s AND LOWER(content) LIKE LOWER(%s) ORDER BY created_at DESC",
            (token, converted_query)
        )
        posts = cursor.fetchall()
        cursor.close()
        conn.close()
        return posts
    except Exception as e:
        print(f"Error searching posts: {e}")
        raise

# 投稿関数
def add_post(token, content):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO {TABLE_NAME} (token, content) VALUES (%s, %s)",
            (token, content)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error adding post: {e}")
        raise

# メインページ
@app.route('/')
def index():
    token = get_token()
    resp = make_response(render_template('index.html'))
    resp.set_cookie('token', token, max_age=60*60*24*365)
    return resp

# 検索API
@app.route('/search', methods=['GET'])
def search():
    try:
        token = get_token()
        query = request.args.get('q', '')
        posts = search_posts(token, query)
        return jsonify([dict(post) for post in posts])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 投稿API
@app.route('/post', methods=['POST'])
def post():
    try:
        token = get_token()
        content = request.json.get('content', '')
        if content:
            add_post(token, content)
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Content is empty'}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# アプリケーション実行
if __name__ == '__main__':
    app.run(debug=True)
