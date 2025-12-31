# coding=utf-8
"""
远程控制服务端程序
功能：接收客户端指令并在本机执行
运行：在被控电脑上运行此程序
"""

import socket
import subprocess
import webbrowser
import os
import threading
from urllib.parse import quote

# 配置参数
SERVER_HOST = '0.0.0.0'  # 监听所有网络接口
SERVER_PORT = 8888       # 监听端口（与客户端一致）

# ==================== 动态程序路径查找 ====================
import shutil
import winreg
import glob

def find_program_path(program_name):
    """
    动态查找程序路径
    优先级：1.系统PATH 2.注册表 3.常见安装路径
    """
    # 方法1：使用 shutil.which() 在系统PATH中查找
    path = shutil.which(program_name)
    if path:
        return path
    
    # 方法2：查找常见安装目录
    common_paths = [
        os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), '**', program_name),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), '**', program_name),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), '**', program_name),
        os.path.join(os.environ.get('APPDATA', ''), '**', program_name),
    ]
    
    for pattern in common_paths:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]
    
    return None


def get_app_from_registry(app_name):
    """
    从Windows注册表获取已安装程序的路径
    """
    # 注册表中常见的程序安装位置
    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ]
    
    for hkey, base_path in registry_paths:
        try:
            key_path = f"{base_path}\\{app_name}"
            with winreg.OpenKey(hkey, key_path) as key:
                path, _ = winreg.QueryValueEx(key, "")
                if path and os.path.exists(path):
                    return path
        except (WindowsError, FileNotFoundError):
            continue
    
    return None


def get_program_path(name):
    """
    获取程序的完整路径
    :param name: 程序名称或别名
    :return: 完整路径或原始名称
    """
    # 首先检查基础映射表
    if name.lower() in APP_MAPPING:
        exe_name = APP_MAPPING[name.lower()]
    else:
        exe_name = name
    
    # 系统程序直接返回（它们在 System32 目录）
    system_apps = ['notepad.exe', 'mspaint.exe', 'calc.exe', 'cmd.exe', 'explorer.exe']
    if exe_name.lower() in system_apps:
        return exe_name
    
    # 特殊程序的固定路径（这些程序安装路径比较固定）
    special_paths = {
        'cloudmusic.exe': [
            r"C:\Program Files (x86)\NetEase\CloudMusic\cloudmusic.exe",
            r"C:\Program Files\NetEase\CloudMusic\cloudmusic.exe",
            r"D:\Program Files (x86)\NetEase\CloudMusic\cloudmusic.exe",
            r"D:\Program Files\NetEase\CloudMusic\cloudmusic.exe",
        ],
        'WeChat.exe': [
            r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
            r"C:\Program Files\Tencent\WeChat\WeChat.exe",
            r"D:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
            r"D:\Program Files\Tencent\WeChat\WeChat.exe",
        ],
        'QQ.exe': [
            r"C:\Program Files (x86)\Tencent\QQ\Bin\QQ.exe",
            r"C:\Program Files\Tencent\QQ\Bin\QQ.exe",
            r"D:\Program Files (x86)\Tencent\QQ\Bin\QQ.exe",
        ],
    }
    
    # 检查特殊路径
    if exe_name.lower() in [k.lower() for k in special_paths.keys()]:
        for key, paths in special_paths.items():
            if key.lower() == exe_name.lower():
                for path in paths:
                    if os.path.exists(path):
                        return path
                break
    
    # 尝试从注册表获取
    reg_path = get_app_from_registry(exe_name)
    if reg_path:
        return reg_path
    
    # 尝试在PATH中查找
    which_path = shutil.which(exe_name)
    if which_path:
        return which_path
    
    # 尝试从常见路径查找
    found_path = find_program_path(exe_name)
    if found_path:
        return found_path
    
    # 都找不到，返回原始名称（让系统尝试）
    return exe_name


# 基础程序映射表（程序别名 -> 可执行文件名）
APP_MAPPING = {
    # 系统自带程序（直接可用）
    'notepad': 'notepad.exe',
    '记事本': 'notepad.exe',
    'paint': 'mspaint.exe',
    '画图': 'mspaint.exe',
    'calc': 'calc.exe',
    '计算器': 'calc.exe',
    'cmd': 'cmd.exe',
    '命令行': 'cmd.exe',
    '命令提示符': 'cmd.exe',
    'explorer': 'explorer.exe',
    '资源管理器': 'explorer.exe',
    '我的电脑': 'explorer.exe',
    
    # 浏览器（需要动态查找）
    'chrome': 'chrome.exe',
    '谷歌浏览器': 'chrome.exe',
    'edge': 'msedge.exe',
    '微软浏览器': 'msedge.exe',
    'firefox': 'firefox.exe',
    '火狐浏览器': 'firefox.exe',
    'browser': 'msedge.exe',
    '浏览器': 'msedge.exe',
    
    # Office 软件
    'word': 'WINWORD.EXE',
    'excel': 'EXCEL.EXE',
    'powerpoint': 'POWERPNT.EXE',
    'ppt': 'POWERPNT.EXE',
    
    # 开发工具
    'vscode': 'code.cmd',
    'code': 'code.cmd',
    
    # 其他常用软件
    '微信': 'WeChat.exe',
    'wechat': 'WeChat.exe',
    'qq': 'QQ.exe',
    '钉钉': 'DingTalk.exe',
    '飞书': 'Feishu.exe',
    '腾讯会议': 'wemeet.exe',
}

