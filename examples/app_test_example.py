#!/usr/bin/env python3
"""
MCPDroid 应用测试示例

此示例演示如何使用MCPDroid服务对Android应用进行简单的自动化测试。
"""
import sys
import json
import time
import requests
import argparse


# 服务器地址配置
MCP_SERVER_URL = "http://localhost:8000/jsonrpc"


def call_jsonrpc(method, params=None):
    """调用JSON-RPC方法"""
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": method,
        "params": params or {}
    }
    
    response = requests.post(MCP_SERVER_URL, headers=headers, json=payload)
    data = response.json()
    
    if "error" in data:
        print(f"错误: {data['error']['message']}")
        return None
        
    return data.get("result")


def call_tool(name, parameters=None):
    """调用工具"""
    result = call_jsonrpc("tools/call", {
        "name": name,
        "parameters": parameters or {}
    })
    
    if result:
        return result.get("result")
    return None


def initialize_session():
    """初始化MCP会话"""
    result = call_jsonrpc("initialize", {
        "client_info": {
            "name": "MCPDroid-AppTest-Example",
            "version": "1.0.0"
        }
    })
    
    if result:
        print(f"连接到 {result['server_info']['name']} {result['server_info']['version']}")
        return True
    return False


def take_screenshot(filename=None):
    """截取屏幕截图"""
    result = call_tool("take_screenshot")
    if result:
        print(f"截图已保存: {result['path']}")
    return result


def check_app_installed(package_name):
    """检查应用是否已安装"""
    result = call_tool("check_app_installed", {"package_name": package_name})
    if result:
        return result.get("installed", False)
    return False


def start_app(package_name, activity_name=None):
    """启动应用"""
    params = {"package_name": package_name}
    if activity_name:
        params["activity_name"] = activity_name
    
    result = call_tool("start_app", params)
    if result:
        return result.get("success", False)
    return False


def stop_app(package_name):
    """停止应用"""
    result = call_tool("stop_app", {"package_name": package_name})
    if result:
        return result.get("success", False)
    return False


def get_current_app():
    """获取当前前台应用"""
    return call_tool("get_current_app")


def tap_screen(x, y, is_percent=True):
    """点击屏幕"""
    result = call_tool("tap_screen", {
        "x": x,
        "y": y,
        "is_percent": is_percent
    })
    if result:
        return result.get("success", False)
    return False


def type_text(text):
    """输入文本"""
    result = call_tool("type_text", {"text": text})
    if result:
        return result.get("success", False)
    return False


def press_back():
    """按下返回键"""
    result = call_tool("press_back", {})
    if result:
        return result.get("success", False)
    return False


def go_to_home():
    """返回桌面"""
    result = call_tool("go_to_home", {})
    if result:
        return result.get("success", False)
    return False


def test_calculator_app():
    """测试计算器应用"""
    print("\n测试计算器应用")
    
    # 常见计算器包名
    calculator_packages = [
        "com.android.calculator2",  # 原生Android
        "com.google.android.calculator",  # Google计算器
        "com.sec.android.app.popupcalculator",  # 三星
        "com.miui.calculator",  # 小米
        "com.oneplus.calculator",  # 一加
        "com.asus.calculator",  # 华硕
        "com.oppo.calculator"  # OPPO
    ]
    
    # 查找已安装的计算器应用
    calculator_package = None
    for package in calculator_packages:
        if check_app_installed(package):
            calculator_package = package
            print(f"找到计算器应用: {package}")
            break
    
    if not calculator_package:
        print("未找到计算器应用，请指定包名")
        return False
    
    # 启动计算器应用
    print("启动计算器应用...")
    if not start_app(calculator_package):
        print("启动计算器应用失败")
        return False
    
    # 等待应用启动
    time.sleep(2)
    
    # 截取初始状态截图
    print("截取初始状态截图")
    take_screenshot()
    
    # 根据不同厂商计算器的布局差异，这里使用相对位置点击
    # 注意: 这只是示例，实际应用中应该结合图像识别或UI元素定位
    print("进行简单计算: 1 + 2 = 3")
    
    # 点击数字1
    tap_screen(0.2, 0.6)
    time.sleep(0.5)
    
    # 点击加号
    tap_screen(0.8, 0.6)
    time.sleep(0.5)
    
    # 点击数字2
    tap_screen(0.2, 0.7)
    time.sleep(0.5)
    
    # 点击等号
    tap_screen(0.8, 0.8)
    time.sleep(1)
    
    # 截取计算结果截图
    print("截取计算结果截图")
    take_screenshot()
    
    # 返回桌面
    print("返回桌面")
    go_to_home()
    
    print("计算器测试完成")
    return True


def test_browser_app(url="https://www.baidu.com"):
    """测试浏览器应用"""
    print(f"\n测试浏览器打开URL: {url}")
    
    # 使用系统浏览器打开URL
    print("打开URL...")
    result = call_tool("open_url", {"url": url})
    if not result or not result.get("success", False):
        print("打开URL失败")
        return False
    
    # 等待页面加载
    print("等待页面加载...")
    time.sleep(5)
    
    # 截取页面截图
    print("截取页面截图")
    take_screenshot()
    
    # 尝试搜索
    print("尝试在搜索框中输入文本")
    # 点击搜索框 (百度搜索框通常在页面上部)
    tap_screen(0.5, 0.2)
    time.sleep(1)
    
    # 输入搜索文本
    print("输入搜索文本: MCPDroid测试")
    type_text("MCPDroid测试")
    time.sleep(1)
    
    # 点击搜索按钮 (通常在键盘右下角)
    tap_screen(0.9, 0.9)
    time.sleep(3)
    
    # 截取搜索结果截图
    print("截取搜索结果截图")
    take_screenshot()
    
    # 返回两次，退出浏览器
    print("退出浏览器")
    press_back()
    time.sleep(1)
    press_back()
    time.sleep(1)
    
    # 返回桌面
    go_to_home()
    
    print("浏览器测试完成")
    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MCPDroid应用测试示例")
    parser.add_argument("--skip-calculator", action="store_true", help="跳过计算器测试")
    parser.add_argument("--skip-browser", action="store_true", help="跳过浏览器测试")
    parser.add_argument("--url", default="https://www.baidu.com", help="浏览器测试的URL")
    args = parser.parse_args()
    
    print("MCPDroid 应用测试示例")
    print("======================\n")
    
    # 初始化会话
    if not initialize_session():
        print("初始化会话失败，请确保MCPDroid服务正在运行")
        return 1
    
    # 获取设备信息
    device_info = call_tool("get_device_info")
    if device_info:
        print(f"设备信息: {json.dumps(device_info, indent=2, ensure_ascii=False)}")
    
    # 测试计算器应用
    if not args.skip_calculator:
        test_calculator_app()
    
    # 测试浏览器应用
    if not args.skip_browser:
        test_browser_app(args.url)
    
    print("\n所有测试完成")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 