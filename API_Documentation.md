# MarkItDown API 接口文档

## 基本信息

- **基础URL**: `/api`
- **服务描述**: MarkItDown是一个文件转换服务，支持将各种格式的文件转换为Markdown格式
- **Swagger文档**: 访问`/docs`端点获取完整的交互式API文档

## 支持的文件格式

- Microsoft Word (.docx)
- Microsoft PowerPoint (.pptx)
- PDF (.pdf)
- HTML (.html)
- 纯文本 (.txt)
- URL (网页内容)

## API端点

### 1. 健康检查

- **端点**: `GET /api/health`
- **描述**: 检查API服务是否正常运行
- **响应**: 
  ```json
  {
    "status": "ok"
  }
  ```

### 2. 文件上传转换

- **端点**: `POST /api/convert/file`
- **描述**: 上传文件并转换为Markdown格式
- **请求参数**:
  - `file`: 要转换的文件（必需，表单数据）
  - `options`: 转换选项（可选，JSON字符串）
- **响应**:
  ```json
  {
    "file_id": "uuid-string",
    "status": "success",
    "download_url": "/api/download/uuid-string"
  }
  ```
- **错误响应**:
  ```json
  {
    "status": "error",
    "message": "错误描述"
  }
  ```

### 3. URL转换

- **端点**: `POST /api/convert/url`
- **描述**: 从URL获取内容并转换为Markdown
- **请求参数**:
  ```json
  {
    "url": "https://example.com/page.html",
    "options": {}
  }
  ```
- **响应**:
  ```json
  {
    "file_id": "uuid-string",
    "status": "success",
    "download_url": "/api/download/uuid-string"
  }
  ```
- **错误响应**:
  ```json
  {
    "status": "error",
    "message": "错误描述"
  }
  ```

### 4. 文件下载

- **端点**: `GET /api/download/<file_id>`
- **描述**: 下载已转换的Markdown文件
- **参数**:
  - `file_id`: 文件标识符（路径参数）
- **响应**: Markdown文件内容（Content-Type: text/markdown）
- **错误响应**:
  ```json
  {
    "status": "error",
    "message": "文件不存在或已过期"
  }
  ```

### 5. 文件列表

- **端点**: `GET /api/files`
- **描述**: 获取所有可用的已转换文件列表
- **响应**:
  ```json
  {
    "files": [
      {
        "file_id": "uuid-string",
        "original_name": "document.docx",
        "created_at": "2023-01-01T12:00:00Z",
        "download_url": "/api/download/uuid-string"
      }
    ]
  }
  ```

## 使用说明

1. **文件上传转换流程**:
   - 使用`POST /api/convert/file`上传文件
   - 从响应中获取`file_id`和`download_url`
   - 使用`GET /api/download/<file_id>`下载转换后的Markdown文件

2. **URL转换流程**:
   - 使用`POST /api/convert/url`提交URL
   - 从响应中获取`file_id`和`download_url`
   - 使用`GET /api/download/<file_id>`下载转换后的Markdown文件

## 错误处理

- **400 Bad Request**: 请求参数无效或缺失
- **404 Not Found**: 请求的资源不存在
- **413 Payload Too Large**: 上传的文件超过大小限制
- **415 Unsupported Media Type**: 不支持的文件类型
- **500 Internal Server Error**: 服务器内部错误

## 注意事项

- 文件会在一段时间后自动过期并被删除
- 文件大小限制为10MB
- 所有API响应均为JSON格式，除非特别说明