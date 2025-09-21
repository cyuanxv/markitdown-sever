#!/usr/bin/env python3
"""
MarkItDown 后端服务
提供文件上传、URL转换为Markdown的服务，支持30分钟自动文件清理
"""

import os
import io
import uuid
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
import requests
from urllib.parse import urlparse
import mimetypes

from flask import Flask, request, jsonify, send_file, abort, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler
from flasgger import Swagger, swag_from

from markitdown import MarkItDown
from flask import after_this_request

# 创建Flask应用
app = Flask(__name__)

# 配置CORS，支持文件上传
CORS(app, 
     origins=["*"],  # 允许所有域名
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "Accept", "Accept-Encoding", "Accept-Language", "Cache-Control", "Connection", "Host", "Origin", "Referer", "User-Agent", "X-Requested-With"],
     supports_credentials=True,
     max_age=86400  # 预检请求缓存时间
)

# 配置Swagger
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs",
    "swagger_ui_config": {
        "supportedSubmitMethods": ["get", "post", "put", "delete", "patch"],
        "validatorUrl": None
    }
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "MarkItDown API",
        "description": "文件转换为 Markdown 格式的 API 服务，支持文件上传和 URL 转换，文件30分钟后自动过期删除",
        "version": "1.0.0",
        "contact": {
            "name": "MarkItDown Service",
            "url": "https://github.com/microsoft/markitdown"
        }
    },
    "basePath": "/",
    "schemes": ["https", "http"],
    "consumes": ["application/json", "multipart/form-data"],
    "produces": ["application/json", "text/markdown"]
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# 配置
UPLOAD_FOLDER = 'uploads'
DOWNLOAD_FOLDER = 'public'
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
CLEANUP_INTERVAL_MINUTES = 5  # 每5分钟检查一次过期文件
FILE_EXPIRY_MINUTES = 30  # 文件30分钟后过期

# 确保目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# 初始化MarkItDown
md_converter = MarkItDown()

# 文件记录：存储文件信息和创建时间
file_records = {}
file_lock = threading.Lock()

def is_allowed_file(filename):
    """检查文件类型是否被支持"""
    # MarkItDown支持的文件扩展名
    allowed_extensions = {
        'pdf', 'docx', 'doc', 'pptx', 'ppt', 'xlsx', 'xls', 
        'html', 'htm', 'csv', 'json', 'xml', 'txt', 'md',
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff',
        'mp3', 'wav', 'm4a', 'zip', 'epub', 'msg', 'rtf'
    }
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def download_file_from_url(url, max_size=MAX_FILE_SIZE):
    """从URL下载文件"""
    try:
        # 发送HEAD请求检查文件大小
        head_response = requests.head(url, timeout=10)
        content_length = head_response.headers.get('content-length')
        
        if content_length and int(content_length) > max_size:
            raise ValueError(f"文件太大: {content_length} 字节")
        
        # 下载文件
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        
        # 检查实际下载大小
        content = io.BytesIO()
        downloaded_size = 0
        
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                downloaded_size += len(chunk)
                if downloaded_size > max_size:
                    raise ValueError(f"文件下载过程中超出大小限制")
                content.write(chunk)
        
        content.seek(0)
        
        # 尝试从响应头获取文件名
        filename = None
        if 'content-disposition' in response.headers:
            cd = response.headers['content-disposition']
            if 'filename=' in cd:
                filename = cd.split('filename=')[1].strip('"\'')
        
        # 如果没有文件名，从URL推断
        if not filename:
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path) or 'downloaded_file'
            
            # 如果没有扩展名，尝试从Content-Type推断
            if '.' not in filename:
                content_type = response.headers.get('content-type', '')
                ext = mimetypes.guess_extension(content_type.split(';')[0])
                if ext:
                    filename += ext
        
        return content, filename
        
    except Exception as e:
        raise Exception(f"下载文件失败: {str(e)}")

