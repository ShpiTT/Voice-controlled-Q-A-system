# coding=utf-8
"""
远程控制客户端程序
功能：发送指令控制远程电脑
运行：在控制端（助手端）运行此程序
"""

import socket
import time

class RemoteController:
    def __init__(self, host='127.0.0.1', port=8888):
        self.host = host
        self.port = port
        self.timeout = 5

    def send_command(self, command):
        """
        发送指令并获取结果
        :param command: 指令字符串
        :return: 服务器返回的结果
        """
        client_socket = None
        try:
            # 创建socket连接
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(self.timeout)
            
            # 连接服务器
            client_socket.connect((self.host, self.port))
            
            # 发送指令
            client_socket.sendall(command.encode('utf-8'))
            
            # 接收结果
            response = client_socket.recv(4096).decode('utf-8')
            return response
            
        except ConnectionRefusedError:
            return "连接失败: 目标计算机拒绝连接，请确认服务端已开启"
        except socket.timeout:
            return "连接超时: 目标计算机无响应"
        except Exception as e:
            return f"发送指令失败: {str(e)}"
        finally:
            if client_socket:
                client_socket.close()

    # ==================== 便捷功能封装 ====================

    def search(self, keyword):
        """百度搜索"""
        return self.send_command(f"search {keyword}")

    def open_app(self, app_name):
        """打开程序"""
        return self.send_command(f"open {app_name}")

    def close_app(self, app_name):
        """关闭程序"""
        return self.send_command(f"close {app_name}")

    def open_url(self, url):
        """打开网址"""
        return self.send_command(f"url {url}")

    def volume_up(self):
        """增加音量"""
        return self.send_command("volume up")

    def volume_down(self):
        """减少音量"""
        return self.send_command("volume down")
    
    def volume_mute(self):
        """静音/取消静音"""
        return self.send_command("volume mute")

    def lock_screen(self):
        """锁定屏幕"""
        return self.send_command("lock")
        
    def check_status(self):
        """检查连接状态"""
        return self.send_command("status")


def main():
    """交互式测试模式"""
    print("=" * 50)
    print("       远程控制客户端 v1.0")
    print("=" * 50)
    
    target_ip = input("请输入目标IP (默认 127.0.0.1): ").strip()
    if not target_ip:
        target_ip = '127.0.0.1'
        
    controller = RemoteController(host=target_ip)
    
    # 测试连接
    print(f"\n正在连接 {target_ip}...")
    status = controller.check_status()
    print(f"服务器状态: {status}")
    
    if "连接失败" in status or "超时" in status:
        print("无法连接到服务器，请确保 remote_server.py 正在运行")
        return

    print("\n输入指令进行控制 (输入 help 查看指令，quit 退出)")
    
    while True:
        try:
            cmd = input("\n>>> ").strip()
            if not cmd:
                continue
                
            if cmd.lower() in ['quit', 'exit']:
                break
                
            if cmd.lower() == 'help':
                print("""
    可用指令示例:
      search 天气      - 百度搜索
      open notepad     - 打开记事本
      open music       - 打开网易云
      close notepad    - 关闭记事本
      url www.bing.com - 打开网址
      volume up        - 音量+
      lock             - 锁屏
                """)
                continue
            
            # 直接发送原始指令
            result = controller.send_command(cmd)
            print(f"服务器响应: {result}")
            
        except KeyboardInterrupt:
            break
            
    print("\n已退出客户端")

if __name__ == '__main__':
    main()
