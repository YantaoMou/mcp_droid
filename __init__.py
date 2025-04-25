"""
MCPDroid: Model Context Protocol Android Device Control

基于MCP协议的Android设备控制服务，使大型语言模型能够通过标准化接口控制和操作Android设备。
"""

__version__ = "1.0.0"

# 添加包导入路径支持
import os
import sys

# 确保当前目录在导入路径中，以支持相对导入
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 将包路径和子模块导出
__all__ = ["core", "tools"] 