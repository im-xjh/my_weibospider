import os
import argparse
import json
import datetime
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from spiders.tweet_by_user_id import TweetSpiderByUserID
from spiders.tweet_by_keyword import TweetSpiderByKeyword
from spiders.tweet_by_tweet_id import TweetSpiderByTweetID
from spiders.comment import CommentSpider
from spiders.follower import FollowerSpider
from spiders.user import UserSpider
from spiders.fan import FanSpider
from spiders.repost import RepostSpider
from scrapy.utils.ossignal import install_shutdown_handlers

# 移除默认的信号处理
install_shutdown_handlers(lambda: None)




def parse_external_file(mode, file_path):
    """
    根据不同 mode 解析外部文件，返回待处理的 ID 列表。
    文件中每行是一个完整的 JSON 对象，例如：
      {"_id":"5056748957731967","mblogid":"OnOizwrr9", …, "user":{"_id":"3238235724", …}}
    """
    ids = []
    if not os.path.isfile(file_path):
        print(f"文件 {file_path} 不存在！")
        return ids

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 评论 / 转发 / 按微博 ID 抓取：取 mblogid
            if mode in ['comment', 'repost', 'tweet_by_tweet_id']:
                mblogid = data.get('mblogid')
                if mblogid:
                    ids.append(mblogid)

            # 按用户 ID 抓取推文：取嵌套 user._id 或顶层 _id
            elif mode == 'tweet_by_user_id':
                user = data.get('user', {})
                uid = user.get('_id') or data.get('_id')
                if uid:
                    ids.append(uid)

            # 粉丝 / 关注：取顶层 _id
            elif mode in ['fan', 'follower']:
                uid = data.get('_id')
                if uid:
                    ids.append(uid)

            # 用户信息模式：优先取嵌套 user._id，再取顶层 _id
            elif mode == 'user':
                uid = data.get('user', {}).get('_id') or data.get('_id')
                if uid:
                    ids.append(uid)

            # 其他 mode 可自行扩展…

    return ids



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run Weibo spider.')
    parser.add_argument('mode', type=str, help='Spider mode')
    parser.add_argument('--user_ids_file', type=str, help='Path to user_ids file', default=None)
    args = parser.parse_args()

    mode = args.mode
    user_ids_file = args.user_ids_file

    os.environ['SCRAPY_SETTINGS_MODULE'] = 'settings'
    settings = get_project_settings()
    process = CrawlerProcess(settings)

    # 仅当有需要时，可在此扩展映射
    mode_to_spider = {
        'comment': CommentSpider,
        'repost': RepostSpider,
        'fan': FanSpider,
        'follow': FollowerSpider,
        'follower': FollowerSpider,        # 注意：用户可能使用 'follower' 或 'follow'
        'user': UserSpider,
        'repost': RepostSpider,
        'tweet_by_tweet_id': TweetSpiderByTweetID,
        'tweet_by_user_id': TweetSpiderByUserID,
        'tweet_by_keyword': TweetSpiderByKeyword,
    }

    spider_class = mode_to_spider.get(mode)
    if not spider_class:
        print(f"Unsupported mode: {mode}")
        exit(1)

    # 如果指定了 user_ids_file，则从文件中批量读取
    if user_ids_file:
        ids_list = parse_external_file(mode, user_ids_file)
        # 是否只有一个 ID
        if len(ids_list) == 1:
            process.crawl(
                spider_class,
                ids_to_process=ids_list,
                is_single=True,
                single_id=ids_list[0]
            )
        else:
            process.crawl(
                spider_class,
                ids_to_process=ids_list,
                is_single=False,
                single_id=None
            )
    else:
        # 未指定文件 => 采用爬虫内部默认的“单一”或“内置”逻辑
        # 此处仍需告知爬虫我们是否只有一个 ID
        # 但如果爬虫里自带多个ID也无妨，这里给个默认 is_single=False 即可
        process.crawl(
            spider_class,
            ids_to_process=None,
            is_single=True,   # 这里默认为 True，表示代码内通常写死一个 ID
            single_id=None
        )

    process.start()