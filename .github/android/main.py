#!/usr/bin/env python3
"""
视频去水印 - 安卓版 (Kivy)
基于 OpenCV Inpainting
"""

import os
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.slider import Slider
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import platform

# 安卓权限
if platform == 'android':
    from android.permissions import request_permissions, Permission
    request_permissions([
        Permission.READ_EXTERNAL_STORAGE,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.READ_MEDIA_VIDEO,
    ])

import cv2
import numpy as np


class WatermarkProcessor:
    """水印处理核心"""

    @staticmethod
    def remove_inpaint(frame, mask):
        return cv2.inpaint(frame, mask, 7, cv2.INPAINT_TELEA)

    @staticmethod
    def remove_blur(frame, mask, strength=51):
        if strength % 2 == 0:
            strength += 1
        blurred = cv2.GaussianBlur(frame, (strength, strength), 0)
        result = frame.copy()
        result[mask > 0] = blurred[mask > 0]
        return result

    @staticmethod
    def remove_mosaic(frame, mask, block_size=20):
        result = frame.copy()
        # 对mask区域做马赛克
        small = cv2.resize(frame, (frame.shape[1] // block_size, frame.shape[0] // block_size))
        mosaic = cv2.resize(small, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_NEAREST)
        result[mask > 0] = mosaic[mask > 0]
        return result


class VideoWatermarkApp(App):
    """主应用"""

    def build(self):
        self.title = "视频去水印"
        self.selected_video = None
        self.is_processing = False

        # 主布局
        layout = BoxLayout(orientation='vertical', padding=15, spacing=10)

        # 标题
        title = Label(
            text='[b]视频去水印工具[/b]',
            markup=True,
            size_hint_y=None,
            height=50,
            font_size='22sp'
        )
        layout.add_widget(title)

        # 选择视频按钮
        self.btn_select = Button(
            text='📁 选择视频',
            size_hint_y=None,
            height=55,
            background_color=(0.2, 0.6, 1, 1)
        )
        self.btn_select.bind(on_press=self.select_video)
        layout.add_widget(self.btn_select)

        # 视频信息
        self.lbl_info = Label(
            text='未选择视频',
            size_hint_y=None,
            height=40,
            font_size='14sp'
        )
        layout.add_widget(self.lbl_info)

        # 水印区域输入
        layout.add_widget(Label(text='水印区域 (x,y,宽,高):', size_hint_y=None, height=30))

        coord_layout = BoxLayout(size_hint_y=None, height=45, spacing=5)
        self.input_x = self._make_input("X")
        self.input_y = self._make_input("Y")
        self.input_w = self._make_input("宽")
        self.input_h = self._make_input("高")
        coord_layout.add_widget(self.input_x)
        coord_layout.add_widget(self.input_y)
        coord_layout.add_widget(self.input_w)
        coord_layout.add_widget(self.input_h)
        layout.add_widget(coord_layout)

        # 修复模式选择
        layout.add_widget(Label(text='修复模式:', size_hint_y=None, height=30))
        self.spinner_mode = Spinner(
            text='智能填充 (推荐)',
            values=('智能填充 (推荐)', '模糊覆盖', '马赛克'),
            size_hint_y=None,
            height=45
        )
        layout.add_widget(self.spinner_mode)

        # 强度调节
        layout.add_widget(Label(text='修复强度:', size_hint_y=None, height=30))
        self.slider_strength = Slider(min=1, max=100, value=50, size_hint_y=None, height=40)
        self.lbl_strength = Label(text='50', size_hint_y=None, height=25)
        self.slider_strength.bind(value=self._update_strength)
        layout.add_widget(self.slider_strength)
        layout.add_widget(self.lbl_strength)

        # 进度
        self.lbl_progress = Label(
            text='',
            size_hint_y=None,
            height=35,
            font_size='14sp'
        )
        layout.add_widget(self.lbl_progress)

        # 开始处理按钮
        self.btn_process = Button(
            text='🚀 开始处理',
            size_hint_y=None,
            height=60,
            background_color=(0.1, 0.8, 0.3, 1),
            font_size='18sp'
        )
        self.btn_process.bind(on_press=self.start_process)
        layout.add_widget(self.btn_process)

        return layout

    def _make_input(self, hint):
        from kivy.uix.textinput import TextInput
        return TextInput(
            hint_text=hint,
            input_filter='int',
            multiline=False,
            size_hint_x=1,
            height=40,
            font_size='14sp'
        )

    def _update_strength(self, instance, value):
        self.lbl_strength.text = str(int(value))

    def select_video(self, instance):
        """选择视频文件"""
        if platform == 'android':
            # 安卓使用文件选择器
            content = BoxLayout(orientation='vertical')
            fc = FileChooserIconView(
                filters=['*.mp4', '*.avi', '*.mov', '*.mkv', '*.flv', '*.wmv'],
                path='/storage/emulated/0/'
            )
            content.add_widget(fc)

            btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)
            btn_ok = Button(text='确定')
            btn_cancel = Button(text='取消')
            btn_layout.add_widget(btn_ok)
            btn_layout.add_widget(btn_cancel)
            content.add_widget(btn_layout)

            popup = Popup(title='选择视频', content=content, size_hint=(0.9, 0.9))
            btn_ok.bind(on_press=lambda x: self._file_selected(fc.selection, popup))
            btn_cancel.bind(on_press=popup.dismiss)
            popup.open()
        else:
            # 桌面测试用
            from kivy.utils import platform as p
            content = BoxLayout(orientation='vertical')
            fc = FileChooserIconView(
                filters=['*.mp4', '*.avi', '*.mov', '*.mkv', '*.flv', '*.wmv'],
                path=os.path.expanduser('~')
            )
            content.add_widget(fc)

            btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)
            btn_ok = Button(text='确定')
            btn_cancel = Button(text='取消')
            btn_layout.add_widget(btn_ok)
            btn_layout.add_widget(btn_cancel)
            content.add_widget(btn_layout)

            popup = Popup(title='选择视频', content=content, size_hint=(0.9, 0.9))
            btn_ok.bind(on_press=lambda x: self._file_selected(fc.selection, popup))
            btn_cancel.bind(on_press=popup.dismiss)
            popup.open()

    def _file_selected(self, selection, popup):
        if selection:
            self.selected_video = selection[0]
            # 获取视频信息
            cap = cv2.VideoCapture(self.selected_video)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = frames / fps if fps > 0 else 0
                cap.release()

                filename = os.path.basename(self.selected_video)
                self.lbl_info.text = f'{filename}\n{w}x{h} | {fps:.0f}fps | {duration:.0f}秒'
                self.btn_select.text = f'✅ {filename[:20]}...'
            else:
                self.lbl_info.text = '❌ 无法读取视频'
        popup.dismiss()

    def start_process(self, instance):
        """开始处理"""
        if not self.selected_video:
            self._show_msg("请先选择视频！")
            return

        # 获取水印区域
        try:
            x = int(self.input_x.text or 0)
            y = int(self.input_y.text or 0)
            w = int(self.input_w.text or 0)
            h = int(self.input_h.text or 0)
        except ValueError:
            self._show_msg("坐标请输入数字！")
            return

        if w <= 0 or h <= 0:
            self._show_msg("请输入有效的水印区域宽高！")
            return

        # 获取模式
        mode_text = self.spinner_mode.text
        if '智能' in mode_text:
            mode = 'inpaint'
        elif '模糊' in mode_text:
            mode = 'blur'
        else:
            mode = 'mosaic'

        strength = int(self.slider_strength.value)

        # 禁用按钮
        self.btn_process.text = '⏳ 处理中...'
        self.btn_process.disabled = True
        self.is_processing = True

        # 后台处理
        thread = threading.Thread(
            target=self._process_video,
            args=(self.selected_video, (x, y, w, h), mode, strength)
        )
        thread.daemon = True
        thread.start()

    def _process_video(self, video_path, region, mode, strength):
        """后台处理视频"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                Clock.schedule_once(lambda dt: self._show_msg("无法打开视频"), 0)
                return

            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # 输出路径
            base, ext = os.path.splitext(video_path)
            output_path = f"{base}_nwm{ext}"

            # 安卓保存到相册目录
            if platform == 'android':
                output_path = f"/storage/emulated/0/DCIM/Camera/wm_{os.path.basename(video_path)}"

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

            # 创建mask
            mask = np.zeros((height, width), dtype=np.uint8)
            x, y, w, h = region
            pad = 3
            x1, y1 = max(0, x - pad), max(0, y - pad)
            x2, y2 = min(width, x + w + pad), min(height, y + h + pad)
            mask[y1:y2, x1:x2] = 255

            processor = WatermarkProcessor()
            frame_count = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if mode == 'inpaint':
                    result = processor.remove_inpaint(frame, mask)
                elif mode == 'blur':
                    result = processor.remove_blur(frame, mask, strength)
                else:
                    result = processor.remove_mosaic(frame, mask, strength // 5 + 5)

                out.write(result)
                frame_count += 1

                if frame_count % 10 == 0:
                    progress = f"处理中: {frame_count}/{total} ({frame_count*100//total}%)"
                    Clock.schedule_once(lambda dt, p=progress: self._update_progress(p), 0)

            cap.release()
            out.release()

            Clock.schedule_once(lambda dt: self._process_done(output_path), 0)

        except Exception as e:
            Clock.schedule_once(lambda dt: self._show_msg(f"处理失败: {e}"), 0)
        finally:
            Clock.schedule_once(lambda dt: self._reset_button(), 0)

    def _update_progress(self, text):
        self.lbl_progress.text = text

    def _process_done(self, output_path):
        self.lbl_progress.text = f'✅ 完成！'
        self._show_msg(f"处理完成！\n\n保存到:\n{output_path}")

    def _reset_button(self):
        self.btn_process.text = '🚀 开始处理'
        self.btn_process.disabled = False
        self.is_processing = False

    def _show_msg(self, text):
        popup = Popup(
            title='提示',
            content=Label(text=text, text_size=(None, None), halign='center'),
            size_hint=(0.8, 0.4)
        )
        popup.content.bind(size=popup.content.setter('text_size'))
        popup.open()


if __name__ == '__main__':
    VideoWatermarkApp().run()
