import atexit
import json
import os
import time
import datetime
import pathlib
import re
from itertools import cycle
from typing import Dict, List, Optional
from urllib.parse import urlparse
from scrapy import signals

class AccountState:
    def __init__(self, account: str, cookie: str):
        self.account = account
        self.cookie = cookie
        self.fail_streak = 0
        self.cooldown_until = 0
        self.cooldown_times = 0
        self.status = 'active'  # active / cooldown / dead
        self.assigned_proxy = None
        self.proxy_assigned_at = 0
        self.xsrf_token = self._extract_xsrf(cookie)

    def is_available(self) -> bool:
        if self.status == 'dead':
            return False
        if self.status == 'cooldown' and time.time() < self.cooldown_until:
            return False
        if self.status == 'cooldown' and time.time() >= self.cooldown_until:
            # 恢复
            self.status = 'active'
            self.fail_streak = 0
        return self.status == 'active'

    def mark_failure(self, spider_logger):
        self.fail_streak += 1
        if self.fail_streak > 10:
            self.cooldown_times += 1
            self.fail_streak = 0
            if self.cooldown_times >= 3:
                self.status = 'dead'
                spider_logger.warning(f"[CookiePool] 账号 {self.account} 连续失败 3 轮，永久下线")
            else:
                self.status = 'cooldown'
                self.cooldown_until = time.time() + 5 * 60
                spider_logger.warning(
                    f"[CookiePool] 账号 {self.account} 连续 401/403 超过 10 次，进入冷却 {self.cooldown_times}/3，5 分钟后再试"
                )

    def mark_success(self):
        self.fail_streak = 0

    @staticmethod
    def _extract_xsrf(cookie: str) -> Optional[str]:
        for part in cookie.split(';'):
            part = part.strip()
            if part.startswith('XSRF-TOKEN='):
                return part.split('=', 1)[1]
        return None


class ProxyConfig:
    def __init__(self, config: Dict):
        self.scheme = config.get('scheme', 'http')
        self.host = config.get('host')
        self.port = config.get('port')
        self.username = config.get('username')
        self.password = config.get('password')
        self.rotate_interval = int(config.get('rotate_interval_seconds', 1800))

    def build_proxy(self) -> Optional[str]:
        if not self.host or not self.port:
            return None
        if self.username and self.password:
            return f"{self.scheme}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.scheme}://{self.host}:{self.port}"


