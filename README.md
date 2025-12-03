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
   该命令会根据 `pyproject.toml` 解析并安装符合约束的最新依赖。仓库不再提交 `uv.lock`，以避免固定版本；uv 会在本地生成临时锁文件用于本次安装。

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
如果无法使用 uv，可直接 `pip install -r requirements.txt`。该文件同样只声明上游依赖的宽松版本范围，pip 会自动解析所需的间接依赖。建议仍然使用虚拟环境（如 `python -m venv .venv && source .venv/bin/activate`）。

## 目录结构
- `weibospider/`：Scrapy 项目及爬虫实现
- `output/`：抓取结果（已在 `.gitignore` 中忽略）

## 常见问题
- **Cookie 403**：如果请求被拒绝，请更新 `cookie.txt`。
- **时间窗口**：关键词模式默认在 `spiders/tweet_by_keyword.py` 中定义关键词及时间段，可根据需要修改。
- **代理/中间件**：`middlewares.IPProxyMiddleware` 需要你自行实现代理逻辑。

## 代理与 Cookie 池配置
- 将 5 个账号的完整 Cookie 写入 `weibospider/cookies.json`（一行一个对象，示例已给出）。
- 代理配置写入 `weibospider/proxy_config.json`，当前示例已填入星辰隧道域名/端口和用户名密码，可按需替换。
- 中间件 `AccountSessionMiddleware` 会为每个账号绑定一个代理，默认 30 分钟更新；401/403 连续超过 10 次进入 5 分钟冷却，3 轮后永久下线并记录日志。
- 重要：`proxy_config.json` 和 `cookies.json` 含敏感信息，可自行加入 `.gitignore`，避免提交到远端。
