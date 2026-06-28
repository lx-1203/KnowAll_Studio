import json
import os
import re
import random
import hashlib
import time
from flask import Flask, render_template, request, jsonify
import requests

import jieba

app = Flask(__name__)

# ============================================================
# DeepSeek API 配置
# ============================================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# ============================================================
# 离线词典（API 不可用时降级方案）
# ============================================================
CN_EN_DICT = {
    "我": "I", "我们": "we", "你": "you", "他": "he", "她": "she",
    "它": "it", "他们": "they", "我的": "my", "你的": "your",
    "是": "is", "有": "have", "去": "go", "来": "come",
    "看": "see", "说": "say", "做": "do", "吃": "eat", "喝": "drink",
    "走": "walk", "跑": "run", "想": "think", "知道": "know",
    "给": "give", "拿": "take", "用": "use", "让": "let",
    "学习": "study", "工作": "work", "玩": "play", "买": "buy",
    "帮助": "help", "喜欢": "like", "爱": "love", "写": "write",
    "读": "read", "听": "listen", "告诉": "tell", "问": "ask",
    "感觉": "feel", "需要": "need", "想要": "want",
    "世界": "world", "人": "person", "朋友": "friend", "家庭": "family",
    "学校": "school", "时间": "time", "今天": "today", "明天": "tomorrow",
    "东西": "thing", "问题": "question", "书": "book", "水": "water",
    "食物": "food", "钱": "money", "孩子": "child", "老师": "teacher",
    "名字": "name", "地方": "place", "国家": "country", "城市": "city",
    "狗": "dog", "猫": "cat", "花": "flower", "树": "tree",
    "太阳": "sun", "月亮": "moon", "天空": "sky", "大海": "sea",
    "眼睛": "eye", "手": "hand", "心": "heart",
    "音乐": "music", "电影": "movie", "游戏": "game", "电脑": "computer",
    "手机": "phone", "房子": "house", "门": "door", "车": "car",
    "大": "big", "小": "small", "好": "good", "坏": "bad", "新": "new",
    "旧": "old", "高": "high", "低": "low", "快": "fast", "慢": "slow",
    "开心": "happy", "难过": "sad", "漂亮": "beautiful",
    "很": "very", "也": "also", "都": "all", "只": "only",
    "和": "and", "或者": "or", "但是": "but", "没有": "no",
    "可以": "can", "不": "not", "真的": "really", "应该": "should",
    "重要": "important", "简单": "simple", "容易": "easy",
    "困难": "difficult", "特别": "special", "不同": "different",
    "经常": "often", "总是": "always", "从不": "never", "一起": "together",
    "文化": "culture", "社会": "society", "科技": "technology",
    "环境": "environment", "生活": "life", "健康": "health",
    "成功": "success", "失败": "failure", "力量": "power",
    "梦想": "dream", "自由": "freedom", "幸福": "happiness",
    "旅行": "travel", "语言": "language", "知识": "knowledge",
    "机会": "chance", "未来": "future", "历史": "history",
}

CN_PUNCT = set("，。！？；：""''（）【】《》、…—·～ ")


# ============================================================
# API 英文替换 Prompt
# ============================================================
def build_prompt(text, level):
    level_config = {
        1: ("10%-25%", "仅替换最常见的基础词汇（如：我→I，是→is，好→good，人→person）。保持句子自然流畅"),
        2: ("25%-50%", "替换常见的内容词（名词、动词、形容词）。可适当保留虚词和专有名词为中文"),
        3: ("50%-80%", "广泛替换可替换的词汇，仅保留虚词（的、了、着、呢）和标点为中文。尽量让英文单词占多数"),
    }
    ratio_range, guidance = level_config.get(level, level_config[1])

    system_prompt = f"""你是一个中英混合文本生成器，用于帮助中文母语者渐进式学习英语。

【规则】
1. 输入一段中文文本，你输出一段中英混合文本
2. 替换比例为 {ratio_range}
3. {guidance}
4. 不要替换中文标点符号（，。！？等）
5. 英文单词之间必须有空格分隔。但英文和中文之间绝对不要加任何空格（例如"我们的world"不是"我们的 world"）。标点符号和英文之间也不要加空格（例如"world，"不是"world ，"）
6. 替换要自然、语义准确，注意英语语法形态（时态、单复数等）

【输出格式 - 必须严格返回 JSON】
{{
  "result": "中英混合的完整文本",
  "vocabulary": [{{"cn": "中文词", "en": "english"}}, ...]
}}"""
    return system_prompt


