import json
from scrapy import Spider
from scrapy.http import Request
from spiders.common import parse_tweet_info, url_to_mid

class RepostSpider(Spider):
    """
    微博转发数据采集
    """
    name = "repost"

    def __init__(self, tweet_ids_file=None, mblogins_to_process=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tweet_ids_file = tweet_ids_file
        if mblogins_to_process:
            self.mblogins_to_process = mblogins_to_process
        else:
            self.mblogins_to_process = self.load_mblogins()

    def load_mblogins(self):
        # 从 tweet_ids_file 加载所有需要处理的 mblogin
        try:
            with open(self.tweet_ids_file, 'rt', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.logger.error(f"文件 {self.tweet_ids_file} 不存在！")
            return []

    def start_requests(self):
        """
        爬虫入口
        """
        for mblogin in self.mblogins_to_process:
            mid = url_to_mid(mblogin)
            url = f"https://weibo.com/ajax/statuses/repostTimeline?id={mid}&page=1&moduleID=feed&count=10"
            yield Request(url, callback=self.parse, meta={'page_num': 1, 'mid': mid, 'mblogin': mblogin})

    def parse(self, response, **kwargs):
        """
        网页解析
        """
        mblogin = response.meta.get('mblogin')
        data = json.loads(response.text)
        for tweet in data.get('data', []):
            item = parse_tweet_info(tweet)
            item['mblogin'] = mblogin  # 添加 mblogin 字段
            yield item
        if data.get('data'):
            mid, page_num = response.meta['mid'], response.meta['page_num']
            page_num += 1
            url = f"https://weibo.com/ajax/statuses/repostTimeline?id={mid}&page={page_num}&moduleID=feed&count=10"
            yield Request(url, callback=self.parse, meta={'page_num': page_num, 'mid': mid, 'mblogin': mblogin})