# 网页版应用映射（直接打开网址）
WEB_APP_MAPPING = {
    '音乐': 'https://music.163.com/',
    '网易云音乐': 'https://music.163.com/',
    '电脑音乐': 'https://music.163.com/',
    'cloudmusic': 'https://music.163.com/',
    'qq音乐': 'https://y.qq.com/',
    '酷狗音乐': 'https://www.kugou.com/',
    'bilibili': 'https://www.bilibili.com/',
    'b站': 'https://www.bilibili.com/',
    '哔哩哔哩': 'https://www.bilibili.com/',
    '淘宝': 'https://www.taobao.com/',
    '京东': 'https://www.jd.com/',
    '百度': 'https://www.baidu.com/',
    '知乎': 'https://www.zhihu.com/',
    '微博': 'https://weibo.com/',
}


def control_volume(action):
    """
    控制系统音量（使用PowerShell，无需第三方工具）
    :param action: up/down/mute/unmute
    :return: 执行结果
    """
    try:
        if action == 'up':
            # 使用 PowerShell 模拟音量键
            ps_cmd = '''
            $obj = New-Object -ComObject WScript.Shell
            $obj.SendKeys([char]175)
            '''
            subprocess.run(['powershell', '-Command', ps_cmd], shell=True, capture_output=True)
            return "已增加音量"
        elif action == 'down':
            ps_cmd = '''
            $obj = New-Object -ComObject WScript.Shell
            $obj.SendKeys([char]174)
            '''
            subprocess.run(['powershell', '-Command', ps_cmd], shell=True, capture_output=True)
            return "已减少音量"
        elif action == 'mute':
            ps_cmd = '''
            $obj = New-Object -ComObject WScript.Shell
            $obj.SendKeys([char]173)
            '''
            subprocess.run(['powershell', '-Command', ps_cmd], shell=True, capture_output=True)
            return "已静音/取消静音"
        elif action == 'unmute':
            # 静音键是切换状态，再按一次取消静音
            ps_cmd = '''
            $obj = New-Object -ComObject WScript.Shell
            $obj.SendKeys([char]173)
            '''
            subprocess.run(['powershell', '-Command', ps_cmd], shell=True, capture_output=True)
            return "已切换静音状态"
        else:
            return "音量指令格式: volume up/down/mute/unmute"
    except Exception as e:
        return f"音量控制失败: {str(e)}"


