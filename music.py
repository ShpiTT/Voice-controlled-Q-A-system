# coding=utf-8
"""
音乐播放模块
功能：通过网易云音乐API搜索歌曲，并在浏览器中播放
"""

import os
import time
import webbrowser
import requests

# 网易云音乐API
NETEASE_SEARCH_URL = "https://music.163.com/api/search/get/web"


class NeteasePlayer:
    """网易云音乐播放器控制（网页版）"""
    
    def __init__(self):
        self.playlist = []          # 播放列表 [(song_id, song_name, artist), ...]
        self.current_index = -1     # 当前播放索引
    
    def search_music(self, keyword, limit=10):
        """
        搜索音乐
        :param keyword: 搜索关键词
        :param limit: 返回数量
        :return: [(song_id, song_name, artist), ...]
        """
        try:
            print(f"[音乐] 正在搜索: {keyword}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://music.163.com/'
            }
            
            params = {
                's': keyword,
                'type': 1,  # 1表示单曲
                'offset': 0,
                'limit': limit
            }
            
            response = requests.post(NETEASE_SEARCH_URL, headers=headers, data=params, timeout=10)
            data = response.json()
            
            if data.get('code') == 200 and data.get('result', {}).get('songs'):
                songs = data['result']['songs']
                result = []
                for song in songs:
                    song_id = song['id']
                    song_name = song['name']
                    artist = '/'.join([a['name'] for a in song.get('artists', [])])
                    result.append((song_id, song_name, artist))
                    print(f"  找到: {song_name} - {artist}")
                return result
            else:
                print("[音乐] 未找到相关歌曲")
                return []
                
        except Exception as e:
            print(f"[音乐] 搜索失败: {str(e)}")
            return []
    
    def play_by_id(self, song_id, song_name="未知歌曲", artist="未知歌手"):
        """
        播放指定ID的歌曲（在浏览器中打开网易云音乐网页版）
        """
        try:
            # 使用网易云音乐网页版播放链接
            # 这个链接会直接打开歌曲页面并自动播放
            web_url = f"https://music.163.com/#/song?id={song_id}&autoplay=true"
            
            print(f"[音乐] 正在播放: {song_name} - {artist}")
            webbrowser.open(web_url)
            
            return True, f"正在播放: {song_name} - {artist}"
                
        except Exception as e:
            print(f"[音乐] 播放失败: {str(e)}")
            return False, f"播放失败: {str(e)}"
    
    def play_by_name(self, keyword):
        """
        根据关键词搜索并播放第一首歌曲
        :param keyword: 搜索关键词
        :return: (success, message)
        """
        # 搜索歌曲
        songs = self.search_music(keyword, limit=5)
        
        if not songs:
            return False, f"未找到与'{keyword}'相关的歌曲"
        
        # 更新播放列表
        self.playlist = songs
        self.current_index = 0
        
        # 播放第一首
        song_id, song_name, artist = songs[0]
        return self.play_by_id(song_id, song_name, artist)
    
    def next(self):
        """播放下一首"""
        if not self.playlist:
            return False, "播放列表为空，请先搜索歌曲"
        
        self.current_index = (self.current_index + 1) % len(self.playlist)
        song_id, song_name, artist = self.playlist[self.current_index]
        return self.play_by_id(song_id, song_name, artist)
    
    def previous(self):
        """播放上一首"""
        if not self.playlist:
            return False, "播放列表为空，请先搜索歌曲"
        
        self.current_index = (self.current_index - 1) % len(self.playlist)
        song_id, song_name, artist = self.playlist[self.current_index]
        return self.play_by_id(song_id, song_name, artist)


# 全局播放器实例
_player = NeteasePlayer()


# ========== 对外接口 ==========

def start_music(keyword=None):
    """
    开始播放音乐
    :param keyword: 搜索关键词，如果为空则打开网易云首页
    """
    if keyword:
        return play_music(keyword)
    else:
        webbrowser.open("https://music.163.com/")
        return True, "已打开网易云音乐"


def play_music(keyword):
    """
    搜索并播放音乐
    :param keyword: 搜索关键词
    :return: (success, message)
    """
    return _player.play_by_name(keyword)


def stop_music():
    """停止音乐（网页版无法控制，提示用户）"""
    return True, "请在浏览器中暂停音乐"


def pause_music():
    """暂停音乐（网页版无法控制，提示用户）"""
    return True, "请在浏览器中暂停音乐"


def next_music():
    """播放下一首"""
    return _player.next()


def previous_music():
    """播放上一首"""
    return _player.previous()


def search_music(keyword, limit=5):
    """
    搜索音乐
    :param keyword: 搜索关键词
    :param limit: 返回数量
    :return: 歌曲列表
    """
    return _player.search_music(keyword, limit)


# ========== 测试 ==========
if __name__ == "__main__":
    print("=" * 50)
    print("网易云音乐播放模块测试（网页版）")
    print("=" * 50)
    
    # 测试搜索
    print("\n1. 测试搜索功能:")
    songs = search_music("周杰伦 稻香", limit=3)
    for i, (sid, name, artist) in enumerate(songs):
        print(f"  {i+1}. {name} - {artist} (ID: {sid})")
    
    # 测试播放
    if songs:
        print("\n2. 测试播放功能:")
        success, msg = play_music("稻香")
        print(f"  结果: {msg}")
        
        if success:
            print("\n歌曲将在浏览器中播放")
            print("等待10秒后测试下一首...")
            time.sleep(10)
            
            print("\n3. 测试下一首:")
            success, msg = next_music()
            print(f"  结果: {msg}")
    
    print("\n测试完成!")
