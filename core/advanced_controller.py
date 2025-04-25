"""
高级功能控制器，提供图像识别、OCR、UI遍历等高级功能
"""
import os
import time
import json
import logging
import subprocess
from typing import Dict, List, Optional, Tuple, Any, Union
import tempfile
import cv2
import numpy as np
from PIL import Image
import re

from core.device_controller import DeviceController

try:
    # 尝试导入Airtest相关模块
    from airtest.core.api import connect_device, auto_setup
    from airtest.core.api import touch, swipe, snapshot, Template, exists, wait
    from airtest.core.helper import G, logwrap
    from airtest.aircv import cv2_2_pil, crop_image
    AIRTEST_AVAILABLE = True
except ImportError:
    AIRTEST_AVAILABLE = False
    
try:
    # 尝试导入OCR组件
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class AdvancedController(DeviceController):
    """
    高级功能控制器，提供图像识别、OCR、UI遍历等高级功能
    """
    
    # 添加类变量用于存储屏幕截图监听器的状态
    _screenshot_watcher_data = {
        "watcher_thread": None,
        "stop_event": None,
        "is_running": False,
        "screenshots": []
    }
    
    def __init__(self, adb_path: str = "adb", device_id: str = None):
        """
        初始化高级功能控制器
        
        Args:
            adb_path: ADB命令路径
            device_id: 设备ID，如果有多个设备连接时需要指定
        """
        super().__init__(adb_path, device_id)
        self.logger = logging.getLogger("AdvancedController")
        self.airtest_initialized = False
        self.init_airtest()
    
    def init_airtest(self) -> bool:
        """
        初始化Airtest连接
        
        Returns:
            是否成功
        """
        if not AIRTEST_AVAILABLE:
            self.logger.warning("Airtest不可用，部分高级功能将不可用")
            return False
            
        try:
            # 使用ADB连接设备
            device_cmd = f"Android:///{self.device_id}" if self.device_id else "Android:///"
            connect_device(device_cmd)
            
            # 初始化Airtest
            auto_setup(__file__, logdir=os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs"))
            
            self.airtest_initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Airtest初始化失败: {str(e)}")
            return False
    
    def image_recognition(self, target_image_path: str, 
                          threshold: float = 0.7, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """
        图像识别与匹配
        
        Args:
            target_image_path: 目标图像路径
            threshold: 匹配阈值，越高越精确
            timeout: 超时时间(秒)
            
        Returns:
            匹配结果 {x, y, confidence} 或None表示未找到
        """
        if not AIRTEST_AVAILABLE:
            return None
            
        if not self.airtest_initialized:
            if not self.init_airtest():
                return None
                
        if not os.path.exists(target_image_path):
            self.logger.error(f"目标图像不存在: {target_image_path}")
            return None
            
        try:
            # 创建模板
            template = Template(target_image_path, threshold=threshold)
            
            # 等待图像出现
            start_time = time.time()
            while time.time() - start_time < timeout:
                # 截图并查找模板
                screen = G.DEVICE.snapshot()
                match_pos = template.match_in(screen)
                
                if match_pos:
                    return {
                        "x": match_pos[0],
                        "y": match_pos[1],
                        "confidence": match_pos[2]["confidence"]
                    }
                    
                time.sleep(1)
                
            return None
        except Exception as e:
            self.logger.error(f"图像识别失败: {str(e)}")
            return None
    
    def wait_for_image(self, target_image_path: str, timeout: int = 20, threshold: float = 0.7) -> bool:
        """
        等待图像出现
        
        Args:
            target_image_path: 目标图像路径
            timeout: 超时时间(秒)
            threshold: 匹配阈值
            
        Returns:
            是否成功找到图像
        """
        if not AIRTEST_AVAILABLE:
            return False
            
        if not self.airtest_initialized:
            if not self.init_airtest():
                return False
                
        if not os.path.exists(target_image_path):
            self.logger.error(f"目标图像不存在: {target_image_path}")
            return False
        
        try:
            # 创建模板
            template = Template(target_image_path, threshold=threshold)
            
            # 等待图像出现
            result = wait(template, timeout=timeout, threshold=threshold)
            return result is not None
        except Exception as e:
            self.logger.error(f"等待图像失败: {str(e)}")
            return False
    
    def tap_image(self, target_image_path: str, timeout: int = 10, threshold: float = 0.7) -> bool:
        """
        点击图像
        
        Args:
            target_image_path: 目标图像路径
            timeout: 超时时间(秒)
            threshold: 匹配阈值
            
        Returns:
            是否成功点击
        """
        match_pos = self.image_recognition(target_image_path, threshold, timeout)
        if not match_pos:
            return False
            
        return self.tap(match_pos["x"], match_pos["y"])
    
    def check_image_exists(self, target_image_path: str, threshold: float = 0.7) -> bool:
        """
        检查图像是否存在
        
        Args:
            target_image_path: 目标图像路径
            threshold: 匹配阈值
            
        Returns:
            图像是否存在
        """
        if not AIRTEST_AVAILABLE:
            return False
            
        if not self.airtest_initialized:
            if not self.init_airtest():
                return False
                
        if not os.path.exists(target_image_path):
            self.logger.error(f"目标图像不存在: {target_image_path}")
            return False
        
        try:
            # 创建模板
            template = Template(target_image_path, threshold=threshold)
            
            # 检查图像是否存在
            return exists(template)
        except Exception as e:
            self.logger.error(f"检查图像失败: {str(e)}")
            return False
    
    def local_image_search(self, target_image_path: str, 
                           region: List[int] = None, 
                           threshold: float = 0.7) -> Optional[Dict[str, Any]]:
        """
        局部区域图像搜索
        
        Args:
            target_image_path: 目标图像路径
            region: 搜索区域 [x1, y1, x2, y2]
            threshold: 匹配阈值
            
        Returns:
            匹配结果 {x, y, confidence} 或None表示未找到
        """
        if not AIRTEST_AVAILABLE:
            return None
            
        if not self.airtest_initialized:
            if not self.init_airtest():
                return None
                
        if not os.path.exists(target_image_path):
            self.logger.error(f"目标图像不存在: {target_image_path}")
            return None
            
        try:
            # 截图
            screen = G.DEVICE.snapshot()
            
            # 如果指定了区域，则裁剪图像
            if region and len(region) == 4:
                x1, y1, x2, y2 = region
                screen = crop_image(screen, (x1, y1, x2, y2))
            
            # 创建模板并匹配
            template = Template(target_image_path, threshold=threshold)
            match_pos = template.match_in(screen)
            
            if match_pos:
                # 如果是局部区域搜索，需要转换坐标
                if region and len(region) == 4:
                    x1, y1 = region[0], region[1]
                    return {
                        "x": match_pos[0] + x1,
                        "y": match_pos[1] + y1,
                        "confidence": match_pos[2]["confidence"]
                    }
                else:
                    return {
                        "x": match_pos[0],
                        "y": match_pos[1],
                        "confidence": match_pos[2]["confidence"]
                    }
                    
            return None
        except Exception as e:
            self.logger.error(f"局部图像搜索失败: {str(e)}")
            return None
    
    def ocr_recognition(self, language: str = "eng", region: List[int] = None) -> Dict[str, Any]:
        """
        OCR文字识别
        
        Args:
            language: 语言，默认为英文
            region: 识别区域 [x1, y1, x2, y2]，为None时识别整个屏幕
            
        Returns:
            识别结果 {text, confidence}
        """
        if not OCR_AVAILABLE:
            self.logger.warning("OCR组件不可用，请安装pytesseract")
            return {"text": "", "confidence": 0.0}
            
        try:
            # 获取截图
            screenshot_path = self.get_screenshot()
            if not screenshot_path:
                return {"text": "", "confidence": 0.0}
                
            # 打开图像
            img = Image.open(screenshot_path)
            
            # 如果指定了区域，则裁剪图像
            if region and len(region) == 4:
                x1, y1, x2, y2 = region
                img = img.crop((x1, y1, x2, y2))
            
            # 执行OCR识别
            text = pytesseract.image_to_string(img, lang=language)
            
            # 获取置信度（一个近似值）
            ocr_data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)
            if ocr_data["conf"]:
                # 过滤掉-1的置信度值，计算平均值
                confidences = [conf for conf in ocr_data["conf"] if conf != -1]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                confidence = avg_confidence / 100.0  # 转换为0-1范围
            else:
                confidence = 0.0
                
            return {
                "text": text.strip(),
                "confidence": confidence
            }
        except Exception as e:
            self.logger.error(f"OCR识别失败: {str(e)}")
            return {"text": "", "confidence": 0.0}
    
    def capture_logs(self, log_type: str = "main", lines: int = 100, package: str = None) -> str:
        """
        截取系统/应用日志
        
        Args:
            log_type: 日志类型 (main, events, radio, system, crash)
            lines: 获取的行数
            package: 应用包名，为None时获取全部日志
            
        Returns:
            日志内容
        """
        cmd = f"shell logcat"
        
        # 添加日志类型
        if log_type != "main":
            if log_type == "events":
                cmd += " -b events"
            elif log_type == "radio":
                cmd += " -b radio"
            elif log_type == "system":
                cmd += " -b system"
            elif log_type == "crash":
                cmd += " -b crash"
        
        # 添加行数限制
        cmd += f" -d -t {lines}"
        
        # 添加包名过滤
        if package:
            cmd += f" | grep {package}"
            
        stdout, stderr, code = self.run_adb_cmd(cmd)
        if code != 0:
            self.logger.error(f"获取日志失败: {stderr}")
            return ""
            
        return stdout
    
    def record_screen(self, duration: int = 10, output_path: str = None) -> str:
        """
        录制屏幕视频
        
        Args:
            duration: 录制时长(秒)
            output_path: 输出文件路径，为None时使用默认路径
            
        Returns:
            录制的视频文件路径
        """
        if duration <= 0 or duration > 180:
            self.logger.warning(f"录制时长 {duration} 超出范围，已调整为10秒")
            duration = 10
            
        if output_path is None:
            # 创建输出目录
            video_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "video")
            os.makedirs(video_dir, exist_ok=True)
            
            # 清理旧的视频文件（保留最新的5个）
            try:
                video_files = sorted(
                    [os.path.join(video_dir, f) for f in os.listdir(video_dir) if f.endswith('.mp4')],
                    key=os.path.getmtime,
                    reverse=True
                )
                
                # 删除旧视频，保留最新的5个
                for old_video in video_files[5:]:
                    try:
                        os.remove(old_video)
                        self.logger.debug(f"已删除旧视频文件: {old_video}")
                    except Exception as e:
                        self.logger.warning(f"删除旧视频文件失败: {str(e)}")
            except Exception as e:
                self.logger.warning(f"清理旧视频文件时出错: {str(e)}")
            
            # 生成输出文件路径
            timestamp = int(time.time())
            output_path = os.path.join(video_dir, f"screen_record_{timestamp}.mp4")
        
        # 设备上的临时文件路径
        remote_path = f"/sdcard/screen_record_{int(time.time())}.mp4"
        
        # 开始录制
        self.logger.info(f"开始录制屏幕，时长: {duration}秒")
        process = None
        
        try:
            # 清理可能存在的旧录制文件
            self.run_adb_cmd(f"shell rm -f {remote_path}")
            
            # 启动录制进程
            cmd = f"shell screenrecord --time-limit {duration} {remote_path}"
            process = subprocess.Popen(
                self._build_adb_cmd(cmd),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 等待录制完成
            process.wait()
            
            # 检查是否录制成功
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                self.logger.error(f"屏幕录制失败: {stderr.decode() if stderr else 'Unknown error'}")
                return ""
                
            # 从设备拉取视频文件
            _, err, code = self.run_adb_cmd(f"pull {remote_path} {output_path}")
            if code != 0:
                self.logger.error(f"获取录制文件失败: {err}")
                return ""
                
            # 清理设备上的临时文件
            self.run_adb_cmd(f"shell rm -f {remote_path}")
            
            return output_path
        except Exception as e:
            self.logger.error(f"录制屏幕时发生错误: {str(e)}")
            return ""
        finally:
            # 确保进程被终止
            if process and process.poll() is None:
                try:
                    process.terminate()
                except:
                    pass
    
    def ui_crawler(self, max_depth: int = 3, max_actions: int = 30) -> Dict[str, Any]:
        """
        自动化UI遍历
        
        Args:
            max_depth: 最大遍历深度
            max_actions: 最大操作次数
            
        Returns:
            遍历结果 {actions, screens}
        """
        if not AIRTEST_AVAILABLE:
            self.logger.warning("Airtest不可用，UI遍历功能不可用")
            return {"actions": [], "screens": []}
            
        if not self.airtest_initialized:
            if not self.init_airtest():
                return {"actions": [], "screens": []}
                
        # 安全限制：防止参数值过大
        max_depth = min(max_depth, 5)  # 限制最大深度为5
        max_actions = min(max_actions, 50)  # 限制最大操作次数为50
                
        # 记录操作和截图
        actions = []
        screens = []
        
        # 已访问的界面（使用截图的哈希值标识）
        visited_screens = set()
        
        # 使用非递归的方式实现深度优先遍历
        try:
            # 堆栈保存(深度,屏幕)信息
            screen_stack = [(0, G.DEVICE.snapshot())]
            action_count = 0
            
            while screen_stack and action_count < max_actions:
                current_depth, current_screen = screen_stack.pop()
                
                # 如果已达到最大深度，跳过
                if current_depth >= max_depth:
                    continue
                    
                # 获取屏幕的哈希值
                screen_hash = self._get_screen_hash(current_screen)
                
                # 如果已访问过该界面，跳过
                if screen_hash in visited_screens:
                    continue
                    
                # 标记为已访问
                visited_screens.add(screen_hash)
                
                # 保存截图
                screenshot_path = os.path.join(
                    self.screenshot_dir, 
                    f"ui_crawler_{len(screens)}.jpg"
                )
                cv2.imwrite(screenshot_path, current_screen)
                screens.append(screenshot_path)
                
                # 查找可点击元素
                elements = self._find_clickable_elements(current_screen)
                
                # 对每个可点击元素进行操作
                for element in elements:
                    # 如果已达到最大操作次数，退出
                    if action_count >= max_actions:
                        break
                        
                    x, y = element["x"], element["y"]
                    
                    # 记录操作
                    actions.append({
                        "action": "tap",
                        "x": x,
                        "y": y,
                        "screen_index": len(screens) - 1
                    })
                    
                    # 点击元素
                    self.tap(x, y)
                    action_count += 1
                    
                    # 等待界面加载
                    time.sleep(1)
                    
                    # 获取新界面截图
                    new_screen = G.DEVICE.snapshot()
                    
                    # 将新界面添加到堆栈
                    screen_stack.append((current_depth + 1, new_screen))
                    
                    # 返回上一界面
                    self.press_back()
                    time.sleep(1)
                
            return {"actions": actions, "screens": screens}
        except Exception as e:
            self.logger.error(f"UI遍历失败: {str(e)}")
            return {"actions": actions, "screens": screens}
    
    def _get_screen_hash(self, screen) -> str:
        """计算屏幕图像的哈希值"""
        # 将图像调整为较小尺寸，减少计算量
        small_screen = cv2.resize(screen, (32, 32))
        # 计算哈希值（简化版perceptual hash）
        gray = cv2.cvtColor(small_screen, cv2.COLOR_BGR2GRAY)
        gray = cv2.blur(gray, (3, 3))
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        hash_value = ""
        for i in range(32):
            for j in range(32):
                hash_value += "1" if binary[i, j] > 127 else "0"
        return hash_value
    
    def _find_clickable_elements(self, screen) -> List[Dict[str, Any]]:
        """
        在屏幕上找到可点击的元素
        
        Args:
            screen: 屏幕图像
            
        Returns:
            可点击元素列表
        """
        # 转换为灰度图像
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        
        # 边缘检测
        edges = cv2.Canny(gray, 50, 150)
        
        # 查找轮廓 - 使用兼容不同OpenCV版本的方法
        opencv_version = cv2.__version__.split('.')
        major_version = int(opencv_version[0])
        
        # 兼容OpenCV 2.x, 3.x 和 4.x
        if major_version < 3:
            # OpenCV 2.x 返回 contours, hierarchy
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        elif major_version == 3:
            # OpenCV 3.x 返回 image, contours, hierarchy
            _, contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        else:
            # OpenCV 4.x 返回 contours, hierarchy
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 筛选可能是按钮、图标的轮廓
        clickable_elements = []
        
        # 过滤小轮廓并提取中心点
        height, width = screen.shape[:2]
        min_size = (width * height) / 1000  # 最小轮廓面积
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > min_size:
                # 计算轮廓的中心点
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    clickable_elements.append({"x": cx, "y": cy, "area": area})
        
        # 按面积排序
        clickable_elements.sort(key=lambda e: e["area"], reverse=True)
        
        # 限制返回的元素数量
        return clickable_elements[:5]
    
    def wake_device(self) -> bool:
        """
        唤醒设备
        
        Returns:
            是否成功
        """
        # 检查设备是否已唤醒
        stdout, _, _ = self.run_adb_cmd("shell dumpsys power | grep 'Display Power'")
        if "ON" in stdout:
            return True
            
        # 按下电源键唤醒设备
        _, _, code = self.run_adb_cmd("shell input keyevent 26")
        if code != 0:
            return False
            
        # 再次检查是否唤醒
        time.sleep(1)
        stdout, _, _ = self.run_adb_cmd("shell dumpsys power | grep 'Display Power'")
        return "ON" in stdout
    
    def sleep_device(self) -> bool:
        """
        休眠设备
        
        Returns:
            是否成功
        """
        # 检查设备是否已休眠
        stdout, _, _ = self.run_adb_cmd("shell dumpsys power | grep 'Display Power'")
        if "OFF" in stdout:
            return True
            
        # 按下电源键休眠设备
        _, _, code = self.run_adb_cmd("shell input keyevent 26")
        if code != 0:
            return False
            
        # 再次检查是否休眠
        time.sleep(1)
        stdout, _, _ = self.run_adb_cmd("shell dumpsys power | grep 'Display Power'")
        return "OFF" in stdout
    
    def reboot_device(self) -> bool:
        """
        重启设备
        
        Returns:
            是否成功执行
        """
        try:
            _, err, code = self.run_adb_cmd("reboot")
            return code == 0
        except Exception as e:
            self.logger.error(f"重启设备失败: {str(e)}")
            return False
            
    def explore_app(self, package_name: str, max_depth: int = 3, max_actions: int = 30) -> Dict[str, Any]:
        """
        探索应用界面
        
        Args:
            package_name: 应用包名
            max_depth: 最大探索深度
            max_actions: 最大操作次数
            
        Returns:
            探索结果
        """
        if not AIRTEST_AVAILABLE:
            return {"success": False, "reason": "Airtest不可用"}
            
        if not self.airtest_initialized:
            if not self.init_airtest():
                return {"success": False, "reason": "Airtest初始化失败"}
                
        # 确保应用已启动
        self.run_adb_cmd(f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
        time.sleep(2)  # 等待应用启动
        
        # 探索记录
        exploration_results = {
            "pages_visited": 0,
            "actions_performed": 0,
            "unique_screens": 0,
            "elements_found": [],
            "screenshots": []
        }
        
        # 已访问的界面（使用屏幕哈希值标识）
        visited_screens = set()
        
        # 探索队列
        def explore_screen(depth: int, remaining_actions: int):
            if depth > max_depth or remaining_actions <= 0:
                return
                
            try:
                # 截图并获取屏幕哈希值
                screen = G.DEVICE.snapshot()
                screen_hash = self._get_screen_hash(screen)
                
                # 如果已访问过此界面，跳过
                if screen_hash in visited_screens:
                    self.logger.info(f"界面已访问过: {screen_hash}")
                    return
                    
                # 记录此界面
                visited_screens.add(screen_hash)
                
                # 保存截图
                screen_path = os.path.join(self.screenshot_dir, f"explore_{len(visited_screens)}.jpg")
                cv2_2_pil(screen).save(screen_path)
                exploration_results["screenshots"].append(screen_path)
                
                # 更新统计信息
                exploration_results["pages_visited"] += 1
                exploration_results["unique_screens"] = len(visited_screens)
                
                # 找出可点击元素
                clickable_elements = self._find_clickable_elements(screen)
                exploration_results["elements_found"].extend(clickable_elements)
                
                # 尝试每个可点击元素
                for element in clickable_elements[:min(5, len(clickable_elements))]:  # 限制每个界面最多点击5个元素
                    if remaining_actions <= 0:
                        break
                        
                    # 点击元素
                    try:
                        self.tap(element["x"], element["y"], False)
                        time.sleep(1)  # 等待界面响应
                        exploration_results["actions_performed"] += 1
                        
                        # 递归探索新界面
                        explore_screen(depth + 1, remaining_actions - 1)
                        
                        # 返回上一界面
                        self.press_back()
                        time.sleep(1)
                    except Exception as e:
                        self.logger.error(f"点击元素失败: {str(e)}")
            except Exception as e:
                self.logger.error(f"探索界面失败: {str(e)}")
        
        # 开始探索
        try:
            explore_screen(1, max_actions)
        except Exception as e:
            self.logger.error(f"应用探索失败: {str(e)}")
            
        return {
            "success": True,
            "results": exploration_results
        }
        
    def file_operations(self, operation: str, local_path: str, device_path: str) -> Dict[str, Any]:
        """
        文件操作(上传/下载)
        
        Args:
            operation: 操作类型，push(上传)或pull(下载)
            local_path: 本地文件路径
            device_path: 设备文件路径
            
        Returns:
            操作结果
        """
        if operation not in ["push", "pull"]:
            return {
                "success": False,
                "message": f"不支持的操作类型: {operation}"
            }
            
        try:
            if operation == "push":
                # 上传文件
                if not os.path.exists(local_path):
                    return {
                        "success": False,
                        "message": f"本地文件不存在: {local_path}"
                    }
                
                _, stderr, code = self.run_adb_cmd(f"push \"{local_path}\" \"{device_path}\"")
                if code != 0:
                    return {
                        "success": False,
                        "message": f"上传文件失败: {stderr}"
                    }
                
                # 验证文件是否已上传
                stdout, _, _ = self.run_adb_cmd(f"shell ls -la \"{device_path}\"")
                if "No such file" in stdout:
                    return {
                        "success": False,
                        "message": "上传后未找到文件"
                    }
                
                return {
                    "success": True,
                    "message": f"文件已上传至: {device_path}"
                }
            else:  # pull
                # 检查设备上的文件是否存在
                stdout, _, _ = self.run_adb_cmd(f"shell ls -la \"{device_path}\"")
                if "No such file" in stdout:
                    return {
                        "success": False,
                        "message": f"设备上的文件不存在: {device_path}"
                    }
                
                # 确保本地目录存在
                local_dir = os.path.dirname(local_path)
                if local_dir and not os.path.exists(local_dir):
                    os.makedirs(local_dir, exist_ok=True)
                
                # 下载文件
                _, stderr, code = self.run_adb_cmd(f"pull \"{device_path}\" \"{local_path}\"")
                if code != 0:
                    return {
                        "success": False,
                        "message": f"下载文件失败: {stderr}"
                    }
                
                # 验证文件是否已下载
                if not os.path.exists(local_path):
                    return {
                        "success": False,
                        "message": "下载后未找到文件"
                    }
                
                return {
                    "success": True,
                    "message": f"文件已下载至: {local_path}",
                    "file_size": os.path.getsize(local_path)
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"文件操作失败: {str(e)}"
            }
    
    def check_root(self) -> Dict[str, Any]:
        """
        检测设备是否已root
        
        Returns:
            检测结果
        """
        result = {
            "rooted": False,
            "su_locations": [],
            "system_rw": False,
            "superuser_app": False
        }
        
        try:
            # 检查su命令
            stdout, _, _ = self.run_adb_cmd("shell which su")
            if stdout.strip():
                result["rooted"] = True
                result["su_locations"].append(stdout.strip())
            
            # 检查常见su路径
            su_paths = [
                "/system/bin/su",
                "/system/xbin/su",
                "/sbin/su",
                "/system/su",
                "/system/app/SuperUser.apk",
                "/data/local/su",
                "/data/local/xbin/su"
            ]
            
            for path in su_paths:
                stdout, _, _ = self.run_adb_cmd(f"shell ls {path}")
                if "No such file" not in stdout and "not found" not in stdout:
                    result["rooted"] = True
                    result["su_locations"].append(path)
            
            # 检查system分区是否可写
            stdout, _, _ = self.run_adb_cmd("shell mount | grep system")
            if "ro," not in stdout:
                result["system_rw"] = True
                result["rooted"] = True
            
            # 检查SuperUser或Magisk等应用
            stdout, _, _ = self.run_adb_cmd("shell pm list packages | grep -E 'supersu|superuser|magisk|chainfire'")
            if stdout.strip():
                result["superuser_app"] = True
                result["rooted"] = True
                
            return result
            
        except Exception as e:
            self.logger.error(f"检测root失败: {str(e)}")
            return {
                "rooted": False,
                "error": str(e)
            }
    
    def connect_over_tcp(self, ip_address: str, port: int = 5555) -> Dict[str, Any]:
        """
        通过TCP/IP连接设备
        
        Args:
            ip_address: 设备IP地址
            port: 端口号，默认为5555
            
        Returns:
            连接结果
        """
        try:
            # 首先检查端口是否已经被占用
            stdout, _, _ = self.run_adb_cmd("devices")
            device_pattern = f"{ip_address}:{port}"
            
            if device_pattern in stdout:
                return {
                    "success": True,
                    "message": f"设备 {device_pattern} 已连接",
                    "device_id": device_pattern
                }
            
            # 连接设备
            _, stderr, code = self.run_adb_cmd(f"connect {ip_address}:{port}")
            if code != 0 or "failed" in stderr.lower():
                return {
                    "success": False,
                    "message": f"连接失败: {stderr}"
                }
                
            # 验证连接
            stdout, _, _ = self.run_adb_cmd("devices")
            if device_pattern in stdout:
                return {
                    "success": True,
                    "message": f"已成功连接到设备 {device_pattern}",
                    "device_id": device_pattern
                }
            else:
                return {
                    "success": False,
                    "message": "连接命令成功但设备未出现在设备列表中"
                }
                
        except Exception as e:
            self.logger.error(f"TCP/IP连接设备失败: {str(e)}")
            return {
                "success": False,
                "message": f"连接过程发生错误: {str(e)}"
            }
    
    def monitor_performance(self, package_name: str = None, duration: int = 10, interval: float = 1.0) -> Dict[str, Any]:
        """
        监控设备性能
        
        Args:
            package_name: 应用包名，为None时监控系统性能
            duration: 监控持续时间(秒)
            interval: 采样间隔(秒)
            
        Returns:
            性能监控结果
        """
        try:
            samples = int(duration / interval)
            samples = max(1, min(samples, 100))  # 限制样本数量
            
            cpu_samples = []
            memory_samples = []
            battery_samples = []
            network_samples = []
            
            # 如果要监控特定应用性能
            if package_name:
                # 确保应用已启动
                self.run_adb_cmd(f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
                time.sleep(1)  # 等待应用启动
                
                # 获取应用PID
                stdout, _, _ = self.run_adb_cmd(f"shell ps | grep {package_name}")
                if not stdout.strip():
                    stdout, _, _ = self.run_adb_cmd(f"shell ps -A | grep {package_name}")
                
                pid = None
                for line in stdout.strip().split("\n"):
                    parts = line.split()
                    if len(parts) > 1 and package_name in line:
                        try:
                            pid = parts[1]  # 通常PID在第2列
                            break
                        except:
                            continue
                
                if not pid:
                    return {
                        "success": False,
                        "message": f"无法获取应用 {package_name} 的PID"
                    }
            
            # 开始采样
            for _ in range(samples):
                # CPU采样
                if package_name and pid:
                    # 应用CPU使用
                    stdout, _, _ = self.run_adb_cmd(f"shell top -p {pid} -n 1")
                    cpu_usage = 0
                    for line in stdout.strip().split("\n"):
                        if package_name in line:
                            parts = line.split()
                            # 查找CPU使用率列
                            for i, part in enumerate(parts):
                                if "%" in part and i > 0:
                                    try:
                                        cpu_usage = float(part.replace("%", ""))
                                        break
                                    except:
                                        pass
                else:
                    # 系统总体CPU使用
                    cpu_usage = self._get_cpu_usage()
                    
                cpu_samples.append(cpu_usage)
                
                # 内存采样
                if package_name:
                    stdout, _, _ = self.run_adb_cmd(f"shell dumpsys meminfo {package_name}")
                    total_memory = 0
                    for line in stdout.strip().split("\n"):
                        if "TOTAL" in line:
                            parts = line.split()
                            try:
                                total_memory = int(parts[1])  # 单位KB
                            except:
                                pass
                            break
                else:
                    # 系统可用内存
                    stdout, _, _ = self.run_adb_cmd("shell cat /proc/meminfo | grep MemAvailable")
                    avail_memory = 0
                    if stdout.strip():
                        try:
                            match = re.search(r'MemAvailable:\s+(\d+)', stdout)
                            if match:
                                avail_memory = int(match.group(1))  # 单位KB
                        except:
                            pass
                    total_memory = avail_memory
                
                memory_samples.append(total_memory)
                
                # 电池采样
                stdout, _, _ = self.run_adb_cmd("shell dumpsys battery")
                battery_level = 0
                for line in stdout.strip().split("\n"):
                    if "level:" in line:
                        try:
                            match = re.search(r'level:\s+(\d+)', line)
                            if match:
                                battery_level = int(match.group(1))
                        except:
                            pass
                        break
                
                battery_samples.append(battery_level)
                
                # 网络采样 - 兼容不同Android版本
                if package_name:
                    # 尝试新版Android的方式
                    stdout, _, _ = self.run_adb_cmd(f"shell dumpsys netstats detail | \
                                                    grep -E '{package_name}|packageName=\"{package_name}\"' -A 10")
                    
                    if not stdout.strip():
                        # 尝试旧版Android的方式
                        stdout, _, _ = self.run_adb_cmd(f"shell cat /proc/net/xt_qtaguid/stats | grep {package_name}")
                    
                    rx_bytes = 0
                    tx_bytes = 0
                    
                    # 解析网络流量
                    if "netstats detail" in stdout:
                        # 新版Android格式解析
                        for line in stdout.strip().split("\n"):
                            if "rxBytes=" in line and "txBytes=" in line:
                                try:
                                    rx_match = re.search(r'rxBytes=(\d+)', line)
                                    tx_match = re.search(r'txBytes=(\d+)', line)
                                    if rx_match and tx_match:
                                        rx_bytes += int(rx_match.group(1))
                                        tx_bytes += int(tx_match.group(1))
                                except Exception as e:
                                    self.logger.warning(f"解析网络流量失败: {str(e)}")
                    else:
                        # 旧版Android格式解析
                        for line in stdout.strip().split("\n"):
                            if package_name in line:
                                parts = line.split()
                                if len(parts) > 7:
                                    try:
                                        rx_bytes += int(parts[5])
                                        tx_bytes += int(parts[7])
                                    except Exception as e:
                                        self.logger.warning(f"解析网络流量失败: {str(e)}")
                    
                    network_samples.append({"rx": rx_bytes, "tx": tx_bytes})
                else:
                    # 系统整体网络流量
                    stdout, _, _ = self.run_adb_cmd("shell cat /proc/net/dev")
                    rx_bytes = 0
                    tx_bytes = 0
                    
                    for line in stdout.strip().split("\n"):
                        if ":" in line and not any(x in line for x in ["lo:", "dummy"]):
                            parts = line.split(":")
                            if len(parts) > 1:
                                data_parts = parts[1].split()
                                if len(data_parts) > 8:
                                    try:
                                        rx_bytes += int(data_parts[0])  # 接收字节
                                        tx_bytes += int(data_parts[8])  # 发送字节
                                    except Exception as e:
                                        self.logger.warning(f"解析网络流量失败: {str(e)}")
                    
                    network_samples.append({"rx": rx_bytes, "tx": tx_bytes})
                
                # 等待下次采样
                if _ < samples - 1:  # 最后一次采样不需要等待
                    time.sleep(interval)
            
            # 计算平均值
            avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
            avg_memory = sum(memory_samples) / len(memory_samples) if memory_samples else 0
            avg_battery = sum(battery_samples) / len(battery_samples) if battery_samples else 0
            
            return {
                "success": True,
                "package_name": package_name,
                "duration": duration,
                "samples": samples,
                "avg_cpu": avg_cpu,
                "max_cpu": max(cpu_samples) if cpu_samples else 0,
                "avg_memory_kb": avg_memory,
                "max_memory_kb": max(memory_samples) if memory_samples else 0,
                "battery_drain": battery_samples[0] - battery_samples[-1] if len(battery_samples) > 1 else 0,
                "cpu_samples": cpu_samples,
                "memory_samples": memory_samples,
                "battery_samples": battery_samples,
                "network_samples": network_samples
            }
                
        except Exception as e:
            self.logger.error(f"性能监控失败: {str(e)}")
            return {
                "success": False,
                "message": f"性能监控过程发生错误: {str(e)}"
            }
    
    def screenshot_watcher(self, start: bool = True, interval: float = 2.0) -> Dict[str, Any]:
        """
        设备截屏监听器
        
        Args:
            start: 是否启动监听器，False表示停止
            interval: 截图间隔(秒)
            
        Returns:
            操作结果
        """
        try:
            if start:
                # 如果监听器已在运行，先停止
                if self._screenshot_watcher_data.get("is_running", False) and \
                    self._screenshot_watcher_data.get("watcher_thread") and \
                        self._screenshot_watcher_data.get("stop_event"):
                    self._screenshot_watcher_data["stop_event"].set()
                    if self._screenshot_watcher_data["watcher_thread"].is_alive():
                        self._screenshot_watcher_data["watcher_thread"].join(5)
                
                # 创建新的停止事件
                import threading
                stop_event = threading.Event()
                self._screenshot_watcher_data["stop_event"] = stop_event
                self._screenshot_watcher_data["screenshots"] = []
                
                # 监听器函数
                def screenshot_watcher_proc():
                    while not stop_event.is_set():
                        try:
                            # 截图
                            screen_path = self.get_screenshot(filename=f"watcher_{int(time.time())}.jpg")
                            if screen_path:
                                self._screenshot_watcher_data["screenshots"].append(screen_path)
                                # 保留最新的20张截图
                                if len(self._screenshot_watcher_data["screenshots"]) > 20:
                                    old_path = self._screenshot_watcher_data["screenshots"].pop(0)
                                    try:
                                        if os.path.exists(old_path):
                                            os.remove(old_path)
                                    except Exception as e:
                                        self.logger.warning(f"删除旧截图失败: {str(e)}")
                        except Exception as e:
                            self.logger.error(f"截图监控失败: {str(e)}")
                        
                        # 等待下次截图
                        stop_event.wait(interval)
                
                # 启动监听线程
                watcher_thread = threading.Thread(target=screenshot_watcher_proc)
                watcher_thread.daemon = True
                watcher_thread.start()
                
                self._screenshot_watcher_data["watcher_thread"] = watcher_thread
                self._screenshot_watcher_data["is_running"] = True
                
                return {
                    "success": True,
                    "message": f"截图监听器已启动，间隔 {interval} 秒",
                    "is_running": True
                }
                
            else:
                # 停止监听器
                if self._screenshot_watcher_data.get("is_running", False) and \
                    self._screenshot_watcher_data.get("stop_event"):
                    self._screenshot_watcher_data["stop_event"].set()
                    if self._screenshot_watcher_data.get("watcher_thread") and \
                        self._screenshot_watcher_data["watcher_thread"].is_alive():
                        self._screenshot_watcher_data["watcher_thread"].join(5)
                    
                    self._screenshot_watcher_data["is_running"] = False
                    
                    return {
                        "success": True,
                        "message": "截图监听器已停止",
                        "is_running": False,
                        "screenshots": self._screenshot_watcher_data.get("screenshots", [])
                    }
                else:
                    return {
                        "success": True,
                        "message": "截图监听器未在运行",
                        "is_running": False
                    }
                    
        except Exception as e:
            self.logger.error(f"截图监听器操作失败: {str(e)}")
            return {
                "success": False,
                "message": f"截图监听器操作错误: {str(e)}"
            }
    
    def record_and_replay(self, action: str, script_path: str = None, record_duration: int = 60) -> Dict[str, Any]:
        """
        脚本录制和回放
        
        Args:
            action: 操作类型，start_record(开始录制)、stop_record(停止录制)或replay(回放)
            script_path: 脚本路径
            record_duration: 录制时长(秒)，仅在action为start_record时有效
            
        Returns:
            操作结果
        """
        if not AIRTEST_AVAILABLE:
            return {
                "success": False,
                "message": "Airtest不可用，无法进行脚本录制和回放"
            }
            
        if not self.airtest_initialized:
            if not self.init_airtest():
                return {
                    "success": False,
                    "message": "Airtest初始化失败"
                }
        
        # 静态数据存储
        static_data = {
            "recording": False,
            "record_thread": None,
            "stop_event": None,
            "recorded_script": None,
            "record_actions": []
        }
        
        try:
            if action == "start_record":
                # 如果已经在录制，先停止
                if static_data.get("recording", False):
                    if static_data.get("stop_event"):
                        static_data["stop_event"].set()
                    if static_data.get("record_thread") and static_data["record_thread"].is_alive():
                        static_data["record_thread"].join(5)
                        
                # 创建脚本文件目录
                if script_path:
                    script_dir = os.path.dirname(script_path)
                    if script_dir and not os.path.exists(script_dir):
                        os.makedirs(script_dir, exist_ok=True)
                else:
                    # 默认脚本路径
                    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
                    os.makedirs(log_dir, exist_ok=True)
                    script_path = os.path.join(log_dir, f"record_script_{int(time.time())}.py")
                
                # 创建停止事件
                import threading
                stop_event = threading.Event()
                static_data["stop_event"] = stop_event
                static_data["record_actions"] = []
                
                # 录制线程函数
                def record_proc():
                    start_time = time.time()
                    actions = []
                    
                    # 记录初始屏幕截图
                    try:
                        screenshot_path = self.get_screenshot(filename=f"record_start_{int(time.time())}.png")
                        if screenshot_path:
                            actions.append({
                                "type": "screenshot",
                                "path": screenshot_path,
                                "time": 0
                            })
                    except Exception as e:
                        self.logger.error(f"记录初始截图失败: {str(e)}")
                    
                    # 监听设备事件，记录用户操作
                    try:
                        # 启动事件监听
                        proc = subprocess.Popen(
                            f"{self.adb_path} {'- s ' + self.device_id if self.device_id else ''} shell getevent -t",
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        
                        last_touch_time = 0
                        touch_x = 0
                        touch_y = 0
                        touch_start_time = 0
                        is_touching = False
                        
                        while not stop_event.is_set() and time.time() - start_time < record_duration:
                            line = proc.stdout.readline().strip()
                            if not line:
                                continue
                                
                            # 解析事件
                            try:
                                # 格式: [时间戳] /dev/input/eventX: type code value
                                parts = line.split()
                                if len(parts) < 5:
                                    continue
                                    
                                timestamp = float(parts[0][1:-1])  # 去除中括号
                                event_type = int(parts[2], 16)
                                event_code = int(parts[3], 16)
                                event_value = int(parts[4], 16)
                                
                                # 触摸事件
                                if event_type == 3:  # EV_ABS
                                    if event_code == 53:  # ABS_MT_POSITION_X
                                        touch_x = event_value
                                    elif event_code == 54:  # ABS_MT_POSITION_Y
                                        touch_y = event_value
                                elif event_type == 1:  # EV_KEY
                                    if event_code == 330:  # BTN_TOUCH
                                        if event_value == 1:  # 按下
                                            is_touching = True
                                            touch_start_time = timestamp
                                        elif event_value == 0:  # 抬起
                                            is_touching = False
                                            touch_duration = timestamp - touch_start_time
                                            
                                            # 添加点击或长按操作
                                            if touch_duration < 0.5:  # 短按
                                                actions.append({
                                                    "type": "tap",
                                                    "x": touch_x,
                                                    "y": touch_y,
                                                    "time": timestamp - start_time
                                                })
                                            else:  # 长按
                                                actions.append({
                                                    "type": "long_press",
                                                    "x": touch_x,
                                                    "y": touch_y,
                                                    "duration": int(touch_duration * 1000),
                                                    "time": timestamp - start_time
                                                })
                                elif event_type == 0 and event_code == 0 and event_value == 0:  # SYN_REPORT
                                    # 检测滑动事件
                                    pass
                                    
                                # 按键事件
                                # ...其他事件解析
                                    
                            except Exception as e:
                                self.logger.error(f"解析事件失败: {str(e)}")
                                
                            # 定期截图
                            now = time.time()
                            if now - last_touch_time > 2:  # 每2秒截图一次
                                try:
                                    screenshot_path = self.get_screenshot(filename=f"record_{int(now)}.png")
                                    if screenshot_path:
                                        actions.append({
                                            "type": "screenshot",
                                            "path": screenshot_path,
                                            "time": now - start_time
                                        })
                                    last_touch_time = now
                                except Exception as e:
                                    self.logger.error(f"录制截图失败: {str(e)}")
                        
                        # 停止事件监听
                        proc.terminate()
                        
                    except Exception as e:
                        self.logger.error(f"事件监听失败: {str(e)}")
                    
                    # 生成脚本文件
                    try:
                        script_content = [
                            "# -*- encoding=utf8 -*-",
                            "# 自动生成的Airtest脚本",
                            "import os",
                            "import time",
                            "from airtest.core.api import *",
                            "",
                            f"# 连接设备: {self.device_id if self.device_id else 'default'}",
                            "auto_setup(__file__)",
                            ""
                        ]
                        
                        # 添加操作
                        for action in actions:
                            action_time = action.get("time", 0)
                            
                            if action["type"] == "screenshot":
                                screenshot_name = os.path.basename(action["path"])
                                script_content.append(f"# 截图: {screenshot_name}")
                                script_content.append("snapshot()")
                            elif action["type"] == "tap":
                                script_content.append(f"# 点击坐标: ({action['x']}, {action['y']})")
                                script_content.append(f"touch(({action['x']}, {action['y']}))")
                            elif action["type"] == "long_press":
                                script_content.append(f"# 长按坐标: ({action['x']}, 
                                                      {action['y']}), 时长: {action['duration']}ms")
                                script_content.append(f"touch(({action['x']}, 
                                                      {action['y']}), duration={action['duration']/1000})")
                            elif action["type"] == "swipe":
                                script_content.append(f"# 滑动: 从({action['x1']}, 
                                                      {action['y1']})到({action['x2']}, {action['y2']})")
                                script_content.append(f"swipe(({action['x1']}, 
                                                      {action['y1']}), ({action['x2']}, {action['y2']}))")
                            
                            # 添加延时
                            if len(actions) > 1 and actions.index(action) < len(actions) - 1:
                                next_time = actions[actions.index(action) + 1].get("time", 0)
                                delay = next_time - action_time
                                if delay > 0.1:  # 忽略很小的延时
                                    script_content.append(f"sleep({delay:.2f})  # 等待{delay:.2f}秒")
                            
                            script_content.append("")
                        
                        # 写入文件
                        with open(script_path, "w", encoding="utf-8") as f:
                            f.write("\n".join(script_content))
                            
                        static_data["recorded_script"] = script_path
                        static_data["record_actions"] = actions
                            
                    except Exception as e:
                        self.logger.error(f"生成脚本失败: {str(e)}")
                
                # 启动录制线程
                record_thread = threading.Thread(target=record_proc)
                record_thread.daemon = True
                record_thread.start()
                
                static_data["record_thread"] = record_thread
                static_data["recording"] = True
                
                return {
                    "success": True,
                    "message": f"开始录制脚本，时长: {record_duration}秒",
                    "script_path": script_path
                }
                
            elif action == "stop_record":
                # 停止录制
                if static_data.get("recording", False) and static_data.get("stop_event"):
                    static_data["stop_event"].set()
                    
                    if static_data.get("record_thread") and static_data["record_thread"].is_alive():
                        static_data["record_thread"].join(5)
                    
                    static_data["recording"] = False
                    
                    return {
                        "success": True,
                        "message": "录制已停止",
                        "script_path": static_data.get("recorded_script")
                    }
                else:
                    return {
                        "success": False,
                        "message": "当前没有录制在进行"
                    }
                    
            elif action == "replay":
                # 回放脚本
                if not script_path:
                    if static_data.get("recorded_script"):
                        script_path = static_data["recorded_script"]
                    else:
                        return {
                            "success": False,
                            "message": "未指定脚本路径且无最近录制的脚本"
                        }
                
                if not os.path.exists(script_path):
                    return {
                        "success": False,
                        "message": f"脚本文件不存在: {script_path}"
                    }
                
                try:
                    # 使用Airtest回放脚本
                    if AIRTEST_AVAILABLE:
                        import subprocess
                        
                        # 构建Airtest运行命令
                        adb_param = f"-s {self.device_id}" if self.device_id else ""
                        cmd = f"python -m airtest run {script_path} --device Android:///{adb_param} --log log/"
                        
                        # 执行回放命令
                        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            return {
                                "success": True,
                                "message": "脚本回放成功",
                                "output": result.stdout
                            }
                        else:
                            return {
                                "success": False,
                                "message": f"脚本回放失败: {result.stderr}"
                            }
                    else:
                        return {
                            "success": False,
                            "message": "Airtest不可用，无法回放脚本"
                        }
                except Exception as e:
                    self.logger.error(f"回放脚本失败: {str(e)}")
                    return {
                        "success": False,
                        "message": f"回放脚本过程中发生错误: {str(e)}"
                    }
            else:
                return {
                    "success": False,
                    "message": f"不支持的操作类型: {action}"
                }
                
        except Exception as e:
            self.logger.error(f"脚本录制/回放操作失败: {str(e)}")
            return {
                "success": False,
                "message": f"操作失败: {str(e)}"
            }
    
    def run_test_case(self, test_path: str, test_type: str = "airtest") -> Dict[str, Any]:
        """
        执行自动化测试用例
        
        Args:
            test_path: 测试用例路径，可以是单个文件或目录
            test_type: 测试类型，支持airtest、appium、python
            
        Returns:
            测试执行结果
        """
        if not os.path.exists(test_path):
            return {
                "success": False,
                "message": f"测试路径不存在: {test_path}"
            }
            
        try:
            if test_type == "airtest":
                if not AIRTEST_AVAILABLE:
                    return {
                        "success": False,
                        "message": "Airtest不可用，无法执行测试"
                    }
                
                # 生成报告目录
                log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
                report_dir = os.path.join(log_dir, f"report_{int(time.time())}")
                os.makedirs(report_dir, exist_ok=True)
                
                # 构建测试命令
                adb_param = f"-s {self.device_id}" if self.device_id else ""
                
                if os.path.isdir(test_path):
                    # 执行目录中的所有测试
                    import glob
                    test_files = glob.glob(os.path.join(test_path, "*.air")) + glob.glob(os.path.join(test_path, "*.py"))
                    
                    results = []
                    for test_file in test_files:
                        cmd = f"python -m airtest run {test_file} --device Android:///{adb_param} --log {report_dir}"
                        
                        # 执行测试
                        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                        
                        results.append({
                            "test_file": test_file,
                            "success": proc.returncode == 0,
                            "output": proc.stdout,
                            "error": proc.stderr if proc.returncode != 0 else ""
                        })
                    
                    # 生成HTML报告
                    try:
                        report_cmd = f"python -m airtest report {test_path} \
                            --log_root {report_dir} --outfile {os.path.join(report_dir, 'report.html')} --lang zh"
                        subprocess.run(report_cmd, shell=True)
                    except Exception as e:
                        self.logger.error(f"生成测试报告失败: {str(e)}")
                    
                    success_count = sum(1 for r in results if r["success"])
                    
                    return {
                        "success": True,
                        "message": f"执行了{len(results)}个测试，{success_count}个成功，{len(results) - success_count}个失败",
                        "report_dir": report_dir,
                        "results": results
                    }
                else:
                    # 执行单个测试文件
                    cmd = f"python -m airtest run {test_path} --device Android:///{adb_param} --log {report_dir}"
                    
                    # 执行测试
                    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    
                    # 生成HTML报告
                    try:
                        report_cmd = f"python -m airtest report {test_path} \
                            --log_root {report_dir} --outfile {os.path.join(report_dir, 'report.html')} --lang zh"
                        subprocess.run(report_cmd, shell=True)
                    except Exception as e:
                        self.logger.error(f"生成测试报告失败: {str(e)}")
                    
                    return {
                        "success": proc.returncode == 0,
                        "message": "测试执行" + ("成功" if proc.returncode == 0 else "失败"),
                        "report_dir": report_dir,
                        "output": proc.stdout,
                        "error": proc.stderr if proc.returncode != 0 else ""
                    }
                    
            elif test_type == "python":
                # 执行Python测试脚本
                env = os.environ.copy()
                if self.device_id:
                    env["ANDROID_DEVICE"] = self.device_id
                    
                # 执行测试
                cmd = f"python {test_path}"
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
                
                return {
                    "success": proc.returncode == 0,
                    "message": "Python测试执行" + ("成功" if proc.returncode == 0 else "失败"),
                    "output": proc.stdout,
                    "error": proc.stderr if proc.returncode != 0 else ""
                }
                
            elif test_type == "appium":
                # 检查是否安装了Appium
                try:
                    appium_check = subprocess.run("appium -v", shell=True, capture_output=True, text=True)
                    if appium_check.returncode != 0:
                        return {
                            "success": False,
                            "message": "Appium未安装或无法访问"
                        }
                except:
                    return {
                        "success": False,
                        "message": "Appium未安装或无法访问"
                    }
                
                # 执行Appium测试
                env = os.environ.copy()
                if self.device_id:
                    env["ANDROID_DEVICE_ID"] = self.device_id
                
                cmd = f"python {test_path}"
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
                
                return {
                    "success": proc.returncode == 0,
                    "message": "Appium测试执行" + ("成功" if proc.returncode == 0 else "失败"),
                    "output": proc.stdout,
                    "error": proc.stderr if proc.returncode != 0 else ""
                }
            else:
                return {
                    "success": False,
                    "message": f"不支持的测试类型: {test_type}"
                }
                
        except Exception as e:
            self.logger.error(f"执行测试用例失败: {str(e)}")
            return {
                "success": False,
                "message": f"执行测试过程中发生错误: {str(e)}"
            }
    
    def cleanup(self):
        """
        清理控制器资源，在服务关闭时调用
        """
        self.logger.info("清理高级控制器资源...")
        
        # 停止屏幕截图监听器
        if self._screenshot_watcher_data.get("is_running", False) and self._screenshot_watcher_data.get("stop_event"):
            self.logger.debug("停止屏幕截图监听器")
            self._screenshot_watcher_data["stop_event"].set()
            
            if self._screenshot_watcher_data.get("watcher_thread") and \
                self._screenshot_watcher_data["watcher_thread"].is_alive():
                try:
                    self._screenshot_watcher_data["watcher_thread"].join(2)
                except Exception as e:
                    self.logger.error(f"停止截图监听器线程失败: {str(e)}")
            
            self._screenshot_watcher_data["is_running"] = False
        
        # 清理截图文件
        try:
            self.logger.debug("清理截图文件夹")
            screenshot_dir = self.screenshot_dir
            if os.path.exists(screenshot_dir):
                # 只保留最新的10张图片
                files = sorted(
                    [os.path.join(screenshot_dir, f) for f in os.listdir(screenshot_dir) \
                     if f.endswith(('.png', '.jpg', '.jpeg'))],
                    key=os.path.getmtime,
                    reverse=True
                )
                
                # 删除旧文件
                for old_file in files[10:]:
                    try:
                        os.remove(old_file)
                    except Exception as e:
                        self.logger.warning(f"删除旧截图失败: {str(e)}")
        except Exception as e:
            self.logger.error(f"清理截图文件夹失败: {str(e)}")
        
        # 断开Airtest连接
        if self.airtest_initialized and AIRTEST_AVAILABLE:
            try:
                self.logger.debug("断开Airtest连接")
                from airtest.core.helper import G
                if hasattr(G, "DEVICE") and G.DEVICE:
                    G.DEVICE.disconnect()
            except Exception as e:
                self.logger.error(f"断开Airtest连接失败: {str(e)}")
        
        self.logger.info("高级控制器资源清理完成") 