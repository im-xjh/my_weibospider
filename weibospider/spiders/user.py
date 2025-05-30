# user.py
import json
from scrapy import Spider
from scrapy.http import Request
from spiders.common import parse_user_info

class UserSpider(Spider):
    """
    微博用户信息爬虫
    支持：
    - 外部传入 user_id 列表
    - 外部传入 mblogid 列表（先抓取微博详情获取发布者 user_id）
    """
    name = "user"

    def __init__(self, ids_to_process=None, is_single=False, single_id=None, *args, **kwargs):
        super(UserSpider, self).__init__(*args, **kwargs)
        self.ids_to_process = ids_to_process or []
        self.is_single = is_single
        self.single_id = single_id

    def start_requests(self):
        # 若外部未指定，则使用默认示例 user_id
        if not self.ids_to_process:
            self.logger.info("No IDs provided, using example user ID.")
            self.ids_to_process = ['6148092570']

        for identifier in self.ids_to_process:
            # 如果 identifier 包含字母，视为微博 mblogid，先抓微博详情获取 user_id
            if any(c.isalpha() for c in identifier):
                tweet_url = f"https://weibo.com/ajax/statuses/show?id={identifier}"
                yield Request(tweet_url, callback=self.parse_tweet, meta={'mblogid': identifier})
            else:
                # 纯数字，直接当 user_id 处理
                profile_url = f"https://weibo.com/ajax/profile/info?uid={identifier}"
                yield Request(profile_url, callback=self.parse_profile, meta={'user_id': identifier})

    def parse_tweet(self, response):
        """
        解析微博详情，获取嵌套 user 信息后，继续抓取用户 profile
        """
        try:
            data_json = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.warning(f"Invalid JSON for mblogid {response.meta.get('mblogid')}")
            return

        user_data = data_json.get('user')
        if not user_data:
            self.logger.warning(f"No 'user' block in tweet {response.meta.get('mblogid')}")
            return

        uid = str(user_data.get('id') or user_data.get('idstr') or '')
        if not uid:
            self.logger.warning(f"Could not extract user ID from tweet {response.meta.get('mblogid')}")
            return

        # 继续抓取用户 profile
        profile_url = f"https://weibo.com/ajax/profile/info?uid={uid}"
        yield Request(profile_url, callback=self.parse_profile, meta={'user_id': uid})

    def parse_profile(self, response):
        """
        解析用户基本信息
        """
        try:
            data_json = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.warning(f"Invalid JSON for user_id {response.meta.get('user_id')}")
            return

        user_block = data_json.get('data', {})
        if not user_block or 'user' not in user_block:
            self.logger.warning(
                f"Missing 'data.user' for user_id {response.meta.get('user_id')}\n"
                f"{response.text[:100]}..."
            )
            return

        user_data = user_block['user']
        item = parse_user_info(user_data)
        item['user_id'] = item.get('_id', response.meta.get('user_id', ''))

        # 请求详情补充
        detail_url = f"https://weibo.com/ajax/profile/detail?uid={item['user_id']}"
        yield Request(detail_url, callback=self.parse_detail, meta={'item': item})

    @staticmethod
    def parse_detail(response):
        """
        解析用户详情页，补充字段
        """
        item = response.meta['item']
        try:
            data_json = json.loads(response.text)
        except json.JSONDecodeError:
            return

        data_detail = data_json.get('data', {})
        item['birthday'] = data_detail.get('birthday', '')
        item.setdefault('created_at', data_detail.get('created_at', ''))
        item['desc_text'] = data_detail.get('desc_text', '')
        item['ip_location'] = data_detail.get('ip_location', '')
        item['sunshine_credit'] = data_detail.get('sunshine_credit', {}).get('level', '')
        item['label_desc'] = [lbl.get('name', '') for lbl in data_detail.get('label_desc', [])]
        if 'company' in data_detail:
            item['company'] = data_detail['company']
        if 'education' in data_detail:
            item['education'] = data_detail['education']
        yield item
