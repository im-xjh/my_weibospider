import json
from scrapy import Spider
from scrapy.http import Request
from spiders.common import parse_tweet_info, parse_long_tweet

class TweetSpiderByTweetID(Spider):
    """
    根据微博 mblogid 抓取推文详细
    """
    name = "tweet_spider_by_tweet_id"

    def __init__(self, ids_to_process=None, is_single=False, single_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ids_to_process = ids_to_process or []
        self.is_single = is_single
        self.single_id = single_id

    def start_requests(self):
        if not self.ids_to_process:
            # 默认示例
            self.ids_to_process = ['Q2UHevp3r']

        for mblogid in self.ids_to_process:
            url = f"https://weibo.com/ajax/statuses/show?id={mblogid}"
            yield Request(url, callback=self.parse, meta={'mblogin': mblogid})

    def parse(self, response, **kwargs):
        data = json.loads(response.text)
        item = parse_tweet_info(data)
        # 在此放上 mblogin
        item['mblogin'] = response.meta.get('mblogin', '')
        if item['isLongText']:
            url = "https://weibo.com/ajax/statuses/longtext?id=" + item['mblogid']
            yield Request(url, callback=parse_long_tweet, meta={'item': item})
        else:
            yield item