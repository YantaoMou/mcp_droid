# MCPDroid本地部署指南

本文档提供了在本地环境中部署MCPDroid服务并将其与Cursor连接的详细步骤。

## 1. 环境准备

### 系统要求
- Python 3.8+
- ADB工具
- Android设备（Android 7.0+）
- USB数据线或保证电脑与手机在同一网络

### 安装ADB工具
#### Windows
1. 下载Android SDK Platform Tools: https://developer.android.com/studio/releases/platform-tools
2. 解压到本地目录
3. 将解压目录添加到系统环境变量PATH中

#### macOS
```bash
brew install android-platform-tools
```

#### Linux
```bash
sudo apt-get install android-tools-adb
```

### 连接Android设备
1. 在Android设备上启用开发者选项：
   - 进入设置 -> 关于手机 -> 连续点击"版本号"7次
   - 返回设置，找到"开发者选项"
   - 开启"USB调试"

2. 使用USB线连接设备到电脑
3. 在设备上确认USB调试授权提示
4. 验证连接：
```bash
adb devices
```
应当显示已连接的设备列表。

## 2. 安装MCPDroid

### 克隆项目
```bash
git clone https://github.com/yourusername/mcp_droid.git
cd mcp_droid
```

### 创建虚拟环境（推荐）
```bash
python -m venv venv
```

#### 激活虚拟环境
Windows:
```bash
venv\Scripts\activate
```

macOS/Linux:
```bash
source venv/bin/activate
```

### 安装依赖
```bash
pip install -r requirements.txt
```

## 3. 启动MCPDroid服务

### 基本启动命令
```bash
python main.py
```

### 带参数启动（自定义配置）
```bash
python main.py --adb-path /path/to/adb --device-id DEVICEID --host 127.0.0.1 --port 8000 --debug
```

参数说明：
- `--adb-path`: ADB命令路径，如果已添加到环境变量可以省略
- `--device-id`: 设备ID，多设备连接时需要指定，可通过`adb devices`查看
- `--host`: 监听地址，默认为"0.0.0.0"
- `--port`: 监听端口，默认为8000
- `--debug`: 开启调试模式，输出更详细的日志

### 验证服务启动
服务启动后，会显示如下信息：
```
INFO - 启动MCPDroid服务，监听地址: 0.0.0.0:8000
```

可以通过浏览器访问`http://localhost:8000/docs`查看API文档。

## 4. 配置Cursor连接MCP服务

### 在Cursor中配置MCP服务
1. 打开Cursor
2. 进入配置文件添加MCP服务地址

#### Windows
编辑`%APPDATA%\Cursor\config.json`

#### macOS
编辑`~/Library/Application Support/Cursor/config.json`

#### Linux
编辑`~/.config/Cursor/config.json`

添加以下配置：
```json
{
  "mcpServers": {
    "android": {
      "type": "sse",
      "url": "http://localhost:8000/jsonrpc"
    }
  }
}
```

如果配置文件已存在其他内容，确保正确合并JSON结构。

### 重启Cursor应用
配置保存后，重启Cursor应用以加载新配置。

## 5. 验证连接

1. 在Cursor中打开一个项目或新建一个文档
2. 通过AI助手使用Android设备控制功能，例如：
   - "截取当前手机屏幕"
   - "在手机上打开微信应用"
   - "帮我在手机上搜索某个内容"

如果配置正确，AI助手将能够通过MCPDroid服务控制您的Android设备。

## 6. 高级功能配置

### OCR文字识别功能
如需使用OCR功能，需安装Tesseract：

#### Windows
1. 下载安装器：https://github.com/UB-Mannheim/tesseract/wiki
2. 安装并记住安装路径
3. 添加环境变量：`TESSDATA_PREFIX=C:\Program Files\Tesseract-OCR\tessdata`

#### macOS
```bash
brew install tesseract
```

#### Linux
```bash
sudo apt-get install tesseract-ocr
```

安装Python绑定：
```bash
pip install pytesseract
```

### 图像识别功能
如需使用图像识别功能，安装额外依赖：
```bash
pip install opencv-python airtest
```

## 7. 常见问题解决

### ADB连接问题
1. 确保设备已开启USB调试
2. 确保已在设备上允许来自电脑的调试
3. 尝试重启ADB服务：
   ```bash
   adb kill-server
   adb start-server
   ```

### 服务启动失败
1. 检查端口占用情况，可能需要更换端口：
   ```bash
   python main.py --port 8001
   ```
2. 检查防火墙设置，确保允许应用通过端口通信

### Cursor无法连接MCP服务
1. 确保服务地址配置正确
2. 检查服务是否正常运行
3. 尝试使用`curl`测试服务可用性：
   ```bash
   curl -X POST http://localhost:8000/jsonrpc -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"list_devices","params":{},"id":1}'
   ```

### 权限问题
如在设备操作时遇到权限问题，可能需要赋予ADB更多权限：
```bash
adb shell pm grant com.android.shell android.permission.READ_LOGS
```

## 8. 资源与参考
- [MCP协议文档](https://github.com/anthropics/anthropic-cookbook/tree/main/mcp)
- [ADB命令文档](https://developer.android.com/studio/command-line/adb)
- [Cursor官方文档](https://cursor.sh/docs) 