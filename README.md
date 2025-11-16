# Weibo Spider

该项目基于 Scrapy，支持按用户 ID、关键词、微博 ID 等多种方式抓取微博数据。本文档说明如何使用 [uv](https://docs.astral.sh/uv/latest/) 创建隔离环境，并提供 `requirements.txt` 以兼容其他包管理方式。

## 依赖与准备
- Python 3.10 或更高
- `uv` 命令行工具（若未安装，可通过 `curl -LsSf https://astral.sh/uv/install.sh | sh` 获取）
- 一个合法的 Weibo Cookie，写入 `weibospider/cookie.txt`

## 快速开始（推荐）
1. **同步依赖并创建虚拟环境**
   ```bash
   uv sync
   ```
   该命令会根据 `pyproject.toml` / `uv.lock` 创建 `.venv` 并安装 Scrapy、python-dateutil 等依赖。

2. **运行爬虫**
   在项目根目录执行：
   ```bash
   uv run python weibospider/run_spider.py <mode> [--user_ids_file path/to/file]
   ```
   例如按关键词抓取：
   ```bash
   uv run python weibospider/run_spider.py tweet_by_keyword
   ```

   `mode` 可选值包括 `tweet_by_keyword`、`tweet_by_user_id`、`tweet_by_tweet_id`、`comment`、`repost`、`fan`、`follower`、`user` 等。若某些模式需要批量 ID，可使用 `--user_ids_file` 指向 JSON 行文件（参考 `run_spider.py` 中的 `parse_external_file` 说明）。

3. **查看结果**
   数据默认写入 `output/` 目录下的 JSONL 文件。`tweet_spider_by_keyword` 始终按照时间命名，其它模式根据 `is_single` 与传入 ID 决定文件名。

## Pip / 其它环境
如果无法使用 uv，可直接 `pip install -r requirements.txt`。建议仍然使用虚拟环境（如 `python -m venv .venv && source .venv/bin/activate`）。

## 目录结构
- `weibospider/`：Scrapy 项目及爬虫实现
- `output/`：抓取结果（已在 `.gitignore` 中忽略）

## 常见问题
- **Cookie 403**：如果请求被拒绝，请更新 `cookie.txt`。
- **时间窗口**：关键词模式默认在 `spiders/tweet_by_keyword.py` 中定义关键词及时间段，可根据需要修改。
- **代理/中间件**：`middlewares.IPProxyMiddleware` 需要你自行实现代理逻辑。
