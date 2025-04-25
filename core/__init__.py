"""
MCPDroid核心模块包
"""
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 导出控制器类
from core.device_controller import DeviceController
from core.app_controller import AppController
from core.system_controller import SystemController
from core.advanced_controller import AdvancedController
from core.multi_device_controller import MultiDeviceController 