import os
from flask import Flask, request, jsonify, render_template, abort
from flask_cors import CORS
import pymysql
from dotenv import load_dotenv

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage

load_dotenv()

# ==========================================
# 0. 憑證設定
# ==========================================
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=BASE_DIR)
CORS(app)

# ==========================================
# 1. 資料庫設定
# ==========================================
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'), 
    'database': os.getenv('DB_NAME'),
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db_connection():
    return pymysql.connect(**DB_CONFIG)

# ==========================================
# 2. 前端網頁路由 (SPA 架構)
# ==========================================
@app.route('/')
@app.route('/login.html')
def index():
    return render_template('login.html')

@app.route('/app_core.html')
@app.route('/dashboard.html')
def serve_app_core():
    # 現在所有功能（大廳、遊戲、好友、獎盃）都已整合進單頁面應用 (SPA)
    return render_template('app_core.html')

# ==========================================
# 3. 核心 API：LIFF 登入身分驗證 & 自動分類綁定
# ==========================================
@app.route('/api/verify-liff', methods=['POST'])
def verify_liff():
    data = request.json
    uid = data.get('line_user_id')
    pic = data.get('picture_url')
    display_name = data.get('display_name')
    invite_uid = data.get('invite_uid')
    invite_type = data.get('invite_type', 'friend')
    
    if not uid:
        return jsonify({'success': False, 'message': '缺少必要參數 UID'}), 400

    # 建立關聯並寫入 relation_type
    inviter_name = "系統用戶"
    conn = get_db_connection()
    bound_success = False
    try:
        with conn.cursor() as cursor:
            # 獲取邀請人姓名
            if invite_uid:
                cursor.execute("SELECT Name FROM User_profiles WHERE User_id = %s", (invite_uid,))
                res = cursor.fetchone()
                if res: inviter_name = res['Name']

            cursor.execute("SELECT auth_id, user_id FROM line_accounts WHERE line_user_id = %s", (uid,))
            user = cursor.fetchone()
            
            if not user:
                # [自動註冊新用戶]
                # 1. 建立基礎個人檔案
                cursor.execute("INSERT INTO User_profiles (Name, Gender, Age, Weight) VALUES (%s, 'M', 65, 60)", (display_name,))
                db_user_id = cursor.lastrowid
                # 2. 建立 LINE 帳號連結
                cursor.execute("""
                    INSERT INTO line_accounts (line_user_id, user_id, display_name, picture_url, last_login)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (uid, db_user_id, display_name, pic))
            else:
                db_user_id = user['user_id']
                cursor.execute("""
                    UPDATE line_accounts 
                    SET picture_url = %s, display_name = %s, last_login = NOW() 
                    WHERE line_user_id = %s
                """, (pic, display_name, uid))
            
            # 建立關聯
            if invite_uid and str(invite_uid) != str(db_user_id):
                cursor.execute("""
                    INSERT INTO friendships (requester_id, receiver_id, status, relation_type, created_at, updated_at) 
                    VALUES (%s, %s, 'accepted', %s, NOW(), NOW())
                    ON DUPLICATE KEY UPDATE status = 'accepted', relation_type = %s, updated_at = NOW()
                """, (invite_uid, db_user_id, invite_type, invite_type))
                bound_success = True
                
            conn.commit()
            return jsonify({
                'success': True, 
                'dbUserId': db_user_id, 
                'bound_success': bound_success,
                'relation_type': invite_type if bound_success else 'none',
                'inviter_name': inviter_name
            })
            
    except Exception as e:
        print("資料庫操作發生錯誤:", str(e))
        return jsonify({'success': False, 'message': f"伺服器內部錯誤：{str(e)}"}), 500
    finally:
        conn.close()

# ==========================================
# 4. 交友系統核心 API 
# ==========================================
@app.route('/api/friends/list', methods=['GET'])
def get_friends_list():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify({'success': False, 'message': '缺少參數'}), 400
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 方案 A 修改：加入 User_profiles 進行 JOIN，優先讀取系統正式名稱
            cursor.execute("""
                SELECT la.user_id as id, COALESCE(up.Name, la.display_name, CONCAT('好友 ', la.user_id)) as name 
                FROM friendships f
                JOIN line_accounts la ON f.requester_id = la.user_id
                LEFT JOIN User_profiles up ON la.user_id = up.User_id
                WHERE f.receiver_id = %s AND f.status = 'pending'
            """, (user_id,))
            pending = cursor.fetchall()

            # 方案 A 修改：加入 User_profiles 進行 JOIN，優先讀取系統正式名稱
            cursor.execute("""
                SELECT la.user_id as id, COALESCE(up.Name, la.display_name, CONCAT('好友 ', la.user_id)) as name 
                FROM friendships f
                JOIN line_accounts la ON (la.user_id = f.receiver_id OR la.user_id = f.requester_id)
                LEFT JOIN User_profiles up ON la.user_id = up.User_id
                WHERE (f.requester_id = %s OR f.receiver_id = %s) 
                  AND f.status = 'accepted' 
                  AND f.relation_type = 'friend' 
                  AND la.user_id != %s
            """, (user_id, user_id, user_id))
            friends = cursor.fetchall()
            
            for f in friends: f['records'] = []
            return jsonify({'success': True, 'pending': pending, 'friends': friends})
    except Exception as e:
        print("Friends List Error:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/friends/request', methods=['POST'])
def send_friend_request():
    data = request.json
    req_id, rec_id = data.get('requester_id'), data.get('receiver_id')
    if str(req_id) == str(rec_id): return jsonify({'success': False, 'message': '不能加自己為好友！'}), 400
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM line_accounts WHERE user_id = %s", (rec_id,))
            if not cursor.fetchone(): return jsonify({'success': False, 'message': '找不到該號碼的用戶'}), 404
            
            cursor.execute("INSERT INTO friendships (requester_id, receiver_id, status, relation_type, created_at, updated_at) VALUES (%s, %s, 'pending', 'friend', NOW(), NOW()) ON DUPLICATE KEY UPDATE status = 'pending'", (req_id, rec_id))
            conn.commit()
            return jsonify({'success': True})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500
    finally: conn.close()

@app.route('/api/friends/accept', methods=['POST'])
def accept_friend_request():
    data = request.json
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE friendships SET status = 'accepted' WHERE requester_id = %s AND receiver_id = %s", (data.get('requester_id'), data.get('receiver_id')))
            conn.commit()
            return jsonify({'success': True})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500
    finally: conn.close()

@app.route('/api/friends/remove', methods=['POST'])
def remove_friend():
    data = request.json
    u1, u2 = data.get('user1_id'), data.get('user2_id')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM friendships WHERE (requester_id = %s AND receiver_id = %s) OR (requester_id = %s AND receiver_id = %s)", (u1, u2, u2, u1))
            conn.commit()
            return jsonify({'success': True})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500
    finally: conn.close()

# ==========================================
# 5. LINE Webhook 接收端點 & 長輩戰績自動推播給家屬
# ==========================================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try: handler.handle(body, signature)
    except InvalidSignatureError: abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event): pass

@app.route('/api/push_score', methods=['POST'])
def push_score_to_family():
    data = request.json
    elder_id = data.get('elder_id')
    game_name = data.get('game_name')
    score = data.get('score')
    angle = data.get('angle', 0)

    if not elder_id: return jsonify({"success": False, "message": "缺少長輩 ID"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 只推送給 relation_type = 'family' 的家屬
            cursor.execute("""
                SELECT la.line_user_id 
                FROM friendships f
                JOIN line_accounts la ON f.receiver_id = la.user_id
                WHERE f.requester_id = %s AND f.status = 'accepted' AND f.relation_type = 'family'
            """, (elder_id,))
            family_members = cursor.fetchall()

            if not family_members: return jsonify({"success": True, "message": "無綁定家屬"})

            message_content = {
                "type": "bubble",
                "header": { "type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "🏃 樂齡健康動 - 進度回報", "weight": "bold", "color": "#22c55e"}] },
                "body": {
                    "type": "box", "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": f"您的家人剛剛完成了：{game_name}", "wrap": True, "weight": "bold", "size": "md"},
                        {"type": "separator", "margin": "md"},
                        {"type": "box", "layout": "vertical", "margin": "md", "contents": [
                            {"type": "text", "text": f"得分：{score} 分", "size": "xl", "color": "#f59e0b", "weight": "bold"},
                            {"type": "text", "text": f"測量角度：{angle}°", "size": "sm", "color": "#9ca3af"}
                        ]}
                    ]
                }
            }

            for member in family_members:
                line_bot_api.push_message(member['line_user_id'], FlexSendMessage(alt_text=f"戰績回報：{score}分", contents=message_content))

            return jsonify({"success": True, "message": f"成功通知 {len(family_members)} 位家屬"})
    except Exception as e:
        print("推播發生錯誤:", str(e))
        return jsonify({"success": False, "message": "伺服器內部錯誤"}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)