"""Reading Language (阅读语言) - Progressive Chinese-English Mixed Reading API
Advanced version with user uploads, streaming, known-word tracking, and smart word picking.
"""
import json
import os
import re
import random
import hashlib
import logging
from datetime import datetime
from collections import Counter

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sa_delete
import httpx

import jieba

from app.database import get_db
from app.models import ReadingArticle, ReadingConversionCache

logger = logging.getLogger("knowall.reading")

router = APIRouter(prefix="/api/v1/reading", tags=["reading"])

# ============================================================
# Configuration
# ============================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

KNOW_THRESHOLD = 5  # 同一词出现 5 次才算掌握


def calc_max_new(cn_count: int) -> int:
    """新词上限：1000字→3, 5000字→7, 10000字→12"""
    if cn_count <= 1000:
        return 3
    elif cn_count <= 5000:
        return 3 + (cn_count - 1000) // 1000
    else:
        return 7 + (cn_count - 5000) // 1000


# ============================================================
# 离线词典
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
# 高频词提取 (smart word picking)
# ============================================================

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

SURNAMES = set("""
李 王 张 刘 陈 杨 赵 黄 周 吴 徐 孙 马 胡 朱 郭 何 林 高 罗 郑 梁 谢
宋 唐 许 邓 韩 冯 曹 曾 彭 肖 陆 顾 沈 苏 蒋 蔡 潘 丁 魏 薛 叶 阎
余 杜 戴 夏 钟 汪 田 任 姜 范 方 石 姚 谭 廖 邹 熊 金 邱 秦 江 史
""".split())


def is_chinese_word(word: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', word))


def is_likely_name(word: str) -> bool:
    """判断是否像中文人名（2-3字，首字为常见姓氏）"""
    return 2 <= len(word) <= 3 and word[0] in SURNAMES


def count_chinese_chars(text: str) -> int:
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def pick_words(text: str, count: int, known_words: list[dict]) -> list[str]:
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
    candidates = [(w, c) for w, c in freq.most_common() if c >= 2]
    if len(candidates) < count:
        extra = [(w, c) for w, c in freq.most_common() if c == 1]
        candidates.extend(extra)
    selected = [w for w, _ in candidates[:count]]
    return selected


# ============================================================
# 离线词典降级方案
# ============================================================
def convert_with_dict(text: str, ratio: int) -> tuple[str, list[dict], int]:
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


# ============================================================
# Prompt building (advanced: includes known words)
# ============================================================

def build_advanced_prompt(text: str, known_words: list[dict], target_words: list[str]) -> str:
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


# ============================================================
# jieba precision fix (apply_replacements)
# ============================================================
FALLBACK_DICT = {
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


def apply_replacements(result_text: str, original_text: str,
                       known_words: list[dict], target_words: list[str]) -> tuple[str, list[dict]]:
    """用 jieba 分词对比原文和结果，精确替换遗漏的词"""
    orig_words = list(jieba.cut(original_text))

    known_map = {w["cn"]: w["en"] for w in known_words}
    result_words = list(jieba.cut(result_text))

    # 统计原文中已知词实际出现的次数
    known_counts: dict[str, int] = {}
    for w in orig_words:
        if w in known_map:
            known_counts[w] = known_counts.get(w, 0) + 1

    # 统计 target_words 的出现次数
    target_counts: dict[str, int] = {}
    for tw in target_words:
        target_counts[tw] = sum(1 for w in orig_words if w == tw)

    # 替换
    final_words = []
    for w in result_words:
        if w in known_counts:
            final_words.append(known_map[w])
        elif w in target_counts:
            cnt = target_counts[w]
            if cnt >= 3:
                en = FALLBACK_DICT.get(w, w)
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

    # 构建词汇表
    vocab = []
    added_cn = set()
    for w in known_counts:
        if w not in added_cn:
            vocab.append({"cn": w, "en": known_map[w]})
            added_cn.add(w)
    for tw in target_words:
        if tw not in added_cn and target_counts.get(tw, 0) >= 3:
            en = FALLBACK_DICT.get(tw, tw)
            vocab.append({"cn": tw, "en": en})
            added_cn.add(tw)

    return result, vocab


def clean_streamed_text(text: str) -> str:
    """去掉 <<>> 标记"""
    return re.sub(r'<<([^>]+)>>', r'\1', text)


# ============================================================
# Conversion cache
# ============================================================
def make_cache_key(text: str, known_words: list[dict]) -> str:
    raw = text + json.dumps(sorted(known_words, key=lambda x: x["cn"]), ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()


async def cache_get(key: str, db: AsyncSession) -> dict | None:
    result = await db.execute(
        select(ReadingConversionCache).where(ReadingConversionCache.cache_key == key)
    )
    row = result.scalar_one_or_none()
    if row:
        return {"result": row.result, "vocabulary": json.loads(row.vocabulary)}
    return None


async def cache_set(key: str, result_text: str, vocabulary: list[dict], db: AsyncSession):
    existing = await db.get(ReadingConversionCache, key)
    if existing:
        existing.result = result_text
        existing.vocabulary = json.dumps(vocabulary, ensure_ascii=False)
        existing.created_at = datetime.utcnow()
    else:
        db.add(ReadingConversionCache(
            cache_key=key,
            result=result_text,
            vocabulary=json.dumps(vocabulary, ensure_ascii=False),
        ))
    await db.commit()


# ============================================================
# DeepSeek API
# ============================================================

async def call_deepseek(text: str, known_words: list[dict],
                        target_words: list[str]) -> tuple[str, list[dict]]:
    system_prompt = build_advanced_prompt(text, known_words, target_words)
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"替换 {len(target_words)} 个新词和所有已知词。直接输出替换后的纯文本，不要任何标记符号。"},
        ],
        "temperature": 0.7, "max_tokens": 4096,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = re.sub(r'^```\w*\n', '', raw)
            raw = re.sub(r'\n```$', '', raw)
        raw = clean_streamed_text(raw)

        result, vocab = apply_replacements(raw, text, known_words, target_words)
        return result, vocab


async def stream_deepseek(text: str, known_words: list[dict],
                          target_words: list[str]):
    """Async generator yielding SSE event strings"""
    system_prompt = build_advanced_prompt(text, known_words, target_words)
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"替换 {len(target_words)} 个新词和所有已知词。直接输出替换后的纯文本，不要任何标记。"},
        ],
        "temperature": 0.7, "max_tokens": 4096, "stream": True,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", DEEPSEEK_API_URL, headers=headers, json=payload) as resp:
            if not resp.is_success:
                yield f"data: {json.dumps({'error': f'API {resp.status_code}'})}\n\n"
                return
            full = ""
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    token = chunk["choices"][0].get("delta", {}).get("content", "")
                    if token:
                        full += token
                        yield f"data: {json.dumps({'token': token})}\n\n"
                except Exception:
                    continue
            full = clean_streamed_text(full)
            result, vocab = apply_replacements(full, text, known_words, target_words)
            yield f"data: {json.dumps({'done': True, 'result': result, 'vocabulary': vocab})}\n\n"


