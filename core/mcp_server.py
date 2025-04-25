"""
MCP协议服务器实现
"""
import os
import json
import logging
import inspect
import signal
import atexit
import threading
from typing import Dict, List, Any, Callable, Optional, Union
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# 日志配置
logger = logging.getLogger("mcp_server")


class MCPError(Exception):
    """MCP错误异常"""
    def __init__(self, message: str, code: int = -32000):
        self.message = message
        self.code = code
        super().__init__(self.message)


class MCPRequest(BaseModel):
    """MCP请求模型"""
    jsonrpc: str = Field("2.0", const=True)
    id: Optional[Union[int, str]] = None
    method: str
    params: Optional[Dict[str, Any]] = {}


class MCPResponse(BaseModel):
    """MCP响应模型"""
    jsonrpc: str = "2.0"
    id: Optional[Union[int, str]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class MCPTool:
    """MCP工具定义"""
    def __init__(
        self, 
        name: str, 
        description: str, 
        handler: Callable, 
        input_schema: Dict[str, Any] = None,
        annotations: Dict[str, Any] = None
    ):
        self.name = name
        self.description = description
        self.handler = handler
        self.input_schema = input_schema or {}
        self.annotations = annotations or {}


class MCPServer:
    """MCP协议服务器实现"""
    
    def __init__(self):
        """初始化MCP服务器"""
        self.app = FastAPI(title="MCPDroid-Service")
        
        # 允许跨域请求
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 注册路由
        self.app.post("/jsonrpc", response_model=None)(self.handle_jsonrpc)
        
        # MCP工具集合
        self.tools = {}
        
        # 添加核心工具
        self.register_core_tools()
        
        # 保存所有资源引用
        self.resources = {
            "running_threads": [],
            "controllers": []
        }
        
        # 注册退出清理函数
        atexit.register(self.cleanup)
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        """处理终止信号"""
        logger.info(f"收到信号 {signum}，准备清理资源并退出")
        self.cleanup()
        
    def register_controller(self, controller):
        """注册控制器，用于资源清理"""
        if controller not in self.resources["controllers"]:
            self.resources["controllers"].append(controller)
    
    def register_thread(self, thread):
        """注册线程，用于资源清理"""
        if thread not in self.resources["running_threads"]:
            self.resources["running_threads"].append(thread)
    
    def cleanup(self):
        """清理资源"""
        logger.info("清理资源...")
        
        # 停止所有运行中的线程
        for thread in self.resources["running_threads"]:
            if thread.is_alive():
                try:
                    logger.debug(f"停止线程: {thread.name}")
                    # 这里无法强制停止线程，依赖线程自己检查退出标志
                except Exception as e:
                    logger.error(f"停止线程失败: {str(e)}")
        
        # 清理控制器资源
        for controller in self.resources["controllers"]:
            try:
                logger.debug(f"清理控制器: {controller.__class__.__name__}")
                if hasattr(controller, "cleanup") and callable(controller.cleanup):
                    controller.cleanup()
            except Exception as e:
                logger.error(f"清理控制器失败: {str(e)}")
                
        logger.info("资源清理完成")
    
    def register_core_tools(self):
        """注册核心工具"""
        # 注册tools/list工具（列出可用工具）
        self.tools["tools/list"] = MCPTool(
            name="list",
            description="列出所有可用工具",
            handler=self._handle_tools_list
        )
        
        # 注册tools/call工具（调用指定工具）
        self.tools["tools/call"] = MCPTool(
            name="call",
            description="调用指定工具",
            handler=self._handle_tools_call,
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "工具名称"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "工具参数"
                    }
                },
                "required": ["name"]
            }
        )
    
    def register_tool(self, tool: MCPTool):
        """
        注册MCP工具
        
        Args:
            tool: 工具实例
        """
        logger.info(f"注册MCP工具: {tool.name}")
        name = f"tools/{tool.name}"
        self.tools[name] = tool
    
    async def handle_jsonrpc(self, request: Request) -> Response:
        """
        处理JSON-RPC请求
        
        Args:
            request: HTTP请求
            
        Returns:
            HTTP响应
        """
        # 在顶层添加异常捕获
        data = None
        try:
            # 解析请求
            body = await request.body()
            if not body:
                return self._create_error_response(None, "无效的空请求", -32600)
                
            try:
                data = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                return self._create_error_response(None, "无效的JSON", -32700)
                
            # 处理批量请求
            if isinstance(data, list):
                return self._handle_batch_request(data)
                
            # 处理单个请求
            return await self._handle_single_request(data)
            
        except MCPError as e:
            # 已知的MCP错误类型，直接传递错误码和消息
            logger.warning(f"MCP错误: {e.message} (代码: {e.code})")
            return self._create_error_response(
                None if data is None else (data.get("id") if isinstance(data, dict) else None),
                e.message,
                e.code
            )
        except Exception as e:
            # 捕获所有其他未处理的异常，返回标准JSON-RPC错误
            logger.error(f"处理JSON-RPC请求时发生未捕获的异常: {str(e)}", exc_info=True)
            return self._create_error_response(
                None if data is None else (data.get("id") if isinstance(data, dict) else None),
                "Internal error",
                -32603
            )
    
    async def _handle_single_request(self, data: Dict[str, Any]) -> Response:
        """处理单个JSON-RPC请求"""
        # 验证请求格式
        if not isinstance(data, dict) or data.get("jsonrpc") != "2.0" or "method" not in data:
            return self._create_error_response(data.get("id"), "无效的请求", -32600)
            
        # 获取请求ID和方法
        request_id = data.get("id")
        method = data.get("method")
        params = data.get("params", {})
        
        # 查找处理方法
        if method not in self.tools:
            return self._create_error_response(request_id, f"方法未找到: {method}", -32601)
            
        try:
            # 调用处理方法
            tool = self.tools[method]
            result = await self._call_handler(tool.handler, params)
            
            # 返回成功响应
            return self._create_success_response(request_id, result)
        except MCPError as e:
            logger.warning(f"处理请求 '{method}' 时发生MCP错误: {e.message} (代码: {e.code})")
            return self._create_error_response(request_id, e.message, e.code)
        except Exception as e:
            logger.error(f"处理请求 '{method}' 时发生错误: {str(e)}", exc_info=True)
            return self._create_error_response(request_id, f"服务器内部错误: {str(e)}", -32603)
    
    def _handle_batch_request(self, batch: List[Dict[str, Any]]) -> Response:
        """处理批量JSON-RPC请求"""
        # 暂不支持批量请求
        return self._create_error_response(None, "不支持批量请求", -32600)
        
    def _create_success_response(self, request_id: Union[int, str, None], result: Any) -> Response:
        """创建成功响应"""
        response = MCPResponse(
            jsonrpc="2.0",
            id=request_id,
            result=result
        )
        return Response(
            content=json.dumps(response.dict(exclude_none=True)),
            media_type="application/json"
        )
        
    def _create_error_response(self, request_id: Union[int, str, None], message: str, code: int = -32000) -> Response:
        """创建错误响应"""
        response = MCPResponse(
            jsonrpc="2.0",
            id=request_id,
            error={
                "code": code,
                "message": message
            }
        )
        return Response(
            content=json.dumps(response.dict(exclude_none=True)),
            media_type="application/json"
        )
        
    async def _call_handler(self, handler: Callable, params: Dict[str, Any]) -> Any:
        """调用处理方法"""
        # 检查处理方法是否为异步
        if inspect.iscoroutinefunction(handler):
            return await handler(params)
        else:
            return handler(params)
    
    def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理tools/list方法
        
        Args:
            params: 请求参数
            
        Returns:
            工具列表
        """
        tools_list = []
        
        for name, tool in self.tools.items():
            # 只返回tools/下的工具，排除核心方法
            if name.startswith("tools/") and name != "tools/list" and name != "tools/call":
                tools_list.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                    "annotations": tool.annotations
                })
        
        return {"tools": tools_list}
    
    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理tools/call方法
        
        Args:
            params: 请求参数
            
        Returns:
            工具调用结果
        """
        tool_name = params.get("name")
        tool_params = params.get("parameters", {})
        
        # 检查工具是否存在
        full_tool_name = f"tools/{tool_name}"
        if full_tool_name not in self.tools:
            raise MCPError(f"工具未找到: {tool_name}", -32601)
            
        # 调用工具
        tool = self.tools[full_tool_name]
        try:
            result = tool.handler(tool_params)
            return {"result": result}
        except Exception as e:
            logger.error(f"调用工具 '{tool_name}' 时发生错误: {str(e)}")
            raise MCPError(f"工具调用失败: {str(e)}")
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """
        启动服务器
        
        Args:
            host: 主机地址
            port: 端口号
        """
        logger.info(f"启动MCP服务器: {host}:{port}")
        config = uvicorn.Config(self.app, host=host, port=port)
        server = uvicorn.Server(config)
        server.run() 