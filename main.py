# coding=utf-8
"""
人机语音交互系统
功能：通过语音指令控制电脑程序运行和手机设备，并将结果通过语音播报
支持：语音唤醒 + PC程序控制 + ADB手机控制
"""

import os
import sys
import json
import base64
import time
import wave
import subprocess
import datetime
import webbrowser
import re
import struct
import threading

# 导入自定义模块
from video import play_bilibili_video
from taobao import search_taobao
from WeChat import send_wechat_message
from music import start_music, stop_music, next_music, previous_music, play_music, pause_music
from LLM_VL import summarize_screen, translate_screen
from LLM import process_query
from word import write_document, parse_write_command

# 尝试导入语音唤醒模块
try:
    import pvporcupine
    WAKE_WORD_AVAILABLE = True
except ImportError:
    print("提示：未安装pvporcupine，语音唤醒功能不可用")
    print("安装命令：pip install pvporcupine")
    WAKE_WORD_AVAILABLE = False

# 检查并安装必要的库
try:
    import requests
except ImportError:
    print("正在安装 requests...")
    os.system("pip install requests")
    import requests

try:
    import pyaudio
except ImportError:
    print("正在安装 pyaudio...")
    os.system("pip install pyaudio")
    import pyaudio

try:
    import pygame
except ImportError:
    print("正在安装 pygame...")
    os.system("pip install pygame")
    import pygame

try:
    import psutil
except ImportError:
    print("正在安装 psutil...")
    os.system("pip install psutil")
    import psutil

# ==================== 百度API配置 ====================
API_KEY = os.getenv("BAIDU_API_KEY", "")
SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "")
TOKEN_URL = os.getenv("BAIDU_TOKEN_URL", "https://aip.baidubce.com/oauth/2.0/token")
ASR_URL = os.getenv("BAIDU_ASR_URL", "https://vop.baidu.com/server_api")
TTS_URL = os.getenv("BAIDU_TTS_URL", "https://tsn.baidu.com/text2audio")

# TTS配置
TTS_PER = 4194  # 发音人
TTS_SPD = 5     # 语速
TTS_PIT = 5     # 音调
TTS_VOL = 5     # 音量

# 录音配置
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 5  # 默认录音时长

# 临时文件路径
AUDIO_FILE = "./temp_audio.wav"
TTS_OUTPUT = "./tts_output.mp3"

# ==================== 语音唤醒配置 ====================
# Picovoice Access Key（从 https://console.picovoice.ai/ 获取）
WAKE_ACCESS_KEY = "e8l7EtexO4ea2jYy0bodkgj74vB2f4GwypZQT5RmdWO//qzpKO9WYA=="

# 获取脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 唤醒词模型文件路径
WAKE_KEYWORD_PATH = os.path.join(SCRIPT_DIR, "voice_wake_word", "models", "小蓝_zh_windows_v3_0_0.ppn")
WAKE_MODEL_PATH = os.path.join(SCRIPT_DIR, "voice_wake_word", "models", "porcupine_params_zh.pv")

# 唤醒词灵敏度 (0.0-1.0)
WAKE_SENSITIVITY = 0.5


def get_access_token():
    """
    使用 AK，SK 生成鉴权签名（Access Token）
    :return: access_token，或是None(如果错误)
    """
    params = {
        "grant_type": "client_credentials",
        "client_id": API_KEY,
        "client_secret": SECRET_KEY
    }
    response = requests.post(TOKEN_URL, params=params)
    return str(response.json().get("access_token"))


