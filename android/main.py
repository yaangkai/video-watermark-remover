"""
视频去水印工具 - Kivy Android 版 (v3 - 修复中文乱码)
"""
import os
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
from kivy.utils import platform
from kivy.resources import resource_add_path

# 设置字体路径
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
if os.path.isdir(FONT_DIR):
    resource_add_path(FONT_DIR)

CHINESE_FONT = os.path.join(FONT_DIR, 'ChineseFont.ttf') if os.path.isdir(FONT_DIR) else None

def _font():
    """返回中文字体路径，不存在则用默认"""
    if CHINESE_FONT and os.path.exists(CHINESE_FONT):
        return CHINESE_FONT
    return 'Roboto'

# Android 权限
if platform == 'android':
    from android.permissions import request_permissions, Permission
    request_permissions([
        Permission.READ_EXTERNAL_STORAGE,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.READ_MEDIA_VIDEO,
    ])


def find_ffmpeg():
    """查找 ffmpeg"""
    candidates = ['ffmpeg']
    if platform == 'android':
        candidates += [
            '/data/data/com.xiake.watermark/files/ffmpeg',
            os.path.join(os.path.dirname(__file__), 'ffmpeg'),
        ]
    for cmd in candidates:
        try:
            import subprocess
            subprocess.run([cmd, '-version'], capture_output=True, timeout=5)
            return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


class WatermarkRemoverApp(App):
    def build(self):
        self.title = '视频去水印'
        self.selected_file = None
        self.ffmpeg_cmd = None
        font = _font()

        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)

        title = Label(text='视频去水印工具', font_size=24, size_hint_y=0.1, bold=True, font_name=font)
        layout.add_widget(title)

        self.status_label = Label(text='正在检查环境...', font_size=16, size_hint_y=0.1, font_name=font)
        layout.add_widget(self.status_label)

        select_btn = Button(text='选择视频文件', size_hint_y=0.1, background_color=(0.2, 0.6, 1, 1), font_name=font)
        select_btn.bind(on_press=self.show_file_chooser)
        layout.add_widget(select_btn)

        self.file_label = Label(text='未选择文件', font_size=14, size_hint_y=0.1, color=(0.5, 0.5, 0.5, 1), font_name=font)
        layout.add_widget(self.file_label)

        self.progress = ProgressBar(max=100, size_hint_y=0.05, value=0)
        layout.add_widget(self.progress)

        self.process_btn = Button(text='开始处理', size_hint_y=0.1, background_color=(0.2, 0.8, 0.2, 1), disabled=True, font_name=font)
        self.process_btn.bind(on_press=self.process_video)
        layout.add_widget(self.process_btn)

        footer = Label(text='提示：处理后的视频保存在原文件同目录', font_size=12, size_hint_y=0.1, color=(0.6, 0.6, 0.6, 1), font_name=font)
        layout.add_widget(footer)

        Clock.schedule_once(self._check_ffmpeg, 0.5)
        return layout

    def _check_ffmpeg(self, dt):
        self.ffmpeg_cmd = find_ffmpeg()
        if self.ffmpeg_cmd:
            self.status_label.text = '环境就绪，请选择视频文件'
        else:
            self.status_label.text = '未找到ffmpeg，将使用基础裁剪模式'

    def show_file_chooser(self, instance):
        font = _font()
        content = BoxLayout(orientation='vertical')

        if platform == 'android':
            default_path = '/storage/emulated/0/DCIM'
        else:
            default_path = os.path.expanduser('~')

        file_chooser = FileChooserListView(
            filters=['*.mp4', '*.avi', '*.mov', '*.mkv', '*.flv', '*.wmv'],
            path=default_path
        )
        content.add_widget(file_chooser)

        btn_layout = BoxLayout(size_hint_y=0.1, spacing=10)
        cancel_btn = Button(text='取消', font_name=font)
        select_btn = Button(text='选择', background_color=(0.2, 0.8, 0.2, 1), font_name=font)
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(select_btn)
        content.add_widget(btn_layout)

        popup = Popup(title='选择视频文件', content=content, size_hint=(0.9, 0.9), title_font=font)

        def on_select(instance):
            if file_chooser.selection:
                self.selected_file = file_chooser.selection[0]
                self.file_label.text = f'已选择: {os.path.basename(self.selected_file)}'
                self.file_label.color = (0.2, 0.8, 0.2, 1)
                self.process_btn.disabled = False
                self.status_label.text = '点击"开始处理"按钮'
            popup.dismiss()

        def on_cancel(instance):
            popup.dismiss()

        select_btn.bind(on_press=on_select)
        cancel_btn.bind(on_press=on_cancel)
        popup.open()

    def process_video(self, instance):
        if not self.selected_file:
            return
        self.process_btn.disabled = True
        self.status_label.text = '正在处理...'
        self.progress.value = 0
        thread = threading.Thread(target=self._process_in_background, daemon=True)
        thread.start()

    def _process_in_background(self):
        try:
            base, ext = os.path.splitext(self.selected_file)
            output_path = f"{base}_no_watermark{ext}"

            if self.ffmpeg_cmd:
                self._process_with_ffmpeg(output_path)
            else:
                self._process_basic_copy(output_path)
        except Exception as e:
            Clock.schedule_once(lambda dt: self._update_status(f'处理失败: {str(e)}'), 0)
        finally:
            Clock.schedule_once(lambda dt: self._enable_button(), 0)

    def _process_with_ffmpeg(self, output_path):
        import subprocess
        Clock.schedule_once(lambda dt: self._update_status('正在用ffmpeg处理...'), 0)

        cmd = [
            self.ffmpeg_cmd, '-y',
            '-i', self.selected_file,
            '-vf', 'crop=iw*0.9:ih*0.9:0:0',
            '-c:a', 'copy',
            output_path
        ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        _, stderr = process.communicate(timeout=600)

        if process.returncode == 0:
            Clock.schedule_once(lambda dt: self._update_status(f'处理完成！保存到: {os.path.basename(output_path)}'), 0)
            Clock.schedule_once(lambda dt: self._update_progress(100), 0)
        else:
            Clock.schedule_once(lambda dt: self._update_status('ffmpeg处理失败，回退到基础模式...'), 0)
            self._process_basic_copy(output_path)

    def _process_basic_copy(self, output_path):
        import shutil
        Clock.schedule_once(lambda dt: self._update_status('基础模式：直接复制视频...'), 0)
        shutil.copy2(self.selected_file, output_path)
        Clock.schedule_once(lambda dt: self._update_progress(100), 0)
        Clock.schedule_once(lambda dt: self._update_status(f'已复制到: {os.path.basename(output_path)}\n基础模式不处理水印，请安装ffmpeg后重试'), 0)

    def _update_status(self, text):
        self.status_label.text = text

    def _update_progress(self, value):
        self.progress.value = value

    def _enable_button(self):
        self.process_btn.disabled = False


if __name__ == '__main__':
    WatermarkRemoverApp().run()
