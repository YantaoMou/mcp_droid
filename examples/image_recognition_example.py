#!/usr/bin/env python3
"""
MCPDroid图像识别示例

此示例演示如何使用MCPDroid服务的图像识别功能。
"""
import sys
import json
import time
import os
import requests
from PIL import Image, ImageDraw


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
            "name": "MCPDroid-ImageRecognition-Example",
            "version": "1.0.0"
        }
    })
    
    if result:
        print(f"连接到 {result['server_info']['name']} {result['server_info']['version']}")
        return True
    return False


def capture_reference_image(target_path):
    """
    截取参考图像
    
    Args:
        target_path: 保存路径
    
    Returns:
        是否成功
    """
    screenshot = call_tool("take_screenshot")
    if not screenshot:
        return False
    
    # 文件已经保存到本地，只要复制即可
    try:
        # 打开截图
        img = Image.open(screenshot["path"])
        
        # 获取屏幕尺寸
        width, height = img.size
        
        # 裁剪屏幕中央部分区域作为参考图像
        # 这里裁剪中央1/9区域，可以根据实际需要调整
        crop_width = width // 3
        crop_height = height // 3
        left = (width - crop_width) // 2
        top = (height - crop_height) // 2
        right = left + crop_width
        bottom = top + crop_height
        
        # 裁剪图像
        cropped_img = img.crop((left, top, right, bottom))
        
        # 保存参考图像
        cropped_img.save(target_path)
        print(f"参考图像已保存: {target_path}")
        print(f"区域: 左={left}, 上={top}, 右={right}, 下={bottom}")
        return True
    except Exception as e:
        print(f"保存参考图像失败: {str(e)}")
        return False


def find_image_on_screen(target_image_path, threshold=0.7, timeout=10):
    """
    在屏幕上查找图像
    
    Args:
        target_image_path: 目标图像路径
        threshold: 匹配阈值，默认0.7
        timeout: 超时时间，默认10秒
        
    Returns:
        匹配结果或None
    """
    result = call_tool("image_recognition", {
        "target_image_path": target_image_path,
        "threshold": threshold,
        "timeout": timeout
    })
    
    return result


def tap_image_if_found(target_image_path, threshold=0.7, timeout=10):
    """
    找到并点击图像
    
    Args:
        target_image_path: 目标图像路径
        threshold: 匹配阈值，默认0.7
        timeout: 超时时间，默认10秒
        
    Returns:
        是否成功点击图像
    """
    result = find_image_on_screen(target_image_path, threshold, timeout)
    
    if result and result.get("found"):
        position = result.get("position", {})
        x, y = position.get("x", 0), position.get("y", 0)
        
        # 点击匹配位置
        tap_result = call_tool("tap_screen", {
            "x": x,
            "y": y,
            "is_percent": False  # 使用绝对坐标
        })
        
        return tap_result and tap_result.get("success", False)
    
    return False


def take_screenshot_and_mark_match(target_image_path, output_path):
    """
    截取屏幕并标记匹配位置
    
    Args:
        target_image_path: 目标图像路径
        output_path: 输出图像路径
        
    Returns:
        是否成功
    """
    # 先截取屏幕
    screenshot = call_tool("take_screenshot")
    if not screenshot:
        return False
    
    # 查找图像位置
    result = find_image_on_screen(target_image_path)
    if not result or not result.get("found"):
        print("未找到匹配图像")
        return False
    
    try:
        # 打开截图
        img = Image.open(screenshot["path"])
        draw = ImageDraw.Draw(img)
        
        # 获取匹配位置
        position = result.get("position", {})
        x, y = position.get("x", 0), position.get("y", 0)
        
        # 打开目标图像以获取尺寸
        target_img = Image.open(target_image_path)
        w, h = target_img.size
        
        # 在截图上绘制矩形标记匹配位置
        draw.rectangle([(x - w // 2, y - h // 2), (x + w // 2, y + h // 2)], outline="red", width=5)
        
        # 在匹配位置附近标注置信度
        confidence = result.get("confidence", 0)
        draw.text((x, y + h // 2 + 10), f"Confidence: {confidence:.2f}", fill="red")
        
        # 保存标记后的图像
        img.save(output_path)
        print(f"标记后的图像已保存: {output_path}")
        return True
    except Exception as e:
        print(f"标记图像失败: {str(e)}")
        return False


def main():
    """主函数"""
    print("MCPDroid 图像识别示例")
    print("======================\n")
    
    # 创建保存目录
    os.makedirs("examples/images", exist_ok=True)
    
    # 初始化会话
    if not initialize_session():
        print("初始化会话失败，请确保MCPDroid服务正在运行")
        return 1
    
    # 演示图像识别功能
    print("\n图像识别功能演示:")
    
    # 步骤1: 截取参考图像
    print("\n1. 截取参考图像")
    reference_image_path = "examples/images/reference.png"
    if not capture_reference_image(reference_image_path):
        print("截取参考图像失败")
        return 1
    
    # 步骤2: 查找图像
    print("\n2. 在屏幕上查找参考图像")
    time.sleep(1)  # 稍等片刻
    result = find_image_on_screen(reference_image_path)
    if result and result.get("found"):
        position = result.get("position", {})
        confidence = result.get("confidence", 0)
        print(f"在屏幕位置 ({position.get('x')}, {position.get('y')}) 找到匹配，置信度: {confidence:.2f}")
    else:
        print("未找到匹配图像")
    
    # 步骤3: 标记匹配位置
    print("\n3. 标记匹配位置")
    marked_image_path = "examples/images/marked_match.png"
    take_screenshot_and_mark_match(reference_image_path, marked_image_path)
    
    # 步骤4: 点击匹配位置
    print("\n4. 点击匹配位置")
    if tap_image_if_found(reference_image_path):
        print("成功点击匹配图像")
    else:
        print("点击匹配图像失败")
    
    print("\n5. OCR文字识别")
    ocr_result = call_tool("ocr_recognition", {"language": "eng"})
    if ocr_result:
        print(f"识别文本: {ocr_result.get('text', '')[:100]}...")
        print(f"置信度: {ocr_result.get('confidence', 0):.2f}")
    else:
        print("OCR文字识别失败")
    
    print("\n示例完成")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 