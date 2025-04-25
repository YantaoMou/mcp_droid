"""
设备控制器基类，提供与Android设备交互的基本功能
"""
import os
import time
import logging
import subprocess
from typing import Tuple, List, Dict, Any, Optional, Union
from PIL import Image
import json
import re


class DeviceController:
    """
    Android设备控制器基类，封装ADB命令与设备交互
    """
    def __init__(self, adb_path: str = "adb", device_id: str = None):
        """
        初始化设备控制器
        
        Args:
            adb_path: ADB命令路径
            device_id: 设备ID，如果有多个设备连接时需要指定
        """
        self.adb_path = adb_path
        self.device_id = device_id
        self.logger = logging.getLogger("DeviceController")
        self.screenshot_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "screenshot")
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
    def _build_adb_cmd(self, cmd: str) -> str:
        """构建ADB命令行"""
        if self.device_id:
            return f"{self.adb_path} -s {self.device_id} {cmd}"
        return f"{self.adb_path} {cmd}"
    
    def run_adb_cmd(self, cmd: str, shell: bool = True, timeout: int = 30) -> Tuple[str, str, int]:
        """
        执行ADB命令并返回结果
        
        Args:
            cmd: ADB命令
            shell: 是否使用shell执行
            timeout: 命令超时时间(秒)
            
        Returns:
            返回元组 (stdout, stderr, return_code)
        """
        full_cmd = self._build_adb_cmd(cmd)
        self.logger.debug(f"执行命令: {full_cmd}")
        try:
            result = subprocess.run(
                full_cmd, 
                shell=shell, 
                timeout=timeout,
                capture_output=True,
                text=True
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            self.logger.error(f"命令执行超时: {full_cmd}")
            return "", f"Command timed out after {timeout} seconds", -1
        except subprocess.CalledProcessError as e:
            self.logger.error(f"命令执行返回错误状态码: {str(e)}")
            return "", f"Command failed with exit code {e.returncode}: {e.stderr if hasattr(e, 'stderr') else ''}", e.returncode
        except OSError as e:
            self.logger.error(f"命令执行系统错误: {str(e)}")
            return "", f"System error: {str(e)}", -2
        except Exception as e:
            self.logger.error(f"命令执行未知错误: {str(e)}")
            return "", f"Unknown error: {str(e)}", -3
    
    def is_device_connected(self) -> bool:
        """检查设备是否已连接"""
        stdout, _, _ = self.run_adb_cmd("devices")
        if self.device_id:
            return self.device_id in stdout
        # 如果没有指定设备ID，检查是否有至少一个设备连接
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        return len(lines) > 1  # 第一行是标题行
    
    def get_device_resolution(self) -> Tuple[int, int]:
        """
        获取设备屏幕分辨率
        
        Returns:
            (width, height) 分辨率元组
        """
        stdout, stderr, code = self.run_adb_cmd("shell wm size")
        if code != 0:
            self.logger.error(f"获取屏幕分辨率失败: {stderr}")
            return (0, 0)
        
        try:
            resolution_line = stdout.strip().split('\n')[-1]
            width, height = map(int, resolution_line.split(' ')[-1].split('x'))
            return width, height
        except Exception as e:
            self.logger.error(f"解析屏幕分辨率失败: {str(e)}")
            return (0, 0)
    
    def get_screenshot(self, filename: str = None, resize_ratio: float = 1.0) -> str:
        """
        获取屏幕截图并保存
        
        Args:
            filename: 文件名(不含路径)，为None时使用时间戳
            resize_ratio: 图像缩放比例，默认为1.0不缩放
            
        Returns:
            保存的图片文件路径
        """
        if filename is None:
            filename = f"screenshot_{int(time.time())}.png"
        
        # 确保文件名有正确的扩展名
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            filename += '.png'
            
        remote_path = f"/sdcard/{filename}"
        local_path = os.path.join(self.screenshot_dir, filename)
        
        # 清理旧截图
        self.run_adb_cmd(f"shell rm -f {remote_path}")
        
        # 截取屏幕
        _, err, code = self.run_adb_cmd(f"shell screencap -p {remote_path}")
        if code != 0:
            self.logger.error(f"截屏失败: {err}")
            return ""
            
        # 从设备拉取截图
        _, err, code = self.run_adb_cmd(f"pull {remote_path} {self.screenshot_dir}")
        if code != 0:
            self.logger.error(f"获取截图失败: {err}")
            return ""
            
        # 如果需要调整大小
        if resize_ratio != 1.0:
            try:
                image = Image.open(local_path)
                original_width, original_height = image.size
                new_width = int(original_width * resize_ratio)
                new_height = int(original_height * resize_ratio)
                resized_image = image.resize((new_width, new_height))
                
                # 转换格式并保存
                jpg_filename = os.path.splitext(filename)[0] + '.jpg'
                jpg_path = os.path.join(self.screenshot_dir, jpg_filename)
                resized_image.convert("RGB").save(jpg_path, "JPEG")
                return jpg_path
            except Exception as e:
                self.logger.error(f"处理截图失败: {str(e)}")
        
        return local_path
    
    def tap(self, x: Union[float, int], y: Union[float, int], is_percent: bool = False) -> bool:
        """
        点击屏幕
        
        Args:
            x: X坐标（像素或百分比）
            y: Y坐标（像素或百分比）
            is_percent: 坐标是否为屏幕百分比
            
        Returns:
            是否成功
        """
        if is_percent:
            width, height = self.get_device_resolution()
            x_pixel = int(x * width)
            y_pixel = int(y * height)
        else:
            x_pixel = int(x)
            y_pixel = int(y)
            
        _, err, code = self.run_adb_cmd(f"shell input tap {x_pixel} {y_pixel}")
        return code == 0
    
    def long_press(self, x: Union[float, int], y: Union[float, int], 
                   duration: int = 1000, is_percent: bool = False) -> bool:
        """
        长按屏幕
        
        Args:
            x: X坐标（像素或百分比）
            y: Y坐标（像素或百分比）
            duration: 按住时长(毫秒)
            is_percent: 坐标是否为屏幕百分比
            
        Returns:
            是否成功
        """
        if is_percent:
            width, height = self.get_device_resolution()
            x_pixel = int(x * width)
            y_pixel = int(y * height)
        else:
            x_pixel = int(x)
            y_pixel = int(y)
            
        _, err, code = self.run_adb_cmd(
            f"shell input swipe {x_pixel} {y_pixel} {x_pixel} {y_pixel} {duration}"
        )
        return code == 0
    
    def swipe(self, x1: Union[float, int], y1: Union[float, int], 
              x2: Union[float, int], y2: Union[float, int], 
              duration: int = 500, is_percent: bool = False) -> bool:
        """
        滑动屏幕
        
        Args:
            x1: 起始X坐标
            y1: 起始Y坐标
            x2: 结束X坐标
            y2: 结束Y坐标
            duration: 滑动时长(毫秒)
            is_percent: 坐标是否为屏幕百分比
            
        Returns:
            是否成功
        """
        if is_percent:
            width, height = self.get_device_resolution()
            x1_pixel = int(x1 * width)
            y1_pixel = int(y1 * height)
            x2_pixel = int(x2 * width)
            y2_pixel = int(y2 * height)
        else:
            x1_pixel = int(x1)
            y1_pixel = int(y1)
            x2_pixel = int(x2)
            y2_pixel = int(y2)
            
        _, err, code = self.run_adb_cmd(
            f"shell input swipe {x1_pixel} {y1_pixel} {x2_pixel} {y2_pixel} {duration}"
        )
        return code == 0
    
    def multi_touch(self, points: List[Tuple[float, float]], is_percent: bool = False) -> bool:
        """
        多点触控操作
        
        Args:
            points: 触控点列表，每个点为(x, y)坐标元组
            is_percent: 坐标是否为屏幕百分比
            
        Returns:
            是否成功
        """
        if not points:
            self.logger.error("未提供触控点")
            return False
            
        # 转换坐标为像素值
        if is_percent:
            width, height = self.get_device_resolution()
            pixel_points = [(int(x * width), int(y * height)) for x, y in points]
        else:
            pixel_points = [(int(x), int(y)) for x, y in points]
            
        # 构建multitouch命令
        # 注意：默认Android不原生支持multi_touch命令，我们需要通过adb shell sendevent模拟多点触控
        # 这里提供一个简化版实现，在实际应用中可能需要更复杂的实现
        try:
            # 获取触摸屏设备
            stdout, _, _ = self.run_adb_cmd("shell getevent -p | grep -e 'add device' -e ABS_MT")
            device_path = None
            
            for line in stdout.splitlines():
                if "/dev/input/event" in line:
                    device_path = line.split(":", 1)[0].strip()
                    break
                    
            if not device_path:
                self.logger.error("未找到触摸屏设备")
                return False
                
            # 为每个点依次执行触摸操作
            for i, (x, y) in enumerate(pixel_points):
                # 简化实现：实际上不是真正的同时多点触控，而是依次快速点击
                # 在实际应用中，需要通过sendevent发送真正的多点触控事件
                if not self.tap(x, y, False):
                    return False
                time.sleep(0.1)  # 短暂延迟，确保命令被执行
                
            return True
        except Exception as e:
            self.logger.error(f"多点触控操作失败: {str(e)}")
            return False
    
    def pinch(self, center_x: Union[float, int], center_y: Union[float, int], 
              start_distance: Union[float, int], end_distance: Union[float, int],
              duration: int = 500, is_percent: bool = False) -> bool:
        """
        双指缩放操作
        
        Args:
            center_x: 缩放中心点X坐标
            center_y: 缩放中心点Y坐标
            start_distance: 起始两指间距离
            end_distance: 结束两指间距离
            duration: 操作持续时间(毫秒)
            is_percent: 坐标是否为屏幕百分比
            
        Returns:
            是否成功
        """
        try:
            # 转换坐标为像素值
            if is_percent:
                width, height = self.get_device_resolution()
                center_x_pixel = int(center_x * width)
                center_y_pixel = int(center_y * height)
                start_distance_pixel = int(start_distance * min(width, height))
                end_distance_pixel = int(end_distance * min(width, height))
            else:
                center_x_pixel = int(center_x)
                center_y_pixel = int(center_y)
                start_distance_pixel = int(start_distance)
                end_distance_pixel = int(end_distance)
                
            # 计算两指起始和结束位置
            half_start = start_distance_pixel / 2
            half_end = end_distance_pixel / 2
            
            # 起始位置
            x1_start = center_x_pixel - half_start
            y1_start = center_y_pixel
            x2_start = center_x_pixel + half_start
            y2_start = center_y_pixel
            
            # 结束位置
            x1_end = center_x_pixel - half_end
            y1_end = center_y_pixel
            x2_end = center_x_pixel + half_end
            y2_end = center_y_pixel
            
            # 使用两个swipe命令模拟双指缩放
            # 注：这种方法不能真正实现同时双指操作，但在很多应用中效果相似
            
            # 第一个手指操作
            swipe1_cmd = f"shell input swipe {int(x1_start)} {int(y1_start)} {int(x1_end)} {int(y1_end)} {duration}"
            _, err1, code1 = self.run_adb_cmd(swipe1_cmd)
            
            # 第二个手指操作
            swipe2_cmd = f"shell input swipe {int(x2_start)} {int(y2_start)} {int(x2_end)} {int(y2_end)} {duration}"
            _, err2, code2 = self.run_adb_cmd(swipe2_cmd)
            
            return code1 == 0 and code2 == 0
        except Exception as e:
            self.logger.error(f"双指缩放操作失败: {str(e)}")
            return False
    
    def slide_up(self, distance_percent: float = 0.3, duration: int = 500) -> bool:
        """
        向上滑动屏幕
        
        Args:
            distance_percent: 滑动距离占屏幕高度的百分比
            duration: 滑动时长(毫秒)
            
        Returns:
            是否成功
        """
        width, height = self.get_device_resolution()
        center_x = width // 2
        start_y = int(height * (0.5 + distance_percent / 2))
        end_y = int(height * (0.5 - distance_percent / 2))
        
        return self.swipe(center_x, start_y, center_x, end_y, duration, False)
    
    def slide_down(self, distance_percent: float = 0.3, duration: int = 500) -> bool:
        """
        向下滑动屏幕
        
        Args:
            distance_percent: 滑动距离占屏幕高度的百分比
            duration: 滑动时长(毫秒)
            
        Returns:
            是否成功
        """
        width, height = self.get_device_resolution()
        center_x = width // 2
        start_y = int(height * (0.5 - distance_percent / 2))
        end_y = int(height * (0.5 + distance_percent / 2))
        
        return self.swipe(center_x, start_y, center_x, end_y, duration, False)
    
    def press_back(self) -> bool:
        """
        按下返回键
        
        Returns:
            是否成功
        """
        _, err, code = self.run_adb_cmd("shell input keyevent 4")
        return code == 0
    
    def go_to_home(self) -> bool:
        """
        返回桌面
        
        Returns:
            是否成功
        """
        _, err, code = self.run_adb_cmd(
            "shell am start -a android.intent.action.MAIN -c android.intent.category.HOME"
        )
        return code == 0
    
    def press_power(self) -> bool:
        """
        按下电源键
        
        Returns:
            是否成功
        """
        _, err, code = self.run_adb_cmd("shell input keyevent 26")
        return code == 0
    
    def keyevent(self, keycode: int) -> bool:
        """
        发送按键事件
        
        Args:
            keycode: 按键代码
            
        Returns:
            是否成功
        """
        _, err, code = self.run_adb_cmd(f"shell input keyevent {keycode}")
        return code == 0
    
    def type_text(self, text: str) -> bool:
        """
        输入文本
        
        Args:
            text: 要输入的文本
            
        Returns:
            是否成功
        """
        # 替换换行符
        text = text.replace("\\n", "_").replace("\n", "_")
        success = True
        
        for char in text:
            if char == ' ':
                _, err, code = self.run_adb_cmd("shell input text %s")
            elif char == '_':
                _, err, code = self.run_adb_cmd("shell input keyevent 66")  # 回车键
            elif 'a' <= char <= 'z' or 'A' <= char <= 'Z' or char.isdigit():
                _, err, code = self.run_adb_cmd(f"shell input text {char}")
            elif char in '-.,!?@\'°/:;()':
                _, err, code = self.run_adb_cmd(f"shell input text \"{char}\"")
            else:
                _, err, code = self.run_adb_cmd(f"shell am broadcast -a ADB_INPUT_TEXT --es msg \"{char}\"")
                
            if code != 0:
                success = False
                
            # 短暂延迟，避免输入过快
            time.sleep(0.05)
            
        return success
    
    def get_device_info(self) -> Dict[str, Any]:
        """
        获取设备信息
        
        Returns:
            设备信息字典
        """
        info = {}
        
        # 获取Android版本
        stdout, _, _ = self.run_adb_cmd("shell getprop ro.build.version.release")
        info["android_version"] = stdout.strip()
        
        # 获取设备型号
        stdout, _, _ = self.run_adb_cmd("shell getprop ro.product.model")
        info["model"] = stdout.strip()
        
        # 获取设备制造商
        stdout, _, _ = self.run_adb_cmd("shell getprop ro.product.manufacturer")
        info["manufacturer"] = stdout.strip()
        
        # 获取设备分辨率
        width, height = self.get_device_resolution()
        info["resolution"] = f"{width}x{height}"
        
        # 获取序列号
        stdout, _, _ = self.run_adb_cmd("shell getprop ro.serialno")
        info["serial"] = stdout.strip()
        
        return info
    
    def execute_shell(self, shell_cmd: str, timeout: int = 30) -> Tuple[str, bool]:
        """
        在设备上执行Shell命令
        
        Args:
            shell_cmd: Shell命令
            timeout: 超时时间(秒)
            
        Returns:
            (命令输出, 是否成功)
        """
        # 安全检查，防止命令注入
        if any(char in shell_cmd for char in [';', '&&', '||', '`', '$', '|', '>']):
            self.logger.warning(f"可能的命令注入尝试: {shell_cmd}")
            return "命令包含不允许的字符", False
        
        # 执行经过验证的命令
        stdout, stderr, code = self.run_adb_cmd(f"shell {shell_cmd}", timeout=timeout)
        
        if code != 0:
            self.logger.error(f"Shell命令执行失败: {stderr}")
            return stderr, False
            
        return stdout, True
    
    def unlock_screen(self) -> bool:
        """
        解锁屏幕
        
        Returns:
            是否成功
        """
        # 首先唤醒设备
        self.keyevent(26)  # 电源键
        time.sleep(0.5)
        
        # 检查设备是否已解锁
        stdout, _, _ = self.run_adb_cmd("shell dumpsys window policy | grep isStatusBarKeyguard")
        if "isStatusBarKeyguard=false" in stdout:
            return True  # 设备已经解锁
            
        # 向上滑动解锁(在锁屏页面上滑动解锁最通用的方式)
        width, height = self.get_device_resolution()
        center_x = width // 2
        start_y = int(height * 0.8)
        end_y = int(height * 0.2)
        
        # 执行滑动解锁
        success = self.swipe(center_x, start_y, center_x, end_y, 300, False)
        if not success:
            return False
            
        # 等待一下，确保解锁动画完成
        time.sleep(1)
        
        # 再次检查设备是否已解锁
        stdout, _, _ = self.run_adb_cmd("shell dumpsys window policy | grep isStatusBarKeyguard")
        return "isStatusBarKeyguard=false" in stdout
    
    def adjust_volume(self, volume_type: str = "music", level: int = None, direction: str = None) -> int:
        """
        调节音量
        
        Args:
            volume_type: 音量类型，可选值：music, call, ring, notification, system, alarm
            level: 要设置的音量级别，如果为None则返回当前音量级别
            direction: 调整方向，可选值："up", "down"，仅在level为None时生效
            
        Returns:
            当前音量级别，失败时返回-1
        """
        # 音量类型对应的流ID
        volume_streams = {
            "music": 3,
            "call": 0,
            "ring": 2,
            "notification": 5,
            "system": 1,
            "alarm": 4
        }
        
        if volume_type not in volume_streams:
            self.logger.error(f"不支持的音量类型: {volume_type}")
            return -1
            
        stream_id = volume_streams[volume_type]
        
        if level is not None:
            # 设置音量
            # 首先获取音量最大值
            stdout, _, _ = self.run_adb_cmd(f"shell dumpsys audio | \
                                            grep -A 20 'STREAM_{volume_type.upper()}' | grep 'Max:'")
            max_volume = 15  # 默认最大值
            if stdout.strip():
                # 解析最大值
                try:
                    max_match = re.search(r'Max:\s+(\d+)', stdout)
                    if max_match:
                        max_volume = int(max_match.group(1))
                except Exception as e:
                    self.logger.warning(f"解析音量最大值失败: {e}")
            
            # 限制音量范围
            safe_level = max(0, min(level, max_volume))
            
            # 设置音量
            _, err, code = self.run_adb_cmd(f"shell media volume --stream {stream_id} --set-volume {safe_level}")
            if code != 0:
                # 尝试备用方法
                _, err, code = self.run_adb_cmd(f"shell service call audio {stream_id} s16 {safe_level}")
                if code != 0:
                    self.logger.error(f"设置音量失败: {err}")
                    return -1
        elif direction is not None:
            # 调整音量
            if direction == "up":
                self.keyevent(24)  # 音量增大键
            elif direction == "down":
                self.keyevent(25)  # 音量减小键
            else:
                self.logger.error(f"不支持的音量调整方向: {direction}")
                return -1
        
        # 获取当前音量
        stdout, _, _ = self.run_adb_cmd(f"shell dumpsys audio | \
                                        grep -A 20 'STREAM_{volume_type.upper()}' | grep 'volume:'")
        current_volume = -1
        
        if stdout.strip():
            # 解析当前音量
            try:
                volume_match = re.search(r'volume:\s+(\d+)/', stdout)
                if volume_match:
                    current_volume = int(volume_match.group(1))
            except Exception as e:
                self.logger.warning(f"解析当前音量失败: {e}")
                
        return current_volume
    
    def rotate_screen(self, orientation: int) -> bool:
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
            是否成功
        """
        # 检查orientation值是否有效
        if orientation not in [0, 1, 2, 3, 4]:
            self.logger.error(f"无效的屏幕方向值: {orientation}")
            return False
            
        if orientation == 0:
            # 设置为自动旋转
            _, err, code = self.run_adb_cmd("shell settings put system accelerometer_rotation 1")
            return code == 0
        else:
            # 先禁用自动旋转
            self.run_adb_cmd("shell settings put system accelerometer_rotation 0")
            
            # 设置特定的屏幕方向
            # 0:自动, 1:竖屏, 2:横屏, 3:反竖屏, 4:反横屏
            _, err, code = self.run_adb_cmd(f"shell settings put system user_rotation {orientation - 1}")
            return code == 0
    
    def set_brightness(self, level: int, auto_mode: bool = False) -> bool:
        """
        设置屏幕亮度
        
        Args:
            level: 亮度级别(0-255)或百分比(0-100)，如果超过100则视为绝对值(0-255)
            auto_mode: 是否设置为自动亮度模式
            
        Returns:
            是否成功
        """
        # 检查level值是否有效
        if level < 0:
            self.logger.error(f"亮度级别不能为负值: {level}")
            return False
            
        # 如果是百分比，转换为绝对值
        brightness_value = level
        if level <= 100:
            brightness_value = int(level * 255 / 100)
        
        # 限制范围为0-255
        brightness_value = max(0, min(brightness_value, 255))
        
        # 处理自动亮度模式
        if auto_mode:
            _, err, code = self.run_adb_cmd("shell settings put system screen_brightness_mode 1")
            return code == 0
        else:
            # 关闭自动亮度
            self.run_adb_cmd("shell settings put system screen_brightness_mode 0")
            
            # 设置亮度
            _, err, code = self.run_adb_cmd(f"shell settings put system screen_brightness {brightness_value}")
            return code == 0
            
    # 文本输入相关功能
    
    def switch_ime(self, ime_id: str = None) -> Union[bool, List[Dict[str, str]]]:
        """
        切换输入法
        
        Args:
            ime_id: 输入法ID，如com.google.android.inputmethod.latin/.LatinIME
                   如果为None，则返回可用输入法列表
                   
        Returns:
            成功切换时返回True，获取列表时返回输入法列表
        """
        if ime_id is None:
            # 获取可用输入法列表
            stdout, _, code = self.run_adb_cmd("shell ime list -a")
            if code != 0:
                return []
                
            ime_list = []
            current_ime = None
            
            # 获取当前输入法
            current_stdout, _, _ = self.run_adb_cmd("shell settings get secure default_input_method")
            if current_stdout:
                current_ime = current_stdout.strip()
            
            # 解析输入法列表
            lines = stdout.strip().split('\n')
            for line in lines:
                if line.startswith("  mId="):
                    ime_id = line.split("mId=")[1].strip()
                    ime_name = ""
                    for name_line in lines:
                        if "mDisplayName=" in name_line:
                            ime_name = name_line.split("mDisplayName=")[1].strip()
                            break
                    
                    is_enabled = "mSelected=true" in stdout
                    is_current = current_ime == ime_id
                    
                    ime_list.append({
                        "id": ime_id,
                        "name": ime_name,
                        "enabled": is_enabled,
                        "current": is_current
                    })
            
            return ime_list
        else:
            # 切换输入法
            # 确保输入法已启用
            self.run_adb_cmd(f"shell ime enable {ime_id}")
            
            # 设置为默认输入法
            _, _, code = self.run_adb_cmd(f"shell ime set {ime_id}")
            return code == 0
    
    def paste_text(self) -> bool:
        """
        粘贴文本（模拟长按后点击粘贴）
        
        Returns:
            是否成功
        """
        # 获取当前焦点所在应用和活动
        app_info = self.get_app_and_activity()
        if not app_info:
            self.logger.error("无法获取当前焦点所在应用")
            return False
        
        try:
            # 模拟长按文本框（假设焦点已在文本框中）
            success = False
            
            # 方法1：使用Ctrl+V组合键（适用于部分应用）
            _, _, code1 = self.run_adb_cmd("shell input keyevent 29 47")  # CTRL+V
            
            # 方法2：尝试发送粘贴命令
            _, _, code2 = self.run_adb_cmd("shell input text '(CMD: paste)'")
            
            # 方法3：使用编辑菜单（适用于大多数原生应用）
            _, _, code3 = self.run_adb_cmd("shell input keyevent 285")  # KEYCODE_PASTE
            
            return code1 == 0 or code2 == 0 or code3 == 0
        except Exception as e:
            self.logger.error(f"粘贴文本失败: {str(e)}")
            return False
    
    def clear_text(self, char_count: int = None) -> bool:
        """
        清除文本
        
        Args:
            char_count: 要删除的字符数量，None表示清除所有文本
            
        Returns:
            是否成功
        """
        try:
            if char_count is None:
                # 尝试使用Ctrl+A全选后删除
                _, _, code1 = self.run_adb_cmd("shell input keyevent 29 30")  # CTRL+A
                time.sleep(0.1)
                _, _, code2 = self.run_adb_cmd("shell input keyevent 67")  # KEYCODE_DEL
                
                # 或者直接使用KEYCODE_CLEAR键
                _, _, code3 = self.run_adb_cmd("shell input keyevent 28")  # KEYCODE_CLEAR
                
                return code1 == 0 and code2 == 0 or code3 == 0
            else:
                # 删除指定数量的字符
                char_count = max(1, char_count)  # 至少删除1个字符
                
                cmds = []
                for _ in range(char_count):
                    cmds.append("input keyevent 67")  # KEYCODE_DEL
                
                # 批量执行删除命令
                cmd_str = " && ".join(cmds)
                _, _, code = self.run_adb_cmd(f"shell {cmd_str}")
                
                return code == 0
        except Exception as e:
            self.logger.error(f"清除文本失败: {str(e)}")
            return False
            
    def get_app_and_activity(self) -> Dict[str, str]:
        """
        获取当前应用和活动
        
        Returns:
            应用和活动信息
        """
        stdout, _, _ = self.run_adb_cmd("shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'")
        
        package_name = ""
        activity_name = ""
        
        for line in stdout.strip().split('\n'):
            if "mCurrentFocus" in line:
                match = re.search(r'mCurrentFocus=.*\{.*\s+([^/\s]+)/([^\s}]+)', line)
                if match:
                    package_name = match.group(1)
                    activity_name = match.group(2)
                    break
                    
        return {
            "package_name": package_name,
            "activity_name": activity_name
        }
    
    def cleanup(self):
        """
        清理控制器资源，在服务关闭时调用
        """
        self.logger.info("清理设备控制器资源...")
        # 目前没有需要清理的资源
        pass 