# ============================================================
# Built-in article library
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


# ============================================================
# Pydantic Schemas
# ============================================================

class VocabItem(BaseModel):
    cn: str
    en: str


class ConvertRequest(BaseModel):
    text: str = Field(..., min_length=1)
    level: int = Field(default=1, ge=1, le=3)
    known_words: list[VocabItem] = Field(default_factory=list)
    seen_words: list[VocabItem] = Field(default_factory=list)


class ConvertStreamRequest(BaseModel):
    text: str = Field(..., min_length=1)
    known_words: list[VocabItem] = Field(default_factory=list)
    seen_words: list[VocabItem] = Field(default_factory=list)
    skip_cache: bool = False


class ArticleUploadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


# ============================================================
# Helpers
# ============================================================

async def get_user_articles(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(ReadingArticle).order_by(ReadingArticle.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "id": f"u{r.id}",
            "title": r.title,
            "content": r.content,
            "difficulty": 0,
            "tags": ["用户上传"],
            "source": "upload",
        }
        for r in rows
    ]


async def get_all_articles(db: AsyncSession) -> list[dict]:
    user_articles = await get_user_articles(db)
    return BUILTIN_ARTICLES + user_articles


# ============================================================
# API Routes
# ============================================================

@router.get("/articles")
async def list_articles(
    difficulty: int | None = Query(default=None, ge=1, le=3),
    db: AsyncSession = Depends(get_db),
):
    """获取所有文章（内置 + 用户上传），可按难度筛选"""
    all_articles = await get_all_articles(db)
    if difficulty is not None:
        return [a for a in all_articles if a.get("difficulty") == difficulty]
    return all_articles


@router.get("/articles/{article_id}")
async def get_article(article_id: str, db: AsyncSession = Depends(get_db)):
    """获取单篇文章详情"""
    # 先查内置
    for a in BUILTIN_ARTICLES:
        if str(a["id"]) == article_id:
            return a
    # 再查用户上传
    if article_id.startswith("u"):
        real_id = int(article_id[1:])
        result = await db.execute(
            select(ReadingArticle).where(ReadingArticle.id == real_id)
        )
        row = result.scalar_one_or_none()
        if row:
            return {
                "id": f"u{row.id}",
                "title": row.title,
                "content": row.content,
                "difficulty": 0,
                "tags": ["用户上传"],
                "source": "upload",
            }
    raise HTTPException(status_code=404, detail="文章不存在")


@router.post("/articles/upload")
async def upload_article(
    req: ArticleUploadRequest,
    db: AsyncSession = Depends(get_db),
):
    """上传自定义文章（JSON）"""
    title = req.title.strip()
    content = req.content.strip()

    cn_count = count_chinese_chars(content)
    if cn_count < 20:
        raise HTTPException(status_code=400, detail="文章太短（至少需要 20 个中文字符）")

    article = ReadingArticle(
        title=title,
        content=content,
        char_count=cn_count,
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)

    article_data = {
        "id": f"u{article.id}",
        "title": article.title,
        "content": article.content,
        "difficulty": 0,
        "tags": ["用户上传"],
        "source": "upload",
    }
    return {"ok": True, "article": article_data}


