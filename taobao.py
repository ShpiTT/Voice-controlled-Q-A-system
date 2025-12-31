# coding=utf-8
"""
淘宝搜索模块
功能：打开浏览器搜索淘宝商品
"""

import webbrowser
from urllib.parse import quote


def search_taobao(keyword):
    """
    打开淘宝搜索指定商品
    :param keyword: 搜索关键词
    :return: (success, message)
    """
    if not keyword:
        return False, "请提供搜索关键词"
    
    # 对关键词编码（处理中文/特殊字符）
    encoded_keyword = quote(keyword, encoding="utf-8")
    # 淘宝搜索结果页URL
    taobao_url = f"https://s.taobao.com/search?q={encoded_keyword}"
    
    print(f"正在打开淘宝搜索：{keyword}")
    webbrowser.open(taobao_url)
    return True, f"已打开淘宝搜索{keyword}"


if __name__ == "__main__":
    # 测试
    keyword = input("请输入淘宝搜索关键词：").strip()
    success, msg = search_taobao(keyword)
    print(msg)
