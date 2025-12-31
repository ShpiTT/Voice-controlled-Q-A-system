# coding=utf-8
"""
视觉大模型模块
功能：截屏并发送给视觉大模型进行分析
支持：内容总结、界面翻译等功能
"""

import os
import base64
import pyautogui
from openai import OpenAI

# 尝试加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 阿里云百炼API配置
API_KEY = os.getenv("ALI_VL_API_KEY", "")
BASE_URL = os.getenv("ALI_VL_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
MODEL = os.getenv("ALI_VL_MODEL", "qwen-vl-plus")  # 视觉模型

# 截图保存路径
SCREENSHOT_PATH = "./screen_capture.png"


def take_screenshot():
    """
    截取当前屏幕
    :return: 截图文件路径
    """
    screenshot = pyautogui.screenshot()
    screenshot.save(SCREENSHOT_PATH)
    return SCREENSHOT_PATH


def image_to_base64(image_path):
    """
    将图片转换为base64编码
    :param image_path: 图片路径
    :return: base64编码字符串
    """
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_image(image_path, prompt):
    """
    使用视觉大模型分析图片
    :param image_path: 图片路径
    :param prompt: 分析提示词
    :return: (success, result)
    """
    try:
        client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL,
        )
        
        # 将图片转为base64
        image_base64 = image_to_base64(image_path)
        
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
        )
        
        result = completion.choices[0].message.content
        return True, result
    
    except Exception as e:
        return False, f"分析失败：{str(e)}"


def summarize_screen():
    """
    总结当前屏幕内容
    :return: (success, result)
    """
    print("正在截取屏幕...")
    image_path = take_screenshot()
    
    print("正在分析屏幕内容...")
    prompt = """请仔细观察这张屏幕截图，总结屏幕上显示的主要内容。
要求：
1. 简洁明了，用2-3句话概括
2. 突出重点信息
3. 使用中文回答"""
    
    success, result = analyze_image(image_path, prompt)
    
    # 清理截图
    try:
        os.remove(image_path)
    except:
        pass
    
    return success, result


def translate_screen():
    """
    翻译当前屏幕界面上的文字
    :return: (success, result)
    """
    print("正在截取屏幕...")
    image_path = take_screenshot()
    
    print("正在翻译屏幕内容...")
    prompt = """请翻译这张屏幕截图中的所有文字内容。
要求：
1. 如果是英文，翻译成中文
2. 如果是中文，翻译成英文
3. 保持原有格式和层级关系
4. 只输出翻译结果，不需要解释"""
    
    success, result = analyze_image(image_path, prompt)
    
    # 清理截图
    try:
        os.remove(image_path)
    except:
        pass
    
    return success, result


def describe_screen():
    """
    详细描述当前屏幕内容
    :return: (success, result)
    """
    print("正在截取屏幕...")
    image_path = take_screenshot()
    
    print("正在描述屏幕内容...")
    prompt = """请详细描述这张屏幕截图中的内容，包括：
1. 当前打开的程序或网页
2. 界面上的主要元素
3. 显示的文字内容摘要
请用中文回答。"""
    
    success, result = analyze_image(image_path, prompt)
    
    # 清理截图
    try:
        os.remove(image_path)
    except:
        pass
    
    return success, result


if __name__ == "__main__":
    print("测试屏幕总结功能...")
    success, result = summarize_screen()
    if success:
        print(f"总结结果：\n{result}")
    else:
        print(f"失败：{result}")
