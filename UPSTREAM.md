# 上游代码记录

- 项目：[assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)
- 导入日期：2026-09-24
- 固定提交：`6f998577d547b1e54ec662dac63583aa11e3b84b`
- 导入方式：`git subtree add --prefix=app upstream/main --squash`
- 上游遥控仓库：`upstream = https://github.com/assafelovic/gpt-researcher.git`
- 原有源码、README、许可证和版权标记保存在 [`app/`](app/README.md)。

新增业务功能优先放独立模块，需要动原模块时附测试和上游同步说明。

## 本地改动

- 2026-09-26：`app/gpt_researcher/memory/embeddings.py` 增加 `fastembed` 提供方，复用 LangChain 的 FastEmbedEmbeddings，在 CPU 上运行多语种向量模型。目的是让 MiMo 联调不依赖 OpenAI 向量 API。原有提供方分支保持原行为，文件已标明修改来源。
- 根目录 `configs/mimo-flash.json`、`scripts/mimo.py` 和 `requirements-mimo.txt` 为本项目新增。用独立入口选择 MiMo，不改上游默认模型。
- 兼容性验证见 `tests/test_mimo_profile.py` 和 `docs/07_MiMo低成本联调.md`。更新上游时检查向量提供方注册和 LangChain 请求序列化行为。

更新前先评估许可证、依赖及上游差异，使用独立分支验证后再合并；命令见[架构说明](docs/02_技术架构与数据.md)。

**许可证待核**：根 [`app/LICENSE`](app/LICENSE) 为 Apache-2.0，根 [`app/pyproject.toml`](app/pyproject.toml)标记 MIT。对外分发或商用前，确认上游对源码和发行包的许可声明。项目先保留所有原有标记。

首次导入时的静态检查：`docker compose -f app/docker-compose.yml config --quiet` 通过。2026-09-26 起采用项目根目录的 Python 3.12 `.venv` 开发 MiMo 配置。原 Docker Compose 尚未加入本项目 MiMo 启动入口，请按联调文档运行。
