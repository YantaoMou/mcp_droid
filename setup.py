#!/usr/bin/env python
"""
MCPDroid 安装脚本
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mcp_droid",
    version="1.0.0",
    author="Yantao",
    author_email="mouyantao@baidu.com",
    description="基于MCP协议的Android设备控制服务",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/mcp_droid",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "fastapi>=0.95.0",
        "uvicorn>=0.22.0",
        "pydantic>=2.0.0",
        "pillow>=9.0.0",
    ],
    extras_require={
        "full": [
            "opencv-python>=4.7.0",
            "airtest>=1.2.7",
            "pytesseract>=0.3.10",
        ],
    },
    entry_points={
        "console_scripts": [
            "mcp_droid=main:main",
        ],
    },
) 