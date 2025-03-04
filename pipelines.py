import datetime
import json
import os
import time

class JsonWriterPipeline(object):
    """
    根据新的需求，对于 comment、repost、fan、follower、tweet_by_tweet_id、tweet_by_user_id、user_spider 等模式：
    - 如果是单一 ID（is_single=True），文件名统一为: {mode}_{ID}.jsonl
    - 如果是多个 ID（is_single=False），文件名统一为: {mode}_{YYYYMMDDHHMMSS}.jsonl
    - tweet_spider_by_keyword 保持原有逻辑：文件名 => {mode}_{YYYYMMDDHHMMSS}.jsonl
    在写入数据时，若存在 mblogin 或 user_id 等字段，需要保证它在最前面（若不重复）。
    """

    def __init__(self):
        self.file = None

    def open_spider(self, spider):
        mode = spider.name
        # 如果是 keyword，就保持原逻辑 => mode_时间.jsonl
        if mode == 'tweet_spider_by_keyword':
            now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{mode}_{now}.jsonl"
            output_dir = '../output'
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            self.file = open(os.path.join(output_dir, filename), 'wt', encoding='utf-8')
            return

        # 否则，根据是否单一 ID 判断
        is_single = getattr(spider, 'is_single', False)
        single_id = getattr(spider, 'single_id', None)

        output_dir = '../output'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if is_single and single_id:
            filename = f"{mode}_{single_id}.jsonl"
        else:
            now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{mode}_{now}.jsonl"

        self.file = open(os.path.join(output_dir, filename), 'wt', encoding='utf-8')

    def process_item(self, item, spider):
        mode = spider.name
        # 将 mblogin 或 user_id 等字段放到最前
        # comment / repost / tweet_spider_by_tweet_id => mblogin
        # fan / follower / tweet_by_user_id / user_spider => user_id
        # 其余模式不变
        if mode in ['comment', 'repost', 'tweet_spider_by_tweet_id']:
            if 'mblogin' in item:
                # 将 'mblogin' 移至字典第一位
                item = {'mblogin': item['mblogin'], **{k: v for k, v in item.items() if k != 'mblogin'}}
        elif mode in ['fan', 'follower', 'fan_spider', 'follower_spider', 'tweet_spider_by_user_id', 'user_spider']:
            # 这里如果在 item 里是 'user_id' 就放前面；若你想和原始 spider 对应字段一致，也可自定义
            # 视具体实现，这里演示如下
            if 'user_id' in item:
                item = {'user_id': item['user_id'], **{k: v for k, v in item.items() if k != 'user_id'}}

        # 补充抓取时间
        item['crawl_time'] = int(time.time())
        line = json.dumps(item, ensure_ascii=False) + "\n"
        if self.file:
            self.file.write(line)
            self.file.flush()
        return item

    def close_spider(self, spider):
        if self.file:
            self.file.close()
            self.file = None