def call_deepseek(text, level):
    """调用 DeepSeek API 生成中英混合文本"""
    system_prompt = build_prompt(text, level)

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.8,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed["result"], parsed.get("vocabulary", [])
    except Exception as e:
        print(f"[DeepSeek API Error] {e}")
        raise


# ============================================================
# 离线词典降级方案
# ============================================================
def is_chinese_word(word):
    return bool(re.search(r'[\u4e00-\u9fff]', word))


def convert_with_dict(text, ratio):
    words = list(jieba.cut(text))
    replaced = []
    vocabulary = []

    total_cn_words = [w for w in words if is_chinese_word(w)]
    target_count = max(1, int(len(total_cn_words) * ratio / 100))

    replaceable = [(i, w) for i, w in enumerate(words) if is_chinese_word(w) and w in CN_EN_DICT]
    if not replaceable:
        return text, [], ratio

    selected_count = min(target_count, len(replaceable))
    selected = random.sample(replaceable, selected_count)
    selected_map = {idx: CN_EN_DICT[w] for idx, w in selected}

    for i, w in enumerate(words):
        if i in selected_map:
            en = selected_map[i]
            replaced.append(en)
            vocabulary.append({"cn": w, "en": en})
        else:
            replaced.append(w)

    result_parts = []
    for i, seg in enumerate(replaced):
        if i == 0:
            result_parts.append(seg)
            continue
        prev = replaced[i - 1]
        prev_cn = is_chinese_word(prev) or prev in CN_PUNCT
        curr_cn = is_chinese_word(seg) or seg in CN_PUNCT
        if prev == ' ' or seg == ' ':
            result_parts.append(seg)
        elif not prev_cn and not curr_cn:
            result_parts.append(" " + seg)
        else:
            result_parts.append(seg)

    result = "".join(result_parts).strip()
    result = re.sub(r'\s+', ' ', result)
    return result, vocabulary, ratio


def convert_text(text, level=1):
    """智能替换：优先使用 DeepSeek API，失败时降级到离线词典"""
    level = max(1, min(3, int(level)))

    # 尝试 API
    try:
        result, vocabulary = call_deepseek(text, level)
        return {
            "result": result,
            "vocabulary": vocabulary,
            "level": level,
            "ratio": f"~{len(vocabulary)}词",
            "word_count": len(vocabulary),
            "source": "deepseek",
        }
    except Exception as e:
        print(f"[Fallback] API 调用失败，使用离线词典: {e}")

    # 降级方案
    ratio = {1: 20, 2: 40, 3: 65}.get(level, 20)
    result, vocabulary, actual_ratio = convert_with_dict(text, ratio)
    return {
        "result": result,
        "vocabulary": vocabulary,
        "level": level,
        "ratio": f"{actual_ratio}%",
        "word_count": len(vocabulary),
        "source": "dictionary",
    }


