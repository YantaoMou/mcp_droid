"""
系统信息控制器，提供设备信息、性能数据等查询功能
"""
import re
import time
from typing import Dict, List, Any, Tuple

from core.device_controller import DeviceController


class SystemController(DeviceController):
    """
    系统信息控制器，提供设备信息、性能数据等查询功能
    """
    
    def get_android_version(self) -> str:
        """
        获取设备Android版本
        
        Returns:
            Android版本号
        """
        stdout, _, _ = self.run_adb_cmd("shell getprop ro.build.version.release")
        return stdout.strip()
    
    def get_device_serial(self) -> str:
        """
        获取设备序列号
        
        Returns:
            设备序列号
        """
        stdout, _, _ = self.run_adb_cmd("shell getprop ro.serialno")
        return stdout.strip()
    
    def get_battery_info(self) -> Dict[str, Any]:
        """
        获取设备电量信息
        
        Returns:
            电量信息 {level, temperature, status, health}
        """
        stdout, stderr, code = self.run_adb_cmd("shell dumpsys battery")
        
        if code != 0:
            self.logger.error(f"获取电池信息失败: {stderr}")
            return {}
            
        battery_info = {}
        lines = stdout.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if "level:" in line:
                match = re.search(r'level:\s+(\d+)', line)
                if match:
                    battery_info["level"] = int(match.group(1))
            elif "temperature:" in line:
                match = re.search(r'temperature:\s+(\d+)', line)
                if match:
                    # 温度通常是实际温度的10倍
                    battery_info["temperature"] = float(match.group(1)) / 10.0
            elif "status:" in line:
                match = re.search(r'status:\s+(\d+)', line)
                if match:
                    status_code = int(match.group(1))
                    status_map = {
                        1: "unknown",
                        2: "charging",
                        3: "discharging",
                        4: "not charging",
                        5: "full"
                    }
                    battery_info["status"] = status_map.get(status_code, "unknown")
            elif "health:" in line:
                match = re.search(r'health:\s+(\d+)', line)
                if match:
                    health_code = int(match.group(1))
                    health_map = {
                        1: "unknown",
                        2: "good",
                        3: "overheat",
                        4: "dead",
                        5: "over voltage",
                        6: "unspecified failure",
                        7: "cold"
                    }
                    battery_info["health"] = health_map.get(health_code, "unknown")
                    
        return battery_info
    
    def get_memory_info(self) -> Dict[str, Any]:
        """
        获取设备内存信息
        
        Returns:
            内存信息 {total, free, available} 单位为MB
        """
        stdout, stderr, code = self.run_adb_cmd("shell cat /proc/meminfo")
        
        if code != 0:
            self.logger.error(f"获取内存信息失败: {stderr}")
            return {}
            
        memory_info = {}
        lines = stdout.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if "MemTotal:" in line:
                match = re.search(r'MemTotal:\s+(\d+)', line)
                if match:
                    # 转换为MB
                    memory_info["total"] = int(match.group(1)) / 1024
            elif "MemFree:" in line:
                match = re.search(r'MemFree:\s+(\d+)', line)
                if match:
                    memory_info["free"] = int(match.group(1)) / 1024
            elif "MemAvailable:" in line:
                match = re.search(r'MemAvailable:\s+(\d+)', line)
                if match:
                    memory_info["available"] = int(match.group(1)) / 1024
                    
        return memory_info
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """
        获取设备CPU信息
        
        Returns:
            CPU信息 {cores, architecture, model, usage}
        """
        # 获取CPU核心数
        stdout, _, _ = self.run_adb_cmd("shell cat /proc/cpuinfo | grep processor | wc -l")
        cores = int(stdout.strip()) if stdout.strip().isdigit() else 0
        
        # 获取CPU架构
        stdout, _, _ = self.run_adb_cmd("shell getprop ro.product.cpu.abi")
        architecture = stdout.strip()
        
        # 获取CPU型号
        stdout, _, _ = self.run_adb_cmd("shell cat /proc/cpuinfo | grep 'model name'")
        model = ""
        if stdout.strip():
            match = re.search(r'model name\s+:\s+(.*)', stdout.strip())
            if match:
                model = match.group(1)
        
        # 获取CPU使用率
        usage = self._get_cpu_usage()
        
        return {
            "cores": cores,
            "architecture": architecture,
            "model": model,
            "usage": usage
        }
    
    def _get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        # 第一次采样
        stdout1, _, _ = self.run_adb_cmd("shell cat /proc/stat | grep '^cpu '")
        if not stdout1.strip():
            return 0.0
            
        # 解析第一次数据
        parts1 = stdout1.strip().split()
        if len(parts1) < 5:
            return 0.0
            
        user1 = int(parts1[1])
        nice1 = int(parts1[2])
        system1 = int(parts1[3])
        idle1 = int(parts1[4])
        
        # 等待一段时间
        time.sleep(0.5)
        
        # 第二次采样
        stdout2, _, _ = self.run_adb_cmd("shell cat /proc/stat | grep '^cpu '")
        if not stdout2.strip():
            return 0.0
            
        # 解析第二次数据
        parts2 = stdout2.strip().split()
        if len(parts2) < 5:
            return 0.0
            
        user2 = int(parts2[1])
        nice2 = int(parts2[2])
        system2 = int(parts2[3])
        idle2 = int(parts2[4])
        
        # 计算使用率
        total1 = user1 + nice1 + system1 + idle1
        total2 = user2 + nice2 + system2 + idle2
        
        total_diff = total2 - total1
        idle_diff = idle2 - idle1
        
        # 防止除零错误
        if total_diff <= 0:
            return 0.0
            
        usage = 100.0 * (1.0 - idle_diff / total_diff)
        return usage
    
    def get_storage_info(self) -> Dict[str, Any]:
        """
        获取设备存储信息
        
        Returns:
            存储信息 {total, used, free} 单位为MB
        """
        stdout, stderr, code = self.run_adb_cmd("shell df -h /data")
        
        if code != 0:
            self.logger.error(f"获取存储信息失败: {stderr}")
            return {}
            
        storage_info = {}
        lines = stdout.strip().split('\n')
        if len(lines) < 2:
            return {}
            
        # 解析df输出
        parts = lines[1].split()
        if len(parts) < 4:
            return {}
            
        # 转换为MB
        def convert_to_mb(size_str):
            if 'G' in size_str:
                return float(size_str.replace('G', '')) * 1024
            elif 'M' in size_str:
                return float(size_str.replace('M', ''))
            elif 'K' in size_str:
                return float(size_str.replace('K', '')) / 1024
            else:
                try:
                    return float(size_str) / (1024 * 1024)
                except ValueError:
                    return 0
        
        storage_info["total"] = convert_to_mb(parts[1])
        storage_info["used"] = convert_to_mb(parts[2])
        storage_info["free"] = convert_to_mb(parts[3])
        
        return storage_info
    
    def get_network_info(self) -> Dict[str, Any]:
        """
        获取设备网络信息
        
        Returns:
            网络信息 {wifi_enabled, mobile_data_enabled, airplane_mode, wifi_name}
        """
        # 获取WiFi状态
        stdout, _, _ = self.run_adb_cmd("shell settings get global wifi_on")
        wifi_enabled = stdout.strip() == "1"
        
        # 获取移动数据状态
        stdout, _, _ = self.run_adb_cmd("shell settings get global mobile_data")
        mobile_data_enabled = stdout.strip() == "1"
        
        # 获取飞行模式状态
        stdout, _, _ = self.run_adb_cmd("shell settings get global airplane_mode_on")
        airplane_mode = stdout.strip() == "1"
        
        # 获取WiFi名称
        wifi_name = ""
        if wifi_enabled:
            stdout, _, _ = self.run_adb_cmd("shell dumpsys wifi | grep 'mWifiInfo'")
            match = re.search(r'SSID: (.*?),', stdout)
            if match:
                wifi_name = match.group(1).strip('"')
        
        return {
            "wifi_enabled": wifi_enabled,
            "mobile_data_enabled": mobile_data_enabled,
            "airplane_mode": airplane_mode,
            "wifi_name": wifi_name
        }
    
    def get_ip_address(self) -> str:
        """
        获取设备IP地址
        
        Returns:
            IP地址
        """
        stdout, _, _ = self.run_adb_cmd("shell ip addr show wlan0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1")
        return stdout.strip()
    
    def get_mac_address(self) -> str:
        """
        获取设备MAC地址
        
        Returns:
            MAC地址
        """
        stdout, _, _ = self.run_adb_cmd("shell cat /sys/class/net/wlan0/address")
        return stdout.strip()
    
    def get_dpi(self) -> int:
        """
        获取设备DPI
        
        Returns:
            DPI
        """
        stdout, _, _ = self.run_adb_cmd("shell getprop ro.sf.lcd_density")
        try:
            return int(stdout.strip())
        except ValueError:
            return 0
            
    def list_devices(self) -> List[Dict[str, str]]:
        """
        列出已连接设备
        
        Returns:
            设备列表 [{serial, status}]
        """
        stdout, stderr, code = self.run_adb_cmd("devices")
        
        if code != 0:
            self.logger.error(f"获取设备列表失败: {stderr}")
            return []
            
        device_list = []
        lines = stdout.strip().split('\n')
        
        # 跳过标题行
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
                
            parts = line.split()
            if len(parts) >= 2:
                device_list.append({
                    "serial": parts[0],
                    "status": parts[1]
                })
                
        return device_list
    
    def toggle_wifi(self, enable: bool) -> bool:
        """
        设置WiFi开关
        
        Args:
            enable: True开启，False关闭
            
        Returns:
            是否成功
        """
        cmd = f"shell svc wifi {enable and 'enable' or 'disable'}"
        _, stderr, code = self.run_adb_cmd(cmd)
        
        if code != 0:
            self.logger.error(f"设置WiFi状态失败: {stderr}")
            return False
            
        # 验证设置是否生效
        current_status = self.get_network_info().get("wifi_enabled", False)
        return current_status == enable
    
    def toggle_bluetooth(self, enable: bool) -> bool:
        """
        设置蓝牙开关
        
        Args:
            enable: True开启，False关闭
            
        Returns:
            是否成功
        """
        if enable:
            cmd = "shell am start -a android.bluetooth.adapter.action.REQUEST_ENABLE"
        else:
            cmd = "shell settings put global bluetooth_on 0"
            
        _, stderr, code = self.run_adb_cmd(cmd)
        
        if code != 0:
            self.logger.error(f"设置蓝牙状态失败: {stderr}")
            return False
            
        # 由于控制蓝牙可能需要UI交互，所以不做严格验证
        return True
    
    def toggle_mobile_data(self, enable: bool) -> bool:
        """
        设置移动数据开关
        
        Args:
            enable: True开启，False关闭
            
        Returns:
            是否成功
        """
        cmd = f"shell svc data {enable and 'enable' or 'disable'}"
        _, stderr, code = self.run_adb_cmd(cmd)
        
        if code != 0:
            self.logger.error(f"设置移动数据状态失败: {stderr}")
            return False
            
        # 验证设置是否生效
        current_status = self.get_network_info().get("mobile_data_enabled", False)
        return current_status == enable
    
    def toggle_airplane_mode(self, enable: bool) -> bool:
        """
        设置飞行模式
        
        Args:
            enable: True开启，False关闭
            
        Returns:
            是否成功
        """
        # 设置飞行模式状态
        cmd1 = f"shell settings put global airplane_mode_on {enable and 1 or 0}"
        _, stderr1, code1 = self.run_adb_cmd(cmd1)
        
        if code1 != 0:
            self.logger.error(f"设置飞行模式状态失败: {stderr1}")
            return False
            
        # 广播飞行模式变更事件
        cmd2 = "shell am broadcast -a android.intent.action.AIRPLANE_MODE --ez state " + (enable and "true" or "false")
        _, stderr2, code2 = self.run_adb_cmd(cmd2)
        
        if code2 != 0:
            self.logger.error(f"广播飞行模式变更事件失败: {stderr2}")
            return False
            
        # 验证设置是否生效
        current_status = self.get_network_info().get("airplane_mode", False)
        return current_status == enable
    
    def connect_wifi(self, ssid: str, password: str = None, security_type: str = "WPA") -> bool:
        """
        连接到指定WiFi
        
        Args:
            ssid: WiFi名称
            password: WiFi密码，开放网络可为None
            security_type: 安全类型，支持NONE/WEP/WPA/WPA2，默认WPA
            
        Returns:
            是否成功
        """
        # 先确认WiFi已开启
        if not self.get_network_info().get("wifi_enabled", False):
            self.toggle_wifi(True)
            # 等待WiFi启动
            time.sleep(1)
            
        # 构建配置文件内容
        if security_type.upper() == "NONE":
            network_config = f'network={{\n\tssid="{ssid}"\n\tkey_mgmt=NONE\n}}\n'
        elif security_type.upper() == "WEP":
            network_config = f'network={{\n\tssid="{ssid}"\n\tkey_mgmt=NONE\n\twep_key0="{password}"\n}}\n'
        else:  # WPA/WPA2
            network_config = f'network={{\n\tssid="{ssid}"\n\tpsk="{password}"\n}}\n'
            
        # 创建临时文件
        tmp_file = "/data/local/tmp/wifi_config.conf"
        
        # 写入配置到设备
        echo_cmd = f"shell echo -e '{network_config}' > {tmp_file}"
        self.run_adb_cmd(echo_cmd, shell=True)
        
        # 添加网络配置
        cmd = f"shell wpa_cli -i wlan0 add_network"
        stdout, _, _ = self.run_adb_cmd(cmd)
        network_id = stdout.strip()
        
        if not network_id.isdigit():
            self.logger.error("添加WiFi网络失败")
            return False
            
        # 加载配置文件
        load_cmd = f"shell wpa_cli -i wlan0 set_network {network_id} ssid '\"{ssid}\"'"
        self.run_adb_cmd(load_cmd)
        
        if password:
            if security_type.upper() == "WEP":
                self.run_adb_cmd(f"shell wpa_cli -i wlan0 set_network {network_id} key_mgmt NONE")
                self.run_adb_cmd(f"shell wpa_cli -i wlan0 set_network {network_id} wep_key0 '\"{password}\"'")
            else:
                self.run_adb_cmd(f"shell wpa_cli -i wlan0 set_network {network_id} psk '\"{password}\"'")
        else:
            self.run_adb_cmd(f"shell wpa_cli -i wlan0 set_network {network_id} key_mgmt NONE")
            
        # 启用网络
        self.run_adb_cmd(f"shell wpa_cli -i wlan0 enable_network {network_id}")
        self.run_adb_cmd(f"shell wpa_cli -i wlan0 select_network {network_id}")
        
        # 保存配置
        self.run_adb_cmd("shell wpa_cli -i wlan0 save_config")
        
        # 删除临时文件
        self.run_adb_cmd(f"shell rm {tmp_file}")
        
        # 等待连接
        max_tries = 10
        for i in range(max_tries):
            time.sleep(1)
            current_wifi = self.get_network_info().get("wifi_name", "")
            if current_wifi == ssid:
                return True
                
        return False
    
    def get_wifi_info(self) -> Dict[str, Any]:
        """
        获取当前WiFi详细信息
        
        Returns:
            WiFi信息 {ssid, bssid, rssi, ip_address, link_speed, frequency}
        """
        # 确认WiFi是否已开启
        if not self.get_network_info().get("wifi_enabled", False):
            return {}
            
        wifi_info = {}
        
        # 获取WiFi信息
        stdout, _, _ = self.run_adb_cmd("shell dumpsys wifi | grep -A 10 'mWifiInfo'")
        lines = stdout.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if "SSID: " in line:
                match = re.search(r'SSID: (.*?)[,}]', line)
                if match:
                    wifi_info["ssid"] = match.group(1).strip('"')
            elif "BSSID: " in line:
                match = re.search(r'BSSID: (.*?)[,}]', line)
                if match:
                    wifi_info["bssid"] = match.group(1)
            elif "RSSI: " in line:
                match = re.search(r'RSSI: (.*?)[,}]', line)
                if match:
                    wifi_info["rssi"] = int(match.group(1))
            elif "Link speed: " in line:
                match = re.search(r'Link speed: (.*?)[,}]', line)
                if match:
                    wifi_info["link_speed"] = match.group(1)
            elif "Frequency: " in line:
                match = re.search(r'Frequency: (.*?)[,}]', line)
                if match:
                    wifi_info["frequency"] = match.group(1)
                    
        # 获取IP地址
        wifi_info["ip_address"] = self.get_ip_address()
            
        return wifi_info 