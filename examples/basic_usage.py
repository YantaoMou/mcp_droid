#!/usr/bin/env python3
"""
MCPDroid基本使用示例

此示例演示如何使用Python通过JSON-RPC客户端调用MCPDroid服务的工具功能。
"""
import sys
import json
import time
import requests


# 服务器地址配置
MCP_SERVER_URL = "http://localhost:8000/jsonrpc"


def call_jsonrpc(method, params=None):
    """
    调用JSON-RPC方法
    
    Args:
        method: 方法名称
        params: 参数字典
        
    Returns:
        响应结果或错误信息
    """
    headers = {
        "Content-Type": "application/json",
    }
    
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


def initialize_session():
    """初始化MCP会话"""
    result = call_jsonrpc("initialize", {
        "client_info": {
            "name": "MCPDroid-Example",
            "version": "1.0.0"
        }
    })
    
    if result:
        print(f"连接到 {result['server_info']['name']} {result['server_info']['version']}")
        return True
    return False


def list_available_tools():
    """列出所有可用工具"""
    result = call_jsonrpc("tools/list")
    if not result:
        return []
        
    tools = result.get("tools", [])
    return tools


def call_tool(name, parameters=None):
    """
    调用工具
    
    Args:
        name: 工具名称
        parameters: 工具参数
        
    Returns:
        工具调用结果
    """
    result = call_jsonrpc("tools/call", {
        "name": name,
        "parameters": parameters or {}
    })
    
    if result:
        return result.get("result")
    return None


def main():
    """主函数"""
    print("MCPDroid 基本使用示例")
    print("======================\n")
    
    # 初始化会话
    if not initialize_session():
        print("初始化会话失败，请确保MCPDroid服务正在运行")
        return 1
        
    # 列出可用工具
    print("\n可用工具列表:")
    tools = list_available_tools()
    for tool in tools:
        print(f"- {tool['name']}: {tool['description']}")
    
    # 基本功能演示
    print("\n基本功能演示:")
    
    # 获取设备信息
    print("\n1. 获取设备信息")
    device_info = call_tool("get_device_info")
    if device_info:
        print(f"设备信息: {json.dumps(device_info, indent=2, ensure_ascii=False)}")
    
    # 获取屏幕尺寸
    print("\n2. 获取屏幕尺寸")
    screen_size = call_tool("get_screen_size")
    if screen_size:
        print(f"屏幕尺寸: {screen_size['width']}x{screen_size['height']}")
    
    # 获取电池信息
    print("\n3. 获取电池信息")
    battery_info = call_tool("get_battery_info")
    if battery_info:
        print(f"电池信息: {json.dumps(battery_info, indent=2, ensure_ascii=False)}")
    
    # 截取屏幕截图
    print("\n4. 截取屏幕截图")
    screenshot = call_tool("take_screenshot", {"resize_ratio": 0.5})
    if screenshot:
        print(f"截图已保存: {screenshot['path']}")
        print(f"访问URL: {screenshot['url']}")
    
    # 列出已安装应用
    print("\n5. 列出已安装应用(前5个)")
    app_list = call_tool("list_apps", {"third_party_apps": True, "system_apps": False})
    if app_list and app_list.get("apps"):
        for i, app in enumerate(app_list["apps"][:5]):
            print(f"  {i+1}. {app['app_name']} ({app['package_name']})")
    
    print("\n示例完成")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 