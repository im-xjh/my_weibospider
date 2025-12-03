import json
import os
import pathlib
import re
from scrapy import Spider
from scrapy.http import Request
from parsel import Selector
from spiders.common import parse_tweet_info, extract_longtext_from_mobile

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
        # 通过环境变量开启调试输出：DUMP_FULL_RESPONSE=1
        self.dump_responses = os.environ.get('DUMP_FULL_RESPONSE') == '1'
        if self.dump_responses:
            self.debug_dir = pathlib.Path(__file__).resolve().parent.parent / "output" / "debug_responses"
            self.debug_dir.mkdir(parents=True, exist_ok=True)

    def start_requests(self):
        if not self.ids_to_process:
            # 默认示例
            self.ids_to_process = ['QgxQFpdTh']

        for idx, mblogid in enumerate(self.ids_to_process):
            url = f"https://weibo.com/ajax/statuses/show?id={mblogid}&is_all=1&ajwvr=6"
            headers = {
                'Referer': 'https://weibo.com/',
                'X-Requested-With': 'XMLHttpRequest',
            }
            yield Request(
                url,
                callback=self.parse,
                meta={'mblogin': mblogid, 'debug_label': 'show_api'},
                headers=headers,
                priority=100000 - idx,
            )

    def parse(self, response, **kwargs):
        data = json.loads(response.text)
        item = parse_tweet_info(data)
        item['mblogin'] = response.meta.get('mblogin', '')
        # 直接尝试使用接口返回的长文本字段
        long_text = data.get('longText') or {}
        if isinstance(long_text, dict) and long_text.get('longTextContent'):
            item['content'] = long_text.get('longTextContent')
            item['longTextExpanded'] = True
        elif data.get('longTextContent'):
            item['content'] = data.get('longTextContent')
            item['longTextExpanded'] = True
        if self.dump_responses:
            self._dump_response(response, prefix="show")

        if item['isLongText'] and not item.get('longTextExpanded'):
            # 先尝试移动端 detail 页解析 render_data
            mobile_url = f"https://m.weibo.cn/detail/{item['mblogid']}"
            mobile_headers = {
                'Referer': 'https://m.weibo.cn/',
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
            }
            yield Request(
                mobile_url,
                callback=self.parse_longtext_mobile,
                meta={'item': item, 'debug_label': 'longtext_mobile'},
                headers=mobile_headers,
            )
        else:
            yield item

    def parse_longtext_api(self, response):
        if self.dump_responses:
            self._dump_response(response, prefix="longtext_api")
        data = json.loads(response.text).get('data', {})
        item = response.meta['item']
        if 'longTextContent' in data:
            item['content'] = data['longTextContent']
            item['longTextExpanded'] = True
        yield item

    def parse_longtext_mobile(self, response):
        if self.dump_responses:
            self._dump_response(response, prefix="longtext_mobile")
        item = response.meta['item']
        content = extract_longtext_from_mobile(response.text)
        if content:
            item['content'] = content
            item['longTextExpanded'] = True
            yield item
            return
        # 若移动端解析失败，继续尝试 PC HTML 兜底
        uid = item.get('user', {}).get('_id')
        if uid:
            detail_url = f"https://weibo.com/{uid}/{item['mblogid']}"
            yield Request(
                detail_url,
                callback=self.parse_longtext_html,
                meta={'item': item, 'debug_label': 'longtext_html'},
                headers={'Referer': detail_url},
            )
        else:
            url = "https://weibo.com/ajax/statuses/longtext?id=" + item['mblogid']
            yield Request(
                url,
                callback=self.parse_longtext_api,
                meta={'item': item, 'debug_label': 'longtext_api'},
            )

    def parse_longtext_html(self, response):
        if self.dump_responses:
            self._dump_response(response, prefix="longtext_html")
        item = response.meta['item']
        selector = Selector(response.text)
        text_nodes = selector.xpath(
            '//article//div[contains(@class,"RichText") or @node-type="feed_list_content_full"]//text()'
        ).getall()
        if not text_nodes:
            text_nodes = selector.xpath('//div[@node-type="feed_list_content"]//text()').getall()
        if text_nodes:
            item['content'] = ''.join(text_nodes).strip()
            item['longTextExpanded'] = True
        yield item

    def _dump_response(self, response, prefix: str):
        """将响应落地，便于排查（状态码 + headers + body）"""
        mblogid = response.meta.get('mblogin') or response.meta.get('item', {}).get('mblogid') or "unknown"
        filename = f"{prefix}_{mblogid}_{response.status}.txt"
        path = self.debug_dir / filename
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"URL: {response.url}\n")
                f.write(f"Status: {response.status}\n")
                f.write("Headers:\n")
                for k, v in response.headers.items():
                    key = k.decode('utf-8', 'ignore') if isinstance(k, (bytes, bytearray)) else str(k)
                    if isinstance(v, (list, tuple)):
                        for vv in v:
                            val = vv.decode('utf-8', 'ignore') if isinstance(vv, (bytes, bytearray)) else str(vv)
                            f.write(f"{key}: {val}\n")
                    else:
                        val = v.decode('utf-8', 'ignore') if isinstance(v, (bytes, bytearray)) else str(v)
                        f.write(f"{key}: {val}\n")
                f.write("\nBody:\n")
                f.write(response.text)
        except Exception as exc:
            self.logger.warning(f"[debug_dump] 写入响应失败: {exc}")
