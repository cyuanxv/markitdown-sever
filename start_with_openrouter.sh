#!/bin/bash

# 设置OpenRouter API环境变量
export OPENROUTER_API_KEY="your_api_key_here"
export OPENROUTER_MODEL="openai/gpt-4-turbo"

# 设置Azure Document Intelligence环境变量
export AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="your_azure_endpoint_here"
export AZURE_API_KEY="your_azure_api_key_here"

# 设置端口
export PORT=5002

# 启动应用
python3 app.py