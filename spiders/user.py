import json
from scrapy import Spider
from scrapy.http import Request
from spiders.common import parse_user_info


class UserSpider(Spider):
    """
    微博用户信息爬虫
    """
    name = "user_spider"

    def __init__(self, user_ids_file=None, *args, **kwargs):
        super(UserSpider, self).__init__(*args, **kwargs)
        self.user_ids_file = user_ids_file

    def start_requests(self):
        """
        爬虫入口
        """
        if self.user_ids_file:
            with open(self.user_ids_file, 'r', encoding='utf-8') as f:
                user_ids = json.load(f)
        else:
            # 如果未指定用户 ID 文件，使用默认的用户 ID 列表
            user_ids = ['']

        urls = [f'https://weibo.com/ajax/profile/info?uid={user_id}' for user_id in user_ids]
        for url in urls:
            yield Request(url, callback=self.parse)

    def parse(self, response, **kwargs):
        """
        解析用户基本信息
        """
        data = json.loads(response.text)
        item = parse_user_info(data['data']['user'])
        url = f"https://weibo.com/ajax/profile/detail?uid={item['_id']}"
        yield Request(url, callback=self.parse_detail, meta={'item': item})

    @staticmethod
    def parse_detail(response):
        """
        解析用户详细信息
        """
        item = response.meta['item']
        data = json.loads(response.text)['data']
        item['birthday'] = data.get('birthday', '')
        if 'created_at' not in item:
            item['created_at'] = data.get('created_at', '')
        item['desc_text'] = data.get('desc_text', '')
        item['ip_location'] = data.get('ip_location', '')
        item['sunshine_credit'] = data.get('sunshine_credit', {}).get('level', '')
        item['label_desc'] = [label['name'] for label in data.get('label_desc', [])]
        if 'company' in data:
            item['company'] = data['company']
        if 'education' in data:
            item['education'] = data['education']
        yield item