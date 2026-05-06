"""
视频去水印 v5.1 - 对标新凌印 UI 重构
功能：视频链接解析 + 本地视频去水印
"""
import os
import re
import json
import time
import shutil
import threading
from urllib.parse import urlparse, unquote

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
from kivy.graphics import Color, RoundedRectangle

# ============ 字体 ============
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
FONT_FILE = os.path.join(FONT_DIR, 'ChineseFont.ttf')
FONT_NAME = 'ChineseFont'

if os.path.exists(FONT_FILE):
    resource_add_path(FONT_DIR)
    LabelBase.register(name=FONT_NAME, fn_regular=FONT_FILE)
else:
    FONT_NAME = 'Roboto'

# ============ Android 权限 ============
if platform == 'android':
    from android.permissions import request_permissions, Permission
    request_permissions([
        Permission.READ_EXTERNAL_STORAGE,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.READ_MEDIA_VIDEO,
        Permission.INTERNET,
    ])

# ============ URL 提取 ============
URL_RE = re.compile(r'https?://[^\s<>"\']+')

PLATFORM_MAP = {
    'douyin': ['douyin.com', 'iesdouyin.com', 'v.douyin.com'],
    'kuaishou': ['kuaishou.com', 'gifshow.com'],
    'bilibili': ['bilibili.com', 'b23.tv'],
    'xiaohongshu': ['xiaohongshu.com', 'xhslink.com'],
    'weibo': ['weibo.com', 'weibo.cn'],
}

def extract_urls(text):
    return URL_RE.findall(text or '')

def detect_platform(url):
    for name, domains in PLATFORM_MAP.items():
        for d in domains:
            if d in url:
                return name
    return 'other'


