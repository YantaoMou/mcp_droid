#!/usr/bin/env python3
"""
MCPDroid 主程序入口
"""
import os
import sys
import logging
import argparse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI

from core.mcp_server import MCPServer
from tools.android_tools import register_android_tools

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="MCPDroid: Android设备控制MCP服务")
    parser.add_argument("--adb-path", default="adb", help="ADB命令路径")
    parser.add_argument("--device-id", help="设备ID，多设备时需要指定")
    parser.add_argument("--host", default="0.0.0.0", help="监听主机地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--debug", action="store_true", help="开启调试模式")
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    # 设置日志级别
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("调试模式已开启")
    
    # 检查ADB是否可用
    try:
        import subprocess
        result = subprocess.run(
            [args.adb_path, "version"], 
            capture_output=True, 
            text=True
        )
        if result.returncode != 0:
            logger.error(f"ADB命令不可用: {result.stderr}")
            return 1
            
        logger.info(f"ADB版本: {result.stdout.strip()}")
    except Exception as e:
        logger.error(f"检查ADB失败: {str(e)}")
        return 1
    
    # 创建服务器实例
    server = MCPServer()
    
    # 确保静态目录及子目录存在
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    
    # 确保截图目录存在
    screenshot_dir = os.path.join(static_dir, "screenshot")
    os.makedirs(screenshot_dir, exist_ok=True)
    
    # 确保日志目录存在
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # 配置静态文件服务
    server.app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # 注册Android工具
    register_android_tools(server, args.adb_path, args.device_id)
    
    # 启动服务器
    logger.info(f"启动MCPDroid服务，监听地址: {args.host}:{args.port}")
    server.run(host=args.host, port=args.port)
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 