# -*- coding: utf-8 -*-
"""
PK10 投注助手 - Kivy 完整移动版 v4.0
基于原版 tkinter 程序 (pk10v9.35.py) 完整重写
功能：登录验证码 / 游戏切换 / 开奖显示 / 批量投注 / 自定义追号 / 余额刷新
适用：Android APK (Buildozer 编译)
"""

import kivy
kivy.require('2.1.0')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.image import Image as KivyImage
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.properties import StringProperty, BooleanProperty, NumericProperty, ObjectProperty
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, Rectangle, RoundedRectangle, Ellipse
from kivy.core.image import Image as CoreImage

import requests
import threading
import time
import json
import os
import re
import base64
from datetime import datetime
from io import BytesIO

# ===== 全局配置 =====
GAMES = {
    "极速赛车":  {"lotCode": "10037", "lottery_url_code": "PK10JSC"},
    "幸运飞艇":  {"lotCode": "10057", "lottery_url_code": "XYFT"},
    "极速飞艇":  {"lotCode": "10035", "lottery_url_code": "LUCKYSB"},
    "澳洲幸运10": {"lotCode": "10012", "lottery_url_code": "AULUCKY10"},
}

CURRENT_DRAW_API = "https://api.api68.com/pks/getLotteryPksInfo.do"
HISTORY_API     = "https://api.api68.com/pks/getPksHistoryList.do"

POS_TITLES = {
    "1": "冠军", "2": "亚军", "3": "季军", "4": "殿军",
    "5": "第五名", "6": "第六名", "7": "第七名",
    "8": "第八名", "9": "第九名", "10": "第十名",
}

# ===== 配色方案 =====
COLORS = {
    "bg": "#F0F4F8", "card": "#FFFFFF",
    "primary": "#3A7BD5", "primary_dk": "#2C60B0",
    "success": "#27AE60", "success_dk": "#1E8449",
    "danger": "#E74C3C", "warning": "#F39C12",
    "purple": "#8E44AD", "text": "#2C3E50",
    "text_sub": "#7F8C8D", "text_light": "#FFFFFF",
    "border": "#D5DDED", "input_bg": "#FAFCFF",
    "header_bg": "#1E3A5F", "header_ctrl": "#264A6E",
    "header_light": "#E8F0FE",
    "log_bg": "#0D1117", "log_text": "#C9D1D9",
}

# PK10 号码球颜色（每号固定颜色）
NUM_COLORS = {
    '1': '#17E2E5', '2': '#F9982E', '3': '#001822',
    '4': '#0092DD', '5': '#E6DE00', '6': '#F1010A',
    '7': '#BFBFBF', '8': '#0092DD', '9': '#5234FF',
    '10': '#07BF00',
}

def hex_to_rgb(hex_color, alpha=1.0):
    """十六进制颜色转 (r, g, b, a) 元组"""
    h = hex_color.lstrip('#')
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r, g, b, alpha)


