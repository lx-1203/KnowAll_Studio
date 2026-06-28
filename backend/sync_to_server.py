"""
全自动数据同步：从本地 SQLite 读取数据，通过 API 上传到服务器。
用法: python sync_to_server.py
"""
import sqlite3, requests, os, time

SERVER = "http://xinghustudio.online"
API = f"{SERVER}/api/v1"
USERNAME = "testuser"
PASSWORD = "123456"

# ---- 1. 登录 ----
print("=" * 50)
print("Step 1: 登录服务器...")
r = requests.post(f"{API}/auth/login", json={"username": USERNAME, "password": PASSWORD})
if r.status_code != 200:
    print(f"登录失败: {r.status_code} {r.text}")
    exit(1)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"登录成功: user_id={r.json()['user']['id']}")

# ---- 2. 读取本地数据 ----
print("\nStep 2: 读取本地 SQLite...")
BASE = os.path.dirname(os.path.abspath(__file__))
db = sqlite3.connect(os.path.join(BASE, "data/app.db"))
db.row_factory = sqlite3.Row

# 获取文档数据
cur = db.cursor()
cur.execute("SELECT * FROM documents")
docs = [dict(r) for r in cur.fetchall()]
print(f"  文档: {len(docs)} 个")

cur.execute("SELECT * FROM question_bank")
questions = [dict(r) for r in cur.fetchall()]
print(f"  题库: {len(questions)} 题")

cur.execute("SELECT * FROM flashcards")
flashcards = [dict(r) for r in cur.fetchall()]
print(f"  闪卡: {len(flashcards)} 张")

cur.execute("SELECT * FROM decks")
decks = [dict(r) for r in cur.fetchall()]
print(f"  牌组: {len(decks)} 个")

cur.execute("SELECT * FROM knowledge_trees")
trees = [dict(r) for r in cur.fetchall()]
print(f"  知识树: {len(trees)} 个")

db.close()

# ---- 3. 上传文档 ----
print("\nStep 3: 上传文档...")
doc_id_map = {}  # old_id -> new_id
for doc in docs:
    local_path = doc.get("local_path")
    filename = doc.get("filename", "unknown")

    if local_path and os.path.exists(local_path):
        with open(local_path, "rb") as f:
            r = requests.post(f"{API}/documents/upload",
                            headers={"Authorization": f"Bearer {token}"},
                            files={"file": (filename, f)})
        if r.status_code in (200, 201):
            new_id = r.json().get("document_id")
            doc_id_map[doc["id"]] = new_id
            print(f"  上传成功: {filename} -> {new_id}")
        else:
            print(f"  上传失败: {filename} - {r.status_code} {r.text[:100]}")
    else:
        print(f"  文件不存在: {local_path}")

# ---- 4. 导入题库 ----
print("\nStep 4: 导入题库...")
if questions:
    # 先获取第一个文档的ID作为素材
    # 实际需要关联文档，这里批量保存
    batch_size = 10
    for i in range(0, len(questions), batch_size):
        batch = questions[i:i+batch_size]
        payload = {"questions": []}
        for q in batch:
            q_data = {
                "question_text": q.get("question_text", ""),
                "question_type": q.get("question_type", "single_choice"),
                "options": q.get("options"),
                "answer": q.get("answer", ""),
                "analysis": q.get("analysis", ""),
                "difficulty": q.get("difficulty", "medium"),
                "difficulty_score": q.get("difficulty_score", 0.5),
                "cognitive_level": q.get("cognitive_level", "L2_understand"),
            }
            # 尝试添加答案相关字段
            for k in ["option_a", "option_b", "option_c", "option_d", "option_e", "blanks"]:
                if k in q and q[k]:
                    q_data[k] = q[k]
            payload["questions"].append(q_data)

        try:
            r = requests.post(f"{API}/quiz/bank/save", json=payload, headers=headers)
            if r.status_code in (200, 201):
                print(f"  批次 {i//batch_size + 1}: {len(batch)} 题入库成功")
            else:
                print(f"  批次 {i//batch_size + 1}: 失败 {r.status_code} - {r.text[:150]}")
        except Exception as e:
            print(f"  批次 {i//batch_size + 1}: 异常 {e}")
    print(f"  题库总计导入完成")

# ---- 5. 导入闪卡 ----
print("\nStep 5: 导入闪卡...")
if flashcards and decks:
    # 根据 deck_id 分组
    by_deck = {}
    for fc in flashcards:
        did = fc.get("deck_id", "default")
        if did not in by_deck:
            by_deck[did] = []
        by_deck[did].append(fc)

    for deck_id, cards in by_deck.items():
        deck_name = next((d["name"] for d in decks if d["id"] == deck_id), "导入牌组")
        print(f"  牌组 '{deck_name}': {len(cards)} 张卡片")

        for i in range(0, len(cards), 20):
            batch = cards[i:i+20]
            payload = {
                "deck_name": deck_name,
                "cards": []
            }
            for fc in batch:
                payload["cards"].append({
                    "front": fc.get("front", ""),
                    "back": fc.get("back", ""),
                    "hint": fc.get("hint", ""),
                    "tags": fc.get("tags", ""),
                })

            try:
                r = requests.post(f"{API}/flashcards/generate", json=payload, headers=headers)
                if r.status_code in (200, 201):
                    print(f"    批次 {i//20 + 1}: {len(batch)} 张入库")
                else:
                    print(f"    批次失败: {r.status_code} - {r.text[:100]}")
            except Exception as e:
                print(f"    异常: {e}")

# ---- 完成 ----
print(f"\n{'='*50}")
print("同步完成! 访问 http://xinghustudio.online/ 查看")
print(f"账号: {USERNAME}  密码: {PASSWORD}")