# ==================== ADB 手机控制类 ====================
class ADBController:
    """ADB手机控制器"""
    
    # 常用应用包名映射
    APP_PACKAGES = {
        "微信": "com.tencent.mm",
        "qq": "com.tencent.mobileqq",
        "QQ": "com.tencent.mobileqq",
        "抖音": "com.ss.android.ugc.aweme",
        "淘宝": "com.taobao.taobao",
        "支付宝": "com.eg.android.AlipayGphone",
        "相机": "com.android.camera",
        "相册": "com.android.gallery3d",
        "设置": "com.android.settings",
        "电话": "com.android.dialer",
        "短信": "com.android.mms",
        "浏览器": "com.android.browser",
        "音乐": "com.android.music",
        "日历": "com.android.calendar",
        "时钟": "com.android.deskclock",
        "地图": "com.autonavi.minimap",
        "高德地图": "com.autonavi.minimap",
        "百度地图": "com.baidu.BaiduMap",
        "网易云音乐": "com.netease.cloudmusic",
        "bilibili": "tv.danmaku.bili",
        "哔哩哔哩": "tv.danmaku.bili",
        "京东": "com.jingdong.app.mall",
        "美团": "com.sankuai.meituan",
        "饿了么": "me.ele",
    }
    
    def __init__(self):
        self.connected = False
        self.device_name = None
    
    def run_adb_command(self, command):
        """执行ADB命令并返回结果"""
        try:
            result = subprocess.run(
                f"adb {command}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", "命令执行超时"
        except Exception as e:
            return False, "", str(e)
    
    def check_adb_installed(self):
        """检查ADB是否已安装"""
        success, stdout, stderr = self.run_adb_command("version")
        return success
    
    def check_device_connected(self):
        """检查是否有设备连接"""
        success, stdout, stderr = self.run_adb_command("devices")
        if success and stdout:
            lines = stdout.strip().split('\n')
            for line in lines[1:]:  # 跳过第一行标题
                if '\tdevice' in line:
                    self.device_name = line.split('\t')[0]
                    self.connected = True
                    return True
        self.connected = False
        return False
    
    def get_device_info(self):
        """获取设备信息"""
        if not self.check_device_connected():
            return None
        
        info = {}
        # 获取设备型号
        success, stdout, _ = self.run_adb_command("shell getprop ro.product.model")
        if success:
            info['model'] = stdout
        
        # 获取Android版本
        success, stdout, _ = self.run_adb_command("shell getprop ro.build.version.release")
        if success:
            info['android_version'] = stdout
        
        # 获取电池电量（Windows不支持grep，直接获取全部输出再解析）
        success, stdout, _ = self.run_adb_command("shell dumpsys battery")
        if success:
            match = re.search(r'level:\s*(\d+)', stdout)
            if match:
                info['battery'] = match.group(1)
        
        return info
    
    def press_key(self, keycode):
        """模拟按键"""
        success, _, _ = self.run_adb_command(f"shell input keyevent {keycode}")
        return success
    
    def press_home(self):
        """按主页键"""
        return self.press_key(3)
    
    def press_back(self):
        """按返回键"""
        return self.press_key(4)
    
    def press_menu(self):
        """按菜单键"""
        return self.press_key(82)
    
    def press_power(self):
        """按电源键（亮屏/息屏）"""
        return self.press_key(26)
    
    def is_screen_on(self):
        """检查屏幕是否亮着"""
        success, stdout, _ = self.run_adb_command('shell dumpsys power | findstr "mWakefulness"')
        if success and "Awake" in stdout:
            return True
        return False
    
    def wake_screen(self):
        """唤醒屏幕（只有在屏幕关闭时才亮屏）"""
        if not self.is_screen_on():
            self.press_key(26)  # 按电源键亮屏
            time.sleep(0.3)
            self.swipe("up")  # 上滑解锁
            return True
        return False
    
    def volume_up(self):
        """音量增加"""
        return self.press_key(24)
    
    def volume_down(self):
        """音量减少"""
        return self.press_key(25)
    
    def take_screenshot(self, save_path="./phone_screenshot.png"):
        """手机截图"""
        # 在手机上截图
        success, _, _ = self.run_adb_command("shell screencap -p /sdcard/screenshot.png")
        if not success:
            return False, "截图失败"
        
        # 拉取到电脑
        success, _, _ = self.run_adb_command(f"pull /sdcard/screenshot.png {save_path}")
        if not success:
            return False, "拉取截图失败"
        
        # 删除手机上的截图
        self.run_adb_command("shell rm /sdcard/screenshot.png")
        
        return True, save_path
    
    # 常用应用的启动Activity映射（用于am start -n方式）
    APP_ACTIVITIES = {
        "com.tencent.mm": "com.tencent.mm/.ui.LauncherUI",  # 微信
        "com.tencent.mobileqq": "com.tencent.mobileqq/.activity.SplashActivity",  # QQ
        "com.ss.android.ugc.aweme": "com.ss.android.ugc.aweme/.splash.SplashActivity",  # 抖音
        "com.sina.weibo": "com.sina.weibo/.SplashActivity",  # 微博
        "com.taobao.taobao": "com.taobao.taobao/.MainApplication",  # 淘宝
        "com.eg.android.AlipayGphone": "com.eg.android.AlipayGphone/.AlipayLogin",  # 支付宝
        "com.jingdong.app.mall": "com.jingdong.app.mall/.main.MainActivity",  # 京东
        "tv.danmaku.bili": "tv.danmaku.bili/.MainActivityV2",  # B站
        "com.netease.cloudmusic": "com.netease.cloudmusic/.activity.LoadingActivity",  # 网易云音乐
        "com.tencent.qqmusic": "com.tencent.qqmusic/.activity.AppStarterActivity",  # QQ音乐
        "com.kugou.android": "com.kugou.android/.app.splash.SplashActivity",  # 酷狗音乐
        "com.sankuai.meituan": "com.sankuai.meituan/.pt.homepage.activity.MainActivity",  # 美团
        "com.autonavi.minimap": "com.autonavi.minimap/.MainMapActivity",  # 高德地图
        "com.baidu.BaiduMap": "com.baidu.BaiduMap/.WelcomeScreen",  # 百度地图
    }
    
    def open_app(self, app_name):
        """打开手机应用"""
        package = self.APP_PACKAGES.get(app_name)
        if not package:
            # 尝试模糊匹配
            for name, pkg in self.APP_PACKAGES.items():
                if app_name in name or name in app_name:
                    package = pkg
                    break
        
        if not package:
            return False, f"未找到应用：{app_name}"
        
        # 只在屏幕关闭时才亮屏，避免屏幕亮着时按电源键反而关闭屏幕
        self.wake_screen()
        
        # 优先使用am start -n直接指定Activity（最可靠）
        if package in self.APP_ACTIVITIES:
            success, stdout, _ = self.run_adb_command(
                f"shell am start -n {self.APP_ACTIVITIES[package]}"
            )
            if success or "Starting:" in stdout:
                return True, f"已打开{app_name}"
        
        # 备用方案1：使用monkey命令
        success, stdout, _ = self.run_adb_command(
            f"shell monkey -p {package} -c android.intent.category.LAUNCHER 1"
        )
        if "Events injected: 1" in stdout:
            # 再检查一下是否真的启动了
            return True, f"已打开{app_name}"
        
        # 备用方案2：使用am start不指定activity，让系统自动解析
        success, stdout, _ = self.run_adb_command(
            f"shell am start {package}"
        )
        if success and "Error" not in stdout:
            return True, f"已打开{app_name}"
        
        return False, f"打开{app_name}失败，请确认应用已安装"
    
    def close_app(self, app_name):
        """关闭手机应用"""
        package = self.APP_PACKAGES.get(app_name)
        if not package:
            for name, pkg in self.APP_PACKAGES.items():
                if app_name in name or name in app_name:
                    package = pkg
                    break
        
        if not package:
            return False, f"未找到应用：{app_name}"
        
        success, _, _ = self.run_adb_command(f"shell am force-stop {package}")
        if success:
            return True, f"已关闭{app_name}"
        else:
            return False, f"关闭{app_name}失败"
    
    def input_text(self, text):
        """输入文字（仅支持英文和数字）"""
        # 注意：ADB直接输入不支持中文
        text = text.replace(" ", "%s")
        success, _, _ = self.run_adb_command(f'shell input text "{text}"')
        return success
    
    def swipe(self, direction):
        """滑动屏幕"""
        # 获取屏幕尺寸（假设1080x1920）
        if direction == "up":
            cmd = "shell input swipe 540 1500 540 500 300"
        elif direction == "down":
            cmd = "shell input swipe 540 500 540 1500 300"
        elif direction == "left":
            cmd = "shell input swipe 900 960 180 960 300"
        elif direction == "right":
            cmd = "shell input swipe 180 960 900 960 300"
        else:
            return False
        
        success, _, _ = self.run_adb_command(cmd)
        return success
    
    def unlock_screen(self):
        """解锁屏幕（滑动解锁）"""
        # 先亮屏
        self.press_power()
        time.sleep(0.5)
        # 上滑解锁
        return self.swipe("up")
    
    def lock_screen(self):
        """锁屏"""
        return self.press_power()
    
    def reboot(self):
        """重启手机"""
        success, _, _ = self.run_adb_command("reboot")
        return success


class VoiceInteractionSystem:
    """语音交互系统主类"""
    
    def __init__(self):
        self.access_token = None
        self.running = True
        self.adb = ADBController()  # ADB控制器
        pygame.mixer.init()
        
        # 语音唤醒相关
        self.wake_word_enabled = False
        self.porcupine = None
        self.wake_detected = False
        
        print("=" * 50)
        print("       智能语音助手 v3.0")
        print("    支持语音唤醒 + PC控制 + 手机控制")
        print("=" * 50)
    
    def init_wake_word(self):
        """初始化语音唤醒系统"""
        if not WAKE_WORD_AVAILABLE:
            print("[唤醒] pvporcupine未安装，语音唤醒不可用")
            return False
        
        # 检查模型文件是否存在
        if not os.path.exists(WAKE_KEYWORD_PATH):
            print(f"[唤醒] 唤醒词模型文件不存在: {WAKE_KEYWORD_PATH}")
            return False
        if not os.path.exists(WAKE_MODEL_PATH):
            print(f"[唤醒] 中文模型文件不存在: {WAKE_MODEL_PATH}")
            return False
        
        try:
            self.porcupine = pvporcupine.create(
                access_key=WAKE_ACCESS_KEY,
                keyword_paths=[WAKE_KEYWORD_PATH],
                sensitivities=[WAKE_SENSITIVITY],
                model_path=WAKE_MODEL_PATH
            )
            self.wake_word_enabled = True
            print("[唤醒] 语音唤醒系统初始化成功！")
            print(f"[唤醒] 唤醒词: 小蓝")
            return True
        except Exception as e:
            print(f"[唤醒] 初始化失败: {str(e)}")
            return False
    
    def wait_for_wake_word(self):
        """等待唤醒词"""
        if not self.wake_word_enabled or not self.porcupine:
            return True  # 如果唤醒不可用，直接返回True
        
        print("\n[唤醒] 正在监听唤醒词，请说'小蓝'...")
        
        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=self.porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.porcupine.frame_length
        )
        
        try:
            while self.running:
                pcm = audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                
                keyword_index = self.porcupine.process(pcm)
                
                if keyword_index >= 0:
                    print("\n[唤醒] 检测到唤醒词！")
                    audio_stream.close()
                    pa.terminate()
                    return True
        except Exception as e:
            print(f"[唤醒] 监听错误: {str(e)}")
        finally:
            try:
                audio_stream.close()
                pa.terminate()
            except:
                pass
        
        return False
    
    def cleanup_wake_word(self):
        """清理语音唤醒资源"""
        if self.porcupine:
            try:
                self.porcupine.delete()
                self.porcupine = None
            except:
                pass
        
    def init_token(self):
        """初始化Access Token"""
        print("\n[初始化] 正在获取百度API Token...")
        try:
            self.access_token = get_access_token()
            if self.access_token and self.access_token != "None":
                print("[初始化] Token获取成功！")
                return True
            else:
                print("[初始化] Token获取失败，请检查API_KEY和SECRET_KEY")
                return False
        except Exception as e:
            print(f"[初始化] 获取Token出错: {str(e)}")
            return False
    
    def record_audio(self, duration=RECORD_SECONDS):
        """录制音频"""
        print(f"\n[录音] 开始录音，时长{duration}秒，请说话...")
        
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT,
                       channels=CHANNELS,
                       rate=RATE,
                       input=True,
                       frames_per_buffer=CHUNK)
        
        frames = []
        for i in range(0, int(RATE / CHUNK * duration)):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            # 显示录音进度
            progress = int((i + 1) / (RATE / CHUNK * duration) * 20)
            print(f"\r[录音] 进度: [{'█' * progress}{'░' * (20 - progress)}]", end="")
        
        print("\n[录音] 录音完成！")
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # 保存为WAV文件
        wf = wave.open(AUDIO_FILE, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        return AUDIO_FILE
    
    def speech_to_text(self, audio_file):
        """语音识别：将音频转为文字"""
        print("[识别] 正在进行语音识别...")
        
        # 读取音频文件
        with open(audio_file, 'rb') as f:
            speech_data = f.read()
        
        # Base64编码
        speech = base64.b64encode(speech_data).decode('utf-8')
        
        # 构建请求
        payload = json.dumps({
            "format": "wav",
            "rate": RATE,
            "channel": 1,
            "cuid": "VoiceInteractionSystem",
            "token": self.access_token,
            "speech": speech,
            "len": len(speech_data)
        }, ensure_ascii=False)
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.post(ASR_URL, headers=headers, data=payload.encode("utf-8"))
            response.encoding = "utf-8"
            result = response.json()
            
            if result.get('err_no') == 0:
                text = result['result'][0]
                print(f"[识别] 识别结果: {text}")
                return text
            else:
                print(f"[识别] 识别失败: {result.get('err_msg', '未知错误')}")
                return None
        except Exception as e:
            print(f"[识别] 网络错误: {str(e)}")
            return None
    
    def _split_text_for_tts(self, text):
        """
        将长文本按标点符号切分成多个短句
        切分规则：以句号、感叹号、问号、分号为主要切分点
        """
        if len(text) <= 10:
            return [text]
        
        # 定义切分标点（按优先级）
        # 主要切分点：句号、感叹号、问号
        # 次要切分点：分号、冒号
        sentences = []
        current = ""
        
        for char in text:
            current += char
            # 遇到主要标点符号，切分
            if char in '。！？；;!?':
                if current.strip():
                    sentences.append(current.strip())
                current = ""
        
        # 处理剩余文本
        if current.strip():
            # 如果剩余文本太长，按逗号再切分
            if len(current) > 30:
                sub_parts = []
                sub_current = ""
                for char in current:
                    sub_current += char
                    if char in '，,、':
                        if len(sub_current) > 5:  # 避免切得太碎
                            sub_parts.append(sub_current.strip())
                            sub_current = ""
                if sub_current.strip():
                    sub_parts.append(sub_current.strip())
                sentences.extend(sub_parts)
            else:
                sentences.append(current.strip())
        
        return sentences if sentences else [text]
    
    def _tts_single(self, text, audio_file=None):
        """合成单段文字并保存到文件"""
        from urllib.parse import quote
        tex = quote(text)
        
        if audio_file is None:
            audio_file = TTS_OUTPUT
        
        payload = f'tex={tex}&tok={self.access_token}&cuid=VoiceInteractionSystem&ctp=1&lan=zh&spd={TTS_SPD}&pit={TTS_PIT}&vol={TTS_VOL}&per={TTS_PER}&aue=3'
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': '*/*'
        }
        
        try:
            response = requests.post(TTS_URL, headers=headers, data=payload.encode("utf-8"))
            
            content_type = response.headers.get('Content-Type', '')
            if 'audio/' in content_type:
                # 写入音频文件
                with open(audio_file, 'wb') as f:
                    f.write(response.content)
                return True, audio_file
            else:
                return False, None
        except Exception as e:
            print(f"[播报] 合成错误: {str(e)}")
            return False, None
    
    def _play_audio(self, audio_file):
        """播放音频文件"""
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except:
            pass
        time.sleep(0.02)  # 短暂等待释放文件句柄
        
        try:
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
        except Exception as e:
            print(f"[播报] 播放错误: {str(e)}")
    
    def text_to_speech(self, text):
        """语音合成：将文字转为语音并播放（支持长文本流式播放，带预加载）"""
        print(f"[播报] 正在合成语音: {text}")
        
        # 先释放之前的音频占用
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except:
            pass
        time.sleep(0.05)
        
        # 切分长文本
        sentences = self._split_text_for_tts(text)
        
        if len(sentences) > 1:
            print(f"[播报] 文本已切分为 {len(sentences)} 段进行流式播放")
        
        # 使用两个临时文件交替，实现预加载
        audio_files = ["./tts_temp_0.mp3", "./tts_temp_1.mp3"]
        
        # 清理可能存在的旧文件
        for f in audio_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass
        
        # 预先合成第一段
        if sentences:
            success, current_audio = self._tts_single(sentences[0], audio_files[0])
            if not success:
                print("[播报] 第 1 段合成失败")
                return False
        
        # 逐段播放，同时预加载下一段
        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue
            
            current_audio = audio_files[i % 2]
            next_audio = audio_files[(i + 1) % 2]
            
            # 如果有下一段，启动后台线程预加载
            next_thread = None
            if i + 1 < len(sentences):
                next_sentence = sentences[i + 1]
                if next_sentence.strip():
                    next_thread = threading.Thread(
                        target=self._tts_single, 
                        args=(next_sentence, next_audio)
                    )
                    next_thread.start()
            
            # 播放当前段
            if len(sentences) > 1:
                print(f"[播报] 播放第 {i+1}/{len(sentences)} 段")
            self._play_audio(current_audio)
            
            # 等待预加载完成
            if next_thread:
                next_thread.join()
        
        # 清理临时文件
        try:
            pygame.mixer.music.unload()
        except:
            pass
        time.sleep(0.02)
        for f in audio_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass
        
        print("[播报] 语音播放完成！")
        return True
    
    def execute_command(self, command, is_subcommand=False):
        """
        解析并执行语音指令
        :param command: 指令内容
        :param is_subcommand: 是否为子指令（用于复合指令）
        :return: 执行结果
        """
        original_command = command
        command = command.replace("，", "").replace("。", "").replace(" ", "").lower()
        print(f"[执行] 正在解析指令: {command}")
        
        # ============ 复合指令处理 ============
        # 检查是否包含复合指令连接词
        compound_keywords = ["并", "然后", "再", "接着", "之后"]
        split_keyword = None
        for keyword in compound_keywords:
            if keyword in command:
                split_keyword = keyword
                break
        
        if split_keyword and not is_subcommand:
            # 拆分复合指令
            parts = command.split(split_keyword, 1)
            if len(parts) == 2:
                first_command = parts[0].strip()
                second_command = parts[1].strip()
                
                print(f"[复合指令] 检测到复合指令，拆分为：")
                print(f"  第一部分: {first_command}")
                print(f"  第二部分: {second_command}")
                
                # 执行第一部分
                first_result = self.execute_command(first_command, is_subcommand=True)
                print(f"[复合指令] 第一部分执行结果: {first_result}")
                
                # 判断是否需要等待（对于打开浏览器、B站、淘宝等需要加载的操作）
                need_wait = False
                wait_keywords = ["浏览器", "b站", "bilibili", "哔哩哔哩", "淘宝", "百度"]
                for kw in wait_keywords:
                    if kw in first_command:
                        need_wait = True
                        break
                
                if need_wait:
                    print(f"[复合指令] 检测到需要等待的操作，等待3秒让页面加载...")
                    time.sleep(3)
                
                # 执行第二部分
                second_result = self.execute_command(second_command, is_subcommand=True)
                print(f"[复合指令] 第二部分执行结果: {second_result}")
                
                # 合并结果
                if first_result and second_result:
                    return f"{first_result}，{second_result}"
                elif first_result:
                    return first_result
                elif second_result:
                    return second_result
                else:
                    return "指令执行完成"
        
        result = None
        
        # ============ 系统信息类指令 ============
        if "时间" in command or "几点" in command:
            now = datetime.datetime.now()
            result = f"现在时间是{now.hour}点{now.minute}分{now.second}秒"
            
        elif "日期" in command or "几号" in command or "星期" in command:
            now = datetime.datetime.now()
            weekdays = ["一", "二", "三", "四", "五", "六", "日"]
            result = f"今天是{now.year}年{now.month}月{now.day}日，星期{weekdays[now.weekday()]}"
            
            
        # ============ 系统操作类指令 ============
        elif "打开记事本" in command or "记事本" in command:
            subprocess.Popen("notepad.exe")
            result = "已为您打开记事本"
             
        elif "打开画图" in command or "画图" in command:
            subprocess.Popen("mspaint.exe")
            result = "已为您打开画图程序"
            
        elif "打开浏览器" in command or "浏览器" in command:
            # 提取搜索关键词（支持复合指令场景）
            keyword = command
            # 移除常见的前缀和后缀
            for prefix in ["打开", "用", "在"]:
                if keyword.startswith(prefix):
                    keyword = keyword[len(prefix):]
            keyword = keyword.replace("浏览器", "").replace("搜索", "").replace("百度", "").strip()
            # 移除可能的连接词（复合指令场景）
            for connector in ["并", "然后", "再", "接着", "之后"]:
                if connector in keyword:
                    keyword = keyword.split(connector)[0].strip()
            keyword = keyword.strip()
            if keyword:
                from urllib.parse import quote
                search_url = f"https://www.baidu.com/s?wd={quote(keyword)}"
                webbrowser.open(search_url)
                result = f"已为您在浏览器中搜索{keyword}"
            else:
                result = "请说出要搜索的内容，例如：打开浏览器搜索Python教程"
            
        elif "打开百度" in command:
            webbrowser.open("https://www.baidu.com")
            result = "已为您打开百度"
            
        elif "打开命令行" in command or "命令提示符" in command or "cmd" in command:
            subprocess.Popen("cmd.exe")
            result = "已为您打开命令提示符"
            
        elif "打开资源管理器" in command or "文件管理" in command or "我的电脑" in command:
            subprocess.Popen("explorer.exe")
            result = "已为您打开资源管理器"
        
        # ============ B站视频播放 ============
        elif "b站" in command or "bilibili" in command or "哔哩哔哩" in command:
            # 提取视频关键词
            keyword = command.replace("打开", "").replace("b站", "").replace("bilibili", "")
            keyword = keyword.replace("哔哩哔哩", "").replace("播放", "").replace("视频", "")
            keyword = keyword.replace("搜索", "").strip()
            if keyword:
                success, msg = play_bilibili_video(keyword)
                result = msg
            else:
                result = "请说出要搜索的视频关键词，例如：打开B站播放音乐视频"
        
        # ============ 淘宝搜索 （排除手机淘宝）============
        elif "淘宝" in command and "手机" not in command:
            # 提取商品关键词
            keyword = command.replace("打开", "").replace("淘宝", "").replace("搜索", "")
            keyword = keyword.replace("商品", "").strip()
            if keyword:
                success, msg = search_taobao(keyword)
                result = msg
            else:
                result = "请说出要搜索的商品，例如：打开淘宝搜索手机壳"
        
        # ============ 微信发消息 ============
        elif "微信" in command and ("发" in command or "消息" in command or "信息" in command):
            # 解析：打开微信发XXX信息给XXX 或 打开微信给XXX发XXX
            import re
            # 尝试匹配 "发XXX给XXX" 或 "给XXX发XXX"
            pattern1 = r"发(.+?)(?:信息|消息)?给(.+)"
            pattern2 = r"给(.+?)发(.+?)(?:信息|消息)?"
            
            match1 = re.search(pattern1, command)
            match2 = re.search(pattern2, command)
            
            if match1:
                content = match1.group(1).strip()
                friend = match1.group(2).strip()
            elif match2:
                friend = match2.group(1).strip()
                content = match2.group(2).strip()
            else:
                content = None
                friend = None
            
            if friend and content:
                success, msg = send_wechat_message(friend, content)
                result = msg
            else:
                result = "请说出完整指令，例如：打开微信发你好给张三"
        
        # ============ 音乐播放控制 ============
        elif "播放" in command and ("音乐" in command or "歌" in command or "歌曲" in command):
            # 提取歌曲关键词
            keyword = command.replace("播放", "").replace("音乐", "").replace("歌曲", "")
            keyword = keyword.replace("歌", "").replace("打开", "").replace("帮我", "")
            keyword = keyword.replace("听", "").replace("放", "").strip()
            
            if keyword:
                # 搜索指定歌曲
                result = f"正在搜索: {keyword}..."
                if not is_subcommand:
                    self.text_to_speech(result)
                success, msg = play_music(keyword)
                result = msg
            else:
                # 播放热门歌曲
                success, msg = start_music()
                result = msg if msg else "已开始播放音乐"
        
        elif "下一首" in command or "切歌" in command:
            success, msg = next_music()
            result = msg
        
        elif "上一首" in command:
            success, msg = previous_music()
            result = msg
        
        elif "暂停音乐" in command or "暂停播放" in command:
            success, msg = pause_music()
            result = msg
        
        elif "停止音乐" in command or "关闭音乐" in command:
            success, msg = stop_music()
            result = msg
        
        # ============ 视觉大模型功能 ============
        elif "总结" in command and ("当前" in command or "屏幕" in command or "内容" in command or "界面" in command or "搜索" in command):
            result = "正在截屏并分析内容，请稍候..."
            if not is_subcommand:
                self.text_to_speech(result)
            success, summary = summarize_screen()
            if success:
                result = f"屏幕内容总结：{summary}"
            else:
                result = summary
        
        elif "翻译" in command and ("当前" in command or "屏幕" in command or "界面" in command or "搜索" in command):
            result = "正在截屏并翻译内容，请稍候..."
            if not is_subcommand:
                self.text_to_speech(result)
            success, translation = translate_screen()
            if success:
                result = f"翻译结果：{translation}"
            else:
                result = translation
        
        # ============ Word文档写入 ============
        elif ("文档" in command or "word" in command.lower()) and ("写" in command or "创建" in command or "生成" in command):
            # 解析指令提取主题和类型
            topic, article_type = parse_write_command(original_command)
            result = f"正在生成关于{topic}的{article_type}，请稍候..."
            if not is_subcommand:
                self.text_to_speech(result)
            success, msg = write_document(topic, article_type)
            if success:
                result = f"文档创建成功，{article_type}已保存到documents文件夹"
            else:
                result = msg
        
        # ============ ADB手机控制类指令 ============
        elif "打开手机" in command:
            # 提取应用名称
            app_name = command.replace("打开手机", "").replace("上的", "").strip()
            if app_name:
                if not self.adb.check_device_connected():
                    result = "未检测到手机连接"
                else:
                    success, msg = self.adb.open_app(app_name)
                    result = msg
            else:
                result = "请说出要打开的应用名称，例如：打开手机微信"
        
        elif "关闭手机" in command and "应用" not in command:
            # 提取应用名称
            app_name = command.replace("关闭手机", "").replace("上的", "").strip()
            if app_name:
                if not self.adb.check_device_connected():
                    result = "未检测到手机连接"
                else:
                    success, msg = self.adb.close_app(app_name)
                    result = msg
            else:
                result = "请说出要关闭的应用名称"
        
        elif "手机截图" in command or "手机截屏" in command:
            if not self.adb.check_device_connected():
                result = "未检测到手机连接"
            else:
                success, msg = self.adb.take_screenshot()
                if success:
                    result = f"手机截图已保存到{msg}"
                else:
                    result = msg
        
        elif "手机返回" in command or "返回键" in command:
            if not self.adb.check_device_connected():
                result = "未检测到手机连接"
            elif self.adb.press_back():
                result = "已按下返回键"
            else:
                result = "返回键操作失败"
        
        elif "手机主页" in command or "主页键" in command or "回到桌面" in command:
            if not self.adb.check_device_connected():
                result = "未检测到手机连接"
            elif self.adb.press_home():
                result = "已返回主页"
            else:
                result = "主页键操作失败"
        
        elif "手机亮屏" in command or "点亮屏幕" in command or "解锁手机" in command:
            if not self.adb.check_device_connected():
                result = "未检测到手机连接"
            elif self.adb.unlock_screen():
                result = "已点亮并解锁屏幕"
            else:
                result = "亮屏操作失败"
        
        elif "手机息屏" in command or "锁屏" in command or "手机锁屏" in command:
            if not self.adb.check_device_connected():
                result = "未检测到手机连接"
            elif self.adb.lock_screen():
                result = "已锁定屏幕"
            else:
                result = "锁屏操作失败"
        
        elif "手机音量" in command:
            if not self.adb.check_device_connected():
                result = "未检测到手机连接"
            elif "增加" in command or "调大" in command or "加" in command:
                if self.adb.volume_up():
                    result = "已增加音量"
                else:
                    result = "音量调节失败"
            elif "减少" in command or "调小" in command or "减" in command:
                if self.adb.volume_down():
                    result = "已减少音量"
                else:
                    result = "音量调节失败"
            else:
                result = "请说手机音量增加或手机音量减少"
        
        elif "手机上滑" in command:
            if not self.adb.check_device_connected():
                result = "未检测到手机连接"
            elif self.adb.swipe("up"):
                result = "已向上滑动"
            else:
                result = "滑动操作失败"
        
        elif "手机下滑" in command:
            if not self.adb.check_device_connected():
                result = "未检测到手机连接"
            elif self.adb.swipe("down"):
                result = "已向下滑动"
            else:
                result = "滑动操作失败"
        
        elif "重启手机" in command:
            if not self.adb.check_device_connected():
                result = "未检测到手机连接"
            elif self.adb.reboot():
                result = "手机正在重启"
            else:
                result = "重启操作失败"
        
        # 检查手机状态（放在所有具体手机指令之后，作为兜底）
        elif "手机" in command or "检查手机" in command:
            if self.adb.check_device_connected():
                info = self.adb.get_device_info()
                if info:
                    result = f"手机已连接，型号{info.get('model', '未知')}，安卓版本{info.get('android_version', '未知')}，电量{info.get('battery', '未知')}%"
                else:
                    result = "手机已连接"
            else:
                result = "未检测到手机连接，请确保USB调试已开启并连接手机"
                
        # ============ 系统控制类指令 ============
        elif "退出" in command or "再见" in command:
            result = "好的，再见！系统即将关闭"
            self.running = False
            
        elif "帮助" in command or "能做什么" in command or "功能" in command:
            result = "我可以：播放B站视频、淘宝搜索商品、微信发消息、播放音乐、总结翻译屏幕内容、创建Word文档。还可以控制手机，如打开手机微信、手机截图等。说检查手机可查看连接状态"
            
        else:
            result = f"抱歉，我不理解指令：{command}，请说帮助查看可用功能"
        
        return result
    
    def run(self, use_wake_word=True):
        """
        运行主循环
        :param use_wake_word: 是否使用语音唤醒模式，False则使用按键模式
        """
        # 初始化Token
        if not self.init_token():
            print("系统初始化失败，请检查网络和API配置！")
            return
        
        # 检查ADB和手机连接
        print("\n[初始化] 检查ADB环境...")
        if self.adb.check_adb_installed():
            print("[初始化] ADB已安装")
            if self.adb.check_device_connected():
                print(f"[初始化] 手机已连接: {self.adb.device_name}")
            else:
                print("[初始化] 未检测到手机连接（可稍后连接）")
        else:
            print("[初始化] ADB未安装，手机控制功能不可用")
        
        # 初始化语音唤醒
        if use_wake_word:
            print("\n[初始化] 正在初始化语音唤醒...")
            if self.init_wake_word():
                print("[初始化] 语音唤醒模式已启用")
            else:
                print("[初始化] 语音唤醒不可用，将使用按键模式")
                use_wake_word = False
        
        # 欢迎语
        if use_wake_word and self.wake_word_enabled:
            welcome = "欢迎使用智能语音助手，说小蓝唤醒我"
        else:
            welcome = "欢迎使用智能语音助手，按回车键开始对话"
        self.text_to_speech(welcome)
        
        print("\n" + "=" * 50)
        if use_wake_word and self.wake_word_enabled:
            print("系统已就绪！说'小蓝'唤醒，按Ctrl+C退出")
        else:
            print("系统已就绪！按Enter键开始录音，输入q退出")
        print("=" * 50)
        print("【智能对话】支持自然语言，自动理解您的意图")
        print("-" * 50)
        print("【电脑控制】查询时间、打开记事本/画图/浏览器")
        print("【多媒体】B站视频、淘宝搜索、微信发消息、播放音乐")
        print("【AI功能】总结当前内容、翻译当前界面")
        print("【文档功能】创建Word文档，自动生成文章内容")
        print("【手机控制】打开手机应用、截图、返回、音量调节等")
        print("-" * 50)
        print("示例：'播放周杰伦的稻香'、'帮我在B站找个搞笑视频'")
        print("=" * 50)
        
        # 根据模式选择运行方式
        if use_wake_word and self.wake_word_enabled:
            self._run_wake_word_mode()
        else:
            self._run_keyboard_mode()
        
        # 清理资源
        self.cleanup()
        self.cleanup_wake_word()
        print("\n系统已退出，感谢使用！")
    
    def _run_wake_word_mode(self):
        """语音唤醒模式主循环"""
        while self.running:
            try:
                # 等待唤醒词
                if not self.wait_for_wake_word():
                    continue
                
                # 播放提示音或提示语
                self.text_to_speech("我在")
                
                # 录音
                audio_file = self.record_audio()
                
                # 语音识别
                text = self.speech_to_text(audio_file)
                
                if text:
                    # 处理指令
                    self._process_and_respond(text)
                else:
                    self.text_to_speech("抱歉，没有听清，请再说一遍")
                    
            except KeyboardInterrupt:
                print("\n\n系统被用户中断")
                break
            except Exception as e:
                print(f"[错误] {str(e)}")
                continue
    
    def _run_keyboard_mode(self):
        """按键模式主循环"""
        while self.running:
            try:
                user_input = input("\n按Enter开始录音 (输入q退出): ")
                if user_input.lower() == 'q':
                    break
                
                # 录音
                audio_file = self.record_audio()
                
                # 语音识别
                text = self.speech_to_text(audio_file)
                
                if text:
                    # 处理指令
                    self._process_and_respond(text)
                else:
                    self.text_to_speech("抱歉，没有识别到有效语音，请重试")
                    
            except KeyboardInterrupt:
                print("\n\n系统被用户中断")
                break
            except Exception as e:
                print(f"[错误] {str(e)}")
                continue
    
    def _process_and_respond(self, text):
        """处理用户输入并响应"""
        # 通过LLM进行指令修正和意图识别
        print(f"[LLM] 正在分析指令...")
        is_instruction, processed_result = process_query(text)
        
        if is_instruction:
            # 是指令类，执行标准化后的指令
            print(f"[LLM] 标准化指令: {processed_result}")
            result = self.execute_command(processed_result)
        else:
            # 是闲谈类，直接使用LLM的回复
            print(f"[LLM] 闲谈回复")
            result = processed_result
        
        print(f"[结果] {result}")
        
        # 语音播报结果
        self.text_to_speech(result)
    
    def cleanup(self):
        """清理临时文件"""
        try:
            pygame.mixer.quit()
            time.sleep(0.5)
            if os.path.exists(AUDIO_FILE):
                os.remove(AUDIO_FILE)
            if os.path.exists(TTS_OUTPUT):
                os.remove(TTS_OUTPUT)
        except:
            pass


if __name__ == "__main__":
    system = VoiceInteractionSystem()
    
    # 选择运行模式
    print("\n请选择运行模式：")
    print("1. 语音唤醒模式（说'小蓝'唤醒）")
    print("2. 按键模式（按Enter开始录音）")
    
    choice = input("请输入选项 (1/2，默认1): ").strip()
    
    if choice == "2":
        system.run(use_wake_word=False)
    else:
        system.run(use_wake_word=True)
