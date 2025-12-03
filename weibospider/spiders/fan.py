import json
from scrapy import Spider
from scrapy.http import Request
from spiders.comment import parse_user_info

class FanSpider(Spider):
    """
    微博粉丝数据采集
    """
    name = "fan"
    base_url = 'https://weibo.com/ajax/friendships/friends'

    def __init__(self, ids_to_process=None, is_single=False, single_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ids_to_process = ids_to_process or []
        self.is_single = is_single
        self.single_id = single_id

    def start_requests(self):
        if not self.ids_to_process:
            # 默认单个示例
            self.ids_to_process = ['6148092570']

        for idx, user_id in enumerate(self.ids_to_process):
            url = f"{self.base_url}?relate=fans&page=1&uid={user_id}&type=fans"
            yield Request(url, callback=self.parse, meta={'user_id': user_id, 'page_num': 1}, priority=100000 - idx)

    def parse(self, response, **kwargs):
        data = json.loads(response.text)
        user_id = response.meta['user_id']
        for user in data.get('users', []):
            item = dict()
            # 这里为了让 pipeline 能将它放到最前，可命名为 user_id
            item['user_id'] = user_id
            item['fan_info'] = parse_user_info(user)
            item['_id'] = user_id + '_' + item['fan_info']['_id']
            yield item

        if data.get('users'):
            page_num = response.meta['page_num'] + 1
            url = f"{self.base_url}?relate=fans&page={page_num}&uid={user_id}&type=fans"
            yield Request(url, callback=self.parse, meta={'user_id': user_id, 'page_num': page_num})