@router.post("/articles/upload-file")
async def upload_article_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """上传 .txt 文件（首行为标题，正文从第二行开始）"""
    if not file.filename or not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="仅支持 .txt 文件")

    raw = (await file.read()).decode('utf-8')
    lines = raw.strip().split('\n')
    title = lines[0].strip()[:200]
    content = '\n'.join(lines[1:]).strip()

    if not title or not content:
        raise HTTPException(status_code=400, detail="文件格式错误：首行为标题，之后为正文")

    cn_count = count_chinese_chars(content)
    if cn_count < 20:
        raise HTTPException(status_code=400, detail="文章太短（至少需要 20 个中文字符）")

    article = ReadingArticle(
        title=title,
        content=content,
        char_count=cn_count,
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)

    article_data = {
        "id": f"u{article.id}",
        "title": article.title,
        "content": article.content,
        "difficulty": 0,
        "tags": ["用户上传"],
        "source": "upload",
    }
    return {"ok": True, "article": article_data}


@router.delete("/articles/{article_id}")
async def delete_article(article_id: str, db: AsyncSession = Depends(get_db)):
    """删除用户上传的文章（仅限 upload 类型）"""
    if not article_id.startswith("u"):
        raise HTTPException(status_code=403, detail="不能删除内置文章")
    real_id = int(article_id[1:])
    await db.execute(sa_delete(ReadingArticle).where(ReadingArticle.id == real_id))
    await db.commit()
    return {"ok": True}


@router.post("/convert")
async def convert_text_endpoint(
    req: ConvertRequest,
    db: AsyncSession = Depends(get_db),
):
    """将中文文本转换为中英混合文本（支持已知/已见词汇追踪）"""
    text = req.text
    known_words = [w.model_dump() for w in req.known_words]
    seen_words = [w.model_dump() for w in req.seen_words]
    all_known = known_words + [{"cn": w["cn"], "en": w["en"]} for w in seen_words]

    cn_count = count_chinese_chars(text)
    max_new = calc_max_new(cn_count)
    target_words = pick_words(text, max_new, known_words)

    # 查缓存
    key = make_cache_key(text, known_words)
    cached = await cache_get(key, db)
    if cached:
        return {
            "result": cached["result"],
            "vocabulary": cached["vocabulary"],
            "max_new": max_new,
            "known_count": len(known_words),
            "seen_count": len(seen_words),
            "source": "cache",
        }

    # 尝试 DeepSeek API
    if DEEPSEEK_API_KEY:
        try:
            result_text, vocabulary = await call_deepseek(text, all_known, target_words)
            await cache_set(key, result_text, vocabulary, db)
            return {
                "result": result_text,
                "vocabulary": vocabulary,
                "max_new": max_new,
                "known_count": len(known_words),
                "seen_count": len(seen_words),
                "source": "deepseek",
            }
        except Exception as e:
            logger.warning(f"DeepSeek API 调用失败，使用离线词典: {e}")

    # 降级：离线词典
    ratio = {1: 20, 2: 40, 3: 65}.get(req.level, 20)
    result_text, vocabulary, actual_ratio = convert_with_dict(text, ratio)
    return {
        "result": result_text,
        "vocabulary": vocabulary,
        "max_new": max_new,
        "known_count": len(known_words),
        "seen_count": len(seen_words),
        "source": "dictionary",
    }


@router.post("/convert/stream")
async def convert_stream(
    req: ConvertStreamRequest,
    db: AsyncSession = Depends(get_db),
):
    """流式 SSE：将中文文本转换为中英混合文本"""
    text = req.text
    known_words = [w.model_dump() for w in req.known_words]
    seen_words = [w.model_dump() for w in req.seen_words]
    skip_cache = req.skip_cache
    all_known = known_words + [{"cn": w["cn"], "en": w["en"]} for w in seen_words]

    cn_count = count_chinese_chars(text)
    max_new = calc_max_new(cn_count)
    target_words = pick_words(text, max_new, known_words)

    key = make_cache_key(text, known_words)

    async def generate():
        if not skip_cache:
            cached = await cache_get(key, db)
            if cached:
                yield f"data: {json.dumps({'cached': True, 'result': cached['result'], 'vocabulary': cached['vocabulary'], 'max_new': max_new})}\n\n"
                return

        result_text = ""
        vocab = []
        async for event in stream_deepseek(text, all_known, target_words):
            yield event
            data_obj = json.loads(event[6:])
            if data_obj.get("done"):
                result_text = data_obj["result"]
                vocab = data_obj.get("vocabulary", [])
        if result_text:
            await cache_set(key, result_text, vocab, db)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
