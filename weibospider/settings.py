BOT_NAME = 'spider'

SPIDER_MODULES = ['spiders']
NEWSPIDER_MODULE = 'spiders'

ROBOTSTXT_OBEY = False

# 读取 cookie.txt 并尝试提取 XSRF token
with open('cookie.txt', 'rt', encoding='utf-8') as f:
    cookie = f.read().strip()

xsrf_token = ""
for part in cookie.split(';'):
    part = part.strip()
    if part.startswith('XSRF-TOKEN='):
        xsrf_token = part.split('=', 1)[1]
        break

DEFAULT_REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:61.0) Gecko/20100101 Firefox/61.0',
    'Cookie': cookie,
    'Referer': 'https://weibo.com/',
}

if xsrf_token:
    DEFAULT_REQUEST_HEADERS['X-XSRF-TOKEN'] = xsrf_token

CONCURRENT_REQUESTS = 16
DOWNLOAD_DELAY = 0.7

DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.cookies.CookiesMiddleware': None,
    'scrapy.downloadermiddlewares.redirect.RedirectMiddleware': None,
    'middlewares.IPProxyMiddleware': 100,
    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 101,
}

ITEM_PIPELINES = {
    'pipelines.JsonWriterPipeline': 300,
}
