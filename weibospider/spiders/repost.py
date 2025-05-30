import json
from scrapy import Spider
from scrapy.http import Request
from spiders.common import parse_tweet_info, url_to_mid

class RepostSpider(Spider):
    """
    微博转发数据采集
    """
    name = "repost"

    def __init__(self, ids_to_process=None, is_single=False, single_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ids_to_process = ids_to_process or []
        self.is_single = is_single
        self.single_id = single_id

    def start_requests(self):
        if not self.ids_to_process:
            self.ids_to_process = ["P5IUOlOur"]  # 仅示例

        for mblogid in self.ids_to_process:
            mid = url_to_mid(mblogid)
            url = f"https://weibo.com/ajax/statuses/repostTimeline?id={mid}&page=1&moduleID=feed&count=10"
            yield Request(url, callback=self.parse, meta={'page_num': 1, 'mid': mid, 'mblogin': mblogid})

    def parse(self, response, **kwargs):
        mblogin = response.meta.get('mblogin')
        data = json.loads(response.text)
        for tweet in data.get('data', []):
            item = parse_tweet_info(tweet)
            item['mblogin'] = mblogin
            yield item

        # 翻页
        if data.get('data'):
            mid, page_num = response.meta['mid'], response.meta['page_num']
            page_num += 1
            url = f"https://weibo.com/ajax/statuses/repostTimeline?id={mid}&page={page_num}&moduleID=feed&count=10"
            yield Request(url, callback=self.parse, meta={'page_num': page_num, 'mid': mid, 'mblogin': mblogin})