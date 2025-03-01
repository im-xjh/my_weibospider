import json
from scrapy import Spider
from scrapy.http import Request
from spiders.common import parse_user_info, parse_time, url_to_mid

class CommentSpider(Spider):
    """
    微博评论数据采集
    """
    name = "comment"

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
            url = f"https://weibo.com/ajax/statuses/buildComments?" \
                  f"is_reload=1&id={mid}&is_show_bulletin=2&is_mix=0&count=20"
            yield Request(url, callback=self.parse, meta={'source_url': url, 'mblogin': mblogin})

    def parse(self, response, **kwargs):
        """
        网页解析
        """
        mblogin = response.meta.get('mblogin')
        data = json.loads(response.text)
        for comment_info in data.get('data', []):
            item = self.parse_comment(comment_info)
            item['mblogin'] = mblogin  # 添加 mblogin 字段
            yield item
            # 解析二级评论
            if 'more_info' in comment_info:
                url = f"https://weibo.com/ajax/statuses/buildComments?is_reload=1&id={comment_info['id']}" \
                      f"&is_show_bulletin=2&is_mix=1&fetch_level=1&max_id=0&count=100"
                yield Request(url, callback=self.parse, priority=20, meta={'mblogin': mblogin})
        if data.get('max_id', 0) != 0 and 'fetch_level=1' not in response.url:
            url = response.meta['source_url'] + '&max_id=' + str(data['max_id'])
            yield Request(url, callback=self.parse, meta={'source_url': response.meta['source_url'], 'mblogin': mblogin})

    @staticmethod
    def parse_comment(data):
        """
        解析comment
        """
        item = dict()
        # item['mblogin'] 在 parse 方法中添加
        item['created_at'] = parse_time(data['created_at'])
        item['_id'] = data['id']
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
