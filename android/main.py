"""
视频去水印工具 v5.0 - 融合新凌印架构重构
支持：抖音/快手/B站/小红书等短视频平台链接解析 + 本地视频去水印
"""
import os
import re
import json
import time
import shutil
import threading
from urllib.parse import urlparse, parse_qs, unquote

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.clock import Clock
from kivy.utils import platform
from kivy.resources import resource_add_path
from kivy.core.text import LabelBase
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage

# ============ 字体设置 ============
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
FONT_FILE = os.path.join(FONT_DIR, 'ChineseFont.ttf')
FONT_NAME = 'ChineseFont'

if os.path.exists(FONT_FILE):
    resource_add_path(FONT_DIR)
    LabelBase.register(name=FONT_NAME, fn_regular=FONT_FILE)
    LabelBase.default_font = FONT_NAME
else:
    FONT_NAME = 'Roboto'

# ============ Android 权限 ============
if platform == 'android':
    from android.permissions import request_permissions, Permission
    request_permissions([
        Permission.READ_EXTERNAL_STORAGE,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.READ_MEDIA_VIDEO,
    ])

# ============ 短视频解析 API ============
# 免费公共解析接口（多个备选）
PARSE_APIS = [
    {
        "name": "解析接口1",
        "url": "https://api.r10086.com/video/api.php",
        "method": "GET",
        "param": "url",
    },
    {
        "name": "解析接口2",
        "url": "https://api.douyin.wtf/api?url=",
        "method": "GET",
        "param": "url",
    },
    {
        "name": "解析接口3",
        "url": "https://www.yemu.xyz/api/video/parse",
        "method": "POST",
        "param": "url",
    },
]

# ============ URL 提取正则 ============
URL_PATTERN = re.compile(
    r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    r'(?::\d+)?'
    r'(?:/(?:[-\w._~:/?#\[\]@!$&\'()*+,;=%])*)?'
)

# 支持的平台
PLATFORM_PATTERNS = {
    'douyin': re.compile(r'(douyin\.com|iesdouyin\.com|v\.douyin\.com)'),
    'kuaishou': re.compile(r'(kuaishou\.com|gifshow\.com|chenzhongtech\.com)'),
    'bilibili': re.compile(r'(bilibili\.com|b23\.tv)'),
    'xiaohongshu': re.compile(r'(xiaohongshu\.com|xhslink\.com)'),
    'weibo': re.compile(r'(weibo\.com|weibo\.cn)'),
    'pipix': re.compile(r'pipix\.com'),
    'doupai': re.compile(r'doupai\.cc'),
    'huoshan': re.compile(r'(huoshan\.com|ishortv\.imito\.mx)'),
    'zuiyou': re.compile(r'zuiyou\.com'),
    'vue': re.compile(r'vuevideo\.net'),
}


def extract_urls(text):
    """从文本中提取所有 URL"""
    return URL_PATTERN.findall(text)


def detect_platform(url):
    """检测 URL 所属平台"""
    for platform_name, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform_name
    return 'unknown'


class ParseResult:
    """解析结果"""
    def __init__(self):
        self.success = False
        self.video_url = ''
        self.poster_url = ''
        self.title = ''
        self.author = ''
        self.platform = ''
        self.error_msg = ''


