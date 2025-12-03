BOT_NAME = 'spider'

SPIDER_MODULES = ['spiders']
NEWSPIDER_MODULE = 'spiders'

ROBOTSTXT_OBEY = False

DEFAULT_REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:61.0) Gecko/20100101 Firefox/61.0',
    'Referer': 'https://weibo.com/',
}

CONCURRENT_REQUESTS = 50
# 单 IP/代理（单 Cookie+IP 绑定）并发上限
CONCURRENT_REQUESTS_PER_IP = 10
CONCURRENT_REQUESTS_PER_DOMAIN = 50
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