def convert_to_markdown(file_stream, filename):
    """将文件转换为Markdown"""
    try:
        # 确保文件流是二进制模式
        if hasattr(file_stream, 'mode') and 'b' not in file_stream.mode:
            # 如果不是二进制模式，重新读取为字节
            content = file_stream.read()
            if isinstance(content, str):
                content = content.encode('utf-8')
            file_stream = io.BytesIO(content)
        elif not hasattr(file_stream, 'read'):
            # 如果不是文件对象，转换为BytesIO
            if isinstance(file_stream, str):
                file_stream = io.BytesIO(file_stream.encode('utf-8'))
            elif isinstance(file_stream, bytes):
                file_stream = io.BytesIO(file_stream)
        
        # 使用MarkItDown进行转换
        result = md_converter.convert_stream(file_stream, file_extension=Path(filename).suffix)
        return result.text_content
        
    except KeyError as e:
        if 'w:ilvl' in str(e):
            # 特殊处理docx文件的w:ilvl错误（列表缩进级别问题）
            error_msg = (
                f"DOCX文件转换失败: 文档包含复杂的列表结构，存在格式问题。\n"
                f"建议解决方案:\n"
                f"1. 在Word中打开文档，重新格式化列表和缩进\n"
                f"2. 另存为新的docx文件后重试\n"
                f"3. 或将文档另存为PDF格式后转换\n"
                f"技术详情: {str(e)}"
            )
        else:
            error_msg = f"文件解析错误: {str(e)}"
        raise Exception(error_msg)
        
    except Exception as e:
        # 检查是否是docx相关的特殊错误
        error_str = str(e).lower()
        if 'docx' in error_str and any(keyword in error_str for keyword in ['list', 'ilvl', 'numbering']):
            error_msg = (
                f"DOCX文件转换失败: 文档格式存在兼容性问题。\n"
                f"建议解决方案:\n"
                f"1. 尝试在Word中重新保存文档\n"
                f"2. 简化文档中的列表和表格格式\n"
                f"3. 或转换为PDF格式后重试\n"
                f"错误详情: {str(e)}"
            )
        else:
            error_msg = f"转换失败: {str(e)}"
        
        raise Exception(error_msg)

