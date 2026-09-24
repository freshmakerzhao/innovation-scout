# 上游代码记录

- 项目：[assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)
- 导入日期：2026-09-24
- 固定提交：`6f998577d547b1e54ec662dac63583aa11e3b84b`
- 导入方式：`git subtree add --prefix=app upstream/main --squash`
- 上游遥控仓库：`upstream = https://github.com/assafelovic/gpt-researcher.git`
- 原有源码、README、许可证和版权标记保存在 [`app/`](app/README.md)。

当前未修改上游源码。新增业务功能优先放 `app/pilot_ext/`，需要动原模块时附测试和上游同步说明。

更新前先评估许可证、依赖及上游差异，使用独立分支验证后再合并；命令见[架构说明](docs/02_技术架构与数据.md)。

**许可证待核**：根 [`app/LICENSE`](app/LICENSE) 为 Apache-2.0，根 [`app/pyproject.toml`](app/pyproject.toml)标记 MIT。对外分发或商用前，确认上游对源码和发行包的许可声明。项目先保留所有原有标记。

本机静态检查：`docker compose -f app/docker-compose.yml config --quiet` 通过；未提供模型密钥，尚未构建容器或运行研究。默认 `python` 为 3.10.10，不满足上游 `>=3.11`；已有另一套 Python 3.11.15 可用，但该环境缺 pytest。项目开发时需创建独立的 Python 3.11+ 环境并安装上游依赖。
