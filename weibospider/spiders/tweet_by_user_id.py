import datetime
import json
from scrapy import Spider
from scrapy.http import Request
from spiders.common import parse_tweet_info, parse_long_tweet

class TweetSpiderByUserID(Spider):
    """
    用户推文数据采集
    """
    name = "tweet_spider_by_user_id"

    def __init__(self, ids_to_process=None, is_single=False, single_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ids_to_process = ids_to_process or []
        self.is_single = is_single
        self.single_id = single_id

    def start_requests(self):
        # 若外部无传入，则仅示例一个 ID
        if not self.ids_to_process:
            self.ids_to_process = ['6148092570']

        # 这里的时间仅做示例
        is_crawl_specific_time_span = True
        start_time = datetime.datetime(year=2022, month=1, day=1)
        end_time = datetime.datetime(year=2023, month=1, day=1)

        for user_id in self.ids_to_process:
            url = f"https://weibo.com/ajax/statuses/searchProfile?uid={user_id}&page=1&hasori=1&hastext=1&haspic=1&hasvideo=1&hasmusic=1&hasret=1"
            if not is_crawl_specific_time_span:
                yield Request(url, callback=self.parse, meta={'user_id': user_id, 'page_num': 1})
            else:
                tmp_start_time = start_time
                while tmp_start_time <= end_time:
                    tmp_end_time = tmp_start_time + datetime.timedelta(days=10)
                    tmp_end_time = min(tmp_end_time, end_time)
                    tmp_url = url + f"&starttime={int(tmp_start_time.timestamp())}&endtime={int(tmp_end_time.timestamp())}"
                    yield Request(tmp_url, callback=self.parse, meta={'user_id': user_id, 'page_num': 1})
                    tmp_start_time = tmp_end_time + datetime.timedelta(days=1)

    def parse(self, response, **kwargs):
        data = json.loads(response.text)
        if 'data' not in data or 'list' not in data['data']:
            return
        tweets = data['data']['list']
        for tweet in tweets:
            item = parse_tweet_info(tweet)
            # 这里演示移除 user 信息后再yield
            if 'user' in item:
                del item['user']
            if item['isLongText']:
                url = "https://weibo.com/ajax/statuses/longtext?id=" + item['mblogid']
                yield Request(url, callback=parse_long_tweet, meta={'item': item})
            else:
                yield item

        if tweets:
            user_id = response.meta['user_id']
            page_num = response.meta['page_num'] + 1
            next_url = response.url.replace(f"page={response.meta['page_num']}", f"page={page_num}")
            yield Request(next_url, callback=self.parse, meta={'user_id': user_id, 'page_num': page_num})