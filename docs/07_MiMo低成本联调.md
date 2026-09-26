# MiMo 低成本联调方案

更新：2026-09-26。开发目录统一为 `E:\WorkSpace_agent\innovation-scout`。

## 选型结论

首版选 `mimo-v2.6-flash` 作为查询规划、摘要和报告生成的主模型，先关闭深度思考。官方列出 OpenAI 兼容接口、流式响应、工具调用和结构化输出，适合接入现有 GPT Researcher。能否达到论文分析、出处忠实性和企业需求匹配要求，需要用实际案例验证；价格和接口兼容不能代替质量验收。

固定使用按量付费接口 `https://api.xiaomimimo.com/v1`。代码里的 `openai:` 表示兼容协议，实际请求发送给小米；需要 MiMo 按量付费 API Key。Token Plan 使用独立 Key 和入口，不要混填。

| 用途 | 首版配置 |
| --- | --- |
| FAST / SMART / STRATEGIC 三类分析 | 全部使用 `mimo-v2.6-flash` |
| 深度思考 | 显式关闭，避免默认开启导致额外推理及工具历史回传问题 |
| 文本向量化 | CPU 上运行 FastEmbed + `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| 论文来源 | OpenAlex；建议申请免费 Key，提高免费配额 |
| 搜索服务 | 本配置只使用 OpenAlex，不要求 Tavily 账户 |
| 报告 | 中文输出，先跑普通研究报告 |

没有把 MiMo 配置为向量服务：目前核对的官方说明未提供可用于本项目的 embeddings 接口。本地向量模型首次运行需要联网下载约 220 MB 模型及配套文件，下载目录为 `.cache/fastembed`，之后复用缓存；向量化不产生 API 账单，但占用本机 CPU、内存和磁盘。多语种模型的跨语言召回仍需验证。已用实际安装的 FastEmbed 支持列表核对模型名称，不使用该版本未注册的 E5-small。

## 价格与试用预算

以下为官方实时按量价格，单位为人民币 / 百万 token，核对日期见页首：

| 模型 | 输入：命中缓存 | 输入：未命中缓存 | 输出 |
| --- | ---: | ---: | ---: |
| MiMo V2.6 Flash | 0.02 | 1.00 | 2.00 |
| MiMo V2.6 Pro | 0.025 | 3.00 | 6.00 |

Pro 价格对应用户提供的官方价格截图；默认配置只启用已在线核实价格的 Flash。若一次研究累计输入 10 万 token、输出 1 万 token，Flash 模型费用约 **0.12 元**；100 次约 **12 元**，300 次约 **36 元**。这是未命中缓存、按假设用量计算的示例，不是实测单价，也不含服务器、数据接口、搜索、重试及人工费用。

初次按实际最低充值要求预留 20–50 元测试余额即可，不建议先购买高价套餐。配置限制查询轮次和输出长度；这些限制及 10 分钟 CLI 超时都不是金额硬上限。上游调用失败仍可能重试。批量推理的折扣需要另接 Batch API，当前流程不会自动享受批量价。

上游页面及 `research_costs` 的美元估算尚未适配 MiMo，不能作为小米账单。`probe` 会显示接口实际返回的 token 用量及 Flash 人民币估算，最终以小米控制台为准。

## 本地启动

需要 Python 3.12，在项目根目录执行。当前电脑的 `.venv` 使用独立环境，避免改动其他工程的 Python 包。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-mimo.txt
Copy-Item .env.example .env
```

如果 `.env` 已存在，保留原文件。仅在本地填写 `MIMO_API_KEY`，可选填写 `OPENALEX_API_KEY`；不要把密钥发到聊天或提交 Git。

```powershell
# 只显示配置和密钥是否存在，不发起付费请求
.\.venv\Scripts\python.exe scripts/mimo.py check

# 首次下载并验证本地 CPU 向量模型，不调用 MiMo
.\.venv\Scripts\python.exe scripts/mimo.py embeddings

# 两次小额 MiMo 请求：JSON 结构与来源 ID、流式响应和用量
.\.venv\Scripts\python.exe scripts/mimo.py probe

# 普通研究闭环；英文检索问题方便匹配国际论文，报告按配置用中文输出
.\.venv\Scripts\python.exe scripts/mimo.py research --query "Recent solid-state battery manufacturing challenges, with sources and evidence limitations"

# 上游轻量网页，访问 http://127.0.0.1:8000
.\.venv\Scripts\python.exe scripts/mimo.py serve
```

CLI 报告保存至根目录 `outputs/`；网页导出由上游保存至 `app/outputs/`。当前入口优先验证论文检索、阅读和报告，专利适配、每日监测、机会卡、企业需求匹配仍待开发。

`scripts/mimo.py` 会明确覆盖三类模型、API 地址、检索器及向量配置，避免继承旧环境中的 GPT/Tavily 默认项。无需改动上游默认配置。直接运行原 `app/main.py` 或原 Docker Compose 不会自动启用这套方案；请使用这里的入口。

## 验证与验收

2026-09-26 本机结果：Python 3.12.12 独立环境已安装，4 项离线兼容测试通过，`pip check` 通过，网页后端 `main` 导入成功。按用户要求暂不提供 Key，因此没有调用真实 MiMo API、生成真实研究报告或验收分析质量。本地向量模型尚未下载和实测推理，后续执行 `embeddings` 命令完成该项。

离线测试通过 HTTP MockTransport 检查真实 LangChain 适配器发出的地址、模型名、关闭思考参数、JSON 和流式协议，不会调用外部付费接口：

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest tests/test_mimo_profile.py -q
```

真实验证按顺序进行：密钥检查 → 两次小额接口验证 → 本地向量模型 → 一份真实论文报告。随后用 10 个固定问题评估来源可打开、结论有依据、不虚构实验条件、中文可读性、耗时和实际费用。离线通过只代表请求与响应处理兼容，不代表小米线上接口或报告质量已经验收。

## 官方依据

- [MiMo V2.6 Flash：能力、价格及接口示例](https://mimo.mi.com/models/en-US/mimo-v2.6-flash)
- [深度思考及工具调用历史回传要求](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/text-generation/deep-thinking)
- [结构化输出](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/text-generation/structured-output)
- [FastEmbed 模型说明](https://qdrant.github.io/fastembed/examples/Supported_Models/)
- [OpenAlex 接口费用与免费额度](https://help.openalex.org/access/pricing/)
