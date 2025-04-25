"""
Android设备控制MCP工具实现
"""
import os
import json
import logging
import inspect
import subprocess
from typing import Dict, List, Any, Optional, Callable, Union
from pydantic import BaseModel, Field, create_model

# 修改为相对导入
from ..core.mcp_server import MCPTool
from ..core.device_controller import DeviceController
from ..core.app_controller import AppController
from ..core.system_controller import SystemController
from ..core.advanced_controller import AdvancedController
from ..core.multi_device_controller import MultiDeviceController

logger = logging.getLogger("android_tools")


class AndroidTools:
    """Android设备控制工具集"""
    
    def __init__(self, adb_path: str = "adb", device_id: str = None):
        """
        初始化Android工具集
        
        Args:
            adb_path: ADB命令路径
            device_id: 设备ID，如果有多个设备连接时需要指定
        """
        self.adb_path = adb_path
        self.device_id = device_id
        
        # 创建不同功能的控制器
        self.device_controller = DeviceController(adb_path, device_id)
        self.app_controller = AppController(adb_path, device_id)
        self.system_controller = SystemController(adb_path, device_id)
        self.advanced_controller = AdvancedController(adb_path, device_id)
        self.multi_device_controller = MultiDeviceController(adb_path, device_id)
    
    def create_tools(self) -> List[MCPTool]:
        """
        创建MCP工具列表
        
        Returns:
            MCP工具列表
        """
        tools = []
        
        # 获取所有以"tool_"开头的方法
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith("tool_"):
                tool_name = name[5:]  # 去掉"tool_"前缀
                
                # 获取方法信息
                docstring = method.__doc__ or ""
                description = docstring.strip().split("\n")[0] if docstring else ""
                
                # 构建参数Schema
                input_schema = self._build_input_schema(method)
                
                # 构建注解
                annotations = {}
                if "获取" in description or "查询" in description or "列出" in description:
                    annotations["readOnlyHint"] = True
                elif "删除" in description or "卸载" in description or "清除" in description:
                    annotations["destructiveHint"] = True
                    
                # 构建工具对象
                tool = MCPTool(
                    name=tool_name,
                    description=description,
                    handler=method,
                    input_schema=input_schema,
                    annotations=annotations
                )
                tools.append(tool)
                
        return tools
    
    def _build_input_schema(self, method: Callable) -> Dict[str, Any]:
        """
        构建输入参数Schema
        
        Args:
            method: 方法
            
        Returns:
            JSON Schema
        """
        # 获取方法签名
        sig = inspect.signature(method)
        
        properties = {}
        required = []
        
        # 遍历参数
        for param_name, param in sig.parameters.items():
            # 跳过self参数
            if param_name == "self" or param_name == "params":
                continue
                
            # 确定参数类型
            if param.annotation == inspect.Parameter.empty:
                param_type = "string"
            elif param.annotation == str:
                param_type = "string"
            elif param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == List[str]:
                param_type = "array"
                item_type = "string"
            elif param.annotation == List[int]:
                param_type = "array"
                item_type = "integer"
            else:
                param_type = "string"
                
            # 构建参数属性
            param_property = {"type": param_type}
            
            # 如果是数组，添加items
            if param_type == "array":
                param_property["items"] = {"type": item_type}
                
            # 添加参数描述
            if method.__doc__:
                lines = method.__doc__.strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if line.startswith(param_name + ":"):
                        param_property["description"] = line.split(":", 1)[1].strip()
                        break
                        
            # 添加属性
            properties[param_name] = param_property
            
            # 如果参数没有默认值，则为必需参数
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
                
        # 构建Schema
        schema = {
            "type": "object",
            "properties": properties
        }
        
        if required:
            schema["required"] = required
            
        return schema
    
    # 以下是工具方法，按功能分组
    
    # 屏幕操作相关工具
    
    def tool_get_screen_size(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取屏幕尺寸
        
        Returns:
            屏幕尺寸 {width, height}
        """
        width, height = self.device_controller.get_device_resolution()
        return {
            "width": width,
            "height": height
        }
    
    def tool_take_screenshot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        截取屏幕截图
        
        Args:
            resize_ratio: 图像缩放比例，默认0.5
            
        Returns:
            截图文件路径
        """
        resize_ratio = params.get("resize_ratio", 0.5)
        screenshot_path = self.device_controller.get_screenshot(resize_ratio=float(resize_ratio))
        
        # 构建URL路径
        file_name = os.path.basename(screenshot_path)
        url_path = f"/static/screenshot/{file_name}"
        
        return {
            "path": screenshot_path,
            "url": url_path
        }
    
    def tool_tap_screen(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        点击屏幕
        
        Args:
            x: X坐标（像素或百分比）
            y: Y坐标（像素或百分比）
            is_percent: 坐标是否为屏幕百分比，默认True
            
        Returns:
            操作结果
        """
        x = params.get("x")
        y = params.get("y")
        is_percent = params.get("is_percent", True)
        
        success = self.device_controller.tap(float(x), float(y), bool(is_percent))
        return {"success": success}
    
    def tool_long_press(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        长按屏幕
        
        Args:
            x: X坐标（像素或百分比）
            y: Y坐标（像素或百分比）
            duration: 按住时长(毫秒)，默认1000
            is_percent: 坐标是否为屏幕百分比，默认True
            
        Returns:
            操作结果
        """
        x = params.get("x")
        y = params.get("y")
        duration = params.get("duration", 1000)
        is_percent = params.get("is_percent", True)
        
        success = self.device_controller.long_press(
            float(x), float(y), int(duration), bool(is_percent)
        )
        return {"success": success}
    
    def tool_swipe(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        滑动屏幕
        
        Args:
            x1: 起始X坐标（像素或百分比）
            y1: 起始Y坐标（像素或百分比）
            x2: 结束X坐标（像素或百分比）
            y2: 结束Y坐标（像素或百分比）
            duration: 滑动时长(毫秒)，默认500
            is_percent: 坐标是否为屏幕百分比，默认True
            
        Returns:
            操作结果
        """
        x1 = params.get("x1")
        y1 = params.get("y1")
        x2 = params.get("x2")
        y2 = params.get("y2")
        duration = params.get("duration", 500)
        is_percent = params.get("is_percent", True)
        
        success = self.device_controller.swipe(
            float(x1), float(y1), float(x2), float(y2), int(duration), bool(is_percent)
        )
        return {"success": success}
    
    def tool_multi_touch(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        多点触控操作
        
        Args:
            points: 触控点列表，每个点为[x, y]坐标数组
            is_percent: 坐标是否为屏幕百分比，默认True
            
        Returns:
            操作结果
        """
        points = params.get("points", [])
        is_percent = params.get("is_percent", True)
        
        # 将points列表转换为元组列表
        points_tuples = [(float(p[0]), float(p[1])) for p in points]
        
        success = self.device_controller.multi_touch(points_tuples, bool(is_percent))
        return {"success": success}
    
    def tool_pinch(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        双指缩放操作
        
        Args:
            center_x: 缩放中心点X坐标（像素或百分比）
            center_y: 缩放中心点Y坐标（像素或百分比）
            start_distance: 起始两指间距离（像素或百分比）
            end_distance: 结束两指间距离（像素或百分比）
            duration: 操作持续时间(毫秒)，默认500
            is_percent: 坐标是否为屏幕百分比，默认True
            
        Returns:
            操作结果
        """
        center_x = params.get("center_x")
        center_y = params.get("center_y")
        start_distance = params.get("start_distance")
        end_distance = params.get("end_distance")
        duration = params.get("duration", 500)
        is_percent = params.get("is_percent", True)
        
        success = self.device_controller.pinch(
            float(center_x), float(center_y),
            float(start_distance), float(end_distance),
            int(duration), bool(is_percent)
        )
        return {"success": success}
    
    def tool_slide_screen(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        向上/向下滑动屏幕
        
        Args:
            direction: 滑动方向，up或down
            distance_percent: 滑动距离占屏幕高度的百分比，默认0.3
            duration: 滑动时长(毫秒)，默认500
            
        Returns:
            操作结果
        """
        direction = params.get("direction")
        distance_percent = params.get("distance_percent", 0.3)
        duration = params.get("duration", 500)
        
        if direction == "up":
            success = self.device_controller.slide_up(float(distance_percent), int(duration))
        elif direction == "down":
            success = self.device_controller.slide_down(float(distance_percent), int(duration))
        else:
            return {"success": False, "error": "无效的滑动方向，应为up或down"}
            
        return {"success": success}
    
    # 设备控制相关工具
    
    def tool_press_back(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        点击返回键
        
        Returns:
            操作结果
        """
        success = self.device_controller.press_back()
        return {"success": success}
    
    def tool_go_to_home(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        返回桌面
        
        Returns:
            操作结果
        """
        success = self.device_controller.go_to_home()
        return {"success": success}
    
    def tool_press_power(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        按下电源键
        
        Returns:
            操作结果
        """
        success = self.device_controller.press_power()
        return {"success": success}
    
    def tool_unlock_screen(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        解锁屏幕
        
        Returns:
            操作结果
        """
        success = self.device_controller.unlock_screen()
        return {"success": success}
    
    def tool_adjust_volume(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        调节音量
        
        Args:
            volume_type: 音量类型，可选值：music, call, ring, notification, system, alarm，默认music
            level: 要设置的音量级别，可选
            direction: 调整方向，可选值："up", "down"，仅在未指定level时生效
            
        Returns:
            操作结果和当前音量
        """
        volume_type = params.get("volume_type", "music")
        level = params.get("level", None)
        direction = params.get("direction", None)
        
        if level is not None:
            level = int(level)
            
        current_volume = self.device_controller.adjust_volume(volume_type, level, direction)
        
        return {
            "success": current_volume >= 0,
            "current_volume": current_volume
        }
    
    def tool_rotate_screen(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        控制屏幕旋转
        
        Args:
            orientation: 屏幕方向
                0: 自动旋转
                1: 竖屏模式 (portrait)
                2: 横屏模式 (landscape)
                3: 反向竖屏 (reverse portrait)
                4: 反向横屏 (reverse landscape)
                
        Returns:
            操作结果
        """
        orientation = params.get("orientation", 0)
        success = self.device_controller.rotate_screen(int(orientation))
        return {"success": success}
    
    def tool_set_brightness(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        设置屏幕亮度
        
        Args:
            level: 亮度级别(0-255)或百分比(0-100)，如果超过100则视为绝对值(0-255)
            auto_mode: 是否设置为自动亮度模式，默认False
            
        Returns:
            操作结果
        """
        level = params.get("level", 50)
        auto_mode = params.get("auto_mode", False)
        
        success = self.device_controller.set_brightness(int(level), bool(auto_mode))
        return {"success": success}
    
    def tool_keyevent(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        发送按键事件
        
        Args:
            keycode: 按键代码
            
        Returns:
            操作结果
        """
        keycode = params.get("keycode")
        success = self.device_controller.keyevent(int(keycode))
        return {"success": success}
    
    # 文本输入相关工具
    
    def tool_type_text(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        输入文本
        
        Args:
            text: 要输入的文本
            
        Returns:
            操作结果
        """
        text = params.get("text")
        success = self.device_controller.type_text(text)
        return {"success": success}
    
    def tool_switch_ime(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        切换输入法
        
        Args:
            ime_id: 输入法ID，可选，为空时返回可用输入法列表
            
        Returns:
            操作结果或输入法列表
        """
        ime_id = params.get("ime_id", None)
        result = self.device_controller.switch_ime(ime_id)
        
        if isinstance(result, list):
            return {"ime_list": result}
        else:
            return {"success": result}
    
    def tool_paste_text(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        粘贴文本
        
        Returns:
            操作结果
        """
        success = self.device_controller.paste_text()
        return {"success": success}
    
    def tool_clear_text(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        清除文本
        
        Args:
            char_count: 要删除的字符数量，可选，为空时清除所有文本
            
        Returns:
            操作结果
        """
        char_count = params.get("char_count", None)
        if char_count is not None:
            char_count = int(char_count)
            
        success = self.device_controller.clear_text(char_count)
        return {"success": success}
    
    # 应用管理相关工具
    
    def tool_start_app(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        启动应用
        
        Args:
            package_name: 应用包名
            activity_name: 活动名称，可选
            
        Returns:
            操作结果
        """
        package_name = params.get("package_name")
        activity_name = params.get("activity_name", None)
        success = self.app_controller.start_app(package_name, activity_name)
        return {"success": success}
    
    def tool_stop_app(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        停止应用
        
        Args:
            package_name: 应用包名
            
        Returns:
            操作结果
        """
        package_name = params.get("package_name")
        success = self.app_controller.stop_app(package_name)
        return {"success": success}
    
    def tool_list_apps(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        列出已安装应用
        
        Args:
            system_apps: 是否包含系统应用，默认False
            third_party_apps: 是否包含第三方应用，默认True
            
        Returns:
            应用列表
        """
        system_apps = params.get("system_apps", False)
        third_party_apps = params.get("third_party_apps", True)
        
        app_list = self.app_controller.list_apps(bool(system_apps), bool(third_party_apps))
        return {"apps": app_list}
    
    def tool_open_url(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        打开网址
        
        Args:
            url: 网址
            
        Returns:
            操作结果
        """
        url = params.get("url")
        success = self.app_controller.open_url(url)
        return {"success": success}
    
    def tool_get_current_app(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取前台应用信息
        
        Returns:
            前台应用信息
        """
        app_info = self.app_controller.get_current_app()
        return app_info
    
    def tool_check_app_installed(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        检查应用是否已安装
        
        Args:
            package_name: 应用包名
            
        Returns:
            是否已安装
        """
        package_name = params.get("package_name")
        installed = self.app_controller.check_app_installed(package_name)
        return {"installed": installed}
    
    def tool_monitor_app_start(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        监控应用启动
        
        Args:
            package_name: 应用包名
            timeout: 超时时间(秒)，默认30
            
        Returns:
            是否成功启动
        """
        package_name = params.get("package_name")
        timeout = params.get("timeout", 30)
        
        success = self.app_controller.monitor_app_start(package_name, int(timeout))
        return {"success": success}
    
    # 设备信息相关工具
    
    def tool_get_device_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取设备信息
        
        Returns:
            设备信息
        """
        return self.device_controller.get_device_info()
    
    def tool_list_devices(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        列出已连接设备
        
        Returns:
            设备列表
        """
        devices = self.system_controller.list_devices()
        return {"devices": devices}
    
    def tool_get_battery_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取设备电量信息
        
        Returns:
            电量信息
        """
        return self.system_controller.get_battery_info()
    
    def tool_get_storage_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取设备存储信息
        
        Returns:
            存储信息
        """
        return self.system_controller.get_storage_info()
    
    # 高级功能相关工具
    
    def tool_execute_shell(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行Shell命令
        
        Args:
            command: Shell命令
            timeout: 超时时间(秒)，默认30
            
        Returns:
            命令执行结果
        """
        command = params.get("command")
        timeout = params.get("timeout", 30)
        
        output, success = self.device_controller.execute_shell(command, int(timeout))
        return {
            "output": output,
            "success": success
        }
    
    def tool_image_recognition(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        图像识别与匹配
        
        Args:
            target_image_path: 目标图像路径
            threshold: 匹配阈值，默认0.7
            timeout: 超时时间(秒)，默认10
            
        Returns:
            匹配结果
        """
        target_image_path = params.get("target_image_path")
        threshold = params.get("threshold", 0.7)
        timeout = params.get("timeout", 10)
        
        result = self.advanced_controller.image_recognition(
            target_image_path, float(threshold), int(timeout)
        )
        
        if result:
            return {
                "found": True,
                "position": {
                    "x": result["x"],
                    "y": result["y"]
                },
                "confidence": result["confidence"]
            }
        else:
            return {"found": False}
    
    def tool_ocr_recognition(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        OCR文字识别
        
        Args:
            language: 语言，默认eng
            region: 识别区域 [x1, y1, x2, y2]，可选
            
        Returns:
            识别结果
        """
        language = params.get("language", "eng")
        region = params.get("region")
        
        result = self.advanced_controller.ocr_recognition(language, region)
        return result
    
    def tool_capture_logs(self, params: Dict[str, Any]) -> Dict[str, str]:
        """
        截取系统日志
        
        Args:
            log_type: 日志类型 (main, events, radio, system, crash)，默认main
            lines: 获取的行数，默认100
            package: 应用包名，可选
            
        Returns:
            日志内容
        """
        log_type = params.get("log_type", "main")
        lines = params.get("lines", 100)
        package = params.get("package")
        
        logs = self.advanced_controller.capture_logs(log_type, int(lines), package)
        return {"logs": logs}
    
    def tool_wake_device(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        唤醒设备
        
        Returns:
            操作结果
        """
        success = self.advanced_controller.wake_device()
        return {"success": success}
    
    def tool_sleep_device(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        休眠设备
        
        Returns:
            操作结果
        """
        success = self.advanced_controller.sleep_device()
        return {"success": success}
    
    def tool_explore_app(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        探索应用界面
        
        Args:
            package_name: 应用包名
            max_depth: 最大探索深度，默认3
            max_actions: 最大操作次数，默认30
            
        Returns:
            探索结果
        """
        package_name = params.get("package_name")
        max_depth = params.get("max_depth", 3)
        max_actions = params.get("max_actions", 30)
        
        result = self.advanced_controller.explore_app(package_name, int(max_depth), int(max_actions))
        return result
    
    def tool_file_operations(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        文件操作(上传/下载)
        
        Args:
            operation: 操作类型，push(上传)或pull(下载)
            local_path: 本地文件路径
            device_path: 设备文件路径
            
        Returns:
            操作结果
        """
        operation = params.get("operation")
        local_path = params.get("local_path")
        device_path = params.get("device_path")
        
        result = self.advanced_controller.file_operations(operation, local_path, device_path)
        return result
    
    def tool_check_root(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        检测设备是否已root
        
        Returns:
            检测结果
        """
        result = self.advanced_controller.check_root()
        return result
    
    def tool_connect_over_tcp(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        通过TCP/IP连接设备
        
        Args:
            ip_address: 设备IP地址
            port: 端口号，默认5555
            
        Returns:
            连接结果
        """
        ip_address = params.get("ip_address")
        port = params.get("port", 5555)
        
        result = self.advanced_controller.connect_over_tcp(ip_address, int(port))
        return result
        
    def tool_monitor_performance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        监控设备性能
        
        Args:
            package_name: 应用包名，可选，为空时监控系统性能
            duration: 监控持续时间(秒)，默认10
            interval: 采样间隔(秒)，默认1.0
            
        Returns:
            性能监控结果
        """
        package_name = params.get("package_name", None)
        duration = params.get("duration", 10)
        interval = params.get("interval", 1.0)
        
        result = self.advanced_controller.monitor_performance(package_name, int(duration), float(interval))
        return result
    
    def tool_screenshot_watcher(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        设备截屏监听器
        
        Args:
            start: 是否启动监听器，默认True，False表示停止
            interval: 截图间隔(秒)，默认2.0
            
        Returns:
            操作结果
        """
        start = params.get("start", True)
        interval = params.get("interval", 2.0)
        
        result = self.advanced_controller.screenshot_watcher(bool(start), float(interval))
        return result
    
    def tool_record_and_replay(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        脚本录制和回放
        
        Args:
            action: 操作类型，start_record(开始录制)、stop_record(停止录制)或replay(回放)
            script_path: 脚本路径，可选
            record_duration: 录制时长(秒)，默认60，仅在action为start_record时有效
            
        Returns:
            操作结果
        """
        action = params.get("action")
        script_path = params.get("script_path", None)
        record_duration = params.get("record_duration", 60)
        
        result = self.advanced_controller.record_and_replay(action, script_path, int(record_duration))
        return result
    
    def tool_run_test_case(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行自动化测试用例
        
        Args:
            test_path: 测试用例路径，可以是单个文件或目录
            test_type: 测试类型，支持airtest、appium、python，默认airtest
            
        Returns:
            测试执行结果
        """
        test_path = params.get("test_path")
        test_type = params.get("test_type", "airtest")
        
        result = self.advanced_controller.run_test_case(test_path, test_type)
        return result
        
    def tool_multi_device_management(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        多设备管理与操作
        
        Args:
            action: 操作类型，list(列出设备)、switch(切换设备)、execute(在多设备上执行命令)
            device_ids: 设备ID列表，在execute操作时使用
            device_id: 设备ID，在switch操作时使用
            command: 要执行的命令，在execute操作时使用
            
        Returns:
            操作结果
        """
        action = params.get("action", "list")
        device_ids = params.get("device_ids", [])
        device_id = params.get("device_id", "")
        command = params.get("command", "")
        
        # 列出所有设备
        if action == "list":
            devices = self.system_controller.list_devices()
            return {"devices": devices}
            
        # 切换当前控制的设备
        elif action == "switch":
            if not device_id:
                return {
                    "success": False,
                    "message": "未指定设备ID"
                }
                
            # 验证设备是否存在
            devices = self.system_controller.list_devices()
            device_exists = any(d.get("id") == device_id for d in devices)
            
            if not device_exists:
                return {
                    "success": False,
                    "message": f"设备 {device_id} 不存在或未连接"
                }
                
            # 更新控制器的设备ID
            self.device_controller.device_id = device_id
            self.app_controller.device_id = device_id
            self.system_controller.device_id = device_id
            self.advanced_controller.device_id = device_id
            
            # 重新初始化Airtest连接
            self.advanced_controller.init_airtest()
            
            return {
                "success": True,
                "message": f"已切换到设备 {device_id}"
            }
            
        # 在多设备上执行命令
        elif action == "execute":
            if not device_ids:
                return {
                    "success": False,
                    "message": "未指定设备ID列表"
                }
                
            if not command:
                return {
                    "success": False,
                    "message": "未指定要执行的命令"
                }
                
            # 执行命令
            results = []
            for dev_id in device_ids:
                # 构建特定设备的ADB命令
                cmd = f"{self.adb_path} -s {dev_id} {command}"
                
                try:
                    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    results.append({
                        "device_id": dev_id,
                        "success": proc.returncode == 0,
                        "output": proc.stdout,
                        "error": proc.stderr if proc.returncode != 0 else ""
                    })
                except Exception as e:
                    results.append({
                        "device_id": dev_id,
                        "success": False,
                        "error": str(e)
                    })
            
            return {
                "success": True,
                "results": results
            }
        else:
            return {
                "success": False,
                "message": f"不支持的操作类型: {action}"
            }
        
    def tool_toggle_wifi(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        设置WiFi开关
        
        Args:
            enable: True开启，False关闭
            
        Returns:
            操作结果
        """
        enable = params.get("enable", True)
        enable = enable if isinstance(enable, bool) else (str(enable).lower() == "true")
        
        success = self.system_controller.toggle_wifi(enable)
        return {"success": success}
    
    def tool_toggle_bluetooth(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        设置蓝牙开关
        
        Args:
            enable: True开启，False关闭
            
        Returns:
            操作结果
        """
        enable = params.get("enable", True)
        enable = enable if isinstance(enable, bool) else (str(enable).lower() == "true")
        
        success = self.system_controller.toggle_bluetooth(enable)
        return {"success": success}
    
    def tool_toggle_mobile_data(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        设置移动数据开关
        
        Args:
            enable: True开启，False关闭
            
        Returns:
            操作结果
        """
        enable = params.get("enable", True)
        enable = enable if isinstance(enable, bool) else (str(enable).lower() == "true")
        
        success = self.system_controller.toggle_mobile_data(enable)
        return {"success": success}
    
    def tool_toggle_airplane_mode(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        设置飞行模式
        
        Args:
            enable: True开启，False关闭
            
        Returns:
            操作结果
        """
        enable = params.get("enable", True)
        enable = enable if isinstance(enable, bool) else (str(enable).lower() == "true")
        
        success = self.system_controller.toggle_airplane_mode(enable)
        return {"success": success}
    
    def tool_connect_wifi(self, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        连接到指定WiFi
        
        Args:
            ssid: WiFi名称
            password: WiFi密码，开放网络可为None
            security_type: 安全类型，支持NONE/WEP/WPA/WPA2，默认WPA
            
        Returns:
            操作结果
        """
        ssid = params.get("ssid", "")
        password = params.get("password", None)
        security_type = params.get("security_type", "WPA")
        
        if not ssid:
            return {"success": False, "message": "WiFi名称不能为空"}
            
        success = self.system_controller.connect_wifi(ssid, password, security_type)
        return {"success": success}
    
    def tool_get_wifi_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取当前WiFi详细信息
        
        Returns:
            WiFi信息 {ssid, bssid, rssi, ip_address, link_speed, frequency}
        """
        wifi_info = self.system_controller.get_wifi_info()
        return wifi_info
    
    def tool_device_messaging(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        设备间消息传递
        
        Args:
            action: 操作类型，send（发送消息）、receive（接收消息）、clear（清空消息）
            device_id: 目标设备ID或来源设备ID
            message: 要发送的消息内容
            timeout: 接收消息的超时时间(秒)，默认5
            
        Returns:
            操作结果
        """
        action = params.get("action", "")
        device_id = params.get("device_id", None)
        message = params.get("message", None)
        timeout = params.get("timeout", 5)
        
        return self.multi_device_controller.device_messaging(
            action, device_id, message, int(timeout)
        )
    
    def tool_sync_operations(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        多设备同步操作
        
        Args:
            action: 操作类型，create（创建锁）、wait（等待锁）、set（设置锁）、release（释放锁）
            lock_name: 锁名称
            timeout: 等待超时时间(秒)，默认30
            
        Returns:
            操作结果
        """
        action = params.get("action", "")
        lock_name = params.get("lock_name", None)
        timeout = params.get("timeout", 30)
        
        return self.multi_device_controller.sync_operations(
            action, lock_name, int(timeout)
        )
    
    def tool_device_group_actions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        设备组操作
        
        Args:
            action: 操作类型，create（创建组）、list（列出组）、execute（执行命令）、delete（删除组）
            group_name: 组名称
            device_ids: 设备ID列表，在create操作时使用
            command: 要执行的命令，在execute操作时使用
            
        Returns:
            操作结果
        """
        action = params.get("action", "")
        group_name = params.get("group_name", None)
        device_ids = params.get("device_ids", [])
        command = params.get("command", None)
        
        # 确保device_ids是列表
        if isinstance(device_ids, str):
            try:
                device_ids = json.loads(device_ids)
            except:
                device_ids = [device_ids]
                
        return self.multi_device_controller.device_group_actions(
            action, group_name, device_ids, command
        )
    
    def tool_share_between_devices(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        设备间文件共享
        
        Args:
            action: 操作类型，copy_file（复制文件）、share_data（共享数据）、get_data（获取数据）
            source_device: 源设备ID，在copy_file操作时使用
            target_device: 目标设备ID，在copy_file操作时使用
            device_path: 设备文件路径，在copy_file操作时使用
            data_key: 数据键，在share_data和get_data操作时使用
            data_value: 数据值，在share_data操作时使用
            
        Returns:
            操作结果
        """
        action = params.get("action", "")
        source_device = params.get("source_device", None)
        target_device = params.get("target_device", None)
        device_path = params.get("device_path", None)
        data_key = params.get("data_key", None)
        data_value = params.get("data_value", None)
        
        return self.multi_device_controller.share_between_devices(
            action, source_device, target_device, None, device_path, data_key, data_value
        )

def register_android_tools(server, adb_path: str = "adb", device_id: str = None):
    """
    注册Android工具到MCP服务器
    
    Args:
        server: MCP服务器实例
        adb_path: ADB命令路径
        device_id: 设备ID
    """
    # 创建工具实例
    android_tools = AndroidTools(adb_path, device_id)
    
    # 注册控制器到服务器，用于资源清理
    if hasattr(server, "register_controller"):
        server.register_controller(android_tools.device_controller)
        server.register_controller(android_tools.app_controller)
        server.register_controller(android_tools.system_controller)
        server.register_controller(android_tools.advanced_controller)
        server.register_controller(android_tools.multi_device_controller)
    
    # 注册工具
    for tool in android_tools.create_tools():
        server.register_tool(tool) 