class AccountSessionMiddleware:
    """
    负责：
    - 轮询 Cookie 池并绑定代理
    - 按账号绑定代理，超过 rotate_interval_seconds 重新分配
    - 401/403 失败策略：>10 连续 -> 冷却 5 分钟，重复 3 轮后永久下线
    - 记录日志：冷却事件、代理分配、请求计数
    """

    cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.json')
    proxy_config_path = os.path.join(os.path.dirname(__file__), 'proxy_config.json')

    def __init__(self):
        self.accounts: List[AccountState] = []
        self.account_iter = None
        self.proxy_config: Optional[ProxyConfig] = None
        self.account_request_count: Dict[str, int] = {}
        self.log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        self._atexit_registered = False
        self._register_atexit()
        self._load_cookies()
        self._load_proxy_config()

    @classmethod
    def from_crawler(cls, crawler):
        mw = cls()
        crawler.signals.connect(mw.spider_closed, signal=signals.spider_closed)
        # 捕获引擎停止（例如 Ctrl+C），尽量落盘统计
        crawler.signals.connect(mw.engine_stopped, signal=signals.engine_stopped)
        return mw

    def _load_cookies(self):
        if not os.path.exists(self.cookies_path):
            self.accounts = []
            return
        try:
            with open(self.cookies_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            self.accounts = []
            return
        self.accounts = [AccountState(item.get('account', f'acct_{idx}'), item.get('cookie', ''))
                         for idx, item in enumerate(data) if item.get('cookie')]
        self.account_iter = cycle(self.accounts) if self.accounts else None
        for acc in self.accounts:
            self.account_request_count[acc.account] = 0

    def _load_proxy_config(self):
        if not os.path.exists(self.proxy_config_path):
            self.proxy_config = None
            return
        try:
            with open(self.proxy_config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.proxy_config = ProxyConfig(data)
        except Exception:
            self.proxy_config = None

    def _pick_account(self, spider):
        if not self.account_iter:
            return None
        for _ in range(len(self.accounts)):
            acc = next(self.account_iter)
            if acc.is_available():
                return acc
        spider.logger.warning("[CookiePool] 没有可用账号，全部处于冷却或下线状态")
        return None

    def _ensure_proxy(self, acc: AccountState):
        if not self.proxy_config:
            return None
        now = time.time()
        if acc.assigned_proxy and now - acc.proxy_assigned_at < self.proxy_config.rotate_interval:
            return acc.assigned_proxy
        proxy_url = self.proxy_config.build_proxy()
        acc.assigned_proxy = proxy_url
        acc.proxy_assigned_at = now
        # 记录代理分配
        self._log_proxy_assignment(acc.account, proxy_url)
        return proxy_url

    def process_request(self, request, spider):
        acc = self._pick_account(spider)
        if not acc:
            return
        # 绑定 Cookie
        request.headers['Cookie'] = acc.cookie
        request.meta['account'] = acc.account
        self.account_request_count[acc.account] = self.account_request_count.get(acc.account, 0) + 1

        # 如果有 XSRF token，则附加到请求头
        if acc.xsrf_token:
            request.headers['X-XSRF-TOKEN'] = acc.xsrf_token
            # 部分接口要求 XMLHttpRequest 头
            request.headers.setdefault('X-Requested-With', 'XMLHttpRequest')

        # 绑定代理
        proxy_url = self._ensure_proxy(acc)
        if proxy_url:
            request.meta['proxy'] = proxy_url
            request.meta['bound_proxy'] = proxy_url
            # 将下载槽切换为账号+代理，确保每个 Cookie+IP 独立节流
            request.meta['download_slot'] = f"{acc.account}_{proxy_url}"
        else:
            # 无代理时，按账号区分下载槽，避免多账号共用一槽
            request.meta['download_slot'] = acc.account

    def process_response(self, request, response, spider):
        account_name = request.meta.get('account')
        acc = next((a for a in self.accounts if a.account == account_name), None)
        if acc and response.status in (401, 403):
            acc.mark_failure(spider.logger)
            self._log_cooldown_event(acc)
        elif acc:
            acc.mark_success()
        return response

    def process_exception(self, request, exception, spider):
        # 网络异常时记录并允许 Scrapy 重试
        account_name = request.meta.get('account')
        acc = next((a for a in self.accounts if a.account == account_name), None)
        if acc:
            acc.mark_failure(spider.logger)
            spider.logger.debug(f"[CookiePool] 账号 {acc.account} 出现异常 {exception}")
        return None

    def spider_closed(self, spider):
        self._flush_request_counts(reason="spider_closed")

    def engine_stopped(self):
        # spider 参数不可用时也尝试落盘
        self._flush_request_counts(reason="engine_stopped")

    # ---- logging helpers ----
    def _append_log(self, filename: str, content: str):
        path = os.path.join(self.log_dir, filename)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(content)

    @staticmethod
    def _now():
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _log_cooldown_event(self, acc: AccountState):
        # 只在进入冷却或死亡时写入；在 mark_failure 中状态已更新
        status = acc.status
        if status in ('cooldown', 'dead'):
            ts = self._now()
            line = (
                f"{ts}\taccount={acc.account}\tstatus={status}\t"
                f"cooldown_times={acc.cooldown_times}\tfail_streak={acc.fail_streak}"
            )
            self._append_log('cooldown.log', line + '\n')

    def _log_proxy_assignment(self, account: str, proxy_url: Optional[str]):
        if not proxy_url:
            return
        ts = self._now()
        line = f"{ts}\taccount={account}\tproxy={proxy_url}"
        self._append_log('proxy_assignment.log', line + '\n')

    def _flush_request_counts(self, reason: str = ""):
        if not self.account_request_count:
            return
        ts = self._now()
        lines = []
        for account, cnt in sorted(self.account_request_count.items()):
            if reason:
                lines.append(f"{ts}\taccount={account}\trequest_count={cnt}\treason={reason}")
            else:
                lines.append(f"{ts}\taccount={account}\trequest_count={cnt}")
        if lines:
            self._append_log('request_counts.log', '\n'.join(lines) + '\n')

    def _register_atexit(self):
        if self._atexit_registered:
            return

        def _cleanup():
            try:
                self._flush_request_counts(reason="atexit")
            except Exception:
                pass

        atexit.register(_cleanup)
        self._atexit_registered = True


class FullResponseDumpMiddleware:
    """
    当设置环境变量 DUMP_FULL_RESPONSE=1 时，将所有响应落地到
    weibospider/output/debug_responses，便于排查接口/数据问题。
    """

    def __init__(self):
        self.enabled = os.environ.get("DUMP_FULL_RESPONSE") == "1"
        if self.enabled:
            base_dir = pathlib.Path(__file__).resolve().parent.parent / "output" / "debug_responses"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.debug_dir = base_dir

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_response(self, request, response, spider):
        if not getattr(self, "enabled", False):
            return response
        mblogid = request.meta.get('mblogin') or request.meta.get('item', {}).get('mblogid') or "unknown"
        spider_name = getattr(spider, "name", "spider")
        label = request.meta.get('debug_label')
        if not label:
            parsed = urlparse(request.url)
            path_part = parsed.path.strip('/').replace('/', '_')
            host_part = (parsed.netloc or 'unknown').replace('.', '_')
            label = "_".join([p for p in [host_part, path_part] if p]) or "response"
            label = re.sub(r'[^A-Za-z0-9_\\-]+', '_', label)
            if len(label) > 80:
                label = label[:80]
        filename = f"{spider_name}_{label}_{mblogid}_{response.status}.txt"
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
            spider.logger.warning(f"[debug_dump] 写入响应失败: {exc}")
        return response
