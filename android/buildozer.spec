[app]
title = 视频去水印
package.name = watermarkremover
package.domain = com.xiake.watermark
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0
requirements = python3,kivy,opencv-python-headless,pillow,android
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_VIDEO,INTERNET
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
fullscreen = 0
orientation = portrait
android.gradle_dependencies = com.android.support:support-compat:28.0.0
p4a.url = https://gitee.com/mirrors/python-for-android.git
p4a.branch = master
android.allow_backup = True
log_level = 2

[buildozer]
warn_on_root = 0
