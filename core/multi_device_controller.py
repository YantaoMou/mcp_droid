"""
多设备协作控制器，提供设备间消息传递、同步操作、文件共享等功能
"""
import os
import json
import time
import logging
import threading
import socket
import tempfile
from typing import Dict, List, Any, Tuple, Optional, Union, Callable
import queue
import subprocess

from core.device_controller import DeviceController


class MultiDeviceController(DeviceController):
    """
    多设备协作控制器，提供设备间的协作功能
    """
    
    def __init__(self, adb_path: str = "adb", device_id: str = None):
        """
        初始化多设备协作控制器
        
        Args:
            adb_path: ADB命令路径
            device_id: 设备ID，如果有多个设备连接时需要指定
        """
        super().__init__(adb_path, device_id)
        self.logger = logging.getLogger("MultiDeviceController")
        
        # 添加线程锁保护共享资源
        self._device_groups_lock = threading.RLock()
        self._message_queues_lock = threading.RLock()
        self._sync_locks_lock = threading.RLock()
        self._shared_data_lock = threading.RLock()
        
        self.device_groups = {}  # 设备组 {组名: [设备ID列表]}
        self.message_queues = {}  # 设备消息队列 {设备ID: Queue}
        self.sync_locks = {}  # 同步锁 {锁名: threading.Event}
        self.shared_data = {}  # 共享数据 {键: 值}
    
    def device_messaging(self, action: str, device_id: str = None, 
                         message: str = None, timeout: int = 5) -> Dict[str, Any]:
        """
        设备间消息传递
        
        Args:
            action: 操作类型，send（发送消息）、receive（接收消息）、clear（清空消息）
            device_id: 目标设备ID或来源设备ID
            message: 要发送的消息内容
            timeout: 接收消息的超时时间(秒)
            
        Returns:
            操作结果
        """
        # 初始化消息队列
        if action in ("send", "receive") and device_id:
            with self._message_queues_lock:
                if device_id not in self.message_queues:
                    self.message_queues[device_id] = queue.Queue()
            
        # 发送消息到设备
        if action == "send":
            if not device_id:
                return {"success": False, "message": "未指定目标设备ID"}
                
            if not message:
                return {"success": False, "message": "消息内容不能为空"}
                
            # 检查目标设备是否存在
            devices = self._list_all_devices()
            device_exists = any(d.get("serial") == device_id for d in devices)
            
            if not device_exists:
                return {"success": False, "message": f"设备 {device_id} 不存在或未连接"}
                
            # 将消息放入队列
            try:
                with self._message_queues_lock:
                    if device_id not in self.message_queues:
                        self.message_queues[device_id] = queue.Queue()
                    
                    self.message_queues[device_id].put({
                        "timestamp": time.time(),
                        "sender": self.device_id or "unknown",
                        "content": message
                    })
                
                return {"success": True, "message": "消息已发送"}
            except Exception as e:
                return {"success": False, "message": f"发送消息失败: {str(e)}"}
                
        # 接收消息
        elif action == "receive":
            if not device_id and not self.device_id:
                return {"success": False, "message": "未指定来源设备ID"}
                
            source_id = device_id or self.device_id
            
            # 检查队列是否存在
            with self._message_queues_lock:
                if source_id not in self.message_queues:
                    self.message_queues[source_id] = queue.Queue()
                    return {"success": True, "messages": []}
            
            # 从队列获取消息
            messages = []
            try:
                # 非阻塞方式获取所有消息
                queue_obj = None
                with self._message_queues_lock:
                    queue_obj = self.message_queues[source_id]
                
                while True:
                    try:
                        msg = queue_obj.get(block=True, timeout=timeout)
                        messages.append(msg)
                        queue_obj.task_done()
                    except queue.Empty:
                        break
                        
                return {"success": True, "messages": messages}
            except Exception as e:
                return {"success": False, "message": f"接收消息失败: {str(e)}"}
                
        # 清空消息
        elif action == "clear":
            if not device_id and not self.device_id:
                return {"success": False, "message": "未指定设备ID"}
                
            target_id = device_id or self.device_id
            
            # 检查队列是否存在
            with self._message_queues_lock:
                if target_id in self.message_queues:
                    try:
                        # 清空队列
                        queue_obj = self.message_queues[target_id]
                        while not queue_obj.empty():
                            queue_obj.get()
                            queue_obj.task_done()
                            
                        return {"success": True, "message": "消息已清空"}
                    except Exception as e:
                        return {"success": False, "message": f"清空消息失败: {str(e)}"}
                else:
                    return {"success": True, "message": "无消息队列需要清空"}
        else:
            return {"success": False, "message": f"不支持的操作类型: {action}"}
    
    def sync_operations(self, action: str, lock_name: str = None, 
                        timeout: int = 30) -> Dict[str, bool]:
        """
        多设备同步操作
        
        Args:
            action: 操作类型，create（创建锁）、wait（等待锁）、set（设置锁）、release（释放锁）
            lock_name: 锁名称
            timeout: 等待超时时间(秒)
            
        Returns:
            操作结果
        """
        if not lock_name:
            return {"success": False, "message": "未指定锁名称"}
            
        # 创建锁
        if action == "create":
            with self._sync_locks_lock:
                self.sync_locks[lock_name] = threading.Event()
            return {"success": True, "message": f"已创建锁 {lock_name}"}
            
        # 等待锁
        elif action == "wait":
            lock_obj = None
            with self._sync_locks_lock:
                if lock_name not in self.sync_locks:
                    self.sync_locks[lock_name] = threading.Event()
                lock_obj = self.sync_locks[lock_name]
                
            try:
                # 等待锁被设置
                success = lock_obj.wait(timeout=timeout)
                if success:
                    return {"success": True, "message": f"锁 {lock_name} 已触发"}
                else:
                    return {"success": False, "message": f"等待锁 {lock_name} 超时"}
            except Exception as e:
                return {"success": False, "message": f"等待锁失败: {str(e)}"}
                
        # 设置锁
        elif action == "set":
            with self._sync_locks_lock:
                if lock_name not in self.sync_locks:
                    self.sync_locks[lock_name] = threading.Event()
                lock_obj = self.sync_locks[lock_name]
                
            try:
                # 设置锁，通知所有等待该锁的线程
                lock_obj.set()
                return {"success": True, "message": f"已设置锁 {lock_name}"}
            except Exception as e:
                return {"success": False, "message": f"设置锁失败: {str(e)}"}
                
        # 释放锁
        elif action == "release":
            lock_obj = None
            with self._sync_locks_lock:
                if lock_name in self.sync_locks:
                    lock_obj = self.sync_locks[lock_name]
                else:
                    return {"success": False, "message": f"锁 {lock_name} 不存在"}
                    
            try:
                # 清除锁，重置为未设置状态
                lock_obj.clear()
                return {"success": True, "message": f"已释放锁 {lock_name}"}
            except Exception as e:
                return {"success": False, "message": f"释放锁失败: {str(e)}"}
        else:
            return {"success": False, "message": f"不支持的操作类型: {action}"}
    
    def device_group_actions(self, action: str, group_name: str = None, 
                             device_ids: List[str] = None, 
                             command: str = None) -> Dict[str, Any]:
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
        # 创建设备组
        if action == "create":
            if not group_name:
                return {"success": False, "message": "未指定组名称"}
                
            if not device_ids:
                return {"success": False, "message": "未指定设备ID列表"}
                
            # 检查设备是否存在
            all_devices = self._list_all_devices()
            device_serials = [d.get("serial") for d in all_devices]
            
            for device_id in device_ids:
                if device_id not in device_serials:
                    return {"success": False, "message": f"设备 {device_id} 不存在或未连接"}
            
            # 创建或更新设备组
            with self._device_groups_lock:
                self.device_groups[group_name] = device_ids
                
            return {"success": True, "message": f"已创建设备组 {group_name}"}
            
        # 列出设备组
        elif action == "list":
            with self._device_groups_lock:
                if not self.device_groups:
                    return {"success": True, "message": "无设备组", "groups": []}
                    
                groups = []
                for name, ids in self.device_groups.items():
                    groups.append({
                        "name": name,
                        "device_ids": ids
                    })
                    
                return {"success": True, "groups": groups}
                
        # 执行组命令
        elif action == "execute":
            if not group_name:
                return {"success": False, "message": "未指定组名称"}
                
            if not command:
                return {"success": False, "message": "未指定要执行的命令"}
                
            # 检查组是否存在
            with self._device_groups_lock:
                if group_name not in self.device_groups:
                    return {"success": False, "message": f"设备组 {group_name} 不存在"}
                    
                device_ids = self.device_groups[group_name]
            
            # 在组内每个设备上执行命令
            results = []
            for device_id in device_ids:
                stdout, stderr, code = self.run_adb_cmd(command, device_id)
                results.append({
                    "device_id": device_id,
                    "success": code == 0,
                    "output": stdout,
                    "error": stderr
                })
                
            return {"success": True, "results": results}
            
        # 删除设备组
        elif action == "delete":
            if not group_name:
                return {"success": False, "message": "未指定组名称"}
                
            # 检查组是否存在
            with self._device_groups_lock:
                if group_name not in self.device_groups:
                    return {"success": False, "message": f"设备组 {group_name} 不存在"}
                    
                # 删除组
                del self.device_groups[group_name]
                
            return {"success": True, "message": f"已删除设备组 {group_name}"}
        else:
            return {"success": False, "message": f"不支持的操作类型: {action}"}
    
    def share_between_devices(self, action: str, source_device: str = None, 
                              target_device: str = None, local_path: str = None, 
                              device_path: str = None, data_key: str = None, 
                              data_value: Any = None) -> Dict[str, Any]:
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
        try:
            # 复制文件
            if action == "copy_file":
                if not source_device:
                    return {"success": False, "message": "未指定源设备ID"}
                    
                if not target_device:
                    return {"success": False, "message": "未指定目标设备ID"}
                    
                if not device_path:
                    return {"success": False, "message": "未指定设备文件路径"}
                    
                # 检查设备是否存在
                all_devices = self._list_all_devices()
                device_serials = [d.get("serial") for d in all_devices]
                
                if source_device not in device_serials:
                    return {"success": False, "message": f"源设备 {source_device} 不存在或未连接"}
                    
                if target_device not in device_serials:
                    return {"success": False, "message": f"目标设备 {target_device} 不存在或未连接"}
                
                # 创建临时文件
                with tempfile.NamedTemporaryFile(delete=False) as temp:
                    temp_path = temp.name
                
                # 从源设备下载文件到临时文件
                _, stderr, code = self.run_adb_cmd(f"pull {device_path} {temp_path}", source_device)
                if code != 0:
                    os.unlink(temp_path)
                    return {"success": False, "message": f"从源设备下载文件失败: {stderr}"}
                    
                # 上传临时文件到目标设备
                _, stderr, code = self.run_adb_cmd(f"push {temp_path} {device_path}", target_device)
                
                # 删除临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
                if code != 0:
                    return {"success": False, "message": f"上传文件到目标设备失败: {stderr}"}
                    
                return {"success": True, "message": "文件已成功复制到目标设备"}
                
            # 共享数据
            elif action == "share_data":
                if not data_key:
                    return {"success": False, "message": "未指定数据键"}
                    
                if data_value is None:
                    return {"success": False, "message": "未指定数据值"}
                    
                # 保存共享数据
                with self._shared_data_lock:
                    self.shared_data[data_key] = data_value
                    
                return {"success": True, "message": f"数据已共享，键: {data_key}"}
                
            # 获取数据
            elif action == "get_data":
                if not data_key:
                    return {"success": False, "message": "未指定数据键"}
                    
                # 获取共享数据
                with self._shared_data_lock:
                    if data_key not in self.shared_data:
                        return {"success": False, "message": f"共享数据中不存在键: {data_key}"}
                        
                    value = self.shared_data[data_key]
                    
                return {"success": True, "data": value}
                
            else:
                return {"success": False, "message": f"不支持的操作类型: {action}"}
                
        except Exception as e:
            self.logger.error(f"设备间共享操作失败: {str(e)}")
            return {"success": False, "message": f"设备间共享操作失败: {str(e)}"}
    
    def _list_all_devices(self) -> List[Dict[str, str]]:
        """
        列出所有已连接设备
        
        Returns:
            设备列表 [{"serial": 设备ID, "status": 设备状态}]
        """
        stdout, _, _ = self.run_adb_cmd("devices")
        devices = []
        
        lines = stdout.strip().split('\n')
        if len(lines) <= 1:
            return []
            
        for line in lines[1:]:  # 跳过标题行
            if not line.strip():
                continue
                
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                serial = parts[0]
                status = parts[1]
                devices.append({
                    "serial": serial,
                    "status": status
                })
                
        return devices
    
    # 在特定设备上执行ADB命令的辅助方法
    def run_adb_cmd(self, cmd: str, device_id: str = None, 
                    shell: bool = True, timeout: int = 30) -> Tuple[str, str, int]:
        """
        在特定设备上执行ADB命令
        
        Args:
            cmd: ADB命令
            device_id: 设备ID，为None时使用当前设备
            shell: 是否使用shell执行
            timeout: 命令超时时间(秒)
            
        Returns:
            返回元组 (stdout, stderr, return_code)
        """
        # 如果未指定设备ID，使用当前设备ID
        target_device = device_id or self.device_id
        
        # 构建ADB命令
        if target_device:
            full_cmd = f"{self.adb_path} -s {target_device} {cmd}"
        else:
            full_cmd = f"{self.adb_path} {cmd}"
            
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
        except Exception as e:
            self.logger.error(f"命令执行错误: {str(e)}")
            return "", str(e), -2
            
    def cleanup(self):
        """
        清理控制器资源，在服务关闭时调用
        """
        self.logger.info("清理多设备控制器资源...")
        
        # 停止所有同步锁
        with self._sync_locks_lock:
            for lock_name, lock_event in self.sync_locks.items():
                try:
                    lock_event.set()  # 解除所有等待
                except Exception as e:
                    self.logger.error(f"释放锁 {lock_name} 失败: {str(e)}")
        
        # 清空消息队列
        with self._message_queues_lock:
            for device_id, queue_obj in self.message_queues.items():
                try:
                    while not queue_obj.empty():
                        try:
                            queue_obj.get_nowait()
                            queue_obj.task_done()
                        except:
                            break
                except Exception as e:
                    self.logger.error(f"清空设备 {device_id} 的消息队列失败: {str(e)}")
        
        self.logger.info("多设备控制器资源清理完成") 