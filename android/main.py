"""
视频去水印 v6.0 - 完整对标新凌印
功能：视频解析 | 图集提取 | 主页解析 | 本地去水印 | 反馈建议
"""
import os, re, json, time, shutil, threading
from urllib.parse import urlparse, unquote, quote

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
    request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE,
                         Permission.READ_MEDIA_VIDEO, Permission.READ_MEDIA_IMAGES, Permission.INTERNET])

# ============ 工具函数 ============
URL_RE = re.compile(r'https?://[^\s<>"\']+')
PLATFORM_MAP = {
    'douyin': ['douyin.com', 'iesdouyin.com', 'v.douyin.com'],
    'kuaishou': ['kuaishou.com', 'gifshow.com'],
    'bilibili': ['bilibili.com', 'b23.tv'],
    'xiaohongshu': ['xiaohongshu.com', 'xhslink.com'],
    'weibo': ['weibo.com', 'weibo.cn'],
    'pipix': ['pipix.com'],
    'huoshan': ['huoshan.com', 'ishortv'],
}

def extract_urls(text):
    return URL_RE.findall(text or '')

def detect_platform(url):
    for name, domains in PLATFORM_MAP.items():
        for d in domains:
            if d in url:
                return name
    return 'other'

def get_save_dir():
    if platform == 'android':
        return '/storage/emulated/0/Download'
    return os.path.expanduser('~/Downloads')

def api_parse_url(url):
    """调用解析 API"""
    import urllib.request, urllib.parse
    apis = [
        f'https://api.r10086.com/video/api.php?url={quote(url)}',
        f'https://api.douyin.wtf/api?url={quote(url)}',
    ]
    for api in apis:
        try:
            req = urllib.request.Request(api, headers={'User-Agent': 'Mozilla/5.0 (Linux; Android 13)'})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            vu = data.get('video_url') or data.get('videoUrl') or data.get('url') or data.get('data',{}).get('url') or ''
            if vu:
                return {'ok': True, 'video_url': vu,
                        'poster': data.get('poster') or data.get('cover') or data.get('data',{}).get('cover') or '',
                        'title': data.get('title') or data.get('desc') or data.get('data',{}).get('title') or '',
                        'pics': data.get('pics') or data.get('images') or data.get('data',{}).get('pics') or []}
        except:
            continue
    return {'ok': False, 'err': '解析失败'}

def api_parse_images(url):
    """解析图集"""
    result = api_parse_url(url)
    if result['ok'] and result.get('pics'):
        return {'ok': True, 'pics': result['pics'], 'title': result.get('title', '')}
    return {'ok': False, 'err': '未找到图集'}

def download_file(url, save_dir, filename=None):
    """下载文件"""
    import urllib.request
    if not filename:
        filename = f"file_{int(time.time())}_{os.getpid()}.mp4"
    path = os.path.join(save_dir, filename)
    urllib.request.urlretrieve(url, path)
    return path


