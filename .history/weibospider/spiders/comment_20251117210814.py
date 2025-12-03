import json
from scrapy import Spider
from scrapy.http import Request
from spiders.common import parse_user_info, parse_time, url_to_mid

class CommentSpider(Spider):
    """
    微博评论数据采集
    """
    name = "comment"

    def __init__(self, ids_to_process=None, is_single=False, single_id=None, *args, **kwargs):
        """
        :param ids_to_process: 外部文件传入的 mblogid 列表
        :param is_single: 是否只有单个ID
        :param single_id: 单个ID的值（若 is_single=True，则可用 single_id）
        """
        super().__init__(*args, **kwargs)
        self.ids_to_process = ids_to_process or []
        self.is_single = is_single
        self.single_id = single_id

    def start_requests(self):
        # 如果外部没传IDs，就走内部预设
        if not self.ids_to_process:
            # 这里给一个演示用途的 mblogid
            self.ids_to_process = ["LbtQJvlnQ"]  # 举例,"","",""

        for mblogid in self.ids_to_process:
            mid = url_to_mid(mblogid)
            base_url = (
                f"https://weibo.com/ajax/statuses/buildComments?"
                f"is_reload=1&id={mid}&is_show_bulletin=2&is_mix=0&count=20&max_id_type=0"
            )
            url = f"{base_url}&max_id=0"
            yield Request(url, callback=self.parse, meta={'base_url': base_url, 'mblogin': mblogid})

    def parse(self, response, **kwargs):
        mblogin = response.meta.get('mblogin')
        data = json.loads(response.text)
        for comment_info in data.get('data', []):
            item = self.parse_comment(comment_info)
            # 为了在 pipeline 中能将其置于最前面，我们这里就直接命名为 mblogin
            item['mblogin'] = mblogin
            yield item

            # 解析二级评论
            if 'more_info' in comment_info:
                url = (
                    f"https://weibo.com/ajax/statuses/buildComments?is_reload=1&id={comment_info['id']}"
                    f"&is_show_bulletin=2&is_mix=1&fetch_level=1&max_id=0&count=100"
                )
                yield Request(url, callback=self.parse, priority=20, meta={'mblogin': mblogin})

        # 翻页
        if 'fetch_level=1' not in response.url:
            max_id = data.get('max_id', 0)
            if max_id:
                max_id_type = data.get('max_id_type', 0)
                base_url = response.meta.get('base_url') or response.url.split('&max_id=')[0]
                next_url = f"{base_url}&max_id={max_id}&max_id_type={max_id_type}"
                yield Request(next_url, callback=self.parse, meta={'base_url': base_url, 'mblogin': mblogin})

    @staticmethod
    def parse_comment(data):
        item = dict()
        item['_id'] = data['id']
        item['created_at'] = parse_time(data['created_at'])
        item['like_counts'] = data['like_counts']
        item['ip_location'] = data.get('source', '')
        item['content'] = data['text_raw']
        item['comment_user'] = parse_user_info(data['user'])
        if 'reply_comment' in data:
            item['reply_comment'] = {
                '_id': data['reply_comment']['id'],
                'text': data['reply_comment']['text'],
                'user': parse_user_info(data['reply_comment']['user']),
            }
        return item
