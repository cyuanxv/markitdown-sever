# OpenRouter API 集成文档

## 概述

OpenRouter API 允许 MarkItDown 应用程序访问多种 AI 模型，包括 GPT-4、Claude 和 Llama 等，以提供更强大的文档处理和转换功能。

## 配置步骤

### 1. 获取 API 密钥

1. 访问 [OpenRouter 官网](https://openrouter.ai/)
2. 注册并创建一个账户
3. 在控制面板中生成 API 密钥

### 2. 设置环境变量

在启动应用程序之前，需要设置以下环境变量：

```bash
export OPENROUTER_API_KEY="your_api_key_here"
```

或者使用提供的启动脚本：

```bash
./start_with_openrouter.sh
```

> **注意**：请确保将 `your_api_key_here` 替换为您实际的 API 密钥。

### 3. 验证配置

启动应用程序后，可以通过以下方式验证 OpenRouter API 是否正确配置：

1. 访问应用程序的健康检查端点：`/api/health`
2. 检查响应中是否包含 `"openrouter_api_status": "available"`

## 使用的模型

MarkItDown 默认使用以下模型：

- **主要模型**：`openai/gpt-4-turbo`
- **备用模型**：`anthropic/claude-3-opus`

## 自定义模型选择

可以通过设置环境变量来自定义使用的模型：

```bash
export OPENROUTER_MODEL="anthropic/claude-3-opus"
```

## 错误处理

常见错误及解决方案：

| 错误代码 | 描述 | 解决方案 |
|---------|------|--------|
| 401 | 未授权 | 检查 API 密钥是否正确设置 |
| 429 | 请求过多 | 减少请求频率或升级账户计划 |
| 500 | 服务器错误 | 稍后重试或联系 OpenRouter 支持 |

## 最佳实践

1. 在生产环境中，始终使用环境变量而非硬编码的 API 密钥
2. 实现请求重试机制以处理临时性错误
3. 监控 API 使用情况以避免超出配额限制

## 相关资源

- [OpenRouter API 文档](https://openrouter.ai/docs)
- [支持的模型列表](https://openrouter.ai/docs#models)
- [价格信息](https://openrouter.ai/pricing)