class VideoParser:
    """视频链接解析器（融合新凌印的多平台解析架构）"""

    def __init__(self):
        self.current_api = 0

    def parse_video_link(self, url):
        """解析视频链接，返回无水印视频 URL"""
        result = ParseResult()
        result.platform = detect_platform(url)

        # 尝试多个 API 接口
        for i, api in enumerate(PARSE_APIS):
            try:
                result = self._try_parse(url, api)
                if result.success:
                    return result
            except Exception as e:
                continue

        result.error_msg = "所有解析接口均失败，请检查链接是否有效"
        return result

    def _try_parse(self, url, api):
        """尝试单个解析接口"""
        import urllib.request
        import urllib.parse

        result = ParseResult()

        if api['method'] == 'GET':
            request_url = api['url'] + '?' + api['param'] + '=' + urllib.parse.quote(url)
            req = urllib.request.Request(request_url, headers={
                'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        else:
            post_data = json.dumps({api['param']: url}).encode('utf-8')
            req = urllib.request.Request(api['url'], data=post_data, headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))

        # 解析返回数据（不同接口格式不同）
        result = self._normalize_response(data, url)
        return result

    def _normalize_response(self, data, original_url):
        """统一不同 API 的返回格式"""
        result = ParseResult()
        result.platform = detect_platform(original_url)

        # 尝试多种返回格式
        video_url = (
            data.get('video_url') or
            data.get('videoUrl') or
            data.get('url') or
            data.get('data', {}).get('video_url') or
            data.get('data', {}).get('videoUrl') or
            data.get('data', {}).get('url') or
            data.get('data', {}).get('video', {}).get('url') or
            data.get('result', {}).get('video_url') or
            ''
        )

        poster_url = (
            data.get('poster') or
            data.get('cover') or
            data.get('thumbnail') or
            data.get('data', {}).get('poster') or
            data.get('data', {}).get('cover') or
            data.get('data', {}).get('thumbnail') or
            ''
        )

        title = (
            data.get('title') or
            data.get('desc') or
            data.get('data', {}).get('title') or
            data.get('data', {}).get('desc') or
            ''
        )

        if video_url:
            result.success = True
            result.video_url = video_url
            result.poster_url = poster_url
            result.title = title
        else:
            result.error_msg = data.get('msg') or data.get('message') or '解析失败'

        return result

    def batch_parse(self, urls, progress_callback=None):
        """批量解析（参考新凌印的批量处理架构）"""
        results = []
        for i, url in enumerate(urls):
            if progress_callback:
                progress_callback(i + 1, len(urls), int((i + 1) / len(urls) * 100))
            result = self.parse_video_link(url)
            results.append(result)
            time.sleep(0.5)  # 避免请求过快
        return results


class VideoDownloader:
    """视频下载器"""

    @staticmethod
    def download(url, save_dir, filename=None):
        """下载视频到本地"""
        import urllib.request

        if not filename:
            parsed = urlparse(url)
            path = unquote(parsed.path)
            filename = os.path.basename(path)
            if not filename or '.' not in filename:
                filename = f"video_{int(time.time())}.mp4"

        save_path = os.path.join(save_dir, filename)
        urllib.request.urlretrieve(url, save_path)
        return save_path


class WatermarkRemoverApp(App):
    def build(self):
        self.title = '视频去水印 v5.0'
        self.parser = VideoParser()
        self.downloader = VideoDownloader()
        self.selected_file = None

        # 主布局
        layout = BoxLayout(orientation='vertical', padding=10, spacing=5)

        # 标题
        title = Label(text='视频去水印 v5.0', font_size=22, size_hint_y=0.08, bold=True, font_name=FONT_NAME)
        layout.add_widget(title)

        # Tab 面板
        self.tabs = TabbedPanel(do_default_tab=False, size_hint_y=0.84)

        # Tab 1: 链接解析（新凌印核心功能）
        tab1 = TabbedPanelItem(text='链接解析', font_name=FONT_NAME)
        tab1.content = self._build_parse_tab()
        self.tabs.add_widget(tab1)

        # Tab 2: 本地去水印
        tab2 = TabbedPanelItem(text='本地去水印', font_name=FONT_NAME)
        tab2.content = self._build_local_tab()
        self.tabs.add_widget(tab2)

        # Tab 3: 批量处理
        tab3 = TabbedPanelItem(text='批量处理', font_name=FONT_NAME)
        tab3.content = self._build_batch_tab()
        self.tabs.add_widget(tab3)

        layout.add_widget(self.tabs)
        return layout

    def _build_parse_tab(self):
        """链接解析 Tab（核心功能，参考新凌印）"""
        layout = BoxLayout(orientation='vertical', padding=10, spacing=8)

        # 输入区域
        layout.add_widget(Label(text='粘贴视频分享链接：', font_size=14, size_hint_y=0.06, font_name=FONT_NAME))

        self.url_input = TextInput(
            hint_text='请输入分享链接...',
            multiline=True,
            size_hint_y=0.2,
            font_name=FONT_NAME,
            font_size=14
        )
        layout.add_widget(self.url_input)

        # 按钮组
        btn_layout = BoxLayout(size_hint_y=0.08, spacing=8)
        paste_btn = Button(text='粘贴', background_color=(0.2, 0.6, 1, 1), font_name=FONT_NAME)
        paste_btn.bind(on_press=self._paste_link)
        clear_btn = Button(text='清空', background_color=(0.8, 0.4, 0.2, 1), font_name=FONT_NAME)
        clear_btn.bind(on_press=self._clear_input)
        parse_btn = Button(text='解析', background_color=(0.2, 0.8, 0.2, 1), font_name=FONT_NAME)
        parse_btn.bind(on_press=self._parse_link)
        btn_layout.add_widget(paste_btn)
        btn_layout.add_widget(clear_btn)
        btn_layout.add_widget(parse_btn)
        layout.add_widget(btn_layout)

        # 状态
        self.parse_status = Label(text='支持：抖音/快手/B站/小红书/微博等', font_size=12, size_hint_y=0.06, font_name=FONT_NAME)
        layout.add_widget(self.parse_status)

        # 进度条
        self.parse_progress = ProgressBar(max=100, size_hint_y=0.03, value=0)
        layout.add_widget(self.parse_progress)

        # 结果区域（可滚动）
        scroll = ScrollView(size_hint_y=0.4)
        self.result_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=5)
        self.result_layout.bind(minimum_height=self.result_layout.setter('height'))
        scroll.add_widget(self.result_layout)
        layout.add_widget(scroll)

        # 操作按钮
        action_layout = BoxLayout(size_hint_y=0.08, spacing=8)
        download_btn = Button(text='下载视频', background_color=(0.2, 0.8, 0.2, 1), font_name=FONT_NAME)
        download_btn.bind(on_press=self._download_video)
        copy_btn = Button(text='复制链接', background_color=(0.4, 0.4, 0.8, 1), font_name=FONT_NAME)
        copy_btn.bind(on_press=self._copy_link)
        action_layout.add_widget(download_btn)
        action_layout.add_widget(copy_btn)
        layout.add_widget(action_layout)

        return layout

    def _build_local_tab(self):
        """本地去水印 Tab"""
        layout = BoxLayout(orientation='vertical', padding=10, spacing=8)

        layout.add_widget(Label(text='本地视频去水印', font_size=16, size_hint_y=0.08, font_name=FONT_NAME))

        select_btn = Button(text='选择视频文件', size_hint_y=0.1, background_color=(0.2, 0.6, 1, 1), font_name=FONT_NAME)
        select_btn.bind(on_press=self.show_file_chooser)
        layout.add_widget(select_btn)

        self.local_file_label = Label(text='未选择文件', font_size=13, size_hint_y=0.08, font_name=FONT_NAME)
        layout.add_widget(self.local_file_label)

        self.local_progress = ProgressBar(max=100, size_hint_y=0.04, value=0)
        layout.add_widget(self.local_progress)

        self.local_status = Label(text='选择视频后点击开始处理', font_size=13, size_hint_y=0.08, font_name=FONT_NAME)
        layout.add_widget(self.local_status)

        process_btn = Button(text='开始处理', size_hint_y=0.1, background_color=(0.2, 0.8, 0.2, 1), disabled=True, font_name=FONT_NAME)
        process_btn.bind(on_press=self._process_local_video)
        self.local_process_btn = process_btn
        layout.add_widget(process_btn)

        layout.add_widget(Label(text='提示：处理后保存在原文件同目录', font_size=11, size_hint_y=0.06, color=(0.6, 0.6, 0.6, 1), font_name=FONT_NAME))

        return layout

    def _build_batch_tab(self):
        """批量处理 Tab（参考新凌印的批量解析功能）"""
        layout = BoxLayout(orientation='vertical', padding=10, spacing=8)

        layout.add_widget(Label(text='批量链接解析', font_size=16, size_hint_y=0.08, font_name=FONT_NAME))

        self.batch_input = TextInput(
            hint_text='每行一个链接，支持批量粘贴...',
            multiline=True,
            size_hint_y=0.25,
            font_name=FONT_NAME,
            font_size=13
        )
        layout.add_widget(self.batch_input)

        btn_layout = BoxLayout(size_hint_y=0.08, spacing=8)
        batch_parse_btn = Button(text='批量解析', background_color=(0.2, 0.8, 0.2, 1), font_name=FONT_NAME)
        batch_parse_btn.bind(on_press=self._batch_parse)
        batch_download_btn = Button(text='批量下载', background_color=(0.2, 0.6, 1, 1), font_name=FONT_NAME)
        batch_download_btn.bind(on_press=self._batch_download)
        btn_layout.add_widget(batch_parse_btn)
        btn_layout.add_widget(batch_download_btn)
        layout.add_widget(btn_layout)

        self.batch_status = Label(text='支持同时解析多个链接', font_size=12, size_hint_y=0.06, font_name=FONT_NAME)
        layout.add_widget(self.batch_status)

        self.batch_progress = ProgressBar(max=100, size_hint_y=0.03, value=0)
        layout.add_widget(self.batch_progress)

        # 批量结果
        scroll = ScrollView(size_hint_y=0.4)
        self.batch_result_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=5)
        self.batch_result_layout.bind(minimum_height=self.batch_result_layout.setter('height'))
        scroll.add_widget(self.batch_result_layout)
        layout.add_widget(scroll)

        return layout

    # ============ 链接解析功能 ============

    def _paste_link(self, instance):
        """粘贴链接"""
        try:
            from kivy.core.clipboard import Clipboard
            text = Clipboard.paste()
            if text:
                self.url_input.text = text
                self.parse_status.text = '已粘贴，点击解析'
        except:
            self.parse_status.text = '无法读取剪贴板'

    def _clear_input(self, instance):
        """清空输入"""
        self.url_input.text = ''
        self.parse_status.text = '已清空'
        self.result_layout.clear_widgets()

    def _parse_link(self, instance):
        """解析链接"""
        text = self.url_input.text.strip()
        if not text:
            self.parse_status.text = '请输入链接'
            return

        urls = extract_urls(text)
        if not urls:
            self.parse_status.text = '未找到有效链接'
            return

        self.parse_status.text = f'正在解析 {len(urls)} 个链接...'
        self.parse_progress.value = 0

        thread = threading.Thread(target=self._do_parse, args=(urls,), daemon=True)
        thread.start()

    def _do_parse(self, urls):
        """后台解析"""
        results = self.parser.batch_parse(urls, progress_callback=lambda cur, total, pct: Clock.schedule_once(lambda dt: self._update_parse_progress(pct), 0))

        Clock.schedule_once(lambda dt: self._show_parse_results(results), 0)

    def _update_parse_progress(self, pct):
        self.parse_progress.value = pct

    def _show_parse_results(self, results):
        """显示解析结果"""
        self.result_layout.clear_widgets()
        self.parse_results = results

        success_count = sum(1 for r in results if r.success)
        self.parse_status.text = f'解析完成：{success_count}/{len(results)} 成功'

        for i, result in enumerate(results):
            item = BoxLayout(orientation='vertical', size_hint_y=None, height=80, padding=5)
            if result.success:
                title = result.title or f'视频 {i+1}'
                item.add_widget(Label(text=f'✅ {title}', font_size=13, size_hint_y=0.5, font_name=FONT_NAME))
                item.add_widget(Label(text=f'平台：{result.platform} | 无水印链接已获取', font_size=11, size_hint_y=0.5, font_name=FONT_NAME))
            else:
                item.add_widget(Label(text=f'❌ 链接 {i+1}: {result.error_msg}', font_size=13, size_hint_y=1, font_name=FONT_NAME))
            self.result_layout.add_widget(item)

    def _download_video(self, instance):
        """下载解析后的视频"""
        if not hasattr(self, 'parse_results') or not self.parse_results:
            self.parse_status.text = '请先解析链接'
            return

        self.parse_status.text = '正在下载...'
        thread = threading.Thread(target=self._do_download, daemon=True)
        thread.start()

    def _do_download(self):
        """后台下载"""
        save_dir = os.path.expanduser('~/Downloads')
        if platform == 'android':
            save_dir = '/storage/emulated/0/Download'

        success = 0
        for result in self.parse_results:
            if result.success:
                try:
                    self.downloader.download(result.video_url, save_dir)
                    success += 1
                except:
                    pass

        Clock.schedule_once(lambda dt: self._update_parse_status(f'下载完成：{success} 个视频已保存'), 0)

    def _copy_link(self, instance):
        """复制解析后的链接"""
        if not hasattr(self, 'parse_results'):
            return
        links = [r.video_url for r in self.parse_results if r.success]
        if links:
            try:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy('\n'.join(links))
                self.parse_status.text = f'已复制 {len(links)} 个链接'
            except:
                self.parse_status.text = '复制失败'

    # ============ 本地去水印功能 ============

    def show_file_chooser(self, instance):
        """文件选择器"""
        content = BoxLayout(orientation='vertical')
        default_path = '/storage/emulated/0/DCIM' if platform == 'android' else os.path.expanduser('~')

        file_chooser = FileChooserListView(
            filters=['*.mp4', '*.avi', '*.mov', '*.mkv', '*.flv', '*.wmv'],
            path=default_path
        )
        content.add_widget(file_chooser)

        btn_layout = BoxLayout(size_hint_y=0.1, spacing=10)
        cancel_btn = Button(text='取消', font_name=FONT_NAME)
        select_btn = Button(text='选择', background_color=(0.2, 0.8, 0.2, 1), font_name=FONT_NAME)
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(select_btn)
        content.add_widget(btn_layout)

        popup = Popup(title='选择视频文件', content=content, size_hint=(0.9, 0.9), title_font=FONT_NAME)

        def on_select(inst):
            if file_chooser.selection:
                self.selected_file = file_chooser.selection[0]
                self.local_file_label.text = f'已选择: {os.path.basename(self.selected_file)}'
                self.local_process_btn.disabled = False
            popup.dismiss()

        def on_cancel(inst):
            popup.dismiss()

        select_btn.bind(on_press=on_select)
        cancel_btn.bind(on_press=on_cancel)
        popup.open()

    def _process_local_video(self, instance):
        """本地视频处理"""
        if not self.selected_file:
            return
        self.local_process_btn.disabled = True
        self.local_status.text = '正在处理...'
        thread = threading.Thread(target=self._do_local_process, daemon=True)
        thread.start()

    def _do_local_process(self):
        """后台处理本地视频"""
        try:
            base, ext = os.path.splitext(self.selected_file)
            output_path = f"{base}_no_watermark{ext}"

            ffmpeg_cmd = self._find_ffmpeg()
            if ffmpeg_cmd:
                self._process_with_ffmpeg(output_path, ffmpeg_cmd)
            else:
                self._process_basic_copy(output_path)
        except Exception as e:
            Clock.schedule_once(lambda dt: self._update_local_status(f'处理失败: {str(e)}'), 0)
        finally:
            Clock.schedule_once(lambda dt: setattr(self.local_process_btn, 'disabled', False), 0)

    def _find_ffmpeg(self):
        """查找 ffmpeg"""
        candidates = ['ffmpeg']
        if platform == 'android':
            candidates += ['/data/data/com.xiake.watermark/files/ffmpeg']
        for cmd in candidates:
            try:
                import subprocess
                subprocess.run([cmd, '-version'], capture_output=True, timeout=5)
                return cmd
            except:
                continue
        return None

    def _process_with_ffmpeg(self, output_path, ffmpeg_cmd):
        """用 ffmpeg 处理"""
        import subprocess
        Clock.schedule_once(lambda dt: self._update_local_status('正在用 ffmpeg 处理...'), 0)

        cmd = [ffmpeg_cmd, '-y', '-i', self.selected_file, '-vf', 'crop=iw*0.9:ih*0.9:0:0', '-c:a', 'copy', output_path]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        _, stderr = process.communicate(timeout=600)

        if process.returncode == 0:
            Clock.schedule_once(lambda dt: self._update_local_status(f'处理完成！保存到: {os.path.basename(output_path)}'), 0)
            Clock.schedule_once(lambda dt: setattr(self.local_progress, 'value', 100), 0)
        else:
            Clock.schedule_once(lambda dt: self._update_local_status('ffmpeg 处理失败，回退到基础模式...'), 0)
            self._process_basic_copy(output_path)

    def _process_basic_copy(self, output_path):
        """基础模式：复制文件"""
        import shutil
        Clock.schedule_once(lambda dt: self._update_local_status('基础模式：直接复制视频...'), 0)
        shutil.copy2(self.selected_file, output_path)
        Clock.schedule_once(lambda dt: setattr(self.local_progress, 'value', 100), 0)
        Clock.schedule_once(lambda dt: self._update_local_status(f'已复制到: {os.path.basename(output_path)}'), 0)

    # ============ 批量处理功能 ============

    def _batch_parse(self, instance):
        """批量解析"""
        text = self.batch_input.text.strip()
        if not text:
            self.batch_status.text = '请输入链接'
            return

        urls = extract_urls(text)
        if not urls:
            self.batch_status.text = '未找到有效链接'
            return

        self.batch_status.text = f'正在批量解析 {len(urls)} 个链接...'
        self.batch_progress.value = 0

        thread = threading.Thread(target=self._do_batch_parse, args=(urls,), daemon=True)
        thread.start()

    def _do_batch_parse(self, urls):
        """后台批量解析"""
        results = self.parser.batch_parse(urls, progress_callback=lambda cur, total, pct: Clock.schedule_once(lambda dt: setattr(self.batch_progress, 'value', pct), 0))

        Clock.schedule_once(lambda dt: self._show_batch_results(results), 0)

    def _show_batch_results(self, results):
        """显示批量结果"""
        self.batch_result_layout.clear_widgets()
        self.batch_results = results

        success_count = sum(1 for r in results if r.success)
        self.batch_status.text = f'批量解析完成：{success_count}/{len(results)} 成功'

        for i, result in enumerate(results):
            item = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
            if result.success:
                item.add_widget(Label(text=f'✅ {result.platform}: {result.title or "视频"}', font_size=12, font_name=FONT_NAME))
            else:
                item.add_widget(Label(text=f'❌ {result.error_msg}', font_size=12, font_name=FONT_NAME))
            self.batch_result_layout.add_widget(item)

    def _batch_download(self, instance):
        """批量下载"""
        if not hasattr(self, 'batch_results'):
            self.batch_status.text = '请先批量解析'
            return

        self.batch_status.text = '正在批量下载...'
        thread = threading.Thread(target=self._do_batch_download, daemon=True)
        thread.start()

    def _do_batch_download(self):
        """后台批量下载"""
        save_dir = os.path.expanduser('~/Downloads')
        if platform == 'android':
            save_dir = '/storage/emulated/0/Download'

        success = 0
        total = len(self.batch_results)
        for i, result in enumerate(self.batch_results):
            if result.success:
                try:
                    self.downloader.download(result.video_url, save_dir)
                    success += 1
                except:
                    pass
            pct = int((i + 1) / total * 100)
            Clock.schedule_once(lambda dt, p=pct: setattr(self.batch_progress, 'value', p), 0)

        Clock.schedule_once(lambda dt: self._update_batch_status(f'批量下载完成：{success}/{total} 成功'), 0)

    # ============ 辅助方法 ============

    def _update_parse_status(self, text):
        self.parse_status.text = text

    def _update_local_status(self, text):
        self.local_status.text = text

    def _update_batch_status(self, text):
        self.batch_status.text = text


if __name__ == '__main__':
    WatermarkRemoverApp().run()
