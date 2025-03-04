import json
from scrapy import Spider
from scrapy.http import Request
from spiders.common import parse_user_info

class UserSpider(Spider):
    """
    微博用户信息爬虫
    """
    name = "user_spider"

    def __init__(self, ids_to_process=None, is_single=False, single_id=None, *args, **kwargs):
        super(UserSpider, self).__init__(*args, **kwargs)
        self.ids_to_process = ids_to_process or []
        self.is_single = is_single
        self.single_id = single_id

    def start_requests(self):
        if not self.ids_to_process:
            # 默认演示
            self.ids_to_process = ['6148092570']

        for user_id in self.ids_to_process:
            url = f'https://weibo.com/ajax/profile/info?uid={user_id}'
            yield Request(url, callback=self.parse, meta={'user_id': user_id})

    def parse(self, response, **kwargs):
        data = json.loads(response.text)
        user_data = data['data']['user']
        item = parse_user_info(user_data)

        # 让 pipeline 可以把它放最前
        item['user_id'] = item['_id']  # 这里把 _id 同步给 user_id

        detail_url = f"https://weibo.com/ajax/profile/detail?uid={item['_id']}"
        yield Request(detail_url, callback=self.parse_detail, meta={'item': item})

    @staticmethod
    def parse_detail(response):
        item = response.meta['item']
        data = json.loads(response.text).get('data', {})
        item['birthday'] = data.get('birthday', '')
        if 'created_at' not in item:
            item['created_at'] = data.get('created_at', '')
        item['desc_text'] = data.get('desc_text', '')
        item['ip_location'] = data.get('ip_location', '')
        item['sunshine_credit'] = data.get('sunshine_credit', {}).get('level', '')
        item['label_desc'] = [label['name'] for label in data.get('label_desc', [])] if 'label_desc' in data else []
        if 'company' in data:
            item['company'] = data['company']
        if 'education' in data:
            item['education'] = data['education']
        yield item