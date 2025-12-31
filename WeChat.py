# coding=utf-8
"""
微信消息发送模块
功能：通过PC端微信发送消息给指定好友
注意：需要先在电脑上登录微信客户端
"""

import pyautogui
import pyperclip
import time


def send_wechat_message(friend, content):
    """
    向指定好友发送微信消息
    :param friend: 好友名称（微信昵称或备注）
    :param content: 消息内容
    :return: (success, message)
    """
    if not friend:
        return False, "请提供好友名称"
    if not content:
        return False, "请提供消息内容"
    
    try:
        # 1. 唤醒微信窗口 (Ctrl+Alt+W 是微信默认快捷键)
        pyautogui.hotkey('ctrl', 'alt', 'w')
        time.sleep(0.5)
        
        # 2. 打开搜索框 (Ctrl+F)
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.3)
        
        # 3. 输入好友名称搜索
        pyperclip.copy(friend)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)
        
        # 4. 按回车选择第一个搜索结果
        pyautogui.press('enter')
        time.sleep(0.5)
        
        # 5. 输入消息内容
        pyperclip.copy(content)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)
        
        # 6. 发送消息
        pyautogui.press('enter')
        
        return True, f"已向{friend}发送消息：{content}"
    
    except Exception as e:
        return False, f"发送消息失败：{str(e)}"


def open_wechat_chat(friend):
    """
    打开与指定好友的聊天窗口（不发送消息）
    :param friend: 好友名称
    :return: (success, message)
    """
    if not friend:
        return False, "请提供好友名称"
    
    try:
        # 唤醒微信窗口
        pyautogui.hotkey('ctrl', 'alt', 'w')
        time.sleep(0.5)
        
        # 打开搜索框
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.3)
        
        # 输入好友名称搜索
        pyperclip.copy(friend)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)
        
        # 按回车选择第一个搜索结果
        pyautogui.press('enter')
        
        return True, f"已打开与{friend}的聊天窗口"
    
    except Exception as e:
        return False, f"打开聊天失败：{str(e)}"


if __name__ == "__main__":
    # 测试
    friend = input("请输入好友名称：").strip()
    content = input("请输入消息内容：").strip()
    success, msg = send_wechat_message(friend, content)
    print(msg)
