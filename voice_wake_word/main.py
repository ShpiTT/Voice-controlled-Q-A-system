#!/usr/bin/env python3
"""
轻量级语音唤醒系统 - 使用Porcupine Tiny模型
内存占用：约240KB
响应延迟：<200ms
支持平台：Linux、macOS、Windows、树莓派等
"""

import os
import sys
import time
import struct
import logging
from typing import List, Optional

# 尝试加载 .env 配置
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pvporcupine
import pyaudio
import numpy as np

# 获取脚本文件所在目录的绝对路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ==================== 配置区域 ====================
# Picovoice Access Key（从 https://console.picovoice.ai/ 获取）
ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "")

# 唤醒词模型文件路径列表（相对于脚本文件目录）
KEYWORD_PATHS = [
    os.path.join(SCRIPT_DIR, "models", "小度_zh_windows_v3_0_0.ppn")
]

# 检测灵敏度 (0.0-1.0)，值越高越灵敏但误报率可能增加
SENSITIVITIES = [0.1]

# Porcupine模型文件路径
# 中文唤醒词必须使用中文模型文件（porcupine_params_zh.pv）
# 从 https://console.picovoice.ai/ 下载中文模型后放入 models/ 目录
MODEL_PATH = os.path.join(SCRIPT_DIR, "models", "porcupine_params_zh.pv")
# ==================== 配置结束 ====================

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class VoiceWakeSystem:
    """语音唤醒系统类"""
    
    def __init__(self, 
                 access_key: str,
                 keyword_paths: List[str] = None,
                 sensitivities: List[float] = None,
                 model_path: str = None):
        """
        初始化语音唤醒系统
        
        Args:
            access_key: Picovoice Access Key
            keyword_paths: 唤醒词模型文件路径列表
            sensitivities: 检测灵敏度列表 (0.0-1.0)
            model_path: Porcupine模型文件路径
        """
        self.access_key = access_key
        self.keyword_paths = keyword_paths or []
        self.sensitivities = sensitivities or [0.5]
        self.model_path = model_path
        
        # 初始化状态
        self.porcupine = None
        self.pa = None
        self.audio_stream = None
        self.is_running = False
        
        # 检查参数
        if not self.keyword_paths:
            self.keyword_paths = self._get_default_keyword_paths()
        
        # 确保灵敏度数量与唤醒词数量匹配
        if len(self.sensitivities) != len(self.keyword_paths):
            self.sensitivities = [0.5] * len(self.keyword_paths)
    
    def _get_default_keyword_paths(self) -> List[str]:
        """获取默认唤醒词模型路径"""
        # 尝试查找系统中安装的Porcupine模型
        try:
            from pvporcupine import KEYWORDS
            return [KEYWORDS["hey pico"]]
        except:
            # 如果没有找到，使用基于脚本目录的路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            default_model = os.path.join(script_dir, "models", "hey-pico_tiny.ppn")
            if os.path.exists(default_model):
                return [default_model]
            else:
                logger.warning("未找到默认唤醒词模型，请确保模型文件存在")
                return []
    
    def initialize(self) -> bool:
        """初始化唤醒系统"""
        try:
            # 验证模型文件是否存在
            for keyword_path in self.keyword_paths:
                if not os.path.exists(keyword_path):
                    logger.error(f"模型文件不存在: {keyword_path}")
                    logger.error(f"请确保文件路径正确，当前工作目录: {os.getcwd()}")
                    return False
            
            # 初始化Porcupine
            self.porcupine = pvporcupine.create(
                access_key=self.access_key,
                keyword_paths=self.keyword_paths,
                sensitivities=self.sensitivities,
                model_path=self.model_path
            )
            
            # 初始化音频设备
            self.pa = pyaudio.PyAudio()
            self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length,
                input_device_index=None  # 使用默认麦克风
            )
            
            logger.info(f"成功初始化语音唤醒系统")
            logger.info(f"采样率: {self.porcupine.sample_rate} Hz")
            logger.info(f"帧长度: {self.porcupine.frame_length} 样本")
            logger.info(f"检测唤醒词数量: {len(self.keyword_paths)}")
            
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")
            self.cleanup()
            return False
    
    def start_listening(self, callback=None):
        """开始监听唤醒词"""
        if not self.porcupine or not self.audio_stream:
            logger.error("系统未正确初始化")
            return
            
        self.is_running = True
        logger.info("开始监听唤醒词...")
        
        try:
            while self.is_running:
                # 读取音频帧
                pcm = self.audio_stream.read(self.porcupine.frame_length)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                
                # 检测唤醒词
                keyword_index = self.porcupine.process(pcm)
                
                if keyword_index >= 0:
                    wake_word = os.path.basename(self.keyword_paths[keyword_index])
                    logger.info(f"检测到唤醒词: {wake_word}")
                    
                    # 执行回调函数
                    if callback:
                        try:
                            callback(keyword_index)
                        except Exception as e:
                            logger.error(f"回调函数执行失败: {str(e)}")
        
        except KeyboardInterrupt:
            logger.info("用户中断监听")
        except Exception as e:
            logger.error(f"监听过程中发生错误: {str(e)}")
        finally:
            self.is_running = False
            self.cleanup()
    
    def stop_listening(self):
        """停止监听"""
        self.is_running = False
    
    def cleanup(self):
        """清理资源"""
        logger.info("清理系统资源...")
        
        if self.audio_stream:
            try:
                self.audio_stream.close()
            except Exception as e:
                logger.error(f"关闭音频流失败: {str(e)}")
        
        if self.pa:
            try:
                self.pa.terminate()
            except Exception as e:
                logger.error(f"终止PyAudio失败: {str(e)}")
        
        if self.porcupine:
            try:
                self.porcupine.delete()
            except Exception as e:
                logger.error(f"删除Porcupine实例失败: {str(e)}")
    
    def get_memory_usage(self) -> Optional[dict]:
        """获取内存使用情况"""
        try:
            # 这里可以添加内存监控代码
            import psutil
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            
            return {
                'rss': mem_info.rss / 1024 / 1024,  # MB
                'vms': mem_info.vms / 1024 / 1024,  # MB
                'porcupine_model_size': self.porcupine.model_size / 1024  # KB
            }
        except Exception as e:
            logger.warning(f"获取内存使用情况失败: {str(e)}")
            return None

def default_callback(keyword_index: int):
    """默认回调函数"""
    print(f"\n唤醒词索引: {keyword_index}")
    print("可以在这里添加自定义的唤醒后处理逻辑")
    print("例如：启动语音识别、执行命令等\n")

def main():
    """主函数"""
    print("="*60)
    print("轻量级语音唤醒系统")
    print("="*60)
    print(f"唤醒词模型: {KEYWORD_PATHS}")
    print(f"灵敏度: {SENSITIVITIES}")
    print("按 Ctrl+C 停止程序")
    print("="*60 + "\n")
    
    # 创建唤醒系统实例
    wake_system = VoiceWakeSystem(
        access_key=ACCESS_KEY,
        keyword_paths=KEYWORD_PATHS,
        sensitivities=SENSITIVITIES,
        model_path=MODEL_PATH
    )
    
    # 初始化系统
    if wake_system.initialize():
        # 启动监听
        wake_system.start_listening(callback=default_callback)
    else:
        logger.error("系统初始化失败，无法启动监听")

if __name__ == "__main__":
    main()