# coding=utf-8
"""
语音助手图形界面
功能：提供可视化界面，集成语音交互系统
"""

import sys
import os
import threading
import markdown

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect, QTimer, QUrl, Signal, QObject
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QFrame, QLabel, QSizePolicy
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

# 获取脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 导入主程序的核心类和函数
from main import VoiceInteractionSystem
from LLM import process_query


# ===== 信号类（用于线程间通信） =====
class SignalBridge(QObject):
    """信号桥接类，用于子线程向主线程发送信号"""
    update_status = Signal(str)        # 更新状态文本
    update_input = Signal(str, bool)   # 更新输入框 (文本, 是否禁用)
    voice_finished = Signal()          # 语音处理完成
    show_result = Signal(str)          # 显示结果


# ===== Markdown 渲染 =====
def render_markdown(md_text: str) -> str:
    HTML = markdown.markdown(md_text, extensions=["fenced_code", "nl2br"])
    return f"""
    <html><head><style>
    body {{ color: #111827; font-family: sans-serif; margin: 0; padding: 0; }}
    p {{ margin: 0; padding: 0; }}
    </style></head><body>{HTML}</body></html>
    """


# ===== 主窗口 =====
class AssistantWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 初始化语音交互系统
        self.system = VoiceInteractionSystem()
        self.voice_listening = False
        self.is_processing = False
        
        # 信号桥接
        self.signals = SignalBridge()
        self.signals.update_status.connect(self._on_update_status)
        self.signals.update_input.connect(self._on_update_input)
        self.signals.voice_finished.connect(self._on_voice_finished)
        self.signals.show_result.connect(self._on_show_result)
        
        # 初始化Token（在后台线程）
        threading.Thread(target=self._init_system, daemon=True).start()

        self.setWindowTitle("语音助手小蓝")
        self.resize(720, 800)
        self.setStyleSheet("background:#ffffff;")
        self._build_ui()

    def _init_system(self):
        """后台初始化系统"""
        self.signals.update_status.emit("正在初始化...")
        if self.system.init_token():
            self.signals.update_status.emit("系统就绪")
            self.signals.update_input.emit("询问任何问题...", False)
        else:
            self.signals.update_status.emit("初始化失败，请检查网络")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        # 主布局
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 40, 20, 20)
        main_layout.setSpacing(10)

        # 1. 顶部标题
        title = QLabel("语音助手小蓝")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: 500; color: #111827; margin-bottom: 20px;")
        main_layout.addWidget(title)

        # 2. 中间视频区域 - 用白色容器包裹
        video_container = QWidget()
        video_container.setStyleSheet("background: white;")
        video_container_layout = QVBoxLayout(video_container)
        video_container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background: white;")
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.IgnoreAspectRatio)
        video_container_layout.addWidget(self.video_widget)
        
        # 创建媒体播放器
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0)  # 静音播放背景视频
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        
        # 设置视频文件路径
        video_path = os.path.join(SCRIPT_DIR, "ui", "12月15日.mp4")
        if os.path.exists(video_path):
            self.media_player.setSource(QUrl.fromLocalFile(video_path))
            self.media_player.setLoops(QMediaPlayer.Loops.Infinite)
            self.media_player.play()
        
        main_layout.addWidget(video_container, 1)

        # 3. 状态标签（显示当前状态/结果）
        self.status_label = QLabel("正在初始化...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("""
            font-size: 14px; 
            color: #666; 
            padding: 10px;
            background: rgba(255,255,255,0.9);
            border-radius: 10px;
        """)
        self.status_label.setMaximumHeight(80)
        main_layout.addWidget(self.status_label)

        # 4. 底部输入区 (包含输入框和语音按钮)
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(12)

        # --- 输入框 ---
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 25px;
            }
        """)
        input_frame.setFixedHeight(50)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(15, 0, 15, 0)
        
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("正在初始化...")
        self.input_box.setStyleSheet("border: none; font-size: 15px; color: #333;")
        self.input_box.setEnabled(False)
        self.input_box.returnPressed.connect(self.send_text)
        
        # 发送按钮
        send_btn = QPushButton("➤")
        send_btn.setStyleSheet("border: none; font-size: 18px; color: #2563eb;")
        send_btn.clicked.connect(self.send_text)
        
        input_layout.addWidget(self.input_box)
        input_layout.addWidget(send_btn)
        
        bottom_layout.addWidget(input_frame, 1)

        # --- 语音按钮 ---
        self.mic_container = QWidget()
        self.mic_container.setFixedSize(50, 50)
        
        self.mic_btn = QPushButton(self.mic_container)
        self.mic_btn.setText("🎤")
        self.mic_btn.setGeometry(0, 0, 50, 50) 
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background-color: #000000;
                color: white;
                border-radius: 25px;
                font-size: 18px;
                border: none;
            }
        """)
        self.mic_btn.clicked.connect(self.start_voice)
        
        bottom_layout.addWidget(self.mic_container)
        main_layout.addWidget(bottom_container)

        # 5. 动画初始化
        self.mic_anim = QPropertyAnimation(self.mic_btn, b"geometry")
        self.mic_anim.setDuration(800)
        self.mic_anim.setEasingCurve(QEasingCurve.InOutSine)

    # ========== 信号槽函数 ==========
    def _on_update_status(self, text):
        """更新状态标签"""
        self.status_label.setText(text)

    def _on_update_input(self, placeholder, disabled):
        """更新输入框状态"""
        self.input_box.setPlaceholderText(placeholder)
        self.input_box.setEnabled(not disabled)

    def _on_voice_finished(self):
        """语音处理完成"""
        self.voice_listening = False
        self.is_processing = False
        self.mic_anim.stop()
        self.mic_btn.setGeometry(0, 0, 50, 50)
        self.mic_btn.setText("🎤")
        self.input_box.setEnabled(True)
        self.input_box.setPlaceholderText("询问任何问题...")

    def _on_show_result(self, text):
        """显示结果"""
        self.status_label.setText(text)

    # ========== 文本输入处理 ==========
    def send_text(self):
        """处理文本输入"""
        text = self.input_box.text().strip()
        if not text or self.is_processing:
            return
        
        self.input_box.clear()
        self.is_processing = True
        self.status_label.setText(f"正在处理: {text}")
        
        # 在后台线程处理
        threading.Thread(target=self._process_text_input, args=(text,), daemon=True).start()

    def _process_text_input(self, text):
        """后台处理文本输入"""
        try:
            # 通过LLM处理
            is_instruction, processed_result = process_query(text)
            
            if is_instruction:
                # 执行指令
                result = self.system.execute_command(processed_result)
            else:
                # 闲谈回复
                result = processed_result
            
            # 显示结果
            self.signals.show_result.emit(f"🤖 {result}")
            
            # 语音播报（在后台）
            self.system.text_to_speech(result)
            
        except Exception as e:
            self.signals.show_result.emit(f"处理出错: {str(e)}")
        finally:
            self.is_processing = False

    # ========== 语音输入处理 ==========
    def start_voice(self):
        """开始语音录制"""
        if self.voice_listening or self.is_processing:
            return
        
        self.voice_listening = True
        self.is_processing = True
        self.input_box.setEnabled(False)
        self.input_box.setPlaceholderText("正在聆听...")
        self.mic_btn.setText("⦿")
        self.status_label.setText("🎤 正在录音，请说话...")
        
        self._start_breath()
        
        # 在后台线程录音
        threading.Thread(target=self._voice_process, daemon=True).start()

    def _voice_process(self):
        """后台处理语音"""
        try:
            # 录音
            audio_file = self.system.record_audio(duration=5)
            
            self.signals.update_status.emit("正在识别...")
            
            # 语音识别
            text = self.system.speech_to_text(audio_file)
            
            if text:
                self.signals.update_status.emit(f"识别结果: {text}")
                
                # 处理指令
                is_instruction, processed_result = process_query(text)
                
                if is_instruction:
                    result = self.system.execute_command(processed_result)
                else:
                    result = processed_result
                
                # 显示结果
                self.signals.show_result.emit(f"🤖 {result}")
                
                # 语音播报
                self.system.text_to_speech(result)
            else:
                self.signals.show_result.emit("未能识别到语音，请重试")
                
        except Exception as e:
            self.signals.show_result.emit(f"处理出错: {str(e)}")
        finally:
            self.signals.voice_finished.emit()

    def _start_breath(self):
        """启动呼吸动画"""
        self.mic_anim.stop()
        self.mic_anim.setStartValue(QRect(0, 0, 50, 50))
        self.mic_anim.setEndValue(QRect(5, 5, 40, 40))
        self.mic_anim.setLoopCount(-1)
        self.mic_anim.start()

    def closeEvent(self, event):
        """窗口关闭时清理资源"""
        self.system.cleanup()
        event.accept()


# ========== 主入口 ==========
if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = AssistantWindow()
    win.show()
    sys.exit(app.exec())