def execute_command(command):
    """
    解析并执行指令
    :param command: 接收到的指令字符串
    :return: 执行结果
    """
    command = command.strip()
    print(f"[执行] 收到指令: {command}")
    
    # 解析指令类型
    parts = command.split(' ', 1)
    cmd_type = parts[0].lower()
    cmd_args = parts[1] if len(parts) > 1 else ''
    
    try:
        # ============ 搜索指令 ============
        if cmd_type == 'search':
            if cmd_args:
                search_url = f"https://www.baidu.com/s?wd={quote(cmd_args)}"
                webbrowser.open(search_url)
                return f"已搜索: {cmd_args}"
            else:
                return "错误: 请提供搜索关键词"
        
        # ============ 打开程序指令 ============
        elif cmd_type == 'open':
            if cmd_args:
                app_name = cmd_args.lower().strip()
                
                # 优先检查是否是网页版应用
                if app_name in WEB_APP_MAPPING:
                    web_url = WEB_APP_MAPPING[app_name]
                    webbrowser.open(web_url)
                    return f"已打开网页: {cmd_args}"
                
                # 使用动态查找获取程序路径
                app_path = get_program_path(app_name)
                
                # 尝试启动程序
                try:
                    subprocess.Popen(app_path, shell=True)
                    return f"已打开: {cmd_args}"
                except Exception as e:
                    return f"打开失败: {str(e)}，程序路径: {app_path}"
            else:
                return "错误: 请提供程序名称"
        
        # ============ 关闭程序指令 ============
        elif cmd_type == 'close':
            if cmd_args:
                app_name = cmd_args.lower().strip()
                
                # 获取进程名
                if app_name in APP_MAPPING:
                    process_name = APP_MAPPING[app_name]
                else:
                    process_name = app_name
                
                # 使用 taskkill 关闭进程
                result = subprocess.run(
                    f'taskkill /IM {process_name} /F',
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return f"已关闭: {cmd_args}"
                else:
                    return f"关闭失败: 未找到进程 {cmd_args}"
            else:
                return "错误: 请提供程序名称"
        
        # ============ 打开网址指令 ============
        elif cmd_type == 'url' or cmd_type == 'web':
            if cmd_args:
                url = cmd_args
                if not url.startswith('http'):
                    url = 'https://' + url
                webbrowser.open(url)
                return f"已打开网址: {url}"
            else:
                return "错误: 请提供网址"
        
        # ============ 执行系统命令 ============
        elif cmd_type == 'run' or cmd_type == 'exec':
            if cmd_args:
                result = subprocess.run(
                    cmd_args,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                output = result.stdout or result.stderr or "命令已执行"
                # 限制返回长度
                if len(output) > 500:
                    output = output[:500] + "...(输出过长已截断)"
                return output
            else:
                return "错误: 请提供要执行的命令"
        
        # ============ 音量控制 ============
        elif cmd_type == 'volume':
            return control_volume(cmd_args)
        
        # ============ 系统控制 ============
        elif cmd_type == 'shutdown':
            subprocess.Popen('shutdown /s /t 60', shell=True)
            return "系统将在60秒后关机，使用 shutdown /a 可取消"
        
        elif cmd_type == 'restart':
            subprocess.Popen('shutdown /r /t 60', shell=True)
            return "系统将在60秒后重启，使用 shutdown /a 可取消"
        
        elif cmd_type == 'lock':
            subprocess.Popen('rundll32.exe user32.dll,LockWorkStation', shell=True)
            return "已锁定屏幕"
        
        elif cmd_type == 'sleep':
            subprocess.Popen('rundll32.exe powrprof.dll,SetSuspendState 0,1,0', shell=True)
            return "系统进入睡眠模式"
        
        # ============ 状态查询 ============
        elif cmd_type == 'status' or cmd_type == 'ping':
            return "服务器运行正常"
        
        # ============ 退出服务器 ============
        elif cmd_type == 'exit' or cmd_type == 'quit':
            return "EXIT_SERVER"
        
        # ============ 帮助信息 ============
        elif cmd_type == 'help':
            help_text = """
可用指令:
  search <关键词>  - 百度搜索
  open <程序名>    - 打开程序
  close <程序名>   - 关闭程序
  url <网址>       - 打开网址
  run <命令>       - 执行系统命令
  volume up/down   - 调节音量
  shutdown         - 关机(60秒后)
  restart          - 重启(60秒后)
  lock             - 锁定屏幕
  sleep            - 睡眠
  status           - 查询状态
  exit             - 退出服务器
"""
            return help_text.strip()
        
        else:
            return f"未知指令: {cmd_type}，输入 help 查看帮助"
    
    except Exception as e:
        return f"执行出错: {str(e)}"


def handle_client(client_socket, client_address):
    """处理单个客户端连接"""
    print(f"[连接] 客户端已连接: {client_address}")
    
    try:
        # 接收指令
        data = client_socket.recv(1024)
        if not data:
            return None
        
        command = data.decode('utf-8')
        
        # 执行指令
        result = execute_command(command)
        
        # 发送结果
        client_socket.sendall(result.encode('utf-8'))
        
        print(f"[完成] 执行结果: {result[:100]}...")
        
        # 检查是否需要退出
        if result == "EXIT_SERVER":
            return "EXIT"
        
    except Exception as e:
        print(f"[错误] 处理客户端时出错: {str(e)}")
        try:
            client_socket.sendall(f"服务器错误: {str(e)}".encode('utf-8'))
        except:
            pass
    finally:
        client_socket.close()
        print(f"[断开] 客户端已断开: {client_address}")
    
    return None


def start_server():
    """启动服务器"""
    # 获取本机IP地址
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "未知"
    
    print("=" * 50)
    print("       远程控制服务端 v1.0")
    print("=" * 50)
    print(f"[信息] 本机名称: {hostname}")
    print(f"[信息] 本机IP: {local_ip}")
    print(f"[信息] 监听端口: {SERVER_PORT}")
    print("=" * 50)
    print("[提示] 请确保防火墙允许此端口通信")
    print("[提示] 客户端需要连接到此IP地址")
    print("=" * 50)
    
    # 创建服务器套接字
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((SERVER_HOST, SERVER_PORT))
        server_socket.listen(5)
        print(f"\n[启动] 服务器已启动，等待连接...")
        print("[提示] 按 Ctrl+C 停止服务器\n")
        
        while True:
            try:
                client_socket, client_address = server_socket.accept()
                
                # 处理客户端（可改为多线程处理多个客户端）
                result = handle_client(client_socket, client_address)
                
                if result == "EXIT":
                    print("[关闭] 收到退出指令，服务器关闭")
                    break
                    
            except KeyboardInterrupt:
                print("\n[关闭] 用户中断，服务器关闭")
                break
    
    except OSError as e:
        print(f"[错误] 无法启动服务器: {str(e)}")
        print("[提示] 端口可能被占用，请检查或更换端口")
    
    finally:
        server_socket.close()
        print("[完成] 服务器已停止")


if __name__ == '__main__':
    start_server()