import datetime
import json
import re
from scrapy import Spider, Request
from spiders.common import parse_tweet_info, extract_longtext_from_mobile

class TweetSpiderByKeyword(Spider):
    """
    关键词搜索采集
    保持原有逻辑与保存方式不变
    """
    name = "tweet_spider_by_keyword"
    base_url = "https://s.weibo.com/"

    def start_requests(self):
        keywords = ["封存"]
        start_time = datetime.datetime(year=2025, month=11, day=29, hour=23)
        end_time = datetime.datetime(year=2025, month=12, day=3, hour=0)
        is_split_by_hour = True

        for keyword in keywords:
            if not is_split_by_hour:
                _start_time = start_time.strftime("%Y-%m-%d-%H")
                _end_time = end_time.strftime("%Y-%m-%d-%H")
                url = f"https://s.weibo.com/weibo?q={keyword}&timescope=custom%3A{_start_time}%3A{_end_time}&page=1"
                yield Request(url, callback=self.parse, meta={'keyword': keyword})
            else:
                time_cur = start_time
                while time_cur < end_time:
                    _start_time = time_cur.strftime("%Y-%m-%d-%H")
                    _end_time = (time_cur + datetime.timedelta(hours=1)).strftime("%Y-%m-%d-%H")
                    url = f"https://s.weibo.com/weibo?q={keyword}&timescope=custom%3A{_start_time}%3A{_end_time}&page=1"
                    yield Request(url, callback=self.parse, meta={'keyword': keyword})
                    time_cur = time_cur + datetime.timedelta(hours=1)

    def parse(self, response, **kwargs):
        html = response.text
        if '<p>抱歉，未找到相关结果。</p>' in html:
            self.logger.info(f'no search result. url: {response.url}')
            return
        tweets_infos = re.findall(r'<div class="from"\s+>(.*?)</div>', html, re.DOTALL)
        for tweets_info in tweets_infos:
            tweet_ids = re.findall(r'weibo\.com/\d+/(.+?)\?refer_flag=1001030103_" ', tweets_info)
            for tweet_id in tweet_ids:
                url = f"https://weibo.com/ajax/statuses/show?id={tweet_id}&is_all=1&ajwvr=6"
                headers = {
                    'Referer': 'https://weibo.com/',
                    'X-Requested-With': 'XMLHttpRequest',
                }
                meta = dict(response.meta)
                meta['debug_label'] = 'show_api'
                yield Request(url, callback=self.parse_tweet, meta=meta, priority=10, headers=headers)

        next_page = re.search('<a href="(.*?)" class="next">下一页</a>', html)
        if next_page:
            url = "https://s.weibo.com" + next_page.group(1)
            yield Request(url, callback=self.parse, meta=response.meta)

    def parse_tweet(self, response):
        data = json.loads(response.text)
        item = parse_tweet_info(data)
        item['keyword'] = response.meta['keyword']
        # 优先使用接口返回的全文
        long_text = data.get('longText') or {}
        if isinstance(long_text, dict) and long_text.get('longTextContent'):
            item['content'] = long_text.get('longTextContent')
            item['isLongText'] = False
        elif data.get('longTextContent'):
            item['content'] = data.get('longTextContent')
            item['isLongText'] = False

        if item['isLongText']:
            mobile_url = f"https://m.weibo.cn/detail/{item['mblogid']}"
            headers = {
                'Referer': 'https://m.weibo.cn/',
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
            }
            yield Request(
                mobile_url,
                callback=self.parse_longtext_mobile,
                meta={'item': item, 'debug_label': 'longtext_mobile'},
                headers=headers,
                priority=20
            )
        else:
            yield item

    def parse_longtext_mobile(self, response):
        item = response.meta['item']
        content = extract_longtext_from_mobile(response.text)
        if content:
            item['content'] = content
            item['isLongText'] = False
        yield item
