import datetime
import json
import re
from collections import defaultdict
from scrapy import Spider, Request
from spiders.common import parse_tweet_info, extract_longtext_from_mobile

class TweetSpiderByKeyword(Spider):
    """
    关键词搜索采集
    保持原有逻辑与保存方式不变
    """
    name = "tweet_spider_by_keyword"
    base_url = "https://s.weibo.com/"
    # 允许常见风控/错误状态进入回调，便于重试和推进后续时间段
    handle_httpstatus_list = [301, 302, 400, 401, 403, 404, 418, 429, 500, 502, 503, 504]
    max_search_retry = 3
    max_empty_retry = 3
    max_api_retry = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timescope_queues = {}
        self.scope_counts = defaultdict(int)

    def _build_timescopes(self, start_time, end_time, is_split_by_hour=True):
        scopes = []
        if not is_split_by_hour:
            scopes.append((start_time, end_time))
            return scopes
        time_cur = start_time
        while time_cur < end_time:
            next_time = min(end_time, time_cur + datetime.timedelta(hours=1))
            scopes.append((time_cur, next_time))
            time_cur = next_time
        return scopes

    def start_requests(self):
        keywords = ["封存"]
        start_time = datetime.datetime(year=2025, month=11, day=28, hour=12)
        end_time = datetime.datetime(year=2025, month=11, day=28, hour=13)
        is_split_by_hour = True

        for keyword in keywords:
            scopes = self._build_timescopes(start_time, end_time, is_split_by_hour)
            if not scopes:
                continue
            total = len(scopes)
            first_scope, rest = scopes[0], scopes[1:]
            self.timescope_queues[keyword] = list(rest)
            yield self._make_search_request(
                keyword,
                first_scope,
                page=1,
                scope_idx=0,
                total_scopes=total
            )

    def parse(self, response, **kwargs):
        if response.status >= 400:
            retry_req = self._retry_search_request(response.request, f"http_status={response.status}")
            if retry_req:
                yield retry_req
            else:
                yield from self._finish_and_advance(response.meta)
            return

        html = response.text
        current_scope = response.meta.get('current_scope')
        if '<p>抱歉，未找到相关结果。</p>' in html:
            self.logger.info(f'no search result. url: {response.url}')
            yield from self._finish_and_advance(response.meta)
            return
        tweets_infos = re.findall(r'<div class="from"\s+>(.*?)</div>', html, re.DOTALL)
        # 搜索结果最多50页，超过50页后页面为空，此时也应认为当前时间段结束
        if not tweets_infos:
            yield from self._handle_empty_search_page(response)
            return

        # 优先处理分页或下一个时间段的调度，确保主线任务不断
        next_page = re.search('<a href="(.*?)" class="next">下一页</a>', html)
        if next_page:
            url = "https://s.weibo.com" + next_page.group(1)
            meta = dict(response.meta)
            meta['page'] = response.meta.get('page', 1) + 1
            meta['search_retry_times'] = 0
            meta['empty_retry_times'] = 0
            yield Request(url, callback=self.parse, meta=meta, errback=self._handle_search_error)

        else:
            # 当前时间段结束
            yield from self._finish_and_advance(response.meta)

        # 处理当前页的微博
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
                yield Request(
                    url,
                    callback=self.parse_tweet,
                    meta=meta,
                    priority=10,
                    headers=headers,
                    errback=self._handle_api_error
                )

    def parse_tweet(self, response):
        if response.status >= 400:
            retry_req = self._retry_api_request(response.request, f"http_status={response.status}")
            if retry_req:
                yield retry_req
            return
        try:
            data = json.loads(response.text)
        except Exception as exc:
            retry_req = self._retry_api_request(response.request, f"json_error={exc}")
            if retry_req:
                yield retry_req
            return

        item = parse_tweet_info(data)
        item['keyword'] = response.meta['keyword']
        # 优先使用接口返回的全文
        long_text = data.get('longText') or {}
        if isinstance(long_text, dict) and long_text.get('longTextContent'):
            item['content'] = long_text.get('longTextContent')
            item['longTextExpanded'] = True
        elif data.get('longTextContent'):
            item['content'] = data.get('longTextContent')
            item['longTextExpanded'] = True

        if item['isLongText'] and not item.get('longTextExpanded'):
            mobile_url = f"https://m.weibo.cn/detail/{item['mblogid']}"
            headers = {
                'Referer': 'https://m.weibo.cn/',
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
            }
            yield Request(
                mobile_url,
                callback=self.parse_longtext_mobile,
                meta={**response.meta, 'item': item, 'debug_label': 'longtext_mobile', 'longtext_retry_times': 0},
                headers=headers,
                priority=20,
                errback=self._handle_longtext_error
            )
        else:
            self._inc_scope_count(response.meta)
            yield item

    def parse_longtext_mobile(self, response):
        if response.status >= 400:
            retry_req = self._retry_api_request(
                response.request,
                f"http_status={response.status}",
                retry_key='longtext_retry_times'
            )
            if retry_req:
                yield retry_req
            else:
                yield response.meta['item']
            return

        item = response.meta['item']
        content = extract_longtext_from_mobile(response.text)
        if content:
            item['content'] = content
            item['longTextExpanded'] = True
        self._inc_scope_count(response.meta)
        yield item

    # -------- helpers --------
    def _make_search_request(self, keyword, timescope, page=1, retry_times=0, scope_idx=0, total_scopes=None):
        _start_time = timescope[0].strftime("%Y-%m-%d-%H")
        _end_time = timescope[1].strftime("%Y-%m-%d-%H")
        url = f"https://s.weibo.com/weibo?q={keyword}&timescope=custom%3A{_start_time}%3A{_end_time}&page={page}&xsort=time"
        meta = {
            'keyword': keyword,
            'current_scope': timescope,
            'page': page,
            'search_retry_times': retry_times,
            'empty_retry_times': 0,
            'scope_idx': scope_idx,
            'total_scopes': total_scopes if total_scopes is not None else None,
        }
        return Request(
            url,
            callback=self.parse,
            meta=meta,
            errback=self._handle_search_error,
            dont_filter=retry_times > 0
        )

    def _scope_key(self, keyword, scope):
        return f"{keyword}:{scope[0].strftime('%Y-%m-%d %H')}->{scope[1].strftime('%Y-%m-%d %H')}"

    def _inc_scope_count(self, meta):
        scope = meta.get('current_scope')
        keyword = meta.get('keyword')
        if not scope or not keyword:
            return
        key = self._scope_key(keyword, scope)
        self.scope_counts[key] += 1

    def _finish_and_advance(self, meta):
        keyword = meta.get('keyword')
        scope = meta.get('current_scope')
        if keyword and scope:
            key = self._scope_key(keyword, scope)
            count = self.scope_counts.get(key, 0)
            self.logger.info(f"[timescope] keyword={keyword} scope={key} done, items={count}")
        yield from self._advance_timescope(keyword, meta)

    def _advance_timescope(self, keyword, meta):
        if not keyword:
            return
        queue = self.timescope_queues.get(keyword, [])
        if not queue:
            self.logger.info(f"[timescope] keyword={keyword} all scopes finished.")
            return
        next_scope = queue.pop(0)
        next_idx = (meta.get('scope_idx') or 0) + 1
        total_scopes = meta.get('total_scopes')
        yield self._make_search_request(
            keyword,
            next_scope,
            page=1,
            retry_times=0,
            scope_idx=next_idx,
            total_scopes=total_scopes
        )

    def _retry_search_request(self, request, reason):
        retry_times = request.meta.get('search_retry_times', 0)
        if retry_times >= self.max_search_retry:
            self.logger.warning(
                f"[search] abandon scope after retries exhausted, reason={reason}, url={request.url}"
            )
            return None
        meta = dict(request.meta)
        meta['search_retry_times'] = retry_times + 1
        self.logger.info(
            f"[search] retry {meta['search_retry_times']}/{self.max_search_retry}, reason={reason}, url={request.url}"
        )
        return request.replace(meta=meta, dont_filter=True)

    def _handle_empty_search_page(self, response):
        meta = dict(response.meta)
        empty_times = meta.get('empty_retry_times', 0)
        if empty_times < self.max_empty_retry:
            meta['empty_retry_times'] = empty_times + 1
            meta['search_retry_times'] = 0
            self.logger.info(
                f"[search] empty page retry {meta['empty_retry_times']}/{self.max_empty_retry}, url={response.url}"
            )
            yield response.request.replace(meta=meta, dont_filter=True)
            return
        self.logger.info(
            f"[search] empty page reached limit, move next scope. url={response.url}"
        )
        yield from self._finish_and_advance(meta)

    def _handle_search_error(self, failure):
        request = failure.request
        reason = repr(getattr(failure, 'value', failure))
        retry_req = self._retry_search_request(request, reason)
        if retry_req:
            yield retry_req
            return
        yield from self._finish_and_advance(request.meta)

    def _retry_api_request(self, request, reason, retry_key='api_retry_times'):
        retry_times = request.meta.get(retry_key, 0)
        if retry_times >= self.max_api_retry:
            self.logger.warning(f"[api] drop request after retries, reason={reason}, url={request.url}")
            return None
        meta = dict(request.meta)
        meta[retry_key] = retry_times + 1
        self.logger.info(
            f"[api] retry {meta[retry_key]}/{self.max_api_retry}, reason={reason}, url={request.url}"
        )
        return request.replace(meta=meta, dont_filter=True)

    def _handle_api_error(self, failure):
        retry_req = self._retry_api_request(
            failure.request,
            reason=repr(getattr(failure, 'value', failure)),
            retry_key='api_retry_times'
        )
        if retry_req:
            yield retry_req

    def _handle_longtext_error(self, failure):
        retry_req = self._retry_api_request(
            failure.request,
            reason=repr(getattr(failure, 'value', failure)),
            retry_key='longtext_retry_times'
        )
        if retry_req:
            yield retry_req
        else:
            yield failure.request.meta.get('item')