class WatermarkApp(App):
    def build(self):
        self.title = '视频去水印'
        self.selected_file = None
        self.parse_results = []
        self.batch_results = []

        root = BoxLayout(orientation='vertical', padding=[10,5], spacing=5)

        # 标题
        root.add_widget(Label(
            text='视频去水印',
            font_size=20, size_hint_y=0.07,
            font_name=FONT_NAME, bold=True
        ))

        # Tabs
        self.tabs = TabbedPanel(do_default_tab=False, size_hint_y=0.88)
        self.tabs.add_widget(self._tab_parse())
        self.tabs.add_widget(self._tab_local())
        self.tabs.add_widget(self._tab_batch())
        root.add_widget(self.tabs)

        return root

    # ==================== Tab 1: 链接解析 ====================
    def _tab_parse(self):
        tab = TabbedPanelItem(text='链接解析', font_name=FONT_NAME)
        lay = BoxLayout(orientation='vertical', padding=10, spacing=8)

        lay.add_widget(Label(text='粘贴视频分享链接', font_size=14, size_hint_y=0.05, font_name=FONT_NAME))

        self.parse_input = TextInput(
            hint_text='请粘贴分享链接...',
            multiline=False, size_hint_y=0.1,
            font_name=FONT_NAME, font_size=14
        )
        lay.add_widget(self.parse_input)

        # 按钮行
        btns = BoxLayout(size_hint_y=0.08, spacing=8)
        self._btn(btns, '粘贴', self._paste, (0.2,0.6,1,1))
        self._btn(btns, '清空', self._clear_parse, (0.8,0.4,0.2,1))
        self._btn(btns, '解析', self._do_parse_link, (0.2,0.8,0.2,1))
        lay.add_widget(btns)

        self.parse_status = Label(
            text='支持：抖音/快手/B站/小红书/微博',
            font_size=12, size_hint_y=0.05, font_name=FONT_NAME
        )
        lay.add_widget(self.parse_status)

        self.parse_bar = ProgressBar(max=100, value=0, size_hint_y=0.03)
        lay.add_widget(self.parse_bar)

        # 结果列表
        sv = ScrollView(size_hint_y=0.45)
        self.parse_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=4)
        self.parse_list.bind(minimum_height=self.parse_list.setter('height'))
        sv.add_widget(self.parse_list)
        lay.add_widget(sv)

        # 下载按钮
        btns2 = BoxLayout(size_hint_y=0.08, spacing=8)
        self._btn(btns2, '下载视频', self._download_parsed, (0.2,0.8,0.2,1))
        self._btn(btns2, '复制链接', self._copy_parsed, (0.4,0.4,0.8,1))
        lay.add_widget(btns2)

        tab.content = lay
        return tab

    # ==================== Tab 2: 本地去水印 ====================
    def _tab_local(self):
        tab = TabbedPanelItem(text='本地去水印', font_name=FONT_NAME)
        lay = BoxLayout(orientation='vertical', padding=10, spacing=8)

        lay.add_widget(Label(text='本地视频去水印', font_size=16, size_hint_y=0.06, font_name=FONT_NAME))

        self._btn(lay, '选择视频文件', self._pick_file, (0.2,0.6,1,1), h=0.08)

        self.local_file = Label(text='未选择文件', font_size=13, size_hint_y=0.06, font_name=FONT_NAME)
        lay.add_widget(self.local_file)

        # 处理模式
        lay.add_widget(Label(text='处理模式', font_size=13, size_hint_y=0.05, font_name=FONT_NAME))

        mode_btns = BoxLayout(size_hint_y=0.08, spacing=8)
        self._btn(mode_btns, '裁剪去水印', self._mode_crop, (0.2,0.7,0.3,1))
        self._btn(mode_btns, '模糊去水印', self._mode_blur, (0.3,0.5,0.8,1))
        lay.add_widget(mode_btns)

        self.local_mode_label = Label(text='模式：裁剪（自动裁掉底部/边缘水印区域）', font_size=11, size_hint_y=0.05, font_name=FONT_NAME)
        lay.add_widget(self.local_mode_label)

        self.local_bar = ProgressBar(max=100, value=0, size_hint_y=0.04)
        lay.add_widget(self.local_bar)

        self.local_status = Label(text='选择视频后点击开始处理', font_size=13, size_hint_y=0.06, font_name=FONT_NAME)
        lay.add_widget(self.local_status)

        self._btn(lay, '开始处理', self._run_local, (0.2,0.8,0.2,1), h=0.08)

        lay.add_widget(Label(
            text='提示：处理后保存在原文件同目录',
            font_size=11, size_hint_y=0.04, color=(0.6,0.6,0.6,1), font_name=FONT_NAME
        ))

        tab.content = lay
        return tab

    # ==================== Tab 3: 批量处理 ====================
    def _tab_batch(self):
        tab = TabbedPanelItem(text='批量处理', font_name=FONT_NAME)
        lay = BoxLayout(orientation='vertical', padding=10, spacing=8)

        lay.add_widget(Label(text='批量链接解析', font_size=16, size_hint_y=0.06, font_name=FONT_NAME))

        self.batch_input = TextInput(
            hint_text='每行一个链接...',
            multiline=True, size_hint_y=0.2,
            font_name=FONT_NAME, font_size=13
        )
        lay.add_widget(self.batch_input)

        btns = BoxLayout(size_hint_y=0.08, spacing=8)
        self._btn(btns, '批量解析', self._batch_parse, (0.2,0.8,0.2,1))
        self._btn(btns, '批量下载', self._batch_download, (0.2,0.6,1,1))
        lay.add_widget(btns)

        self.batch_status = Label(text='支持同时解析多个链接', font_size=12, size_hint_y=0.05, font_name=FONT_NAME)
        lay.add_widget(self.batch_status)

        self.batch_bar = ProgressBar(max=100, value=0, size_hint_y=0.03)
        lay.add_widget(self.batch_bar)

        sv = ScrollView(size_hint_y=0.4)
        self.batch_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=4)
        self.batch_list.bind(minimum_height=self.batch_list.setter('height'))
        sv.add_widget(self.batch_list)
        lay.add_widget(sv)

        tab.content = lay
        return tab

    # ==================== 公共控件 ====================
    def _btn(self, parent, text, callback, color, h=None):
        b = Button(text=text, font_name=FONT_NAME, font_size=14,
                   background_color=color, size_hint_y=h or 0.07)
        b.bind(on_press=callback)
        parent.add_widget(b)
        return b

    # ==================== 链接解析 ====================
    def _paste(self, *a):
        try:
            from kivy.core.clipboard import Clipboard
            self.parse_input.text = Clipboard.paste() or ''
            self.parse_status.text = '已粘贴，点击解析'
        except:
            self.parse_status.text = '无法读取剪贴板'

    def _clear_parse(self, *a):
        self.parse_input.text = ''
        self.parse_list.clear_widgets()
        self.parse_status.text = '已清空'
        self.parse_bar.value = 0

    def _do_parse_link(self, *a):
        text = self.parse_input.text.strip()
        if not text:
            self.parse_status.text = '请输入链接'
            return
        urls = extract_urls(text)
        if not urls:
            self.parse_status.text = '未找到有效链接'
            return
        self.parse_status.text = f'正在解析 {len(urls)} 个链接...'
        self.parse_bar.value = 0
        threading.Thread(target=self._parse_worker, args=(urls,), daemon=True).start()

    def _parse_worker(self, urls):
        results = []
        for i, url in enumerate(urls):
            try:
                import urllib.request, urllib.parse
                api = f'https://api.r10086.com/video/api.php?url={urllib.parse.quote(url)}'
                req = urllib.request.Request(api, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read())
                vu = data.get('video_url') or data.get('videoUrl') or data.get('url') or ''
                results.append({'ok': bool(vu), 'url': vu, 'title': data.get('title',''), 'platform': detect_platform(url)})
            except:
                results.append({'ok': False, 'url': '', 'title': '', 'platform': detect_platform(url), 'err': '解析失败'})
            pct = int((i+1)/len(urls)*100)
            Clock.schedule_once(lambda dt, p=pct: setattr(self.parse_bar, 'value', p))
            time.sleep(0.3)
        self.parse_results = results
        Clock.schedule_once(lambda dt: self._show_parse(results))

    def _show_parse(self, results):
        self.parse_list.clear_widgets()
        ok = sum(1 for r in results if r['ok'])
        self.parse_status.text = f'解析完成：{ok}/{len(results)} 成功'
        for r in results:
            h = 50
            item = BoxLayout(size_hint_y=None, height=h, padding=[5,2])
            if r['ok']:
                item.add_widget(Label(text=f"✅ {r['platform']} | {r['title'][:20] or '视频'}", font_size=12, font_name=FONT_NAME))
            else:
                item.add_widget(Label(text=f"❌ {r.get('err','解析失败')}", font_size=12, font_name=FONT_NAME))
            self.parse_list.add_widget(item)

    def _download_parsed(self, *a):
        if not self.parse_results:
            self.parse_status.text = '请先解析链接'
            return
        self.parse_status.text = '正在下载...'
        threading.Thread(target=self._dl_worker, daemon=True).start()

    def _dl_worker(self):
        import urllib.request
        save_dir = '/storage/emulated/0/Download' if platform == 'android' else os.path.expanduser('~/Downloads')
        ok = 0
        for r in self.parse_results:
            if r['ok'] and r['url']:
                try:
                    fn = f"video_{int(time.time())}_{ok}.mp4"
                    urllib.request.urlretrieve(r['url'], os.path.join(save_dir, fn))
                    ok += 1
                except:
                    pass
        Clock.schedule_once(lambda dt: setattr(self.parse_status, 'text', f'下载完成：{ok} 个视频'))

    def _copy_parsed(self, *a):
        links = [r['url'] for r in self.parse_results if r['ok']]
        if not links:
            self.parse_status.text = '没有可复制的链接'
            return
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy('\n'.join(links))
            self.parse_status.text = f'已复制 {len(links)} 个链接'
        except:
            self.parse_status.text = '复制失败'

    # ==================== 本地去水印 ====================
    def _pick_file(self, *a):
        content = BoxLayout(orientation='vertical')
        path = '/storage/emulated/0/DCIM' if platform == 'android' else os.path.expanduser('~')
        fc = FileChooserListView(path=path, filters=['*.mp4','*.avi','*.mov','*.mkv','*.flv','*.wmv','*.3gp'])
        content.add_widget(fc)
        btns = BoxLayout(size_hint_y=0.1, spacing=8)
        cancel = Button(text='取消', font_name=FONT_NAME)
        ok_btn = Button(text='选择', background_color=(0.2,0.8,0.2,1), font_name=FONT_NAME)
        btns.add_widget(cancel)
        btns.add_widget(ok_btn)
        content.add_widget(btns)
        popup = Popup(title='选择视频', content=content, size_hint=(0.9,0.9))
        def on_ok(*a):
            if fc.selection:
                self.selected_file = fc.selection[0]
                self.local_file.text = f'已选：{os.path.basename(self.selected_file)}'
            popup.dismiss()
        cancel.bind(on_press=lambda *a: popup.dismiss())
        ok_btn.bind(on_press=on_ok)
        popup.open()

    def _mode_crop(self, *a):
        self.local_mode = 'crop'
        self.local_mode_label.text = '模式：裁剪（裁掉底部/边缘水印区域）'

    def _mode_blur(self, *a):
        self.local_mode = 'blur'
        self.local_mode_label.text = '模式：模糊（模糊水印区域，保留画面）'

    def _run_local(self, *a):
        if not self.selected_file:
            self.local_status.text = '请先选择视频'
            return
        self.local_status.text = '正在处理...'
        self.local_bar.value = 0
        mode = getattr(self, 'local_mode', 'crop')
        threading.Thread(target=self._local_worker, args=(mode,), daemon=True).start()

    def _local_worker(self, mode):
        try:
            base, ext = os.path.splitext(self.selected_file)
            out = f"{base}_no_wm{ext}"
            ffmpeg = self._find_ffmpeg()
            if not ffmpeg:
                shutil.copy2(self.selected_file, out)
                Clock.schedule_once(lambda dt: self._set_local(f'已复制：{os.path.basename(out)}（未安装ffmpeg）'))
                return

            if mode == 'crop':
                cmd = [ffmpeg, '-y', '-i', self.selected_file,
                       '-vf', 'crop=iw*0.92:ih*0.88:0:0', '-c:a', 'copy', out]
            else:
                # 模糊模式：对底部区域应用模糊滤镜
                cmd = [ffmpeg, '-y', '-i', self.selected_file,
                       '-vf', 'split[original][blur];[blur]crop=iw:ih*0.15:0:ih*0.85,boxblur=10:10[blurred];[original][blurred]overlay=0:H-h*0.15',
                       '-c:a', 'copy', out]

            import subprocess
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            _, err = proc.communicate(timeout=600)

            if proc.returncode == 0:
                Clock.schedule_once(lambda dt: setattr(self.local_bar, 'value', 100))
                Clock.schedule_once(lambda dt: self._set_local(f'处理完成：{os.path.basename(out)}'))
            else:
                shutil.copy2(self.selected_file, out)
                Clock.schedule_once(lambda dt: self._set_local(f'ffmpeg错误，已复制原文件'))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._set_local(f'处理失败：{str(e)[:50]}'))

    def _find_ffmpeg(self):
        for cmd in ['ffmpeg', '/data/data/com.xiake.watermark/files/ffmpeg']:
            try:
                import subprocess
                subprocess.run([cmd, '-version'], capture_output=True, timeout=3)
                return cmd
            except:
                continue
        return None

    # ==================== 批量处理 ====================
    def _batch_parse(self, *a):
        text = self.batch_input.text.strip()
        if not text:
            self.batch_status.text = '请输入链接'
            return
        urls = extract_urls(text)
        if not urls:
            self.batch_status.text = '未找到有效链接'
            return
        self.batch_status.text = f'正在批量解析 {len(urls)} 个链接...'
        self.batch_bar.value = 0
        threading.Thread(target=self._batch_worker, args=(urls,), daemon=True).start()

    def _batch_worker(self, urls):
        results = []
        for i, url in enumerate(urls):
            try:
                import urllib.request, urllib.parse
                api = f'https://api.r10086.com/video/api.php?url={urllib.parse.quote(url)}'
                req = urllib.request.Request(api, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read())
                vu = data.get('video_url') or data.get('videoUrl') or data.get('url') or ''
                results.append({'ok': bool(vu), 'url': vu, 'title': data.get('title',''), 'platform': detect_platform(url)})
            except:
                results.append({'ok': False, 'url': '', 'title': '', 'platform': detect_platform(url), 'err': '解析失败'})
            Clock.schedule_once(lambda dt, p=int((i+1)/len(urls)*100): setattr(self.batch_bar, 'value', p))
            time.sleep(0.3)
        self.batch_results = results
        Clock.schedule_once(lambda dt: self._show_batch(results))

    def _show_batch(self, results):
        self.batch_list.clear_widgets()
        ok = sum(1 for r in results if r['ok'])
        self.batch_status.text = f'批量解析完成：{ok}/{len(results)} 成功'
        for r in results:
            item = BoxLayout(size_hint_y=None, height=40, padding=[5,2])
            if r['ok']:
                item.add_widget(Label(text=f"✅ {r['platform']} | {r['title'][:25] or '视频'}", font_size=12, font_name=FONT_NAME))
            else:
                item.add_widget(Label(text=f"❌ {r.get('err','失败')}", font_size=12, font_name=FONT_NAME))
            self.batch_list.add_widget(item)

    def _batch_download(self, *a):
        if not self.batch_results:
            self.batch_status.text = '请先批量解析'
            return
        self.batch_status.text = '正在批量下载...'
        threading.Thread(target=self._batch_dl_worker, daemon=True).start()

    def _batch_dl_worker(self):
        import urllib.request
        save_dir = '/storage/emulated/0/Download' if platform == 'android' else os.path.expanduser('~/Downloads')
        ok = 0
        for i, r in enumerate(self.batch_results):
            if r['ok'] and r['url']:
                try:
                    fn = f"batch_{int(time.time())}_{i}.mp4"
                    urllib.request.urlretrieve(r['url'], os.path.join(save_dir, fn))
                    ok += 1
                except:
                    pass
            Clock.schedule_once(lambda dt, p=int((i+1)/len(self.batch_results)*100): setattr(self.batch_bar, 'value', p))
        Clock.schedule_once(lambda dt: setattr(self.batch_status, 'text', f'批量下载完成：{ok} 个'))

    # ==================== 辅助 ====================
    def _set_local(self, text):
        self.local_status.text = text


if __name__ == '__main__':
    WatermarkApp().run()
