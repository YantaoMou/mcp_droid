# MCPDroid 示例

本目录包含了一些MCPDroid的使用示例，帮助您了解如何通过编程方式与MCPDroid服务交互。

## 示例列表

1. `basic_usage.py` - 基本使用示例，展示如何使用JSON-RPC客户端调用MCPDroid服务
2. `image_recognition_example.py` - 图像识别示例，演示如何使用图像识别功能
3. `app_test_example.py` - 应用测试示例，演示如何编写简单的应用自动化测试

## 运行示例

确保您已启动MCPDroid服务并连接了Android设备，然后运行：

```bash
# 运行基本使用示例
python basic_usage.py

# 运行图像识别示例
python image_recognition_example.py

# 运行应用测试示例
python app_test_example.py

# 查看应用测试示例的可选参数
python app_test_example.py --help
```

## 注意事项

- 示例代码默认连接到本地的MCPDroid服务 (http://localhost:8000/jsonrpc)
- 请确保已正确安装`requests`库: `pip install requests`
- 图像识别示例需要设备上有明显的界面元素以便识别
- 应用测试示例可能需要根据您的设备屏幕和应用调整坐标 