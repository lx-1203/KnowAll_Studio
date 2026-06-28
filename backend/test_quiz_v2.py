"""Quick test script: Generate quiz questions using the new v2 pipeline."""
import asyncio
import json
import sys
import os
import logging

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Suppress noisy SQLAlchemy logs
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env for API configuration
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

# Configure the API adapter (mirrors main.py startup logic)
from app.core.api_scheduler.client import api_client

anthropic_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
anthropic_base = os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")
anthropic_model = os.getenv("ANTHROPIC_MODEL", "deepseek-v4-pro")

if anthropic_token:
    api_client.configure_adapter(
        "anthropic",
        anthropic_token,
        base_url=anthropic_base,
        model_name=anthropic_model,
    )
    print(f"Adapter configured: anthropic -> {anthropic_model} @ {anthropic_base}")
else:
    print("ERROR: ANTHROPIC_AUTH_TOKEN not found in .env")
    sys.exit(1)

MODEL = f"anthropic/{anthropic_model}"

# Test knowledge content - 计算机网络基础 (a self-contained topic for testing)
TEST_KNOWLEDGE = """
## 1. OSI七层模型
OSI（Open Systems Interconnection）七层模型是国际标准化组织（ISO）提出的网络互连标准框架。
从下到上依次为：物理层、数据链路层、网络层、传输层、会话层、表示层、应用层。
每层有各自的协议和功能，下层为上层提供服务。

## 2. TCP与UDP
TCP（传输控制协议）是面向连接的可靠传输协议，通过三次握手建立连接，提供流量控制和拥塞控制。
UDP（用户数据报协议）是无连接的不可靠传输协议，不保证数据到达，但传输效率高，适合流媒体等场景。
TCP头部20字节，包含序列号、确认号、窗口大小等字段；UDP头部仅8字节。

## 3. HTTP协议
HTTP（超文本传输协议）是基于TCP的应用层协议，使用请求-响应模型。
HTTP/1.1支持持久连接和管道化；HTTP/2引入二进制分帧、多路复用、头部压缩和服务端推送；
HTTP/3基于QUIC协议（UDP），进一步降低延迟。
HTTPS在HTTP基础上增加了TLS/SSL加密层，确保通信安全。

## 4. IP地址与子网划分
IPv4地址是32位二进制数，通常用点分十进制表示，如192.168.1.1。
子网掩码用于划分网络位和主机位，如255.255.255.0表示前24位是网络位。
CIDR（无类别域间路由）使用斜线表示法，如192.168.1.0/24。
IPv6使用128位地址，解决了IPv4地址枯竭问题。

## 5. DNS域名系统
DNS（域名系统）将域名转换为IP地址。查询过程：浏览器缓存 → 操作系统缓存 → 本地DNS服务器
→ 根域名服务器 → 顶级域名服务器 → 权威域名服务器。DNS使用UDP协议的53端口。

## 6. 路由算法
距离矢量路由（如RIP）基于Bellman-Ford算法，每跳路由器与邻居交换路由表。
链路状态路由（如OSPF）基于Dijkstra算法，每个路由器维护全网拓扑图。
RIP最大跳数为15，适合小型网络；OSPF收敛速度快，适合大型网络。
"""

