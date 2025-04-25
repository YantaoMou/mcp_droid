"""
应用管理控制器，提供应用安装、卸载、启动等操作
"""
import os
import re
import time
from typing import Dict, List, Optional, Tuple, Any

from core.device_controller import DeviceController


class AppController(DeviceController):
    """
    应用管理控制器，提供应用安装、卸载、启动等操作
    """
    
    def install_app(self, apk_path: str, replace: bool = True) -> Tuple[str, bool]:
        """
        安装应用
        
        Args:
            apk_path: APK文件路径（本地文件系统路径）
            replace: 是否替换已存在的应用
            
        Returns:
            (安装结果信息, 是否成功)
        """
        if not os.path.exists(apk_path):
            return f"APK文件不存在: {apk_path}", False
            
        cmd = "install"
        if replace:
            cmd += " -r"
            
        stdout, stderr, code = self.run_adb_cmd(f"{cmd} \"{apk_path}\"")
        if code != 0 or "Failure" in stdout:
            return f"安装失败: {stderr if stderr else stdout}", False
            
        return "安装成功", True
    
    def uninstall_app(self, package_name: str, keep_data: bool = False) -> Tuple[str, bool]:
        """
        卸载应用
        
        Args:
            package_name: 应用包名
            keep_data: 是否保留应用数据
            
        Returns:
            (卸载结果信息, 是否成功)
        """
        cmd = "uninstall"
        if keep_data:
            cmd += " -k"
            
        stdout, stderr, code = self.run_adb_cmd(f"{cmd} {package_name}")
        if code != 0 or "Failure" in stdout:
            return f"卸载失败: {stderr if stderr else stdout}", False
            
        return "卸载成功", True
    
    def start_app(self, package_name: str, activity_name: str = None) -> bool:
        """
        启动应用
        
        Args:
            package_name: 应用包名
            activity_name: 活动名称，为None时启动主活动
            
        Returns:
            是否成功
        """
        if activity_name:
            cmd = f"shell am start -n {package_name}/{activity_name}"
        else:
            cmd = f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
            
        _, stderr, code = self.run_adb_cmd(cmd)
        return code == 0
    
    def stop_app(self, package_name: str) -> bool:
        """
        停止应用
        
        Args:
            package_name: 应用包名
            
        Returns:
            是否成功
        """
        _, stderr, code = self.run_adb_cmd(f"shell am force-stop {package_name}")
        return code == 0
    
    def clear_app(self, package_name: str) -> bool:
        """
        清理应用数据
        
        Args:
            package_name: 应用包名
            
        Returns:
            是否成功
        """
        _, stderr, code = self.run_adb_cmd(f"shell pm clear {package_name}")
        return code == 0
        
    def list_apps(self, system_apps: bool = False, third_party_apps: bool = True) -> List[Dict[str, str]]:
        """
        列出已安装应用
        
        Args:
            system_apps: 是否包含系统应用
            third_party_apps: 是否包含第三方应用
            
        Returns:
            应用列表，每个应用为字典 {package_name, app_name}
        """
        app_list = []
        
        # 获取所有应用包名
        cmd = "shell pm list packages"
        if system_apps and not third_party_apps:
            cmd += " -s"  # 仅系统应用
        elif third_party_apps and not system_apps:
            cmd += " -3"  # 仅第三方应用
            
        stdout, stderr, code = self.run_adb_cmd(cmd)
        
        if code != 0:
            self.logger.error(f"获取应用列表失败: {stderr}")
            return []
            
        package_lines = stdout.strip().split('\n')
        for line in package_lines:
            if not line.strip():
                continue
                
            # 解析包名
            match = re.match(r'package:(.+)', line.strip())
            if match:
                package_name = match.group(1)
                
                # 获取应用名称
                app_name = self._get_app_name(package_name)
                
                app_list.append({
                    "package_name": package_name,
                    "app_name": app_name
                })
                
        return app_list
    
    def _get_app_name(self, package_name: str) -> str:
        """获取应用显示名称"""
        cmd = f"shell dumpsys package {package_name} | grep -E 'targetSdk|versionName'"
        stdout, _, _ = self.run_adb_cmd(cmd)
        
        app_info = {}
        
        lines = stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            if "versionName=" in line:
                match = re.search(r'versionName=([^\s]+)', line)
                if match:
                    app_info["version"] = match.group(1)
            elif "targetSdk=" in line:
                match = re.search(r'targetSdk=([0-9]+)', line)
                if match:
                    app_info["target_sdk"] = match.group(1)
                    
        # 尝试获取应用标签（显示名称）
        label_cmd = f"shell dumpsys package {package_name} | grep -E 'labelRes|nonLocalizedLabel'"
        stdout, _, _ = self.run_adb_cmd(label_cmd)
        
        app_name = package_name  # 默认使用包名
        
        lines = stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            if "nonLocalizedLabel=" in line:
                match = re.search(r'nonLocalizedLabel=([^\s]+)', line)
                if match:
                    app_name = match.group(1)
                    break
        
        return app_name
    
    def open_url(self, url: str) -> bool:
        """
        打开网址
        
        Args:
            url: 网址
            
        Returns:
            是否成功
        """
        if not url.startswith(('http://', 'https://')):
            url = f"http://{url}"
            
        _, stderr, code = self.run_adb_cmd(f"shell am start -a android.intent.action.VIEW -d \"{url}\"")
        return code == 0
    
    def get_current_app(self) -> Dict[str, str]:
        """
        获取前台应用信息
        
        Returns:
            前台应用信息 {package_name, activity_name}
        """
        stdout, stderr, code = self.run_adb_cmd("shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'")
        
        if code != 0:
            self.logger.error(f"获取前台应用失败: {stderr}")
            return {"package_name": "", "activity_name": ""}
            
        package_name = ""
        activity_name = ""
        
        lines = stdout.strip().split('\n')
        for line in lines:
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
    
    def get_current_activity(self) -> str:
        """
        获取当前活动
        
        Returns:
            当前活动名称
        """
        app_info = self.get_current_app()
        return app_info["activity_name"]
    
    def check_app_installed(self, package_name: str) -> bool:
        """
        检查应用是否已安装
        
        Args:
            package_name: 应用包名
            
        Returns:
            是否已安装
        """
        stdout, _, code = self.run_adb_cmd(f"shell pm list packages {package_name}")
        return code == 0 and package_name in stdout
    
    def get_app_version(self, package_name: str) -> Dict[str, str]:
        """
        获取应用版本信息
        
        Args:
            package_name: 应用包名
            
        Returns:
            版本信息 {version_name, version_code}
        """
        stdout, stderr, code = self.run_adb_cmd(f"shell dumpsys package {package_name} \
                                                | grep -E 'versionName|versionCode'")
        
        if code != 0:
            self.logger.error(f"获取应用版本失败: {stderr}")
            return {"version_name": "", "version_code": ""}
            
        version_name = ""
        version_code = ""
        
        lines = stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            if "versionName=" in line:
                match = re.search(r'versionName=([^\s]+)', line)
                if match:
                    version_name = match.group(1)
            elif "versionCode=" in line:
                match = re.search(r'versionCode=([0-9]+)', line)
                if match:
                    version_code = match.group(1)
                    
        return {
            "version_name": version_name,
            "version_code": version_code
        }
    
    def force_stop_app(self, package_name: str) -> bool:
        """
        强制停止应用
        
        Args:
            package_name: 应用包名
            
        Returns:
            是否成功
        """
        _, stderr, code = self.run_adb_cmd(f"shell am force-stop {package_name}")
        return code == 0
    
    def grant_permission(self, package_name: str, permission: str) -> bool:
        """
        给应用授权
        
        Args:
            package_name: 应用包名
            permission: 权限名称
            
        Returns:
            是否成功
        """
        _, stderr, code = self.run_adb_cmd(f"shell pm grant {package_name} {permission}")
        return code == 0
        
    def monitor_app_start(self, package_name: str, timeout: int = 30) -> bool:
        """
        监控应用启动
        
        Args:
            package_name: 应用包名
            timeout: 超时时间(秒)
            
        Returns:
            是否成功启动
        """
        # 清除应用打开记录，便于监控
        self.run_adb_cmd(f"shell am force-stop {package_name}")
        
        # 启动监控进程
        import threading
        import queue
        
        result_queue = queue.Queue()
        stop_event = threading.Event()
        
        def monitor_proc():
            start_time = time.time()
            is_started = False
            
            while not stop_event.is_set() and time.time() - start_time < timeout:
                stdout, _, _ = self.run_adb_cmd("shell dumpsys activity | grep -E 'mResumedActivity|mFocusedActivity'")
                
                if package_name in stdout:
                    is_started = True
                    break
                
                # 更频繁地检查stop_event，从0.5秒缩短到0.2秒
                time.sleep(0.2)
                # 再次检查stop_event，确保能更快地响应停止信号
                if stop_event.is_set():
                    break
            
            # 仅在队列未满且事件未设置时放入结果，避免在停止后继续尝试写入
            if not stop_event.is_set():
                try:
                    result_queue.put(is_started, block=False)
                except queue.Full:
                    pass
        
        # 启动监控线程
        monitor_thread = threading.Thread(target=monitor_proc, name=f"monitor-{package_name}")
        # 设置为守护线程，这样主程序退出时线程会自动终止
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # 启动应用
        self.start_app(package_name)
        
        # 等待结果
        try:
            result = result_queue.get(timeout=timeout+5)
            return result
        except queue.Empty:
            return False
        finally:
            # 确保事件被设置，线程能够退出
            stop_event.set()
            # 给予足够时间让线程自行退出，从1秒增加到3秒
            if monitor_thread.is_alive():
                monitor_thread.join(timeout=3) 