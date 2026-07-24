# 🧠 AI 产品团队 —— 多 Agent 自动 PRD 系统

甩一句模糊需求进去，4 个 AI 角色分工协作，帮你反问澄清、联网调研竞品、
写出一份能直接发给开发团队的专业 PRD（产品需求文档）。

## 它是怎么工作的

```
你打一句「我想做个帮宠物主人记疫苗的 APP」
        ↓
🎯 需求分析师  反问你几个关键问题        ← 关口①：你回答
        ↓
📋 整理出「需求简报」交你审阅/编辑/确认   ← 关口②：你说了算，确认才继续
        ↓ ─────── 以下是耗时环节，确认后才启动 ───────
🔍 市场调研员  联网查竞品、市场、现有方案
        ↓
✍️ 产品经理    写出完整 PRD（功能清单、用户故事、验收标准、P0/P1/P2）
        ↓
🕵️ 评审专家    打分挑毛病，不合格自动打回返修
        ↓
交付：可下载的 Markdown 版 PRD
```

**两个由你把关的关口**：不会闷头跑偏。信息不够会先问你；简报没经你确认，
绝不进入又慢又费 token 的调研与撰写环节。

## 快速开始

### 1. 装依赖

项目自带独立虚拟环境 `.venv`（和你电脑上其它 Python 项目隔离，互不干扰）。
依赖已装好。如需重装：

```powershell
# 用国内清华源，快
.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 配置 API Key

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`，至少填一个大模型的 key。**推荐 DeepSeek**（国产、免翻墙、便宜）：

```
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你在 platform.deepseek.com 申请的key
```

联网搜索是**可选**的。不填也能跑（调研会标注"基于已有知识"）；
想要真实竞品数据就填一个：

```
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=你的key          # 免费额度每月 1000 次，tavily.com
```

### 3. 打开网页

```powershell
.venv\Scripts\streamlit run app.py
```

浏览器会自动打开，像聊天一样用即可。

## 支持的模型

改 `.env` 里的 `LLM_PROVIDER` 一行就能换家，代码不用动：

| provider | 是谁 | 默认模型 | key 申请 |
|----------|------|----------|----------|
| `deepseek` | DeepSeek（推荐） | deepseek-chat | platform.deepseek.com |
| `dashscope` | 阿里通义千问 | qwen-plus | dashscope.aliyun.com |
| `zhipu` | 智谱 GLM | glm-4-flash | open.bigmodel.cn |
| `moonshot` | Kimi | moonshot-v1-8k | platform.moonshot.cn |
| `openai` | OpenAI | gpt-4o-mini | 需自备网络 |

## 常用调整

`.env` 里的可选项：

| 配置 | 作用 | 默认 |
|------|------|------|
| `PRD_PASS_SCORE` | PRD 评审合格线，达不到自动返修 | 80 |
| `MAX_REVISION_ROUNDS` | 最多返修几轮 | 2 |
| `MAX_CLARIFY_ROUNDS` | 澄清最多问几轮 | 2 |

想调 AI 的说话风格或 PRD 结构，改 `prompts/` 里对应角色的文件即可。

## 项目结构

```
MultipleAgent/
├── app.py            # 网页界面（Streamlit）
├── graph.py          # 流水线编排（4 角色 + 两个人工关口 + 返修循环）
├── state.py          # 4 个 AI 共享的工作记忆
├── config.py         # 配置与模型工厂（切换模型的地方）
├── agents/           # 4 个 AI 角色
│   ├── clarifier.py  #   需求分析师（澄清 + 简报）
│   ├── researcher.py #   市场调研员（联网调研）
│   ├── writer.py     #   产品经理（撰写 PRD）
│   ├── reviewer.py   #   评审专家（打分返修）
│   └── common.py     #   公共小工具（调模型、解析 JSON）
├── prompts/          # 各角色的"岗位说明书"（提示词）
├── tools/search.py   # 联网搜索（可切换 Tavily/博查 + 优雅降级）
└── tests/            # 测试（用假数据测逻辑，不烧 API 钱）
```

## 跑测试

```powershell
.venv\Scripts\python.exe -m pytest
```

测试只覆盖不花钱的确定性逻辑（JSON 解析、状态、搜索降级、配置、路由）。
真正调用大模型的部分需要配好 key 后在网页里实测。

## 常见问题

**Q：没配搜索 key 能用吗？**
能。调研阶段会自动降级为"基于已有知识"，并在文档里注明未联网核实。

**Q：一次生成大概花多少钱？**
用 DeepSeek 的话，一份 PRD 通常几分钱到一两毛，取决于返修轮数。

**Q：生成卡在"调研与撰写"很久？**
正常。这一步要联网 + 多次调用大模型 + 可能返修，耐心等一两分钟。
