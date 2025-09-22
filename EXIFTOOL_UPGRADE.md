# ExifTool 升级指南

## 问题背景

当前项目使用的 ExifTool 版本为 11.20，该版本存在安全漏洞。为了确保项目的安全性，我们需要升级 ExifTool 到 12.24 或更高版本。

## 解决方案

### 方案一：设置环境变量指向新版本

1. 下载并安装 ExifTool 13.36 版本（或更高版本）
2. 设置环境变量 `EXIFTOOL_PATH` 指向新版本的 ExifTool 可执行文件

```bash
export EXIFTOOL_PATH=/path/to/exiftool
```

3. 验证设置是否生效

```bash
$EXIFTOOL_PATH -ver
# 应输出 13.36 或更高版本
```

### 方案二：跳过版本检查

如果暂时无法升级 ExifTool，可以设置环境变量 `SKIP_EXIFTOOL_VERSION_CHECK=true` 来跳过版本检查。

```bash
export SKIP_EXIFTOOL_VERSION_CHECK=true
```

> **注意**：此方案仅作为临时解决方案，不推荐长期使用，因为低版本的 ExifTool 存在安全风险。

## 永久设置

要永久设置环境变量，可以将上述命令添加到 `~/.bashrc`、`~/.zshrc` 或其他 shell 配置文件中。