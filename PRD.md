# KnowAll Studio 智识工坊 — 产品需求文档（简版）

## 1. 产品定位

**一句话**：把任意文档（PDF / Word / Markdown / TXT / 网页）一键变成可学、可练、可复习的个人知识内化工作台。

**解决什么问题**：用户收藏了大量资料却没时间消化。KnowAll Studio 用 LLM 自动把文档拆成「知识树 + 题目 + 闪卡」，配合 FSRS 间隔复习算法和 AI 答疑助手，让"存了就等于学了"变成可能。

**目标用户**：自学者、考研/考证人群、知识工作者。

---

## 2. 核心功能

按学习闭环划分，每项对应实际页面/后端模块：

| 模块 | 能力 | 后端 API | 前端页面 |
|------|------|---------|---------|
| **文档导入** | 上传文档 → 解析 → 切分 chunk → 向量索引 | `documents` / `search` | UploadPage |
| **知识结构化** | 自动生成知识树 + Markdown 大纲 | `knowledge` / `knowledge_points` | KnowledgePage |
| **题目生成与练习** | 选择/填空/简答题；严格评分；来源 chunk 溯源 | `questions` / `quiz` | QuizPage |
| **闪卡 & 间隔复习** | FSRS 算法安排复习；Anki 导出 | `flashcards` / `memory` | FlashcardPage |
| **AI 对话答疑** | 基于文档的 RAG 对话（SSE 流式） | `chat` / `rag_assistant` | ChatPage |
| **语义搜索** | 跨文档检索 | `search` | SearchPage |
| **全链路生成** | 一键跑完 知识树→题目→闪卡 | `pipeline` | PipelinePage |
| **学习统计 & 仪表盘** | 学习进度/正确率/复习量 | `stats` | DashboardPage / StudyPage |
| **测验游戏** | 游戏化练习 | `game` | GamePage |
| **资源分享** | 分享文档/题目/闪卡/知识树 | `share` | SharePage |
| **阅读模式** | 文档预览与渐进式阅读 | `reading` | ReadingPage |
| **个人中心 / 设置** | 用户、API Key 配置、备份 | `user` / `auth` / `admin` / `backup` | PersonalCenterPage / SettingsPage |

---

## 3. 技术架构

```
Electron 桌面壳（可选）
        ↓
React + Vite + Tailwind  (:5173)
        ↓ HTTP / SSE
FastAPI + SQLAlchemy + Alembic  (:8000)
        ↓
SQLite（结构化） + ChromaDB（向量）
        ↓
LLM（DeepSeek / Anthropic / OpenAI 三选一，通过统一 adapter）
```

**关键设计**：
- **多 LLM 适配器**：通过 `.env` 切换 DeepSeek / Claude / OpenAI，业务代码不感知差异
- **本地优先**：默认全本地部署（SQLite + ChromaDB），数据不出本机
- **热重载开发**：前后端都开 reload，改完即生效

---

## 4. 快速开始

**前置**：Python 3.10+、Node.js 18+、3GB 可用磁盘

**一键启动**（Windows）：
```bash
start.bat
```
脚本会自动：装 Python 依赖（含国内镜像 fallback）→ 装 npm 包 → 启动后端 :8000 → 启动前端 :5173 → 自动开浏览器。

**API 配置**：在 `backend/.env` 填一个 LLM Key：
```env
DEEPSEEK_API_KEY=sk-...        # 或
ANTHROPIC_AUTH_TOKEN=sk-ant-... # 或
OPENAI_API_KEY=sk-...
```

**API 文档**：启动后访问 `http://localhost:8000/docs`

---

## 5. 项目结构

```
KnowAll_Studio/
├── backend/             # FastAPI 后端
│   ├── app/api/         # 19 个路由模块
│   ├── app/core/        # pipeline / rag / quiz / memory / parsing ...
│   ├── app/models/      # ORM 模型
│   └── app/prompts/     # LLM 提示词
├── frontend/            # React + Vite
│   ├── src/pages/       # 15 个页面
│   ├── src/components/  # 组件
│   └── tests/           # Playwright E2E
├── electron/            # 桌面打包
├── docker/              # 容器化部署
├── specs/system-fix/    # 系统修复需求/设计/任务
└── start.bat            # 一键启动
```

---

## 6. 非功能性要求

- **数据本地化**：默认不依赖云端，适合隐私敏感场景
- **多 LLM 中立**：业务代码不绑定单一供应商
- **可移植**：支持开发热重载、Docker 部署、Electron 桌面分发三种形态
- **E2E 覆盖**：Playwright 测试关键用户路径

---

## 7. 当前状态（2026-06）

- MVP 已跑通完整学习闭环
- `specs/system-fix/` 列出 11 项缺陷修复（数据完整性 / 算法准确性 / 资源管理 / 可靠性）
- 后续路线：见 `specs/system-fix/tasks.md`
