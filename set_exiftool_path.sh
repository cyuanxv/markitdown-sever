#!/bin/bash

# 设置ExifTool路径环境变量
export EXIFTOOL_PATH=/usr/local/bin/exiftool

# 验证设置是否生效
echo "当前ExifTool版本: $($EXIFTOOL_PATH -ver)"

# 提示如何永久设置
echo "\n要永久设置此环境变量，请将以下行添加到您的~/.bashrc或~/.zshrc文件中："
echo "export EXIFTOOL_PATH=/usr/local/bin/exiftool"