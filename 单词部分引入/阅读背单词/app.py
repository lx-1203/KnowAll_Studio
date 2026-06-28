import hashlib
import json
import math
import re
import sqlite3
import os
import time
from collections import Counter
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

import jieba
import requests

app = Flask(__name__)

DEEPSEEK_API_KEY = "YOUR_DEEPSEEK_KEY_HERE"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

KNOW_THRESHOLD = 5          # 同一词出现 5 次才算掌握


def calc_max_new(cn_count):
    """新词上限：1000字→3, 5000字→7, 10000字→12"""
    if cn_count <= 1000:
        return 3
    elif cn_count <= 5000:
        return 3 + (cn_count - 1000) // 1000
    else:
        return 7 + (cn_count - 5000) // 1000

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "reading.db")


# ============================================================
# 数据库
# ============================================================
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            char_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversion_cache (
            cache_key TEXT PRIMARY KEY,
            result TEXT NOT NULL,
            vocabulary TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def get_user_articles():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, title, content, char_count, created_at FROM user_articles ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [
        {
            "id": f"u{r[0]}",
            "title": r[1],
            "content": r[2],
            "difficulty": 0,  # 用户文章无预设难度
            "tags": ["用户上传"],
            "source": "upload"
        }
        for r in rows
    ]


def save_user_article(title, content, char_count):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO user_articles (title, content, char_count, created_at) VALUES (?, ?, ?, ?)",
        (title, content, char_count, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


# ============================================================
# 内置文章库
# ============================================================
BUILTIN_ARTICLES = [
    {
        "id": 1, "title": "早晨的阳光", "difficulty": 1,
        "content": "今天早上，我打开窗户，看见太阳慢慢地升起来了。天空很蓝，有几朵白色的云。小鸟在树上唱歌，声音很好听。我喝了一杯水，吃了一些面包，然后去公园散步。公园里有很多人，有的在跑步，有的在做运动。我看见一个小孩子在放风筝，风筝飞得很高很高。这是一个美丽的早晨，让我感觉非常开心。",
        "tags": ["日常", "自然"], "source": "builtin"
    },
    {
        "id": 2, "title": "我的朋友小明", "difficulty": 1,
        "content": "我有一个好朋友，他的名字叫小明。他个子很高，眼睛很大，喜欢笑。我们经常一起学习，一起玩游戏。小明是一个好学生，他的成绩很好，特别是数学。他帮助我做作业，我帮助他学习英语。周末的时候，我们一起去图书馆看书，或者去操场踢足球。我很高兴有这样的朋友，我希望我们永远是朋友。",
        "tags": ["友谊", "日常"], "source": "builtin"
    },
    {
        "id": 3, "title": "城市和乡村", "difficulty": 1,
        "content": "城市很大，有很多高楼和汽车。人们每天都很忙，走在路上很快。乡村很安静，有绿色的山和干净的水。人们的生活很慢，但是很开心。城市里有很多商店和餐厅，我们可以买到很多东西。乡村里有新鲜的空气和美丽的风景。两种生活不同，但是都很好。",
        "tags": ["生活", "对比"], "source": "builtin"
    },
    {
        "id": 4, "title": "四季之美", "difficulty": 2,
        "content": "一年有四个季节：春天、夏天、秋天和冬天。春天到了，花儿开了，树木变绿了，天气变暖和了。夏天很热，人们喜欢去海边游泳，吃冰淇淋。秋天是收获的季节，树叶变成金色和红色，非常漂亮。冬天很冷，有时会下雪，孩子们喜欢堆雪人和打雪仗。每个季节都有自己的美丽，我都很喜欢。",
        "tags": ["自然", "季节"], "source": "builtin"
    },
    {
        "id": 5, "title": "健康的饮食习惯", "difficulty": 2,
        "content": "健康的生活需要良好的饮食习惯。首先，我们应该每天吃早餐，因为早餐给我们力量开始新的一天。其次，我们要多吃蔬菜和水果，少吃油炸食品和甜食。喝水也很重要，每天应该喝足够的水。另外，吃饭的时间要规律，不要吃得太快。好的习惯可以让我们更健康，更有精力去工作和学习。",
        "tags": ["健康", "生活"], "source": "builtin"
    },
    {
        "id": 6, "title": "旅行的意义", "difficulty": 2,
        "content": "很多人喜欢旅行。旅行可以让我们看到不同的风景，了解不同的文化，认识新的朋友。当你去一个新的地方，你会发现自己原来不知道的东西。也许是一种美食，也许是一种传统，也许是一个有趣的故事。旅行不只是走路和拍照，更重要的是用心去感受。每一次旅行都是一次成长的机会，让我们的世界变得更大。",
        "tags": ["旅行", "文化"], "source": "builtin"
    },
    {
        "id": 7, "title": "互联网改变生活", "difficulty": 2,
        "content": "互联网已经改变了我们的生活方式。过去，人们需要去商店买东西，现在可以在网上购物。过去，写信需要很长时间才能到达，现在发邮件只需要几秒钟。我们可以通过互联网学习新知识，看世界各地的新闻，和远方的朋友聊天。但是，互联网也有不好的地方，比如有些人花太多时间上网，忘记了真实的生活。我们要学会合理使用互联网。",
        "tags": ["科技", "社会"], "source": "builtin"
    },
    {
        "id": 8, "title": "坚持的力量", "difficulty": 3,
        "content": "在这个世界上，没有什么成功是容易得到的。每一个伟大的人背后，都有无数次的失败和坚持。坚持是一种品质，也是一种力量。当你遇到困难的时候，不要轻易放弃，因为成功可能就在下一个路口等着你。学习一门语言需要坚持，养成一个好习惯需要坚持，实现一个梦想更需要坚持。记住，今天的一小步，就是明天的一大步。",
        "tags": ["励志", "人生"], "source": "builtin"
    },
    {
        "id": 9, "title": "环境保护的紧迫性", "difficulty": 3,
        "content": "随着经济的发展，环境问题变得越来越严重。空气污染、水污染、土地污染，这些都威胁着我们的健康和未来。许多动物失去了它们的家园，一些物种甚至已经灭绝。我们每一个人都有责任保护环境。从小事做起，比如减少使用塑料袋，节约用水，多种树木。政府和企业也应该采取有效的措施，推动可持续发展。保护地球，就是保护我们自己。",
        "tags": ["环境", "社会"], "source": "builtin"
    },
    {
        "id": 10, "title": "人工智能的未来", "difficulty": 3,
        "content": "人工智能正在快速发展，它已经开始影响我们的工作和生活。人工智能可以帮助医生诊断疾病，帮助教师个性化教学，帮助农民提高粮食产量。但是，人工智能也带来了挑战和问题。很多人担心人工智能会取代人类的工作，也有人担心人工智能的安全性和伦理问题。未来，人类和人工智能应该是一种合作的关系，而不是对立的关系。我们要学会与人工智能共同发展。",
        "tags": ["科技", "未来"], "source": "builtin"
    },
]


def count_chinese_chars(text):
    return len(re.findall(r'[\u4e00-\u9fff]', text))


# ============================================================
# 高频词提取 + Prompt
# ============================================================

# 常见停用词（功能词，不替换）
STOP_WORDS = set("""
的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你
会 着 没有 看 好 自己 这 他 她 它 们 那 些 什么 怎么 哪 吗 呢
吧 啊 哦 嗯 但 而 因为 所以 如果 虽然 然后 可以 应该 已经 还
又 再 才 刚 便 对 从 跟 向 把 被 让 给 用 以 为 为了 关于
这个 那个 这些 那些 这样 那样 这样 那样 谁 几 多少
来 中 里 外 前 后 左 右 上 下 旁 边 时候 年 月 日 时 分
现在 今天 明天 昨天 这里 那里 哪里 怎么 怎样 怎么样
只是 还是 就是 不是 也是 真是 都是
一些 一点 有点 什么 这么 那么 怎么 怎样
其实 当然 虽然 但是 不过 而且 或者 然后 所以 因为 如果
可以 可能 应该 必须 需要 能够 希望 觉得 认为 知道 以为
开始 继续 一直 已经 曾经 正在 将要 马上 立刻 忽然 突然
起来 下来 出来 进去 回来 过去 过来 出去 上去 下去
一下 一会 一会儿 一下下 一下子 越来越
""".split())

# 常见姓氏（用于过滤人名）
SURNAMES = set("""
李 王 张 刘 陈 杨 赵 黄 周 吴 徐 孙 马 胡 朱 郭 何 林 高 罗 郑 梁 谢
宋 唐 许 邓 韩 冯 曹 曾 彭 肖 陆 顾 沈 苏 蒋 蔡 潘 丁 魏 薛 叶 阎
余 杜 戴 夏 钟 汪 田 任 姜 范 方 石 姚 谭 廖 邹 熊 金 邱 秦 江 史
""".split())

def is_likely_name(word):
    """判断是否像中文人名（2-3字，首字为常见姓氏）"""
    return 2 <= len(word) <= 3 and word[0] in SURNAMES


def pick_words(text, count, known_words):
    """从文本中选取 count 个最频繁的内容词"""
    known_cn = set(w["cn"] for w in known_words) if known_words else set()
    words = [
        w for w in jieba.cut(text)
        if len(w) >= 2
        and re.search(r'[\u4e00-\u9fff]', w)
        and w not in STOP_WORDS
        and w not in known_cn
        and not is_likely_name(w)
    ]
    freq = Counter(words)
    # 优先选出现 >= 2 次的词，不够的话降级到 >= 1 次
    candidates = [(w, c) for w, c in freq.most_common() if c >= 2]
    if len(candidates) < count:
        extra = [(w, c) for w, c in freq.most_common() if c == 1]
        candidates.extend(extra)
    selected = [w for w, _ in candidates[:count]]
    return selected


def build_prompt(text, known_words, target_words):
    known_list = "\n".join(
        f'  {w["cn"]} → {w["en"]}' for w in known_words[:200]
    ) if known_words else "（暂无）"
    new_list = "、".join(target_words) if target_words else "（无新词）"

    return f"""你是文本替换引擎。把中文文章中的指定词汇替换为英文。

【用户已掌握的词汇】（★ 每个出现都要换成英文，不限量）
{known_list}

【本次新学词汇】（仅 {len(target_words)} 个：{new_list}。前 1-2 次保留中文，第 2-3 次起全部替换为英文）

【文章】
{text}

【规则】
- 已知词汇：每个出现全部替换为英文，不计数量。
- 新词汇：仅 {len(target_words)} 个。每个词前 1-2 次保留中文，第 2-3 次起全部替换为英文。
- 英文之间空格分隔。英文与中文之间不加空格。注意时态单复数。
- 只输出替换后的纯文本，不要 JSON，不要任何标记。"""


def parse_streamed_vocab(result_text, target_words, known_words):
    """从结果文本提取英文词，匹配到新词列表（排除已知词）"""
    en_words = re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?(?: [a-zA-Z]+(?:'[a-zA-Z]+)?)*", result_text)
    known_en = set(w["en"].lower() for w in known_words) if known_words else set()
    seen = set()
    new_en = []
    for w in en_words:
        key = w.lower().strip()
        if key and key not in seen and key not in known_en:
            seen.add(key)
            new_en.append(w)
    vocab = []
    for i, tw in enumerate(target_words):
        if i < len(new_en):
            vocab.append({"cn": tw, "en": new_en[i]})
    return vocab


def clean_streamed_text(text):
    """去掉 <<>> 标记"""
    return re.sub(r'<<([^>]+)>>', r'\1', text)


def call_deepseek(text, known_words, target_words):
    """调用 LLM，返回 (result_text, all_vocabulary)"""
    system_prompt = build_prompt(text, known_words, target_words)
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"替换 {len(target_words)} 个新词和所有已知词。直接输出替换后的纯文本，不要任何标记符号。"},
        ],
        "temperature": 0.7, "max_tokens": 4096,
    }
    resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
    if not resp.ok:
        raise Exception(f"DeepSeek API {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    raw = data["choices"][0]["message"]["content"].strip()
    if raw.startswith("```"):
        raw = re.sub(r'^```\w*\n', '', raw)
        raw = re.sub(r'\n```$', '', raw)
    # 去标记（兼容 LLM 偶尔输出的标记）
    raw = clean_streamed_text(raw)

    # 用 jieba 分词后精确替换遗漏的词
    result, vocab = apply_replacements(raw, text, known_words, target_words)
    return result, vocab


def apply_replacements(result_text, original_text, known_words, target_words):
    """用 jieba 分词对比原文和结果，精确替换遗漏的词"""
    orig_words = list(jieba.cut(original_text))
    result_words = list(jieba.cut(result_text))

    # 建立词汇映射
    known_map = {w["cn"]: w["en"] for w in known_words}
    fallback = {
        "世界": "world", "太阳": "sun", "天空": "sky", "大海": "sea",
        "城市": "city", "朋友": "friend", "家庭": "family",
        "记忆": "memory", "忘记": "forget", "痛苦": "pain", "幸福": "happiness",
        "美丽": "beautiful", "风景": "scenery", "声音": "sound", "眼睛": "eye",
        "工作": "work", "生活": "life", "希望": "hope", "梦想": "dream",
        "爱": "love", "时间": "time", "空气": "air", "树木": "tree",
        "季节": "season", "花朵": "flower", "颜色": "color", "音乐": "music",
        "森林": "forest", "河流": "river", "星星": "star", "月亮": "moon",
        "未来": "future", "历史": "history", "成功": "success", "失败": "failure",
        "健康": "health", "力量": "power", "自由": "freedom", "文化": "culture",
        "科技": "technology", "环境": "environment", "社会": "society",
    }

    # 统计原文中已知词实际出现的次数（不出现的不计入）
    known_counts = {}
    for w in orig_words:
        if w in known_map:
            known_counts[w] = known_counts.get(w, 0) + 1

    # 统计 target_words 的出现次数
    target_counts = {}
    for tw in target_words:
        target_counts[tw] = sum(1 for w in orig_words if w == tw)

    # 替换：仅替换原文中实际出现的已知词 + 出现 >= 3 次的 target 词
    final_words = []
    for w in result_words:
        if w in known_counts:
            final_words.append(known_map[w])
        elif w in target_counts:
            cnt = target_counts[w]
            if cnt >= 3:
                en = fallback.get(w, w)
                final_words.append(en)
            else:
                final_words.append(w)
        else:
            final_words.append(w)

    # 拼接（英文词之间加空格，中文间不加）
    parts = []
    for i, w in enumerate(final_words):
        if i > 0:
            prev = final_words[i - 1]
            prev_en = not bool(re.search(r'[\u4e00-\u9fff]', prev)) and prev.strip()
            curr_en = not bool(re.search(r'[\u4e00-\u9fff]', w)) and w.strip()
            if prev_en and curr_en:
                parts.append(" " + w)
            else:
                parts.append(w)
        else:
            parts.append(w)
    result = "".join(parts).strip()
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r'\s+([，。！？；：、,\.!\?;:])', r'\1', result)
    result = re.sub(r'([，。！？；：、])\s+', r'\1', result)

    # 构建词汇表：仅包含原文中出现的已知词 + 被替换的 target 词
    vocab = []
    for w in known_counts:
        vocab.append({"cn": w, "en": known_map[w]})
    for tw in target_words:
        if target_counts.get(tw, 0) >= 3:
            en = fallback.get(tw, tw)
            vocab.append({"cn": tw, "en": en})

    return result, vocab


def force_replace(text, target_words, vocab, known_words):
    """用 jieba 分词精确替换：先替换所有已知词，再渐进替换新词"""
    words = list(jieba.cut(text))
    all_vocab = list(vocab)
    # 已通过 LLM 获取到的翻译
    known_map = {w["cn"]: w["en"] for w in known_words}
    new_map = {v["cn"]: v["en"] for v in vocab}

    fallback = {
        "世界": "world", "太阳": "sun", "天空": "sky", "大海": "sea",
        "城市": "city", "乡村": "village", "朋友": "friend", "家庭": "family",
        "记忆": "memory", "忘记": "forget", "痛苦": "pain", "幸福": "happiness",
        "美丽": "beautiful", "风景": "scenery", "声音": "sound", "眼睛": "eye",
        "工作": "work", "生活": "life", "希望": "hope", "梦想": "dream",
        "爱": "love", "时间": "time", "空气": "air", "树木": "tree",
        "季节": "season", "花朵": "flower", "颜色": "color", "音乐": "music",
        "森林": "forest", "河流": "river", "星星": "star", "月亮": "moon",
        "未来": "future", "历史": "history", "成功": "success", "失败": "failure",
        "健康": "health", "力量": "power", "自由": "freedom", "文化": "culture",
        "科技": "technology", "环境": "environment", "社会": "society",
    }

    # 统计每个目标词的出现次数
    new_word_counts = {}
    for tw in target_words:
        cnt = sum(1 for w in words if w == tw)
        new_word_counts[tw] = cnt

    # 重建文本
    result_words = []
    for w in words:
        if w in known_map:
            result_words.append(known_map[w])
        elif w in new_map:
            result_words.append(new_map[w])
        elif w in new_word_counts and new_word_counts[w] >= 3:
            # 出现在目标列表中但 LLM 没有替换 → 用 fallback 渐进替换
            en = fallback.get(w)
            if en:
                result_words.append(en)
            else:
                result_words.append(w)
        else:
            result_words.append(w)

    result = ""
    for i, w in enumerate(result_words):
        if i == 0:
            result = w
            continue
        prev = result_words[i - 1]
        prev_is_cn = bool(re.search(r'[\u4e00-\u9fff]', prev))
        curr_is_cn = bool(re.search(r'[\u4e00-\u9fff]', w))
        if not prev_is_cn and not curr_is_cn:
            result += " " + w
        else:
            result += w
    result = result.strip()

    # 补充 vocab：已知词 + LLM 新词 + fallback 新词
    final_vocab = []
    added_cn = set()
    for kw in known_words:
        if kw["cn"] not in added_cn:
            final_vocab.append({"cn": kw["cn"], "en": kw["en"]})
            added_cn.add(kw["cn"])
    for v in vocab:
        if v["cn"] not in added_cn:
            final_vocab.append(v)
            added_cn.add(v["cn"])
    # fallback 新词
    for tw in target_words:
        if tw not in added_cn and new_word_counts.get(tw, 0) >= 3:
            en = fallback.get(tw)
            if en:
                final_vocab.append({"cn": tw, "en": en})
                added_cn.add(tw)

    return result, final_vocab


def cache_key(text, known_words):
    """生成缓存键"""
    raw = text + json.dumps(sorted(known_words, key=lambda x: x["cn"]), ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()


def cache_get(key):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT result, vocabulary FROM conversion_cache WHERE cache_key = ?", (key,)).fetchone()
    conn.close()
    if row:
        return {"result": row[0], "vocabulary": json.loads(row[1])}
    return None


def cache_set(key, result, vocabulary):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO conversion_cache (cache_key, result, vocabulary, created_at) VALUES (?, ?, ?, ?)",
        (key, result, json.dumps(vocabulary, ensure_ascii=False), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def stream_deepseek(text, known_words, target_words):
    """流式调用，yield token + 最终解析"""
    system_prompt = build_prompt(text, known_words, target_words)
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"替换 {len(target_words)} 个新词和所有已知词。直接输出替换后的纯文本，不要任何标记。"},
        ],
        "temperature": 0.7, "max_tokens": 4096, "stream": True,
    }
    resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=120, stream=True)
    if not resp.ok:
        yield f"data: {json.dumps({'error': f'API {resp.status_code}'})}\n\n"
        return
    full = ""
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "): continue
        data_str = line[6:]
        if data_str == "[DONE]": break
        try:
            chunk = json.loads(data_str)
            token = chunk["choices"][0].get("delta", {}).get("content", "")
            if token:
                full += token
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception: continue
    # 清理 LLM 可能输出的标记，再用 jieba 精确替换
    full = clean_streamed_text(full)
    result, vocab = apply_replacements(full, text, known_words, target_words)
    yield f"data: {json.dumps({'done': True, 'result': result, 'vocabulary': vocab})}\n\n"


