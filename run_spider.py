import os
import argparse
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

# 移除信号处理程序
install_shutdown_handlers(lambda: None)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run Weibo spider.')
    parser.add_argument('mode', type=str, help='Spider mode')
    parser.add_argument('--user_ids_file', type=str, help='Path to user_ids file')

    args = parser.parse_args()

    mode = args.mode
    user_ids_file = args.user_ids_file

    os.environ['SCRAPY_SETTINGS_MODULE'] = 'settings'
    settings = get_project_settings()
    process = CrawlerProcess(settings)
    mode_to_spider = {
        'comment': CommentSpider,
        'fan': FanSpider,
        'follow': FollowerSpider,
        'user': UserSpider,
        'repost': RepostSpider,
        'tweet_by_tweet_id': TweetSpiderByTweetID,
        'tweet_by_user_id': TweetSpiderByUserID,
        'tweet_by_keyword': TweetSpiderByKeyword,
    }

    # 获取对应爬虫类
    spider_class = mode_to_spider.get(mode)
    
    if spider_class:
        if mode in ['comment', 'repost']:
            # 从外部文件加载 mblogin
            try:
                with open(user_ids_file, 'rt', encoding='utf-8') as f:
                    mblogins = [line.strip() for line in f if line.strip()]
            except FileNotFoundError:
                print(f"文件 {user_ids_file} 不存在！")
                exit(1)
            process.crawl(spider_class, mblogins_to_process=mblogins)
        else:
            process.crawl(spider_class)
        process.start()
    else:
        print(f"Unsupported mode: {mode}")
