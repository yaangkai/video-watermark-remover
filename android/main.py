"""
视频去水印工具 - Kivy Android 版（修复权限问题）
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

# Android 权限处理
if platform == 'android':
    from android.permissions import request_permissions, Permission
    request_permissions([
        Permission.READ_EXTERNAL_STORAGE,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.READ_MEDIA_VIDEO,
    ])


class WatermarkRemoverApp(App):
    def build(self):
        self.title = '视频去水印'
        self.selected_file = None
        
        # 主布局
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        # 标题
        title = Label(
            text='视频去水印工具',
            font_size=24,
            size_hint_y=0.1,
            bold=True
        )
        layout.add_widget(title)
        
        # 状态标签
        self.status_label = Label(
            text='请选择视频文件',
            font_size=16,
            size_hint_y=0.1
        )
        layout.add_widget(self.status_label)
        
        # 选择文件按钮
        select_btn = Button(
            text='选择视频文件',
            size_hint_y=0.1,
            background_color=(0.2, 0.6, 1, 1)
        )
        select_btn.bind(on_press=self.show_file_chooser)
        layout.add_widget(select_btn)
        
        # 文件路径显示
        self.file_label = Label(
            text='未选择文件',
            font_size=14,
            size_hint_y=0.1,
            color=(0.5, 0.5, 0.5, 1)
        )
        layout.add_widget(self.file_label)
        
        # 进度条
        self.progress = ProgressBar(
            max=100,
            size_hint_y=0.05,
            value=0
        )
        layout.add_widget(self.progress)
        
        # 处理按钮
        self.process_btn = Button(
            text='开始处理',
            size_hint_y=0.1,
            background_color=(0.2, 0.8, 0.2, 1),
            disabled=True
        )
        self.process_btn.bind(on_press=self.process_video)
        layout.add_widget(self.process_btn)
        
        # 底部说明
        footer = Label(
            text='提示：处理后的视频将保存在原文件同目录',
            font_size=12,
            size_hint_y=0.1,
            color=(0.6, 0.6, 0.6, 1)
        )
        layout.add_widget(footer)
        
        return layout
    
    def show_file_chooser(self, instance):
        """显示文件选择器"""
        content = BoxLayout(orientation='vertical')
        
        # 根据平台选择默认路径
        if platform == 'android':
            default_path = '/storage/emulated/0/DCIM'
        else:
            default_path = os.path.expanduser('~')
        
        # 文件选择器
        file_chooser = FileChooserListView(
            filters=['*.mp4', '*.avi', '*.mov', '*.mkv', '*.flv', '*.wmv'],
            path=default_path
        )
        content.add_widget(file_chooser)
        
        # 按钮布局
        btn_layout = BoxLayout(size_hint_y=0.1, spacing=10)
        
        cancel_btn = Button(text='取消')
        select_btn = Button(text='选择', background_color=(0.2, 0.8, 0.2, 1))
        
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(select_btn)
        content.add_widget(btn_layout)
        
        # 弹窗
        popup = Popup(
            title='选择视频文件',
            content=content,
            size_hint=(0.9, 0.9)
        )
        
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
        """处理视频"""
        if not self.selected_file:
            return
        
        self.process_btn.disabled = True
        self.status_label.text = '正在处理...'
        self.progress.value = 0
        
        # 在后台线程处理
        thread = threading.Thread(target=self._process_in_background)
        thread.daemon = True
        thread.start()
    
    def _process_in_background(self):
        """后台处理视频"""
        try:
            import cv2
            
            # 读取视频
            cap = cv2.VideoCapture(self.selected_file)
            if not cap.isOpened():
                Clock.schedule_once(lambda dt: self._update_status('无法打开视频文件'), 0)
                return
            
            # 获取视频信息
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 输出文件路径
            base, ext = os.path.splitext(self.selected_file)
            output_path = f"{base}_no_watermark{ext}"
            
            # 创建视频写入器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 简单处理：裁剪掉右下角水印区域
                h, w = frame.shape[:2]
                watermark_h = int(h * 0.1)
                watermark_w = int(w * 0.1)
                
                # 用周围像素填充水印区域
                if watermark_h > 0 and watermark_w > 0:
                    source_region = frame[h-watermark_h-watermark_h:h-watermark_h, w-watermark_w:w]
                    frame[h-watermark_h:h, w-watermark_w:w] = source_region
                
                out.write(frame)
                frame_count += 1
                
                # 更新进度
                progress = int((frame_count / total_frames) * 100)
                Clock.schedule_once(lambda dt, p=progress: self._update_progress(p), 0)
            
            # 释放资源
            cap.release()
            out.release()
            
            Clock.schedule_once(lambda dt: self._update_status(f'处理完成！保存到: {output_path}'), 0)
            Clock.schedule_once(lambda dt: self._update_progress(100), 0)
            
        except Exception as e:
            Clock.schedule_once(lambda dt: self._update_status(f'处理失败: {str(e)}'), 0)
        finally:
            Clock.schedule_once(lambda dt: self._enable_button(), 0)
    
    def _update_status(self, text):
        """更新状态标签"""
        self.status_label.text = text
    
    def _update_progress(self, value):
        """更新进度条"""
        self.progress.value = value
    
    def _enable_button(self):
        """启用处理按钮"""
        self.process_btn.disabled = False


if __name__ == '__main__':
    WatermarkRemoverApp().run()