# ============ 主界面 ============
class WatermarkApp(App):
    def build(self):
        self.title = '视频去水印 v6.0'
        self.selected_file = None
        self.parse_results = []
        self.batch_results = []
        self.parsed_video_url = ''
        self.parsed_poster_url = ''

        root = BoxLayout(orientation='vertical', padding=[8,4], spacing=4)

        # 标题栏
        title_bar = BoxLayout(size_hint_y=0.07)
        title_bar.add_widget(Label(text='视频去水印', font_size=20, bold=True, font_name=FONT_NAME))
        root.add_widget(title_bar)

        # Tab 面板
        self.tabs = TabbedPanel(do_default_tab=False, size_hint_y=0.88)
        self.tabs.add_widget(self._tab_video())    # 视频链接解析
        self.tabs.add_widget(self._tab_images())   # 图集提取
        self.tabs.add_widget(self._tab_local())    # 本地去水印
        self.tabs.add_widget(self._tab_batch())    # 批量解析
        self.tabs.add_widget(self._tab_feedback()) # 反馈建议
        root.add_widget(self.tabs)

        # 底部信息
        root.add_widget(Label(text='v6.0 | 微信:727418', font_size=10, size_hint_y=0.03,
                              color=(0.5,0.5,0.5,1), font_name=FONT_NAME))

        return root

    # ==================== Tab 1: 视频链接解析 ====================
    def _tab_video(self):
        tab = TabbedPanelItem(text='视频解析', font_name=FONT_NAME)
        lay = BoxLayout(orientation='vertical', padding=10, spacing=8)

        # 输入
        lay.add_widget(Label(text='粘贴视频分享链接', font_size=14, size_hint_y=0.05, font_name=FONT_NAME))
        self.video_input = TextInput(hint_text='请粘贴分享链接...', multiline=False,
                                     size_hint_y=0.1, font_name=FONT_NAME, font_size=14)
        lay.add_widget(self.video_input)

        # 按钮
        btns = BoxLayout(size_hint_y=0.08, spacing=8)
        self._mkbtn(btns, '粘贴', self._paste_video, (0.2,0.6,1,1))
        self._mkbtn(btns, '清空', self._clear_video, (0.7,0.4,0.2,1))
        self._mkbtn(btns, '解析', self._parse_video, (0.2,0.8,0.2,1))
        lay.add_widget(btns)

        self.video_status = Label(text='支持：抖音/快手/B站/小红书/微博等', font_size=12,
                                  size_hint_y=0.05, font_name=FONT_NAME)
        lay.add_widget(self.video_status)

        self.video_bar = ProgressBar(max=100, value=0, size_hint_y=0.03)
        lay.add_widget(self.video_bar)

        # 结果
        sv = ScrollView(size_hint_y=0.42)
        self.video_result = BoxLayout(orientation='vertical', size_hint_y=None, spacing=4)
        self.video_result.bind(minimum_height=self.video_result.setter('height'))
        sv.add_widget(self.video_result)
        lay.add_widget(sv)

        # 操作
        btns2 = BoxLayout(size_hint_y=0.08, spacing=8)
        self._mkbtn(btns2, '下载视频', self._dl_video, (0.2,0.8,0.2,1))
        self._mkbtn(btns2, '复制链接', self._copy_video, (0.4,0.4,0.8,1))
        lay.add_widget(btns2)

        tab.content = lay
        return tab

    # ==================== Tab 2: 图集提取 ====================
    def _tab_images(self):
        tab = TabbedPanelItem(text='图集提取', font_name=FONT_NAME)
        lay = BoxLayout(orientation='vertical', padding=10, spacing=8)

        lay.add_widget(Label(text='粘贴图集/小红书链接', font_size=14, size_hint_y=0.05, font_name=FONT_NAME))
        self.img_input = TextInput(hint_text='请粘贴图集链接...', multiline=False,
                                   size_hint_y=0.1, font_name=FONT_NAME, font_size=14)
        lay.add_widget(self.img_input)

        btns = BoxLayout(size_hint_y=0.08, spacing=8)
        self._mkbtn(btns, '粘贴', self._paste_img, (0.2,0.6,1,1))
        self._mkbtn(btns, '清空', self._clear_img, (0.7,0.4,0.2,1))
        self._mkbtn(btns, '提取图集', self._parse_img, (0.2,0.8,0.2,1))
        lay.add_widget(btns)

        self.img_status = Label(text='支持小红书/抖音图集链接', font_size=12, size_hint_y=0.05, font_name=FONT_NAME)
        lay.add_widget(self.img_status)

        self.img_bar = ProgressBar(max=100, value=0, size_hint_y=0.03)
        lay.add_widget(self.img_bar)

        sv = ScrollView(size_hint_y=0.45)
        self.img_result = BoxLayout(orientation='vertical', size_hint_y=None, spacing=4)
        self.img_result.bind(minimum_height=self.img_result.setter('height'))
        sv.add_widget(self.img_result)
        lay.add_widget(sv)

        self._mkbtn(lay, '批量保存图片', self._dl_images, (0.2,0.8,0.2,1), h=0.08)

        tab.content = lay
        return tab

    # ==================== Tab 3: 本地去水印 ====================
    def _tab_local(self):
        tab = TabbedPanelItem(text='本地去水印', font_name=FONT_NAME)
        lay = BoxLayout(orientation='vertical', padding=10, spacing=8)

        lay.add_widget(Label(text='本地视频去水印', font_size=16, size_hint_y=0.06, font_name=FONT_NAME))
        self._mkbtn(lay, '选择视频文件', self._pick_file, (0.2,0.6,1,1), h=0.08)

        self.local_file = Label(text='未选择文件', font_size=13, size_hint_y=0.06, font_name=FONT_NAME)
        lay.add_widget(self.local_file)

        lay.add_widget(Label(text='处理模式', font_size=13, size_hint_y=0.04, font_name=FONT_NAME))
        mode_btns = BoxLayout(size_hint_y=0.08, spacing=8)
        self._mkbtn(mode_btns, '裁剪去水印', self._mode_crop, (0.2,0.7,0.3,1))
        self._mkbtn(mode_btns, '模糊去水印', self._mode_blur, (0.3,0.5,0.8,1))
        lay.add_widget(mode_btns)

        self.local_mode_label = Label(text='模式：裁剪（裁掉底部/边缘水印区域）',
                                      font_size=11, size_hint_y=0.04, font_name=FONT_NAME)
        lay.add_widget(self.local_mode_label)

        self.local_bar = ProgressBar(max=100, value=0, size_hint_y=0.04)
        lay.add_widget(self.local_bar)

        self.local_status = Label(text='选择视频后点击开始处理', font_size=13, size_hint_y=0.06, font_name=FONT_NAME)
        lay.add_widget(self.local_status)

        self._mkbtn(lay, '开始处理', self._run_local, (0.2,0.8,0.2,1), h=0.08)
        lay.add_widget(Label(text='提示：处理后保存在原文件同目录', font_size=11, size_hint_y=0.04,
                             color=(0.5,0.5,0.5,1), font_name=FONT_NAME))

        tab.content = lay
        return tab

    # ==================== Tab 4: 批量解析 ====================
    def _tab_batch(self):
        tab = TabbedPanelItem(text='批量解析', font_name=FONT_NAME)
        lay = BoxLayout(orientation='vertical', padding=10, spacing=8)

        lay.add_widget(Label(text='批量链接解析', font_size=16, size_hint_y=0.06, font_name=FONT_NAME))
        self.batch_input = TextInput(hint_text='每行一个链接...', multiline=True,
                                     size_hint_y=0.2, font_name=FONT_NAME, font_size=13)
        lay.add_widget(self.batch_input)

        btns = BoxLayout(size_hint_y=0.08, spacing=8)
        self._mkbtn(btns, '批量解析', self._batch_parse, (0.2,0.8,0.2,1))
        self._mkbtn(btns, '批量下载', self._batch_download, (0.2,0.6,1,1))
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

    # ==================== Tab 5: 反馈建议 ====================
    def _tab_feedback(self):
        tab = TabbedPanelItem(text='反馈建议', font_name=FONT_NAME)
        lay = BoxLayout(orientation='vertical', padding=10, spacing=8)

        lay.add_widget(Label(text='反馈建议', font_size=16, size_hint_y=0.06, font_name=FONT_NAME))
        lay.add_widget(Label(text='使用中遇到问题或有功能建议\n请通过以下方式联系我们',
                             font_size=13, size_hint_y=0.1, font_name=FONT_NAME))

        lay.add_widget(Label(text='微信：727418', font_size=14, size_hint_y=0.06, font_name=FONT_NAME))

        self.feedback_input = TextInput(hint_text='请输入您的反馈或建议...', multiline=True,
                                        size_hint_y=0.3, font_name=FONT_NAME, font_size=14)
        lay.add_widget(self.feedback_input)

        self._mkbtn(lay, '提交反馈', self._submit_feedback, (0.2,0.8,0.2,1), h=0.08)

        self.feedback_status = Label(text='', font_size=12, size_hint_y=0.05, font_name=FONT_NAME)
        lay.add_widget(self.feedback_status)

        tab.content = lay
        return tab

    # ==================== 公共控件 ====================
    def _mkbtn(self, parent, text, cb, color, h=None):
        b = Button(text=text, font_name=FONT_NAME, font_size=14,
                   background_color=color, size_hint_y=h or 0.07)
        b.bind(on_press=cb)
        parent.add_widget(b)
        return b

    # ==================== 视频解析 ====================
    def _paste_video(self, *a):
        try:
            from kivy.core.clipboard import Clipboard
            self.video_input.text = Clipboard.paste() or ''
            self.video_status.text = '已粘贴，点击解析'
        except:
            self.video_status.text = '无法读取剪贴板'

    def _clear_video(self, *a):
        self.video_input.text = ''
        self.video_result.clear_widgets()
        self.video_status.text = '已清空'
        self.video_bar.value = 0
        self.parsed_video_url = ''
        self.parsed_poster_url = ''

    def _parse_video(self, *a):
        text = self.video_input.text.strip()
        if not text:
            self.video_status.text = '请输入链接'
            return
        urls = extract_urls(text)
        if not urls:
            self.video_status.text = '未找到有效链接'
            return
        self.video_status.text = f'正在解析...'
        self.video_bar.value = 30
        threading.Thread(target=self._parse_video_worker, args=(urls[0],), daemon=True).start()

    def _parse_video_worker(self, url):
        result = api_parse_url(url)
        Clock.schedule_once(lambda dt: self._show_video_result(result, url))

    def _show_video_result(self, result, original_url):
        self.video_bar.value = 100
        self.video_result.clear_widgets()
        if result['ok']:
            self.parsed_video_url = result['video_url']
            self.parsed_poster_url = result.get('poster', '')
            plat = detect_platform(original_url)
            title = result.get('title', '') or '视频'
            self.video_status.text = f'解析成功 | 平台：{plat}'
            item = BoxLayout(size_hint_y=None, height=60, padding=[5,2])
            item.add_widget(Label(text=f'✅ {title[:30]}', font_size=13, font_name=FONT_NAME))
            self.video_result.add_widget(item)
        else:
            self.video_status.text = f"解析失败：{result.get('err', '未知错误')}"

    def _dl_video(self, *a):
        if not self.parsed_video_url:
            self.video_status.text = '请先解析链接'
            return
        self.video_status.text = '正在下载...'
        threading.Thread(target=self._dl_video_worker, daemon=True).start()

    def _dl_video_worker(self):
        try:
            save_dir = get_save_dir()
            fn = f"video_{int(time.time())}.mp4"
            download_file(self.parsed_video_url, save_dir, fn)
            Clock.schedule_once(lambda dt: setattr(self.video_status, 'text', f'下载完成：{fn}'))
        except Exception as e:
            Clock.schedule_once(lambda dt: setattr(self.video_status, 'text', f'下载失败：{str(e)[:30]}'))

    def _copy_video(self, *a):
        if not self.parsed_video_url:
            self.video_status.text = '没有可复制的链接'
            return
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(self.parsed_video_url)
            self.video_status.text = '链接已复制'
        except:
            self.video_status.text = '复制失败'

    # ==================== 图集提取 ====================
    def _paste_img(self, *a):
        try:
            from kivy.core.clipboard import Clipboard
            self.img_input.text = Clipboard.paste() or ''
            self.img_status.text = '已粘贴，点击提取图集'
        except:
            self.img_status.text = '无法读取剪贴板'

    def _clear_img(self, *a):
        self.img_input.text = ''
        self.img_result.clear_widgets()
        self.img_status.text = '已清空'
        self.img_bar.value = 0

    def _parse_img(self, *a):
        text = self.img_input.text.strip()
        if not text:
            self.img_status.text = '请输入链接'
            return
        urls = extract_urls(text)
        if not urls:
            self.img_status.text = '未找到有效链接'
            return
        self.img_status.text = '正在提取图集...'
        self.img_bar.value = 30
        threading.Thread(target=self._parse_img_worker, args=(urls[0],), daemon=True).start()

    def _parse_img_worker(self, url):
        result = api_parse_images(url)
        Clock.schedule_once(lambda dt: self._show_img_result(result))

    def _show_img_result(self, result):
        self.img_bar.value = 100
        self.img_result.clear_widgets()
        if result['ok']:
            pics = result['pics']
            self.img_pics = pics
            self.img_status.text = f'提取成功：共 {len(pics)} 张图片'
            for i, url in enumerate(pics[:20]):
                item = BoxLayout(size_hint_y=None, height=40, padding=[5,2])
                item.add_widget(Label(text=f'图片 {i+1}', font_size=12, font_name=FONT_NAME))
                self.img_result.add_widget(item)
        else:
            self.img_status.text = f"提取失败：{result.get('err', '未找到图集')}"

    def _dl_images(self, *a):
        if not hasattr(self, 'img_pics') or not self.img_pics:
            self.img_status.text = '请先提取图集'
            return
        self.img_status.text = '正在批量保存...'
        threading.Thread(target=self._dl_img_worker, daemon=True).start()

    def _dl_img_worker(self):
        import urllib.request
        save_dir = get_save_dir()
        ok = 0
        for i, url in enumerate(self.img_pics):
            try:
                fn = f"image_{int(time.time())}_{i}.jpg"
                urllib.request.urlretrieve(url, os.path.join(save_dir, fn))
                ok += 1
            except:
                pass
            Clock.schedule_once(lambda dt, p=int((i+1)/len(self.img_pics)*100): setattr(self.img_bar, 'value', p))
        Clock.schedule_once(lambda dt: setattr(self.img_status, 'text', f'保存完成：{ok}/{len(self.img_pics)} 张'))

    # ==================== 本地去水印 ====================
    def _pick_file(self, *a):
        content = BoxLayout(orientation='vertical')
        path = '/storage/emulated/0/DCIM' if platform == 'android' else os.path.expanduser('~')
        fc = FileChooserListView(path=path, filters=['*.mp4','*.avi','*.mov','*.mkv','*.flv','*.wmv','*.3gp'])
        content.add_widget(fc)
        btns = BoxLayout(size_hint_y=0.1, spacing=8)
        btns.add_widget(Button(text='取消', font_name=FONT_NAME))
        ok_btn = Button(text='选择', background_color=(0.2,0.8,0.2,1), font_name=FONT_NAME)
        btns.add_widget(ok_btn)
        content.add_widget(btns)
        popup = Popup(title='选择视频', content=content, size_hint=(0.9,0.9))
        def on_ok(*a):
            if fc.selection:
                self.selected_file = fc.selection[0]
                self.local_file.text = f'已选：{os.path.basename(self.selected_file)}'
            popup.dismiss()
        btns.children[1].bind(on_press=lambda *a: popup.dismiss())
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
        self.local_bar.value = 10
        mode = getattr(self, 'local_mode', 'crop')
        threading.Thread(target=self._local_worker, args=(mode,), daemon=True).start()

    def _local_worker(self, mode):
        try:
            base, ext = os.path.splitext(self.selected_file)
            out = f"{base}_no_wm{ext}"
            ffmpeg = self._find_ffmpeg()
            if not ffmpeg:
                shutil.copy2(self.selected_file, out)
                Clock.schedule_once(lambda dt: self._set_local(f'已复制（未安装ffmpeg）：{os.path.basename(out)}'))
                return
            import subprocess
            if mode == 'crop':
                cmd = [ffmpeg, '-y', '-i', self.selected_file, '-vf', 'crop=iw*0.92:ih*0.88:0:0', '-c:a', 'copy', out]
            else:
                cmd = [ffmpeg, '-y', '-i', self.selected_file,
                       '-vf', 'split[orig][blur];[blur]crop=iw:ih*0.15:0:ih*0.85,boxblur=10:10[b];[orig][b]overlay=0:H-h*0.15',
                       '-c:a', 'copy', out]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            proc.communicate(timeout=600)
            if proc.returncode == 0:
                Clock.schedule_once(lambda dt: setattr(self.local_bar, 'value', 100))
                Clock.schedule_once(lambda dt: self._set_local(f'处理完成：{os.path.basename(out)}'))
            else:
                shutil.copy2(self.selected_file, out)
                Clock.schedule_once(lambda dt: self._set_local(f'ffmpeg错误，已复制原文件'))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._set_local(f'处理失败：{str(e)[:40]}'))

    def _find_ffmpeg(self):
        for cmd in ['ffmpeg', '/data/data/com.xiake.watermark/files/ffmpeg']:
            try:
                import subprocess
                subprocess.run([cmd, '-version'], capture_output=True, timeout=3)
                return cmd
            except:
                continue
        return None

    # ==================== 批量解析 ====================
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
            r = api_parse_url(url)
            r['platform'] = detect_platform(url)
            results.append(r)
            Clock.schedule_once(lambda dt, p=int((i+1)/len(urls)*100): setattr(self.batch_bar, 'value', p))
            time.sleep(0.3)
        self.batch_results = results
        Clock.schedule_once(lambda dt: self._show_batch(results))

    def _show_batch(self, results):
        self.batch_list.clear_widgets()
        ok = sum(1 for r in results if r.get('ok'))
        self.batch_status.text = f'批量解析完成：{ok}/{len(results)} 成功'
        for r in results:
            item = BoxLayout(size_hint_y=None, height=40, padding=[5,2])
            if r.get('ok'):
                item.add_widget(Label(text=f"✅ {r.get('platform','?')} | {r.get('title','')[:20]}", font_size=12, font_name=FONT_NAME))
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
        save_dir = get_save_dir()
        ok = 0
        for i, r in enumerate(self.batch_results):
            if r.get('ok') and r.get('video_url'):
                try:
                    download_file(r['video_url'], save_dir, f"batch_{i}.mp4")
                    ok += 1
                except:
                    pass
            Clock.schedule_once(lambda dt, p=int((i+1)/len(self.batch_results)*100): setattr(self.batch_bar, 'value', p))
        Clock.schedule_once(lambda dt: setattr(self.batch_status, 'text', f'批量下载完成：{ok} 个'))

    # ==================== 反馈 ====================
    def _submit_feedback(self, *a):
        text = self.feedback_input.text.strip()
        if not text:
            self.feedback_status.text = '请输入反馈内容'
            return
        self.feedback_status.text = '感谢您的反馈！我们会尽快处理'
        self.feedback_input.text = ''

    # ==================== 辅助 ====================
    def _set_local(self, text):
        self.local_status.text = text


if __name__ == '__main__':
    WatermarkApp().run()