# ============================================================
# 文章库
# ============================================================
ARTICLES = [
    {
        "id": 1, "title": "早晨的阳光", "difficulty": 1,
        "content": "今天早上，我打开窗户，看见太阳慢慢地升起来了。天空很蓝，有几朵白色的云。小鸟在树上唱歌，声音很好听。我喝了一杯水，吃了一些面包，然后去公园散步。公园里有很多人，有的在跑步，有的在做运动。我看见一个小孩子在放风筝，风筝飞得很高很高。这是一个美丽的早晨，让我感觉非常开心。",
        "tags": ["日常", "自然"]
    },
    {
        "id": 2, "title": "我的朋友小明", "difficulty": 1,
        "content": "我有一个好朋友，他的名字叫小明。他个子很高，眼睛很大，喜欢笑。我们经常一起学习，一起玩游戏。小明是一个好学生，他的成绩很好，特别是数学。他帮助我做作业，我帮助他学习英语。周末的时候，我们一起去图书馆看书，或者去操场踢足球。我很高兴有这样的朋友，我希望我们永远是朋友。",
        "tags": ["友谊", "日常"]
    },
    {
        "id": 3, "title": "城市和乡村", "difficulty": 1,
        "content": "城市很大，有很多高楼和汽车。人们每天都很忙，走在路上很快。乡村很安静，有绿色的山和干净的水。人们的生活很慢，但是很开心。城市里有很多商店和餐厅，我们可以买到很多东西。乡村里有新鲜的空气和美丽的风景。两种生活不同，但是都很好。",
        "tags": ["生活", "对比"]
    },
    {
        "id": 4, "title": "四季之美", "difficulty": 2,
        "content": "一年有四个季节：春天、夏天、秋天和冬天。春天到了，花儿开了，树木变绿了，天气变暖和了。夏天很热，人们喜欢去海边游泳，吃冰淇淋。秋天是收获的季节，树叶变成金色和红色，非常漂亮。冬天很冷，有时会下雪，孩子们喜欢堆雪人和打雪仗。每个季节都有自己的美丽，我都很喜欢。",
        "tags": ["自然", "季节"]
    },
    {
        "id": 5, "title": "健康的饮食习惯", "difficulty": 2,
        "content": "健康的生活需要良好的饮食习惯。首先，我们应该每天吃早餐，因为早餐给我们力量开始新的一天。其次，我们要多吃蔬菜和水果，少吃油炸食品和甜食。喝水也很重要，每天应该喝足够的水。另外，吃饭的时间要规律，不要吃得太快。好的习惯可以让我们更健康，更有精力去工作和学习。",
        "tags": ["健康", "生活"]
    },
    {
        "id": 6, "title": "旅行的意义", "difficulty": 2,
        "content": "很多人喜欢旅行。旅行可以让我们看到不同的风景，了解不同的文化，认识新的朋友。当你去一个新的地方，你会发现自己原来不知道的东西。也许是一种美食，也许是一种传统，也许是一个有趣的故事。旅行不只是走路和拍照，更重要的是用心去感受。每一次旅行都是一次成长的机会，让我们的世界变得更大。",
        "tags": ["旅行", "文化"]
    },
    {
        "id": 7, "title": "互联网改变生活", "difficulty": 2,
        "content": "互联网已经改变了我们的生活方式。过去，人们需要去商店买东西，现在可以在网上购物。过去，写信需要很长时间才能到达，现在发邮件只需要几秒钟。我们可以通过互联网学习新知识，看世界各地的新闻，和远方的朋友聊天。但是，互联网也有不好的地方，比如有些人花太多时间上网，忘记了真实的生活。我们要学会合理使用互联网。",
        "tags": ["科技", "社会"]
    },
    {
        "id": 8, "title": "坚持的力量", "difficulty": 3,
        "content": "在这个世界上，没有什么成功是容易得到的。每一个伟大的人背后，都有无数次的失败和坚持。坚持是一种品质，也是一种力量。当你遇到困难的时候，不要轻易放弃，因为成功可能就在下一个路口等着你。学习一门语言需要坚持，养成一个好习惯需要坚持，实现一个梦想更需要坚持。记住，今天的一小步，就是明天的一大步。",
        "tags": ["励志", "人生"]
    },
    {
        "id": 9, "title": "环境保护的紧迫性", "difficulty": 3,
        "content": "随着经济的发展，环境问题变得越来越严重。空气污染、水污染、土地污染，这些都威胁着我们的健康和未来。许多动物失去了它们的家园，一些物种甚至已经灭绝。我们每一个人都有责任保护环境。从小事做起，比如减少使用塑料袋，节约用水，多种树木。政府和企业也应该采取有效的措施，推动可持续发展。保护地球，就是保护我们自己。",
        "tags": ["环境", "社会"]
    },
    {
        "id": 10, "title": "人工智能的未来", "difficulty": 3,
        "content": "人工智能正在快速发展，它已经开始影响我们的工作和生活。人工智能可以帮助医生诊断疾病，帮助教师个性化教学，帮助农民提高粮食产量。但是，人工智能也带来了挑战和问题。很多人担心人工智能会取代人类的工作，也有人担心人工智能的安全性和伦理问题。未来，人类和人工智能应该是一种合作的关系，而不是对立的关系。我们要学会与人工智能共同发展。",
        "tags": ["科技", "未来"]
    },
]


# ============================================================
# API 路由
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/articles')
def get_articles():
    difficulty = request.args.get('difficulty', type=int)
    filtered = [a for a in ARTICLES if a['difficulty'] == difficulty] if difficulty else ARTICLES
    return jsonify(filtered)


@app.route('/api/article/<int:article_id>')
def get_article(article_id):
    for a in ARTICLES:
        if a['id'] == article_id:
            return jsonify(a)
    return jsonify({"error": "文章不存在"}), 404


@app.route('/api/convert', methods=['POST'])
def convert():
    data = request.get_json()
    text = data.get('text', '').strip()
    level = int(data.get('level', 1))

    if not text:
        return jsonify({"error": "请输入文本"}), 400

    result = convert_text(text, level)
    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True, port=5001)