def save_markdown_file(content, original_filename):
    """保存Markdown文件并返回下载URL"""
    # 生成唯一的文件ID
    file_id = str(uuid.uuid4())
    
    # 创建Markdown文件名
    base_name = Path(original_filename).stem
    md_filename = f"{base_name}_{file_id}.md"
    md_filepath = os.path.join(DOWNLOAD_FOLDER, md_filename)
    
    # 保存文件
    with open(md_filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 记录文件信息
    with file_lock:
        file_records[file_id] = {
            'filename': md_filename,
            'filepath': md_filepath,
            'created_at': datetime.now(),
            'original_filename': original_filename
        }
    
    return file_id, md_filename

def cleanup_expired_files():
    """清理过期文件"""
    current_time = datetime.now()
    expired_files = []
    
    with file_lock:
        for file_id, record in list(file_records.items()):
            if current_time - record['created_at'] > timedelta(minutes=FILE_EXPIRY_MINUTES):
                expired_files.append((file_id, record))
        
        # 删除过期文件记录和实际文件
        for file_id, record in expired_files:
            try:
                if os.path.exists(record['filepath']):
                    os.remove(record['filepath'])
                del file_records[file_id]
                print(f"已删除过期文件: {record['filename']}")
            except Exception as e:
                print(f"删除文件失败 {record['filename']}: {e}")

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点
    ---
    tags:
      - 健康检查
    summary: 检查服务状态
    description: 返回服务的健康状态信息
    responses:
      200:
        description: 服务正常运行
        schema:
          type: object
          properties:
            status:
              type: string
              example: "healthy"
            service:
              type: string
              example: "MarkItDown API"
            version:
              type: string
              example: "1.0.0"
            timestamp:
              type: string
              format: date-time
              example: "2025-09-21T09:30:00.123456"
    """
    return jsonify({
        'status': 'healthy',
        'service': 'MarkItDown API',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/convert/file', methods=['POST', 'OPTIONS'])
def convert_file():
    """文件上传转换端点
    ---
    tags:
      - 文件转换
    summary: 上传文件并转换为 Markdown
    description: |
      上传各种格式的文件（PDF, DOCX, PPTX, XLSX, 图片, 音频等）并转换为 Markdown 格式。
      转换后的文件会在30分钟后自动删除。
      
      支持的文件格式：
      - 文档：PDF, Word(DOCX/DOC), PowerPoint(PPTX/PPT), Excel(XLSX/XLS)
      - 网页：HTML, HTM
      - 数据：CSV, JSON, XML
      - 图片：JPG, PNG, GIF, BMP, TIFF
      - 音频：MP3, WAV, M4A
      - 其他：ZIP, EPUB, MSG, RTF, TXT, MD
    consumes:
      - multipart/form-data
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: 要转换的文件（最大50MB）
    responses:
      200:
        description: 转换成功
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            file_id:
              type: string
              example: "bcf5d839-97e2-4036-8ccd-902bfa3e8205"
            download_url:
              type: string
              example: "/api/download/bcf5d839-97e2-4036-8ccd-902bfa3e8205"
            filename:
              type: string
              example: "document_bcf5d839-97e2-4036-8ccd-902bfa3e8205.md"
            original_filename:
              type: string
              example: "document.pdf"
            expires_at:
              type: string
              format: date-time
              example: "2025-09-21T10:30:00.123456"
      400:
        description: 请求错误（文件格式不支持、文件过大等）
        schema:
          type: object
          properties:
            error:
              type: string
              example: "不支持的文件类型"
      500:
        description: 服务器错误（转换失败等）
        schema:
          type: object
          properties:
            error:
              type: string
              example: "转换失败: 具体错误信息"
    """
    # 处理 OPTIONS 预检请求
    if request.method == 'OPTIONS':
        response = jsonify()
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
        
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({'error': '没有文件上传'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        # 检查文件类型
        if not is_allowed_file(file.filename):
            return jsonify({'error': '不支持的文件类型'}), 400
        
        # 检查文件大小
        file.seek(0, 2)  # 移动到文件末尾
        file_size = file.tell()
        file.seek(0)  # 回到文件开头
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': f'文件太大，最大支持 {MAX_FILE_SIZE//1024//1024}MB'}), 400
        
        # 读取文件内容并转换
        file_content = file.read()
        file_stream = io.BytesIO(file_content)
        markdown_content = convert_to_markdown(file_stream, file.filename)
        
        # 保存Markdown文件
        file_id, md_filename = save_markdown_file(markdown_content, file.filename)
        
        return jsonify({
            'success': True,
            'file_id': file_id,
            'download_url': f'/api/download/{file_id}',
            'filename': md_filename,
            'original_filename': file.filename,
            'expires_at': (datetime.now() + timedelta(minutes=FILE_EXPIRY_MINUTES)).isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/convert/url', methods=['POST', 'OPTIONS'])
def convert_url():
    """URL转换端点
    ---
    tags:
      - 文件转换
    summary: 通过 URL 下载文件并转换为 Markdown
    description: |
      从指定 URL 下载文件并转换为 Markdown 格式。
      支持的文件类型与文件上传接口相同。
      转换后的文件会在30分钟后自动删除。
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - url
          properties:
            url:
              type: string
              format: uri
              description: 要下载和转换的文件URL
              example: "https://example.com/document.pdf"
    responses:
      200:
        description: 转换成功
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            file_id:
              type: string
              example: "b8da8278-dd4a-4631-af13-421622c65432"
            download_url:
              type: string
              example: "/api/download/b8da8278-dd4a-4631-af13-421622c65432"
            filename:
              type: string
              example: "document_b8da8278-dd4a-4631-af13-421622c65432.md"
            original_filename:
              type: string
              example: "document.pdf"
            source_url:
              type: string
              example: "https://example.com/document.pdf"
            expires_at:
              type: string
              format: date-time
              example: "2025-09-21T10:30:00.123456"
      400:
        description: 请求错误（URL无效、文件格式不支持等）
        schema:
          type: object
          properties:
            error:
              type: string
              example: "需要提供URL"
      500:
        description: 服务器错误（下载失败、转换失败等）
        schema:
          type: object
          properties:
            error:
              type: string
              example: "下载文件失败: 具体错误信息"
    """
    # 处理 OPTIONS 预检请求
    if request.method == 'OPTIONS':
        response = jsonify()
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
        
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': '需要提供URL'}), 400
        
        url = data['url'].strip()
        if not url:
            return jsonify({'error': 'URL不能为空'}), 400
        
        # 下载文件
        file_stream, filename = download_file_from_url(url)
        
        # 检查文件类型
        if not is_allowed_file(filename):
            return jsonify({'error': f'不支持的文件类型: {filename}'}), 400
        
        # 转换文件
        markdown_content = convert_to_markdown(file_stream, filename)
        
        # 保存Markdown文件
        file_id, md_filename = save_markdown_file(markdown_content, filename)
        
        return jsonify({
            'success': True,
            'file_id': file_id,
            'download_url': f'/api/download/{file_id}',
            'filename': md_filename,
            'original_filename': filename,
            'source_url': url,
            'expires_at': (datetime.now() + timedelta(minutes=FILE_EXPIRY_MINUTES)).isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<file_id>', methods=['GET'])
def download_file(file_id):
    """文件下载端点
    ---
    tags:
      - 文件下载
    summary: 下载转换后的 Markdown 文件
    description: |
      根据文件ID下载对应的 Markdown 文件。
      文件在创建30分钟后会自动过期并删除。
    parameters:
      - name: file_id
        in: path
        type: string
        required: true
        description: 文件唯一标识符
        example: "bcf5d839-97e2-4036-8ccd-902bfa3e8205"
    produces:
      - text/markdown
    responses:
      200:
        description: 文件下载成功
        headers:
          Content-Disposition:
            type: string
            description: attachment; filename="filename.md"
          Content-Type:
            type: string
            description: text/markdown
        schema:
          type: string
          format: binary
          description: Markdown 文件内容
      404:
        description: 文件不存在或已过期
        schema:
          type: object
          properties:
            message:
              type: string
              example: "文件不存在或已过期"
    """
    with file_lock:
        if file_id not in file_records:
            abort(404, description="文件不存在或已过期")
        
        record = file_records[file_id]
        
        # 检查文件是否过期
        if datetime.now() - record['created_at'] > timedelta(minutes=FILE_EXPIRY_MINUTES):
            # 清理过期文件
            try:
                if os.path.exists(record['filepath']):
                    os.remove(record['filepath'])
                del file_records[file_id]
            except:
                pass
            abort(404, description="文件已过期")
        
        # 检查文件是否存在
        if not os.path.exists(record['filepath']):
            del file_records[file_id]
            abort(404, description="文件不存在")
        
        # 返回文件
        return send_file(
            record['filepath'],
            as_attachment=True,
            download_name=record['filename'],
            mimetype='text/markdown'
        )

@app.route('/api/files', methods=['GET'])
def list_files():
    """列出所有可用文件
    ---
    tags:
      - 文件管理
    summary: 获取所有可用文件列表
    description: |
      返回当前所有可用的转换文件列表，包括文件信息和剩余有效时间。
      只显示未过期的文件。
    responses:
      200:
        description: 文件列表获取成功
        schema:
          type: object
          properties:
            files:
              type: array
              items:
                type: object
                properties:
                  file_id:
                    type: string
                    description: 文件唯一标识符
                    example: "bcf5d839-97e2-4036-8ccd-902bfa3e8205"
                  filename:
                    type: string
                    description: 转换后的文件名
                    example: "document_bcf5d839-97e2-4036-8ccd-902bfa3e8205.md"
                  original_filename:
                    type: string
                    description: 原始文件名
                    example: "document.pdf"
                  created_at:
                    type: string
                    format: date-time
                    description: 文件创建时间
                    example: "2025-09-21T09:30:00.123456"
                  remaining_seconds:
                    type: integer
                    description: 剩余有效时间（秒）
                    example: 1500
                  download_url:
                    type: string
                    description: 下载链接
                    example: "/api/download/bcf5d839-97e2-4036-8ccd-902bfa3e8205"
    """
    with file_lock:
        files = []
        current_time = datetime.now()
        
        for file_id, record in file_records.items():
            remaining_time = FILE_EXPIRY_MINUTES * 60 - (current_time - record['created_at']).total_seconds()
            if remaining_time > 0:
                files.append({
                    'file_id': file_id,
                    'filename': record['filename'],
                    'original_filename': record['original_filename'],
                    'created_at': record['created_at'].isoformat(),
                    'remaining_seconds': int(remaining_time),
                    'download_url': f'/api/download/{file_id}'
                })
        
        return jsonify({'files': files})

@app.route('/')
def index():
    """提供前端页面"""
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    """提供静态文件"""
    return send_from_directory('static', filename)

# 启动定时清理任务
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=cleanup_expired_files,
    trigger='interval',
    minutes=CLEANUP_INTERVAL_MINUTES,
    id='cleanup_files'
)
scheduler.start()

if __name__ == '__main__':
    print("MarkItDown 后端服务正在启动...")
    print(f"文件过期时间: {FILE_EXPIRY_MINUTES} 分钟")
    print(f"最大文件大小: {MAX_FILE_SIZE//1024//1024} MB")
    print("API端点:")
    print("  POST /api/convert/file - 文件上传转换")
    print("  POST /api/convert/url - URL转换")
    print("  GET /api/download/<file_id> - 文件下载")
    print("  GET /api/files - 列出所有文件")
    print("  GET /api/health - 健康检查")
    
    app.run(host='0.0.0.0', port=5000, debug=True)