def extract_vocab(result_text, target_words):
    """通过对比原文与结果的分词差异，找出被替换的词→英文对应"""
    # 从结果中提取所有英文词/短语
    en_tokens = re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?(?: [a-zA-Z]+(?:'[a-zA-Z]+)?)*", result_text)
    if not en_tokens:
        return []

    # 对 results 分词，找出已不在结果中的中文词
    result_cn = set(w for w in jieba.cut(result_text) if len(w) >= 2 and re.search(r'[\u4e00-\u9fff]', w))

    # 从 target_words 中找出不在结果中的词（被替换了）
    replaced = [w for w in target_words if w not in result_cn]

    # 按结果中英文词的出现顺序，一一对应
    vocab = []
    for i, tw in enumerate(replaced):
        if i < len(en_tokens):
            vocab.append({"cn": tw, "en": en_tokens[i]})
    return vocab


# ============================================================
# API 路由
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/articles')
def get_articles():
    """返回内置文章 + 用户上传文章"""
    user_articles = get_user_articles()
    all_articles = BUILTIN_ARTICLES + user_articles
    return jsonify(all_articles)


@app.route('/api/article/<article_id>')
def get_article(article_id):
    # 先查内置
    for a in BUILTIN_ARTICLES:
        if str(a['id']) == article_id:
            return jsonify(a)
    # 再查用户上传
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT id, title, content, char_count, created_at FROM user_articles WHERE 'u' || id = ?", (article_id,)).fetchone()
    conn.close()
    if row:
        return jsonify({
            "id": f"u{row[0]}",
            "title": row[1],
            "content": row[2],
            "difficulty": 0,
            "tags": ["用户上传"],
            "source": "upload"
        })
    return jsonify({"error": "文章不存在"}), 404


@app.route('/api/articles/upload', methods=['POST'])
def upload_article():
    title = None
    content = None

    # 尝试解析 JSON
    if request.is_json:
        data = request.get_json()
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()

    # 尝试读取文件
    if not content and 'file' in request.files:
        file = request.files['file']
        raw = file.read().decode('utf-8')
        # 第一行作为标题，最多 50 字
        lines = raw.strip().split('\n')
        title = lines[0].strip()[:50]
        content = '\n'.join(lines[1:]).strip()

    if not title or not content:
        return jsonify({"error": "请提供标题和内容，或上传 .txt 文件（首行为标题）"}), 400

    cn_count = count_chinese_chars(content)
    if cn_count < 20:
        return jsonify({"error": "文章太短（至少需要 20 个中文字符）"}), 400

    save_user_article(title, content, cn_count)

    articles = get_user_articles()
    latest = articles[0] if articles else None

    return jsonify({"ok": True, "article": latest}), 201


@app.route('/api/articles/<article_id>', methods=['DELETE'])
def delete_article(article_id):
    """删除用户上传的文章（仅限 upload 类型）"""
    if not article_id.startswith('u'):
        return jsonify({"error": "不能删除内置文章"}), 403
    real_id = int(article_id[1:])
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM user_articles WHERE id = ?", (real_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route('/api/convert', methods=['POST'])
def convert():
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "请输入文本"}), 400

    known_words = data.get('known_words', [])
    seen_words = data.get('seen_words', [])
    all_known = known_words + [{"cn": w["cn"], "en": w["en"]} for w in seen_words]

    cn_count = count_chinese_chars(text)
    max_new = calc_max_new(cn_count)
    target_words = pick_words(text, max_new, known_words)

    # 查缓存
    key = cache_key(text, known_words)
    cached = cache_get(key)
    if cached:
        return jsonify({
            "result": cached["result"],
            "vocabulary": cached["vocabulary"],
            "max_new": max_new,
            "known_count": len(known_words),
            "seen_count": len(seen_words),
            "source": "cache",
        })

    try:
        result, vocabulary = call_deepseek(text, all_known, target_words)
        cache_set(key, result, vocabulary)
        return jsonify({
            "result": result,
            "vocabulary": vocabulary,
            "max_new": max_new,
            "known_count": len(known_words),
            "seen_count": len(seen_words),
            "source": "deepseek",
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "result": text,
            "vocabulary": [],
            "max_new": max_new,
            "known_count": len(known_words),
            "seen_count": len(seen_words),
            "source": "error",
            "error_detail": str(e),
        }), 200


@app.route('/api/convert/stream', methods=['POST'])
def convert_stream():
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "请输入文本"}), 400

    known_words = data.get('known_words', [])
    seen_words = data.get('seen_words', [])
    skip_cache = data.get('skip_cache', False)
    all_known = known_words + [{"cn": w["cn"], "en": w["en"]} for w in seen_words]

    cn_count = count_chinese_chars(text)
    max_new = calc_max_new(cn_count)
    target_words = pick_words(text, max_new, known_words)

    key = cache_key(text, known_words)
    cached = None if skip_cache else cache_get(key)

    def generate():
        if cached:
            yield f"data: {json.dumps({'cached': True, 'result': cached['result'], 'vocabulary': cached['vocabulary'], 'max_new': max_new})}\n\n"
            return

        result_text = ""
        vocab = []
        for event in stream_deepseek(text, all_known, target_words):
            yield event
            data_obj = json.loads(event[6:])  # strip "data: " prefix
            if data_obj.get("done"):
                result_text = data_obj["result"]
                vocab = data_obj.get("vocabulary", [])
        if result_text:
            cache_set(key, result_text, vocab)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


# ============================================================
# 启动
# ============================================================
if __name__ == '__main__':
    init_db()
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True
    app.run(debug=True, port=5002)