async def main():
    from app.core.quiz import quiz_generator, QuizGenerationConfig

    print("=" * 60)
    print("测试1: 单选题 (L2_understand, difficulty=0.4, with review)")
    print("=" * 60)

    config = QuizGenerationConfig(
        question_type="single_choice",
        count=3,
        difficulty="medium",
        difficulty_score=0.4,
        cognitive_level="L2_understand",
        enable_review=True,
    )
    questions = await quiz_generator.generate(TEST_KNOWLEDGE, config, model=MODEL)
    for i, q in enumerate(questions):
        print(f"\n--- 题目 {i+1} ---")
        print(f"认知层次: {q.get('cognitive_level')}  难度: {q.get('difficulty_score')}")
        print(f"题目: {q.get('question_text', '')}")
        options = q.get('options', [])
        if options:
            for opt in options:
                mark = " [ANSWER]" if opt['label'] == q.get('answer', '') else ""
                print(f"  {opt['label']}. {opt['text']}{mark}")
        print(f"解析: {q.get('analysis', '')[:200]}")
        if q.get('reviewed'):
            print(f"审核: {q.get('review_decision')} (总分: {q.get('review_total')})")

    print("\n" + "=" * 60)
    print("测试2: 多选题 (L4_analyze, difficulty=0.65)")
    print("=" * 60)

    config2 = QuizGenerationConfig(
        question_type="multi_choice",
        count=2,
        difficulty="hard",
        difficulty_score=0.65,
        cognitive_level="L4_analyze",
        enable_review=True,
    )
    questions2 = await quiz_generator.generate(TEST_KNOWLEDGE, config2, model=MODEL)
    for i, q in enumerate(questions2):
        print(f"\n--- 题目 {i+1} ---")
        print(f"认知层次: {q.get('cognitive_level')}  难度: {q.get('difficulty_score')}")
        print(f"题目: {q.get('question_text', '')}")
        options = q.get('options', [])
        if options:
            answers = q.get('answer', [])
            if isinstance(answers, str):
                answers = [answers]
            for opt in options:
                mark = " [ANSWER]" if opt['label'] in answers else ""
                print(f"  {opt['label']}. {opt['text']}{mark}")
        print(f"解析: {q.get('analysis', '')[:200]}")

    print("\n" + "=" * 60)
    print("测试3: 简答题 (L5_evaluate, difficulty=0.75)")
    print("=" * 60)

    config3 = QuizGenerationConfig(
        question_type="short_answer",
        count=1,
        difficulty="hard",
        difficulty_score=0.75,
        cognitive_level="L5_evaluate",
        enable_review=True,
    )
    questions3 = await quiz_generator.generate(TEST_KNOWLEDGE, config3, model=MODEL)
    for i, q in enumerate(questions3):
        print(f"\n--- 题目 {i+1} ---")
        print(f"认知层次: {q.get('cognitive_level')}  难度: {q.get('difficulty_score')}")
        print(f"题目: {q.get('question_text', '')}")
        print(f"参考答案: {str(q.get('answer', ''))[:300]}")
        print(f"解析: {q.get('analysis', '')[:200]}")

    print("\n" + "=" * 60)
    print("测试4: 语义评分 (对简答题的模拟作答进行LLM评分)")
    print("=" * 60)

    # Test semantic grading
    if questions3:
        q = questions3[0]
        user_answer = "TCP和UDP的主要区别在于TCP是面向连接的，有三次握手，而UDP是无连接的。TCP可靠传输，UDP不可靠但速度快。TCP有流量控制和拥塞控制，UDP没有。我觉得应该根据场景选择。"

        from app.core.quiz import exam_engine
        result = await exam_engine.grade_semantic(
            question_text=q.get('question_text', ''),
            reference_answer=str(q.get('answer', '')),
            user_answer=user_answer,
            model=MODEL,
        )
        if result:
            print(f"正确性: {result['scores']['correctness']}/10")
            print(f"完整性: {result['scores']['completeness']}/10")
            print(f"清晰度: {result['scores']['clarity']}/10")
            print(f"总分: {result['total_score']}/10 {'通过' if result['passed'] else '未通过'}")
            fb = result.get('feedback', {})
            if fb.get('strengths'):
                print(f"优点: {'; '.join(fb['strengths'])}")
            if fb.get('weaknesses'):
                print(f"不足: {'; '.join(fb['weaknesses'])}")
            if fb.get('suggestion'):
                print(f"建议: {fb['suggestion']}")
            if result.get('key_points_matched'):
                print(f"匹配要点: {', '.join(result['key_points_matched'])}")
            if result.get('key_points_missed'):
                print(f"遗漏要点: {', '.join(result['key_points_missed'])}")

    print("\nAll tests completed.")

if __name__ == "__main__":
    asyncio.run(main())
