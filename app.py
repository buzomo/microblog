from flask import Flask, request, jsonify, render_template, make_response
import os
import psycopg2
from psycopg2.extras import DictCursor
import secrets
import re

app = Flask(__name__)

# Neonデータベース接続設定
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://user:password@localhost:5432/dbname"
)
TABLE_NAME_POSTS = "posts_2b6a83"
TABLE_NAME_FREQ_WORDS = "freq_words_7bf883"


# データベース接続関数
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


# テーブル作成関数（投稿用）
def create_posts_table():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME_POSTS} (
                id SERIAL PRIMARY KEY,
                token VARCHAR(64) NOT NULL,
                content TEXT NOT NULL,
                is_highlight BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error creating posts table: {e}")
        raise


# テーブル作成関数（頻出ワード用）
def create_freq_words_table():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME_FREQ_WORDS} (
                id SERIAL PRIMARY KEY,
                token VARCHAR(64) NOT NULL,
                word TEXT NOT NULL
            )
            """
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error creating freq_words table: {e}")
        raise


# アプリケーション起動時にテーブルを作成
create_posts_table()
create_freq_words_table()


# トークン生成関数
def generate_token():
    return secrets.token_hex(32)


# トークン取得関数
def get_token():
    token = request.args.get("token")
    if token:
        return token
    token = request.cookies.get("token")
    if not token:
        token = generate_token()
    return token


# 頻出ワード一覧取得
@app.route("/freq_words", methods=["GET"])
def get_freq_words():
    try:
        token = get_token()
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute(
            f"SELECT * FROM {TABLE_NAME_FREQ_WORDS} WHERE token = %s ORDER BY id DESC",
            (token,),
        )
        words = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify([dict(word) for word in words])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 頻出ワード追加
@app.route("/freq_words", methods=["POST"])
def add_freq_word():
    try:
        token = get_token()
        word = request.json.get("word", "")
        if not word:
            return jsonify({"status": "error", "message": "Word is empty"}), 400
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO {TABLE_NAME_FREQ_WORDS} (token, word) VALUES (%s, %s)",
            (token, word),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 検索関数（部分一致、ひらがな⇄カタカナ、半角⇄全角、大文字⇄小文字を吸収）
def search_posts(token, query):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        def kana_convert(s):
            return re.sub(r"[ァ-ヴ]", lambda m: chr(ord(m.group(0)) - 0x60), s)

        def width_convert(s):
            return re.sub(
                r"[Ａ-Ｚａ-ｚ０-９]", lambda m: chr(ord(m.group(0)) - 0xFEE0), s
            )

        def case_convert(s):
            return s.lower()

        converted_query = f"%{kana_convert(width_convert(case_convert(query))) }%"
        cursor.execute(
            f"SELECT * FROM {TABLE_NAME_POSTS} WHERE token = %s AND LOWER(content) LIKE LOWER(%s) ORDER BY created_at DESC",
            (token, converted_query),
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
            f"INSERT INTO {TABLE_NAME_POSTS} (token, content) VALUES (%s, %s)",
            (token, content),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error adding post: {e}")
        raise


# メインページ
@app.route("/")
def index():
    token = get_token()
    resp = make_response(render_template("index.html"))
    resp.set_cookie("token", token, max_age=60 * 60 * 24 * 365)
    return resp


@app.route("/stats")
def stats():
    resp = make_response(render_template("stats.html"))
    return resp


# 検索API
@app.route("/search", methods=["GET"])
def search():
    try:
        token = get_token()
        query = request.args.get("q", "")
        posts = search_posts(token, query)
        return jsonify([dict(post) for post in posts])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 投稿API
@app.route("/post", methods=["POST"])
def post():
    try:
        token = get_token()
        content = request.json.get("content", "")
        if content:
            add_post(token, content)
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Content is empty"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ハイライトAPI
@app.route("/highlight", methods=["POST"])
def highlight():
    try:
        token = get_token()
        post_id = request.json.get("id")
        is_highlight = request.json.get("is_highlight", False)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE {TABLE_NAME_POSTS} SET is_highlight = %s WHERE id = %s AND token = %s",
            (is_highlight, post_id, token),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
