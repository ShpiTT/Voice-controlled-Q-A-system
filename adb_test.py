"""
ADB熄屏控制工具
"""

import subprocess


def screen_off():
    """熄灭手机屏幕"""
    try:
        # KEYCODE_SLEEP = 223
        result = subprocess.run(
            ["adb", "shell", "input", "keyevent", "223"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ 屏幕已熄灭")
            return True
        else:
            print("❌ 熄屏失败")
            return False
    except Exception as e:
        print(f"❌ 执行出错: {e}")
        return False


if __name__ == "__main__":
    screen_off()
