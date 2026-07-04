[app]

# 应用包名（唯一标识，不要用默认的）
package.name = pk10bet
package.domain = com.whwwyswhw

# 应用名
title = PK10 投注助手

# 应用图标 (可选，需要 .png 文件)
# icon.filename = %(source.dir)s/icon.png

# 版本
version = 4.0
version.code = 4

# 应用主入口文件
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt

# Python 主文件
main_filename = main.py

# Requirements - Kivy + 依赖
requirements = python3,kivy==2.1.0,requests,urllib3,charset-normalizer,certifi,idna

# Kivy 版本
osx.kivy_version = 2.1.0

# Android 权限
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE

# Android 最低 API 级别
android.minapi = 21

# Android 目标 API 级别
android.api = 33
android.ndk = 23b

# Android SDK
android.sdk = 31

# 架构支持 (armeabi-v7a 兼容最广，arm64-v8a 性能好)
android.arch = armeabi-v7a,arm64-v8a

# 编译模式 debug/release
android.release_artifact = aab

# 屏幕方向
orientation = portrait

# 启动画面
# 设为 False 去掉启动闪屏（可选）
presplash.color = 1E3A5F

# 全屏
fullscreen = 0

# Log 级别 (debug/info/warning/error/critical)
log_level = 2

# 允许应用后台运行
android.allow_backup = True

# Gradle 依赖
android.gradle_dependencies = 

# 应用退到后台时行为
android.entrypoint = org.kivy.android.PythonActivity

# 唤醒锁
android.wakelock = False

# 服务
services = 

# 意图过滤器
android.add_activity = 

# ===== Buildozer 自动生成标记 =====
# (c) 会自动填充 build 环境参数