# ===== API 客户端 =====
class APIClient:
    """处理所有网络请求（登录、开奖、投注、余额）"""

    def __init__(self):
        self.session = None
        self.base_url = "https://6942087513-ds.for9dong.com"
        self.logged_in = False
        self.account = ""
        self.balance = 0.0

    def _get_session(self):
        if self.session is None:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9',
            })
        return self.session

    # ── 验证码 ──
    def fetch_captcha(self):
        session = self._get_session()
        try:
            session.get(self.base_url + "/login", timeout=30)
        except:
            pass

        ts = int(time.time() * 1000)
        urls = [
            self.base_url + f"/code?_={ts}",
            self.base_url + "/code",
            self.base_url + f"/captcha?_={ts}",
            self.base_url + "/captcha",
        ]
        captcha_data = None
        for url in urls:
            try:
                r = session.get(url, timeout=15)
                if r.status_code == 200 and len(r.content) > 100:
                    ct = (r.headers.get("Content-Type") or "").lower()
                    if ct.startswith("image/") or (ct == "" and not r.content[:5].startswith(b"<")):
                        captcha_data = r.content
                        break
            except:
                continue

        if captcha_data:
            return True, captcha_data
        return False, "获取验证码失败"

    # ── 登录 ──
    def login(self, account, password, code=""):
        session = self._get_session()
        login_url = self.base_url + "/login"
        data = {
            "type": "", "account": account,
            "password": password, "code": code, "submit": "登录"
        }
        headers = {
            'Referer': login_url,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': self.base_url,
        }
        try:
            resp = session.post(login_url, data=data, headers=headers,
                                allow_redirects=False, timeout=30)
            success = False
            if resp.status_code in [301, 302, 303, 307, 308]:
                loc = resp.headers.get("Location", "").strip()
                if "login" not in loc and "fail" not in loc.lower():
                    success = True
                    if not loc.startswith(("http://", "https://")):
                        loc = self.base_url.rstrip("/") + "/" + loc.lstrip("/")
                    session.get(loc, allow_redirects=True, timeout=30)
            else:
                pt = resp.text.lower()
                if "退出" in pt or "logout" in pt or "member" in pt:
                    success = True

            if success:
                self.logged_in = True
                self.account = account
                # 登录后获取余额
                try:
                    self._fetch_balance_internal()
                except:
                    pass
                return True, "登录成功"

            # 解析错误信息
            error_msg = "登录失败"
            if resp.status_code in [301, 302]:
                loc = resp.headers.get("Location", "")
                if '?e=' in loc:
                    error_msg = f"登录失败(错误代码: {loc.split('?e=')[-1][:20]})"
            return False, error_msg

        except Exception as e:
            return False, f"网络错误: {str(e)[:50]}"

    def _fetch_balance_internal(self):
        """内部获取余额"""
        session = self._get_session()
        try:
            r = session.get(self.base_url + "/member", timeout=15)
            m = re.search(r'余额[：:]\s*<[^>]*>\s*[¥￥]?\s*([\d,.]+)', r.text)
            if m:
                self.balance = float(m.group(1).replace(',', ''))
            else:
                m2 = re.search(r'([\d,]+\.?\d*)\s*元?\s*</span>', r.text)
                if m2:
                    self.balance = float(m2.group(1).replace(',', ''))
        except:
            pass

    # ── 获取当前期开奖 ──
    def get_current_draw(self, game_name):
        game_info = GAMES.get(game_name)
        if not game_info:
            return None
        try:
            params = {"lotCode": game_info["lotCode"]}
            r = requests.get(CURRENT_DRAW_API, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict):
                    result = data.get("result", {}) or data.get("data", {})
                    if not result and isinstance(data.get("result"), list):
                        result = data["result"][0] if data["result"] else {}
                    if not result:
                        result = data
                    issue = str(result.get("drawIssue", result.get("preDrawIssue", "---")))
                    pre_code = str(result.get("preDrawCode", result.get("preDrawIssue", "")))
                    numbers = pre_code.split(",") if pre_code else []
                    next_issue = str(result.get("drawIssue", "---"))
                    return {
                        "issue": issue,
                        "numbers": numbers,
                        "next_issue": next_issue,
                        "pre_draw_time": result.get("preDrawTime", ""),
                    }
        except Exception as e:
            print(f"获取开奖失败: {e}")
        return None

    # ── 投注 ──
    def submit_bet(self, lottery_code, issue, position, number, amount, lot_code):
        """提交单注投注"""
        session = self._get_session()
        bet_url = self.base_url + "/api/bet/submit"

        data = {
            "lotCode": lot_code,
            "playCode": "dfsm",
            "betCode": f"{position},{number}",
            "amount": int(amount),
            "issue": str(issue),
            "betType": 1,
        }
        headers = {
            'Referer': self.base_url + '/member/bet',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        try:
            r = session.post(bet_url, data=data, headers=headers, timeout=15)
            if r.status_code == 200:
                try:
                    resp = r.json()
                    if isinstance(resp, dict):
                        code = resp.get("code")
                        msg = resp.get("msg", "")
                        if code in [200, 0] or "成功" in str(msg):
                            return True, str(msg) if msg else "投注成功"
                        return False, str(msg) if msg else "投注失败"
                except:
                    if "成功" in r.text:
                        return True, "投注成功"
            return False, f"HTTP {r.status_code}"
        except Exception as e:
            return False, f"网络错误: {str(e)[:40]}"

    # ── 刷新余额 ──
    def refresh_balance(self):
        try:
            self._fetch_balance_internal()
            return True, self.balance
        except:
            return False, 0

    # ── 登出 ──
    def logout(self):
        self.logged_in = False
        self.account = ""
        self.balance = 0.0
        self.session = None


# ===== 登录界面 =====
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "login"
        self.captcha_data = None

        # 外层 ScrollView 确保小屏能滚动
        root = ScrollView()
        main = BoxLayout(orientation='vertical', padding=['30dp', '40dp'], spacing='20dp')
        main.size_hint_y = None
        main.bind(minimum_height=main.setter('height'))

        # Logo
        logo = Label(
            text="PK10 投注助手",
            font_size='32sp', bold=True,
            color=hex_to_rgb(COLORS["primary"]),
            size_hint_y=None, height='60dp',
            halign='center'
        )
        main.add_widget(logo)

        sub = Label(
            text="极速赛车 · 幸运飞艇 · 澳洲幸运10",
            font_size='13sp',
            color=hex_to_rgb(COLORS["text_sub"]),
            size_hint_y=None, height='30dp'
        )
        main.add_widget(sub)

        # 网址输入
        main.add_widget(Label(text="网站地址", size_hint_y=None, height='25dp',
                               font_size='13sp', halign='left',
                               color=hex_to_rgb(COLORS["text_sub"])))
        self.url_input = self._make_input("https://6942087513-ds.for9dong.com")
        main.add_widget(self.url_input)

        # 账号
        main.add_widget(Label(text="账号", size_hint_y=None, height='25dp',
                               font_size='13sp', halign='left',
                               color=hex_to_rgb(COLORS["text_sub"])))
        self.account_input = self._make_input("")
        main.add_widget(self.account_input)

        # 密码
        main.add_widget(Label(text="密码", size_hint_y=None, height='25dp',
                               font_size='13sp', halign='left',
                               color=hex_to_rgb(COLORS["text_sub"])))
        self.pwd_input = TextInput(
            multiline=False, password=True, hint_text="请输入密码",
            size_hint_y=None, height='48dp', font_size='16sp',
            padding=['12dp', '10dp'], write_tab=False
        )
        main.add_widget(self.pwd_input)

        # 验证码行
        code_row = BoxLayout(orientation='horizontal', size_hint_y=None, height='60dp', spacing='10dp')
        self.captcha_img = KivyImage(
            size_hint_x=None, width='120dp',
            allow_stretch=True, keep_ratio=True
        )
        with self.captcha_img.canvas.before:
            Color(*hex_to_rgb("#E0E6ED"))
            self._captcha_bg = Rectangle(pos=self.captcha_img.pos, size=self.captcha_img.size)
        self.captcha_img.bind(pos=self._update_captcha_bg, size=self._update_captcha_bg)
        code_row.add_widget(self.captcha_img)

        self.code_input = TextInput(
            multiline=False, hint_text="验证码",
            size_hint_y=None, height='48dp', font_size='18sp',
            padding=['10dp', '10dp'], write_tab=False,
            halign='center'
        )
        code_row.add_widget(self.code_input)

        get_captcha_btn = Button(
            text="获取", size_hint_x=None, width='70dp',
            size_hint_y=None, height='48dp',
            background_normal='', background_color=hex_to_rgb(COLORS["warning"]),
            color=hex_to_rgb(COLORS["text_light"]),
            font_size='13sp', bold=True
        )
        get_captcha_btn.bind(on_press=self._on_get_captcha)
        code_row.add_widget(get_captcha_btn)
        main.add_widget(code_row)

        # 状态提示
        self.status_label = Label(
            text="请先获取验证码", size_hint_y=None, height='25dp',
            font_size='12sp', color=hex_to_rgb(COLORS["text_sub"])
        )
        main.add_widget(self.status_label)

        # 登录按钮
        self.login_btn = Button(
            text="登  录", size_hint_y=None, height='55dp',
            background_normal='', background_color=hex_to_rgb(COLORS["primary"]),
            color=hex_to_rgb(COLORS["text_light"]),
            font_size='22sp', bold=True
        )
        self.login_btn.bind(on_press=self._do_login)
        main.add_widget(self.login_btn)

        # 版本信息
        main.add_widget(Label(
            text="v4.0 Kivy 移动版 · Buildozer APK",
            font_size='11sp', color=hex_to_rgb(COLORS["text_sub"]),
            size_hint_y=None, height='25dp'
        ))

        root.add_widget(main)
        self.add_widget(root)

    def _make_input(self, default_text=""):
        t = TextInput(
            text=default_text, multiline=False,
            size_hint_y=None, height='48dp', font_size='16sp',
            padding=['12dp', '10dp'], write_tab=False
        )
        return t

    def _update_captcha_bg(self, instance, value):
        self._captcha_bg.pos = instance.pos
        self._captcha_bg.size = instance.size

    def _on_get_captcha(self, instance):
        self.status_label.text = "正在获取验证码..."
        self.status_label.color = hex_to_rgb(COLORS["primary"])

        api = App.get_running_app().api
        if self.url_input.text.strip():
            api.base_url = self.url_input.text.strip()

        def fetch():
            ok, data = api.fetch_captcha()
            if ok:
                self.captcha_data = data
                Clock.schedule_once(self._show_captcha, 0)
            else:
                Clock.schedule_once(lambda dt: self._set_status("获取失败，请重试", COLORS["danger"]), 0)

        threading.Thread(target=fetch, daemon=True).start()

    @mainthread
    def _show_captcha(self, dt):
        try:
            from io import BytesIO
            data = BytesIO(self.captcha_data)
            self.captcha_img.texture = CoreImage(data, ext="png").texture
            self.status_label.text = "验证码已获取，请输入"
            self.status_label.color = hex_to_rgb(COLORS["success"])
        except Exception as e:
            self.status_label.text = f"验证码显示失败: {e}"
            self.status_label.color = hex_to_rgb(COLORS["danger"])

    def _set_status(self, text, color):
        self.status_label.text = text
        self.status_label.color = hex_to_rgb(color)

    def _do_login(self, instance):
        url = self.url_input.text.strip()
        account = self.account_input.text.strip()
        password = self.pwd_input.text.strip()
        code = self.code_input.text.strip()

        if not account or not password:
            self._set_status("请输入账号和密码", COLORS["warning"])
            return

        self._set_status("登录中...", COLORS["primary"])
        self.login_btn.disabled = True

        api = App.get_running_app().api
        if url:
            api.base_url = url.rstrip('/')

        def login_thread():
            ok, msg = api.login(account, password, code)
            if ok:
                Clock.schedule_once(lambda dt: App.get_running_app().on_login_success(), 0)
            else:
                Clock.schedule_once(lambda dt: self._on_login_fail(msg), 0)

        threading.Thread(target=login_thread, daemon=True).start()

    @mainthread
    def _on_login_fail(self, msg):
        self._set_status(msg, COLORS["danger"])
        self.login_btn.disabled = False


# ===== 主界面 =====
class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "main"
        self.current_game = "极速赛车"
        self.chase_active = False
        self.chase_position = 5
        self.chase_target_nums = [1, 2, 3, 8, 9, 10]
        self.chase_sequence = [1, 3, 7, 15, 31, 63, 127, 255]
        self.chase_current_step = 0
        self.chase_bet_issue = None
        self.chase_last_attempted = None
        self.chase_history = []
        self.chase_submitting = False

        main = BoxLayout(orientation='vertical')

        # 顶部开奖信息栏
        main.add_widget(self._build_header())

        # Tab 面板
        main.add_widget(self._build_tabs())

        self.add_widget(main)

        # 定时刷新
        Clock.schedule_interval(self._auto_refresh, 5)

    # ━━━━━━━━ 顶部栏 ━━━━━━━━
    def _build_header(self):
        header = BoxLayout(size_hint_y=None, height='120dp',
                           padding=['8dp', '4dp'], spacing='6dp')

        with header.canvas.before:
            Color(*hex_to_rgb(COLORS["header_bg"]))
            self._hdr_bg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=self._upd_hdr_bg, size=self._upd_hdr_bg)

        # 左侧：游戏选择
        left = BoxLayout(orientation='vertical', size_hint_x=None, width='125dp', spacing='4dp')
        left.add_widget(Label(text="选择游戏", size_hint_y=None, height='20dp',
                               font_size='11sp', color=hex_to_rgb(COLORS["header_light"]),
                               halign='left'))
        self.game_spinner = Spinner(
            text="极速赛车",
            values=list(GAMES.keys()),
            size_hint_y=None, height='38dp',
            background_normal='', background_color=hex_to_rgb(COLORS["header_ctrl"]),
            color=hex_to_rgb(COLORS["text_light"]), font_size='14sp'
        )
        self.game_spinner.bind(text=self._on_game_change)
        left.add_widget(self.game_spinner)
        header.add_widget(left)

        # 中间：开奖信息
        center = BoxLayout(orientation='vertical', spacing='2dp')
        self.issue_label = Label(
            text="期号: ---",
            size_hint_y=None, height='22dp',
            color=hex_to_rgb(COLORS["header_light"]),
            font_size='13sp', bold=True
        )
        center.add_widget(self.issue_label)

        # 号码球行
        self.balls_box = BoxLayout(
            size_hint_y=None, height='40dp', spacing='2dp'
        )
        for i in range(10):
            ball = Label(text=str(i+1), bold=True,
                          size_hint_x=None, width='30dp',
                          size_hint_y=None, height='30dp',
                          font_size='12sp')
            ball.color = hex_to_rgb("#888")
            self.balls_box.add_widget(ball)
        center.add_widget(self.balls_box)

        # 倒计时
        self.countdown_label = Label(
            text="--:--",
            size_hint_y=None, height='24dp',
            color=hex_to_rgb("#FF6B6B"), font_size='18sp', bold=True
        )
        center.add_widget(self.countdown_label)
        header.add_widget(center)

        # 右侧：余额+操作
        right = BoxLayout(orientation='vertical', size_hint_x=None, width='110dp', spacing='4dp')
        self.balance_label = Label(
            text="余额\n¥ ---",
            size_hint_y=None, height='50dp',
            color=hex_to_rgb(COLORS["success"]), font_size='12sp',
            halign='right', valign='middle'
        )
        right.add_widget(self.balance_label)

        btns = BoxLayout(orientation='horizontal', size_hint_y=None, height='36dp', spacing='4dp')
        refresh_btn = Button(
            text="刷新", size_hint_x=None, width='48dp',
            background_normal='', background_color=hex_to_rgb(COLORS["header_ctrl"]),
            color=hex_to_rgb(COLORS["text_light"]), font_size='10sp'
        )
        refresh_btn.bind(on_press=lambda x: self._refresh_draw())
        btns.add_widget(refresh_btn)

        logout_btn = Button(
            text="退出", size_hint_x=None, width='48dp',
            background_normal='', background_color=hex_to_rgb(COLORS["danger"]),
            color=hex_to_rgb(COLORS["text_light"]), font_size='10sp'
        )
        logout_btn.bind(on_press=self._do_logout)
        btns.add_widget(logout_btn)
        right.add_widget(btns)
        header.add_widget(right)

        return header

    def _upd_hdr_bg(self, instance, value):
        self._hdr_bg.pos = instance.pos
        self._hdr_bg.size = instance.size

    # ━━━━━━━━ Tab面板 ━━━━━━━━
    def _build_tabs(self):
        self.tabs = TabbedPanel(do_default_tab=False, tab_height='42dp',
                                 tab_width='120dp')
        # 投注 tab
        bet_tab = TabbedPanelItem(text="投注")
        bet_tab.add_widget(self._build_bet_tab())
        self.tabs.add_widget(bet_tab)
        # 追号 tab
        chase_tab = TabbedPanelItem(text="追号")
        chase_tab.add_widget(self._build_chase_tab())
        self.tabs.add_widget(chase_tab)
        # 日志 tab
        log_tab = TabbedPanelItem(text="日志")
        log_tab.add_widget(self._build_log_tab())
        self.tabs.add_widget(log_tab)
        return self.tabs

    # ━━━━━━━━ 投注标签 ━━━━━━━━
    def _build_bet_tab(self):
        scroll = ScrollView()
        layout = BoxLayout(orientation='vertical', spacing='12dp',
                           size_hint_y=None, padding='10dp')
        layout.bind(minimum_height=layout.setter('height'))

        # 名次选择
        layout.add_widget(Label(
            text="选择名次（可多选）", size_hint_y=None, height='30dp',
            font_size='15sp', bold=True, halign='left',
            color=hex_to_rgb(COLORS["text"])
        ))
        self.pos_checks = {}
        pos_grid = GridLayout(cols=5, spacing='6dp', size_hint_y=None, height='90dp')
        for i in range(1, 11):
            row = BoxLayout(orientation='horizontal', spacing='2dp')
            cb = CheckBox(color=hex_to_rgb(COLORS["primary"]), size_hint_x=None, width='35dp')
            lbl = Label(text=f"第{i}名", font_size='11sp',
                        size_hint_x=None, width='65dp',
                        color=hex_to_rgb(COLORS["text"]))
            row.add_widget(cb); row.add_widget(lbl)
            pos_grid.add_widget(row)
            self.pos_checks[str(i)] = cb
        layout.add_widget(pos_grid)

        # 全选按钮
        btn_row = BoxLayout(size_hint_y=None, height='32dp', spacing='8dp')
        all_pos = Button(text="全选名次", size_hint_y=None, height='32dp',
                          background_normal='', background_color=hex_to_rgb("#E8F4FD"),
                          color=hex_to_rgb(COLORS["primary"]), font_size='11sp')
        all_pos.bind(on_press=lambda x: self._toggle_all_pos(True))
        btn_row.add_widget(all_pos)
        none_pos = Button(text="取消名次", size_hint_y=None, height='32dp',
                           background_normal='', background_color=hex_to_rgb("#F0F0F0"),
                           color=hex_to_rgb(COLORS["text_sub"]), font_size='11sp')
        none_pos.bind(on_press=lambda x: self._toggle_all_pos(False))
        btn_row.add_widget(none_pos)
        layout.add_widget(btn_row)

        # 号码选择
        layout.add_widget(Label(
            text="选择号码（可多选）", size_hint_y=None, height='30dp',
            font_size='15sp', bold=True, halign='left',
            color=hex_to_rgb(COLORS["text"])
        ))
        self.num_checks = {}
        num_grid = GridLayout(cols=5, spacing='6dp', size_hint_y=None, height='90dp')
        for i in range(1, 11):
            s = str(i)
            row = BoxLayout(orientation='horizontal', spacing='2dp')
            cb = CheckBox(color=hex_to_rgb(COLORS["primary"]), size_hint_x=None, width='35dp')
            lbl = Label(text=s, font_size='12sp', bold=True,
                        size_hint_x=None, width='40dp',
                        color=hex_to_rgb(NUM_COLORS.get(s, "#888")))
            row.add_widget(cb); row.add_widget(lbl)
            num_grid.add_widget(row)
            self.num_checks[s] = cb
        layout.add_widget(num_grid)

        btn_row2 = BoxLayout(size_hint_y=None, height='32dp', spacing='8dp')
        all_num = Button(text="全选号码", size_hint_y=None, height='32dp',
                          background_normal='', background_color=hex_to_rgb("#E8F4FD"),
                          color=hex_to_rgb(COLORS["primary"]), font_size='11sp')
        all_num.bind(on_press=lambda x: self._toggle_all_num(True))
        btn_row2.add_widget(all_num)
        none_num = Button(text="取消号码", size_hint_y=None, height='32dp',
                           background_normal='', background_color=hex_to_rgb("#F0F0F0"),
                           color=hex_to_rgb(COLORS["text_sub"]), font_size='11sp')
        none_num.bind(on_press=lambda x: self._toggle_all_num(False))
        btn_row2.add_widget(none_num)
        layout.add_widget(btn_row2)

        # 金额
        amt_row = BoxLayout(orientation='horizontal', size_hint_y=None, height='45dp', spacing='8dp')
        amt_row.add_widget(Label(text="金额/注:", size_hint_x=None, width='80dp',
                                  font_size='15sp', halign='right',
                                  color=hex_to_rgb(COLORS["text"])))
        self.amount_input = TextInput(
            text="10", multiline=False, input_filter='int',
            size_hint_y=None, height='42dp', font_size='16sp',
            padding=['10dp', '8dp'], write_tab=False
        )
        amt_row.add_widget(self.amount_input)
        layout.add_widget(amt_row)

        # 投注按钮
        bet_btn = Button(
            text="立即投注", size_hint_y=None, height='55dp',
            background_normal='', background_color=hex_to_rgb(COLORS["success"]),
            color=hex_to_rgb(COLORS["text_light"]),
            font_size='20sp', bold=True
        )
        bet_btn.bind(on_press=self._do_bet)
        layout.add_widget(bet_btn)

        scroll.add_widget(layout)
        return scroll

    def _toggle_all_pos(self, state):
        for cb in self.pos_checks.values():
            cb.active = state

    def _toggle_all_num(self, state):
        for cb in self.num_checks.values():
            cb.active = state

    # ━━━━━━━━ 追号标签 ━━━━━━━━
    def _build_chase_tab(self):
        scroll = ScrollView()
        layout = BoxLayout(orientation='vertical', spacing='12dp',
                           size_hint_y=None, padding='10dp')
        layout.bind(minimum_height=layout.setter('height'))

        layout.add_widget(Label(
            text="自定义追号投注\n选择一个名次 + 目标号码 + 金额序列\n中奖后自动重置第一步，未中则按序列递增",
            size_hint_y=None, height='65dp', font_size='12sp',
            halign='left', valign='top',
            color=hex_to_rgb(COLORS["text_sub"])
        ))

        # 名次
        row1 = BoxLayout(orientation='horizontal', size_hint_y=None, height='42dp', spacing='8dp')
        row1.add_widget(Label(text="追号名次:", size_hint_x=None, width='90dp',
                               font_size='14sp', halign='right',
                               color=hex_to_rgb(COLORS["text"])))
        self.chase_pos_spinner = Spinner(
            text="5", values=[str(i) for i in range(1, 11)],
            size_hint_x=None, width='80dp', height='40dp'
        )
        row1.add_widget(self.chase_pos_spinner)
        layout.add_widget(row1)

        # 目标号码
        row2 = BoxLayout(orientation='horizontal', size_hint_y=None, height='42dp', spacing='8dp')
        row2.add_widget(Label(text="目标号码:", size_hint_x=None, width='90dp',
                               font_size='14sp', halign='right',
                               color=hex_to_rgb(COLORS["text"])))
        self.chase_num_input = TextInput(
            text="1,2,3,8,9,10", multiline=False,
            size_hint_y=None, height='40dp', font_size='14sp',
            padding=['10dp', '8dp'], write_tab=False
        )
        row2.add_widget(self.chase_num_input)
        layout.add_widget(row2)

        # 金额序列
        row3 = BoxLayout(orientation='horizontal', size_hint_y=None, height='42dp', spacing='8dp')
        row3.add_widget(Label(text="金额序列:", size_hint_x=None, width='90dp',
                               font_size='14sp', halign='right',
                               color=hex_to_rgb(COLORS["text"])))
        self.chase_seq_input = TextInput(
            text="1,3,7,15,31,63,127,255", multiline=False,
            size_hint_y=None, height='40dp', font_size='14sp',
            padding=['10dp', '8dp'], write_tab=False
        )
        row3.add_widget(self.chase_seq_input)
        layout.add_widget(row3)

        # 控制按钮
        btns = BoxLayout(orientation='horizontal', size_hint_y=None, height='48dp', spacing='10dp')
        self.chase_start_btn = Button(
            text="开始追号", background_normal='',
            background_color=hex_to_rgb(COLORS["primary"]),
            color=hex_to_rgb(COLORS["text_light"]),
            font_size='16sp', bold=True
        )
        self.chase_start_btn.bind(on_press=self._start_chase)
        btns.add_widget(self.chase_start_btn)

        self.chase_stop_btn = Button(
            text="停止追号", background_normal='',
            background_color=hex_to_rgb(COLORS["danger"]),
            color=hex_to_rgb(COLORS["text_light"]),
            font_size='16sp', bold=True,
            disabled=True
        )
        self.chase_stop_btn.bind(on_press=self._stop_chase)
        btns.add_widget(self.chase_stop_btn)
        layout.add_widget(btns)

        # 状态
        self.chase_status_label = Label(
            text="状态: 未启动", size_hint_y=None, height='28dp',
            font_size='13sp', color=hex_to_rgb(COLORS["text"]), halign='left'
        )
        layout.add_widget(self.chase_status_label)

        # 追号历史
        layout.add_widget(Label(
            text="追号历史:", size_hint_y=None, height='25dp',
            font_size='13sp', color=hex_to_rgb(COLORS["text"]), halign='left'
        ))
        self.chase_history_label = Label(
            text="尚无记录", size_hint_y=None, height='120dp',
            font_size='11sp', color=hex_to_rgb(COLORS["text_sub"]),
            halign='left', valign='top'
        )
        layout.add_widget(self.chase_history_label)

        scroll.add_widget(layout)
        return scroll

    # ━━━━━━━━ 日志标签 ━━━━━━━━
    def _build_log_tab(self):
        box = BoxLayout(orientation='vertical', spacing='8dp', padding='8dp')
        title_row = BoxLayout(orientation='horizontal', size_hint_y=None, height='38dp')
        title_row.add_widget(Label(
            text="运行日志", font_size='16sp', bold=True,
            color=hex_to_rgb(COLORS["text"]), halign='left'
        ))
        clear_btn = Button(
            text="清空", size_hint_x=None, width='70dp',
            background_normal='', background_color=hex_to_rgb(COLORS["text_sub"]),
            color=hex_to_rgb(COLORS["text_light"]), font_size='12sp'
        )
        clear_btn.bind(on_press=lambda x: setattr(self, '_log_text_widget', None) or
                       setattr(self.log_input, 'text', ''))
        title_row.add_widget(clear_btn)
        box.add_widget(title_row)

        self.log_input = TextInput(
            readonly=True, font_name="RobotoMono",
            font_size='11sp', background_color=hex_to_rgb(COLORS["log_bg"]),
            foreground_color=hex_to_rgb(COLORS["log_text"]),
            padding=['8dp', '8dp']
        )
        box.add_widget(self.log_input)
        return box

    # ━━━━━━━━ 功能方法 ━━━━━━━━
    def _on_game_change(self, spinner, text):
        self.current_game = text
        app = App.get_running_app()
        app.log(f"切换游戏: {text}")
        self._refresh_draw()

    def _refresh_draw(self):
        app = App.get_running_app()
        if not app.api.logged_in:
            return

        def fetch():
            data = app.api.get_current_draw(self.current_game)
            if data:
                Clock.schedule_once(lambda dt: self._update_draw(data), 0)

        threading.Thread(target=fetch, daemon=True).start()

    @mainthread
    def _update_draw(self, data):
        self.issue_label.text = f"期号: {data.get('issue', '---')}"

        # 更新号码球
        numbers = data.get('numbers', [])
        balls = self.balls_box.children
        balls_list = list(reversed(balls))
        for i, child in enumerate(balls_list):
            if i < len(numbers):
                n = numbers[i]
                child.text = n
                child.color = hex_to_rgb("#FFFFFF")
                # 清除旧背景并绘制彩色圆
                child.canvas.before.clear()
                with child.canvas.before:
                    Color(*hex_to_rgb(NUM_COLORS.get(n, '#999999')))
                    RoundedRectangle(
                        pos=(child.x + 2, child.y + 2),
                        size=('26dp', '26dp'), radius=[13]
                    )
            else:
                child.text = "-"
                child.color = hex_to_rgb("#888")
                child.canvas.before.clear()

        self.countdown_label.text = "--:--"

    # 自动刷新
    def _auto_refresh(self, dt):
        if self.chase_active:
            self._check_chase_result()
        else:
            self._refresh_draw()
        return True

    # ━━━━━━━━ 投注逻辑 ━━━━━━━━
    def _do_bet(self, instance):
        app = App.get_running_app()
        if not app.api.logged_in:
            self._show_toast("请先登录！")
            return

        positions = [p for p, cb in self.pos_checks.items() if cb.active]
        numbers = [n for n, cb in self.num_checks.items() if cb.active]

        if not positions:
            self._show_toast("请选择至少一个名次！")
            return
        if not numbers:
            self._show_toast("请选择至少一个号码！")
            return

        amt = self.amount_input.text
        if not amt or int(amt) <= 0:
            self._show_toast("请输入有效金额！")
            return

        total = len(positions) * len(numbers)
        total_amt = int(amt) * total

        # 确认弹窗
        msg = f"确认投注？\n\n场次×{len(positions)}  号码×{len(numbers)}\n共{total}注  ¥{total_amt}"
        self._confirm_popup("确认投注", msg, lambda: self._submit_bets(positions, numbers, amt))

    def _submit_bets(self, positions, numbers, amount):
        app = App.get_running_app()
        game = GAMES.get(self.current_game, {})
        lottery_code = game.get("lottery_url_code", "")
        lot_code = game.get("lotCode", "")

        # 获取最新期号
        draw = app.api.get_current_draw(self.current_game)
        issue = draw.get("next_issue", "") if draw else ""

        def submit_thread():
            ok_count = 0
            fail_count = 0
            for pos in positions:
                for num in numbers:
                    ok, msg = app.api.submit_bet(lottery_code, issue, pos, num, amount, lot_code)
                    if ok:
                        ok_count += 1
                    else:
                        fail_count += 1
                        app.log(f"投注失败 [{pos},{num}]: {msg}")
            Clock.schedule_once(
                lambda dt: self._on_bet_done(ok_count, fail_count, positions, numbers), 0)

        threading.Thread(target=submit_thread, daemon=True).start()
        app.log(f"投注中: {len(positions)}场次 × {len(numbers)}号码 = {len(positions)*len(numbers)}注")

    @mainthread
    def _on_bet_done(self, ok, fail, positions, numbers):
        self._show_toast(f"投注完成!\n成功: {ok}  失败: {fail}")
        App.get_running_app().log(f"投注结果: 成功{ok} 失败{fail}")

    # ━━━━━━━━ 追号逻辑 ━━━━━━━━
    def _start_chase(self, instance):
        app = App.get_running_app()
        if not app.api.logged_in:
            self._show_toast("请先登录！")
            return

        try:
            pos = int(self.chase_pos_spinner.text)
            nums = [int(x.strip()) for x in self.chase_num_input.text.split(',') if x.strip()]
            seq = [int(x.strip()) for x in self.chase_seq_input.text.split(',') if x.strip()]
            if not seq:
                raise ValueError("序列为空")
        except Exception as e:
            self._show_toast(f"配置错误: {e}")
            return

        self.chase_position = pos
        self.chase_target_nums = nums
        self.chase_sequence = seq
        self.chase_current_step = 0
        self.chase_bet_issue = None
        self.chase_history = []
        self.chase_active = True

        pos_title = POS_TITLES.get(str(pos), f"第{pos}名")
        app.log(f"★ 追号启动: {pos_title} 号码{nums} 序列{seq}")

        self.chase_start_btn.disabled = True
        self.chase_stop_btn.disabled = False
        self._update_chase_status()

        # 立即投注
        self._execute_chase_bet()

    def _stop_chase(self, instance=None):
        was_active = self.chase_active
        self.chase_active = False
        self.chase_bet_issue = None
        self.chase_submitting = False
        self.chase_start_btn.disabled = False
        self.chase_stop_btn.disabled = True
        self.chase_status_label.text = "状态: 已停止"
        self.chase_status_label.color = hex_to_rgb(COLORS["danger"])

        if was_active and self.chase_history:
            hits = sum(1 for h in self.chase_history if h['hit'])
            App.get_running_app().log(f"追号停止: {len(self.chase_history)}期中{hits}次")

    def _execute_chase_bet(self):
        if not self.chase_active or self.chase_submitting:
            return
        if self.chase_current_step >= len(self.chase_sequence):
            App.get_running_app().log("追号序列用完，自动停止")
            self._stop_chase()
            return

        self.chase_submitting = True
        app = App.get_running_app()
        game = GAMES.get(self.current_game, {})
        lottery_code = game.get("lottery_url_code", "")
        lot_code = game.get("lotCode", "")
        amt = self.chase_sequence[self.chase_current_step]

        draw = app.api.get_current_draw(self.current_game)
        issue = draw.get("next_issue", str(int(time.time()))) if draw else str(int(time.time()))
        self.chase_bet_issue = issue

        def submit():
            ok_count = 0
            for num in self.chase_target_nums:
                ok, msg = app.api.submit_bet(lottery_code, issue, str(self.chase_position),
                                             str(num), amt, lot_code)
                if ok:
                    ok_count += 1
                else:
                    app.log(f"追号投注失败 [{num}]: {msg}")

            self.chase_submitting = False
            if ok_count > 0:
                app.log(f"追号投注成功: {issue} ¥{amt}×{ok_count}")
            Clock.schedule_once(lambda dt: self._update_chase_status(), 0)

        threading.Thread(target=submit, daemon=True).start()

    def _check_chase_result(self):
        if not self.chase_active or not self.chase_bet_issue:
            return

        app = App.get_running_app()
        draw = app.api.get_current_draw(self.current_game)
        if not draw:
            return

        numbers = draw.get('numbers', [])
        current_issue = draw.get('issue', '')

        if not numbers or current_issue == self.chase_bet_issue:
            return

        # 获取指定名次的结果号码
        try:
            idx = self.chase_position - 1
            drawn = int(numbers[idx]) if idx < len(numbers) else 0
        except:
            return

        hit = drawn in self.chase_target_nums
        amt = self.chase_sequence[self.chase_current_step]

        self.chase_history.append({
            'issue': current_issue, 'drawn': drawn, 'hit': hit,
            'amount': amt, 'step': self.chase_current_step
        })
        self._update_chase_history()

        if hit:
            self.chase_current_step = 0
            app.log(f"追号命中! {current_issue}开出{drawn} ✓ 重置→¥{self.chase_sequence[0]}")
        else:
            self.chase_current_step += 1
            if self.chase_current_step >= len(self.chase_sequence):
                app.log(f"追号序列用完({current_issue}开{drawn})，停止")
                self._stop_chase()
                return
            app.log(f"追号未中({current_issue}开{drawn}) → 第{self.chase_current_step+1}步 ¥{self.chase_sequence[self.chase_current_step]}")

        self._update_chase_status()
        self.chase_bet_issue = None

        if self.chase_active:
            Clock.schedule_once(lambda dt: self._execute_chase_bet(), 3)

    def _update_chase_status(self):
        if not self.chase_active:
            return
        step = self.chase_current_step
        if step >= len(self.chase_sequence):
            return
        amt = self.chase_sequence[step]
        parts = [f"第{step+1}步 ¥{amt}/注"]
        if step + 1 < len(self.chase_sequence):
            parts.append(f"未中→¥{self.chase_sequence[step+1]}")
        if self.chase_history:
            hits = sum(1 for h in self.chase_history if h['hit'])
            parts.append(f"{len(self.chase_history)}期中{hits}")
        self.chase_status_label.text = " | ".join(parts)
        self.chase_status_label.color = hex_to_rgb(COLORS["success"])

    @mainthread
    def _update_chase_history(self):
        lines = []
        for h in reversed(self.chase_history[-20:]):
            mark = "✓ 命中" if h['hit'] else "✗ 未中"
            lines.append(f"{h['issue']} 开{h['drawn']} {mark} ¥{h['amount']}")
        self.chase_history_label.text = "\n".join(lines) if lines else "尚无记录"

    # ━━━━━━━━ 退出 ━━━━━━━━
    def _do_logout(self, instance):
        if self.chase_active:
            self._stop_chase()
        app = App.get_running_app()
        app.api.logout()
        app.show_login()

    # ━━━━━━━━ 弹窗 ━━━━━━━━
    def _show_toast(self, msg):
        popup = Popup(title="提示",
                       content=Label(text=msg, font_size='15sp', padding='15dp'),
                       size_hint=(0.78, 0.35))
        popup.open()

    def _confirm_popup(self, title, msg, callback):
        content = BoxLayout(orientation='vertical', spacing='15dp', padding='15dp')
        content.add_widget(Label(text=msg, font_size='14sp', halign='left'))

        btns = BoxLayout(orientation='horizontal', size_hint_y=None, height='45dp', spacing='12dp')
        yes = Button(text="确认", background_normal='',
                     background_color=hex_to_rgb(COLORS["success"]),
                     color=hex_to_rgb(COLORS["text_light"]), font_size='16sp')
        no = Button(text="取消", background_normal='',
                    background_color=hex_to_rgb(COLORS["danger"]),
                    color=hex_to_rgb(COLORS["text_light"]), font_size='16sp')
        btns.add_widget(yes); btns.add_widget(no)
        content.add_widget(btns)

        popup = Popup(title=title, content=content, size_hint=(0.85, 0.55))
        yes.bind(on_press=lambda x: (popup.dismiss(), callback()))
        no.bind(on_press=popup.dismiss)
        popup.open()


# ===== 应用主类 =====
class PK10App(App):
    logged_in = BooleanProperty(False)

    def build(self):
        self.title = "PK10 投注助手"
        self.api = APIClient()
        self.sm = ScreenManager()

        self.login_screen = LoginScreen()
        self.sm.add_widget(self.login_screen)

        self.main_screen = MainScreen()
        self.sm.add_widget(self.main_screen)

        self.sm.current = "login"
        return self.sm

    def on_login_success(self):
        self.logged_in = True
        success, balance = self.api.refresh_balance()
        bal_text = f"{balance:.2f}" if success else "--"
        self.main_screen.balance_label.text = f"余额\n¥ {bal_text}"
        self.main_screen._refresh_draw()
        self.log("登录成功 ✓")
        self.show_main()

    def show_login(self):
        self.logged_in = False
        self.sm.current = "login"

    def show_main(self):
        self.sm.current = "main"

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = f"[{timestamp}] {message}\n"

        def update(dt):
            if hasattr(self.main_screen, 'log_input'):
                self.main_screen.log_input.text += msg

        Clock.schedule_once(update, 0)


if __name__ == '__main__':
    PK10App().run()
