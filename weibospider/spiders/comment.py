import json
from urllib.parse import urlencode

from scrapy import Spider
from scrapy.http import Request

from spiders.common import parse_user_info, parse_time, url_to_mid


class CommentSpider(Spider):
    """
    微博评论数据采集
    """

    name = "comment"

    def __init__(self, ids_to_process=None, is_single=False, single_id=None, flow=0, *args, **kwargs):
        """
        :param ids_to_process: 外部文件传入的 mblogid 列表
        :param is_single: 是否只有单个ID
        :param single_id: 单个ID的值（若 is_single=True，则可用 single_id）
        :param flow: 评论排序模式（0=热度，1=按时间；首条请求不携带 flow）
        """
        super().__init__(*args, **kwargs)
        self.ids_to_process = ids_to_process or []
        self.is_single = is_single
        self.single_id = single_id
        self.flow = 1 if str(flow) == "1" else 0
        self.seen_comment_ids = {}
        self.last_max_id = {}

    def start_requests(self):
        # 如果外部没传IDs，就走内部预设
        if not self.ids_to_process:
            # 这里给一个演示用途的 mblogid
            self.ids_to_process = [""]  # 举例

        for mblogid in self.ids_to_process:
            mblogid = (mblogid or "").strip()
            if not mblogid:
                self.logger.warning("跳过空的 mblogid 目标")
                continue
            mid = url_to_mid(mblogid)
            referer = self._build_referer(mblogid)
            meta = {
                'mblogin': mblogid,
                'target_id': mid,
                'fetch_level': 0,
                'referer': referer,
            }
            yield self._build_comment_request(
                target_id=mid,
                fetch_level=0,
                include_flow=False,
                meta=meta,
            )

    def parse(self, response, **kwargs):
        mblogin = response.meta.get('mblogin')
        fetch_level = response.meta.get('fetch_level', 0)
        data = json.loads(response.text)
        target_id = response.meta.get('target_id')
        key = (mblogin, target_id, fetch_level)
        seen_ids = self.seen_comment_ids.setdefault(key, set())
        new_found = 0

        for comment_info in data.get('data', []):
            comment_id = comment_info.get('id')
            if comment_id in seen_ids:
                continue
            seen_ids.add(comment_id)
            new_found += 1
            item = self.parse_comment(comment_info)
            # 为了在 pipeline 中能将其置于最前面，我们这里就直接命名为 mblogin
            item['mblogin'] = mblogin
            yield item

            # 解析二级评论
            if 'more_info' in comment_info:
                child_meta = {
                    'mblogin': mblogin,
                    'target_id': comment_info['id'],
                    'fetch_level': 1,
                    'referer': response.meta.get('referer'),
                }
                yield self._build_comment_request(
                    target_id=comment_info['id'],
                    fetch_level=1,
                    include_flow=False,
                    meta=child_meta,
                    priority=20,
                )

        if new_found == 0:
            return

        # 翻页
        max_id = data.get('max_id', 0)
        if max_id:
            max_id_str = str(max_id)
            last_key = (mblogin, fetch_level, target_id)
            if self.last_max_id.get(last_key) == max_id_str:
                return
            self.last_max_id[last_key] = max_id_str
            next_meta = {
                'mblogin': mblogin,
                'target_id': target_id,
                'fetch_level': fetch_level,
                'referer': response.meta.get('referer'),
            }
            yield self._build_comment_request(
                target_id=target_id,
                fetch_level=fetch_level,
                include_flow=True,
                meta=next_meta,
                max_id=max_id,
                max_id_type=data.get('max_id_type', 0),
            )

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

    def _build_comment_request(self, target_id, fetch_level, include_flow, meta, max_id=0, max_id_type=0, priority=0):
        params = {
            'is_reload': 1,
            'id': target_id,
            'is_show_bulletin': 2,
            'is_mix': 1 if fetch_level else 0,
            'count': 20,
            'fetch_level': fetch_level,
        }
        if include_flow:
            params['flow'] = self.flow
        if max_id:
            params['max_id'] = max_id
            params['max_id_type'] = max_id_type
        url = f"https://weibo.com/ajax/statuses/buildComments?{urlencode(params)}"

        headers = self._build_headers(meta.get('referer'))
        request_meta = {
            'mblogin': meta.get('mblogin'),
            'target_id': target_id,
            'fetch_level': fetch_level,
            'referer': meta.get('referer'),
        }
        return Request(
            url,
            callback=self.parse,
            headers=headers,
            meta=request_meta,
            dont_filter=True,
            priority=priority,
        )

    @staticmethod
    def _build_headers(referer):
        headers = {
            'Referer': referer or 'https://weibo.com/',
            'X-Requested-With': 'XMLHttpRequest',
        }
        return headers

    @staticmethod
    def _build_referer(mblogid):
        if not mblogid:
            return 'https://weibo.com/'
        return f"https://weibo.com/{mblogid}"
