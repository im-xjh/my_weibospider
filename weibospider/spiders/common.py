import json
import re
import dateutil.parser

def base62_decode(string):
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    string = str(string)
    num = 0
    idx = 0
    for char in string:
        power = (len(string) - (idx + 1))
        num += alphabet.index(char) * (len(alphabet) ** power)
        idx += 1
    return num

def reverse_cut_to_length(content, code_func, cut_num=4, fill_num=7):
    content = str(content)
    cut_list = [content[i - cut_num if i >= cut_num else 0:i] for i in range(len(content), 0, (-1 * cut_num))]
    cut_list.reverse()
    result = []
    for i, item in enumerate(cut_list):
        s = str(code_func(item))
        if i > 0 and len(s) < fill_num:
            s = (fill_num - len(s)) * '0' + s
        result.append(s)
    return ''.join(result)

def url_to_mid(url: str):
    """
    将 base62 格式的 mblogid => 数字mid
    例如: url_to_mid('z0JH2lOMb') => 3501756485200075
    """
    result = reverse_cut_to_length(url, base62_decode)
    return int(result)

def parse_time(s):
    """
    将形如 Wed Oct 19 23:44:36 +0800 2022 的微博时间转换为 2022-10-19 23:44:36
    """
    return dateutil.parser.parse(s).strftime('%Y-%m-%d %H:%M:%S')

def parse_user_info(data):
    user = {
        "_id": str(data['id']),
        "avatar_hd": data['avatar_hd'],
        "nick_name": data['screen_name'],
        "verified": data['verified'],
    }
    keys = ['description', 'followers_count', 'friends_count', 'statuses_count',
            'gender', 'location', 'mbrank', 'mbtype', 'credit_score']
    for key in keys:
        if key in data:
            user[key] = data[key]
    if 'created_at' in data:
        user['created_at'] = parse_time(data.get('created_at'))
    if user['verified']:
        user['verified_type'] = data.get('verified_type', '')
        if 'verified_reason' in data:
            user['verified_reason'] = data['verified_reason']
    return user

def parse_tweet_info(data):
    tweet = {
        "_id": str(data['mid']),
        "mblogid": data['mblogid'],
        "created_at": parse_time(data['created_at']),
        "geo": data.get('geo', None),
        "ip_location": data.get('region_name', None),
        "reposts_count": data['reposts_count'],
        "comments_count": data['comments_count'],
        "attitudes_count": data['attitudes_count'],
        "source": data['source'],
        "content": data['text_raw'].replace('\u200b', ''),
        "pic_urls": ["https://wx1.sinaimg.cn/orj960/" + pic_id for pic_id in data.get('pic_ids', [])],
        "pic_num": data['pic_num'],
        'isLongText': False,
        'is_retweet': False,
        "user": parse_user_info(data['user']),
    }
    if '</a>' in tweet['source']:
        match = re.search(r'>(.*?)</a>', tweet['source'])
        if match:
            tweet['source'] = match.group(1)
    if 'page_info' in data and data['page_info'].get('object_type', '') == 'video':
        media_info = None
        if 'media_info' in data['page_info']:
            media_info = data['page_info']['media_info']
        elif 'cards' in data['page_info'] and 'media_info' in data['page_info']['cards'][0]:
            media_info = data['page_info']['cards'][0]['media_info']
        if media_info:
            tweet['video'] = media_info.get('stream_url')
            tweet['video_online_numbers'] = media_info.get('online_users_number', None)
    tweet['url'] = f"https://weibo.com/{tweet['user']['_id']}/{tweet['mblogid']}"
    if data.get('isLongText') and 'continue_tag' in data:
        tweet['isLongText'] = True
    if 'retweeted_status' in data:
        tweet['is_retweet'] = True
        tweet['retweet_id'] = data['retweeted_status']['mid']
    if 'reads_count' in data:
        tweet['reads_count'] = data['reads_count']
    return tweet

def parse_long_tweet(response):
    data = json.loads(response.text)['data']
    item = response.meta['item']
    # 覆盖 content
    item['content'] = data['longTextContent']
    yield item