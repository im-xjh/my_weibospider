# -*- coding: utf-8 -*-
import datetime
import json
import os
import time

class JsonWriterPipeline(object):
    """
    Pipeline 用于将抓取到的Item写入JSON文件。
    对于 'comment' 和 'repost' 模式，每个 mblogin 对应一个单独的文件。
    确保即使没有抓取到数据，也会生成对应的空文件。
    """

    def __init__(self):
        self.files = {}  # 存储每个mblogin对应的文件句柄
        self.mblogins = set()  # 用于记录所有处理过的mblogin
        self.empty_mblogins = set()  # 用于记录需要生成空文件的mblogin

        output_dir = '../output'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.output_dir = output_dir

    def open_file(self, mblogin):
        """
        打开或创建一个对应mblogin的文件。
        """
        if mblogin not in self.files:
            file_path = os.path.join(self.output_dir, f"{mblogin}.jsonl")
            self.files[mblogin] = open(file_path, 'wt', encoding='utf-8')

    def close_file(self, mblogin):
        """
        关闭对应mblogin的文件。
        """
        if mblogin in self.files:
            self.files[mblogin].close()
            del self.files[mblogin]

    def process_item(self, item, spider):
        """
        处理每个Item，根据不同模式将其写入相应的文件。
        """
        mode = spider.name
        if mode in ['comment', 'repost']:
            mblogin = item.get('mblogin')

            if mblogin:
                self.mblogins.add(mblogin)  # 记录处理过的mblogin
                self.open_file(mblogin)

                # 写入数据项
                item['crawl_time'] = int(time.time())
                line = json.dumps(dict(item), ensure_ascii=False) + "\n"
                self.files[mblogin].write(line)
                self.files[mblogin].flush()
            else:
                spider.logger.warning("Item 缺少 'mblogin' 字段。")
        else:
            # 处理其他模式，使用单一文件
            if not hasattr(self, 'file') or self.file is None:
                now = datetime.datetime.now()
                file_name = spider.name + "_" + now.strftime("%Y%m%d%H%M%S") + '.jsonl'
                self.file = open(os.path.join(self.output_dir, file_name), 'wt', encoding='utf-8')

            item['crawl_time'] = int(time.time())
            line = json.dumps(dict(item), ensure_ascii=False) + "\n"
            self.file.write(line)
            self.file.flush()
        return item

    def open_spider(self, spider):
        """
        当蜘蛛打开时，初始化需要生成空文件的mblogin列表。
        """
        mode = spider.name
        if mode in ['comment', 'repost']:
            # Assume spiders have 'mblogins_to_process' attribute
            self.empty_mblogins = set(getattr(spider, 'mblogins_to_process', []))
        else:
            pass  # 其他模式无需特殊处理

    def close_spider(self, spider):
        """
        当蜘蛛关闭时，确保所有文件被关闭，并生成空文件。
        """
        mode = spider.name
        if mode in ['comment', 'repost']:
            # 生成空文件：那些在抓取过程中没有写入任何数据的mblogin
            remaining_mblogins = self.empty_mblogins - self.mblogins
            for mblogin in remaining_mblogins:
                file_path = os.path.join(self.output_dir, f"{mblogin}.jsonl")
                open(file_path, 'wt', encoding='utf-8').close()  # 创建空文件

            # 关闭所有打开的文件
            for f in self.files.values():
                f.close()
            self.files.clear()
        else:
            # 关闭其他模式的单一文件
            if hasattr(self, 'file') and self.file:
                self.file.close()
                self.file = None
