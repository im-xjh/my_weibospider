BOT_NAME = 'spider'

SPIDER_MODULES = ['spiders']
NEWSPIDER_MODULE = 'spiders'

ROBOTSTXT_OBEY = False

DEFAULT_REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:61.0) Gecko/20100101 Firefox/61.0',
    'Referer': 'https://weibo.com/',
}

CONCURRENT_REQUESTS = 100
# 单 IP/代理（单 Cookie+IP 绑定）并发上限；下载槽按账号+代理拆分
# 设为 0 关闭 IP 级别的全局并发限制，避免所有请求被同域名 IP 上限锁死
CONCURRENT_REQUESTS_PER_IP = 0
CONCURRENT_REQUESTS_PER_DOMAIN = 100
# 以每槽约 1.0s 间隔，单 Cookie+IP 约 60 条/分钟；若需 70，可调到 0.85
DOWNLOAD_DELAY = 0.7

DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.cookies.CookiesMiddleware': None,
    'scrapy.downloadermiddlewares.redirect.RedirectMiddleware': None,
    'middlewares.AccountSessionMiddleware': 90,
    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 95,
    # 可通过环境变量 DUMP_FULL_RESPONSE=1 开启全量响应调试
    'middlewares.FullResponseDumpMiddleware': 200,
}

ITEM_PIPELINES = {
    'pipelines.JsonWriterPipeline': 300,
}
