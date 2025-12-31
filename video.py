import webbrowser
import requests
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

def search_bilibili_videos(keyword):
    """
    适配B站搜索页最新结构，精准提取视频链接
    """
    encoded_keyword = quote(keyword, encoding="utf-8")
    # B站搜索页（第一页，综合排序）
    search_url = f"https://search.bilibili.com/all?keyword={encoded_keyword}&order=totalrank"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        # 可选：添加Cookie（登录后F12复制，解决部分内容限制）
        # "Cookie": "buvid3=你的buvid3; bili_jct=你的bili_jct;"
    }
    
    video_links = set()

    try:
        print(f"正在搜索关键词：{keyword}")
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # ========== 核心修复：适配B站搜索页最新视频卡片结构 ==========
        # 优先级1：新版搜索页卡片（bili-video-card-small）
        video_cards = soup.find_all("div", class_="bili-video-card-small")
        if not video_cards:
            # 优先级2：旧版搜索页卡片（video-item matrix）
            video_cards = soup.find_all("div", class_="video-item matrix")
        if not video_cards:
            # 优先级3：通用卡片（bili-video-card）
            video_cards = soup.find_all("div", class_="bili-video-card")

        print(f"识别到 {len(video_cards)} 个视频卡片")
        if len(video_cards) == 0:
            print("❌ 未识别到任何视频卡片，可能是B站反爬或结构更新")
            return []

        # ========== 修复链接提取逻辑 ==========
        for idx, card in enumerate(video_cards):
            # 提取所有a标签（不限制class，先收集再过滤）
            all_a_tags = card.find_all("a", href=True)
            for a_tag in all_a_tags:
                href = a_tag["href"].strip()
                # 过滤有效视频链接（包含BV号或/video/）
                if "/video/" in href or "BV" in href:
                    # 拼接绝对URL（处理相对路径/绝对路径两种情况）
                    if href.startswith("http"):
                        full_url = href
                    else:
                        full_url = urljoin("https://www.bilibili.com/", href)
                    # 去重并添加
                    video_links.add(full_url)
                    # 调试：打印提取的链接
                    print(f"  卡片{idx+1}提取到链接：{full_url}")
                    break  # 每个卡片只取第一个有效链接

        # 最终结果处理
        video_links = list(video_links)
        print(f"✅ 成功提取 {len(video_links)} 个有效视频链接")
        return video_links

    except requests.exceptions.Timeout:
        print("❌ 错误：请求超时，请检查网络")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ 错误：请求失败 - {str(e)}")
        return []
    except Exception as e:
        print(f"❌ 未知错误 - {str(e)}")
        return []

def play_bilibili_video(keyword):
    """
    搜索B站视频并用默认浏览器播放
    :param keyword: 搜索关键词
    :return: (success, message)
    """
    if not keyword:
        return False, "请提供搜索关键词"
    
    # 搜索视频
    video_links = search_bilibili_videos(keyword)
    
    if not video_links:
        return False, f"未找到「{keyword}」相关视频"
    
    # 随机选一个播放
    random_video = random.choice(video_links)
    print(f"🎉 正在播放视频：{random_video}")
    webbrowser.open(random_video)
    return True, f"正在播放B站{keyword}相关视频"


def play_random_searched_video():
    """关键词搜索 + 默认浏览器播放随机视频（交互式）"""
    keyword = input("请输入B站视频搜索关键词：").strip()
    if not keyword:
        print("❌ 错误：关键词不能为空！")
        return
    success, msg = play_bilibili_video(keyword)
    print(msg)


if __name__ == "__main__":
    play_random_searched_video()