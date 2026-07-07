import json
import os
import sys
import threading
import urllib.request
import webbrowser

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressDialog, QPushButton, QPlainTextEdit, QStackedWidget, QSystemTrayIcon, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QListWidget,
    QListWidgetItem, QInputDialog
)

from constants import *
import account_info
import codex_control
import codex_repair
import config_manager
import gateway
import restore_manager
import runtime
from version import check_update


def app_icon():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
    path = os.path.join(base, "assets", "app_icon.ico")
    if os.path.exists(path):
        return QIcon(path)
    return QIcon()


QSS = """
QMainWindow { background: #f5f7fb; }
QWidget { font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; color: #172033; }
QLabel { border: none; background: transparent; }
QLabel#Title { font-size: 26px; font-weight: 800; color: #0b1220; }
QLabel#Subtitle { color: #64748b; font-size: 14px; }
QLabel#CardTitle { font-size: 15px; font-weight: 700; color: #0f172a; }
QLabel#Metric { color: #64748b; font-size: 12px; }
QLabel#Value { color: #0f172a; font-size: 21px; font-weight: 800; }
QLabel#Pill { color: #075985; background: #e0f2fe; border-radius: 10px; padding: 5px 10px; font-weight: 700; }
QWidget#Card { background: #ffffff; border: 1px solid #e7ebf0; border-radius: 14px; }
QWidget#HeroCard { background: #0f172a; border-radius: 18px; }
QLabel#HeroTitle { color: white; font-size: 24px; font-weight: 800; }
QLabel#HeroText { color: #cbd5e1; font-size: 14px; }
QPushButton { background: #111827; color: #ffffff; border: 0; border-radius: 9px; padding: 9px 16px; font-weight: 600; outline: none; }
QPushButton:hover { background: #1f2937; }
QPushButton:focus { outline: none; border: 0; }
QPushButton:pressed { background: #0b1220; padding-top: 10px; padding-bottom: 8px; }
QPushButton:disabled { background: #d8e0ea; color: #7b8794; }
QPushButton#Secondary { background: #e8eef6; color: #172033; }
QPushButton#Secondary:hover { background: #dbe4ef; }
QPushButton#Danger { background: #dc2626; }
QPushButton#Danger:hover { background: #b91c1c; }
QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {
  background: #ffffff; border: 1px solid #d6dee8; border-radius: 9px; padding: 8px;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
  border: 1px solid #60a5fa;
}
QTableWidget { background: #ffffff; border: 1px solid #e7ebf0; border-radius: 12px; gridline-color: #eef2f7; selection-background-color: #dbeafe; selection-color: #0f172a; outline: none; }
QTableWidget:focus { outline: none; border: 1px solid #cbd5e1; }
QTableWidget::item:focus { outline: none; border: 0; }
QHeaderView::section { background: #f8fafc; color: #334155; padding: 9px; border: 0; border-bottom: 1px solid #e2e8f0; font-weight: 700; }
QListWidget { background: #0b1220; color: #cbd5e1; border: 0; padding: 14px; font-size: 14px; outline: none; }
QListWidget::item { padding: 13px 16px; border-radius: 10px; margin: 3px 0; outline: none; border: 0; }
QListWidget::item:selected { background: #2563eb; color: white; }
QListWidget::item:focus { outline: none; border: 0; }
QProgressDialog { background: #ffffff; border: 1px solid #e7ebf0; border-radius: 12px; }
QProgressBar { border: 1px solid #d6dee8; border-radius: 7px; background: #eef2f7; text-align: center; min-height: 14px; }
QProgressBar::chunk { background: #2563eb; border-radius: 7px; }
"""


class Card(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 16)
        self.layout.setSpacing(10)
        label = QLabel(title)
        label.setObjectName("CardTitle")
        self.layout.addWidget(label)


class HeroCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HeroCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(22, 18, 22, 18)
        self.layout.setSpacing(8)
        self.title = QLabel("检测中")
        self.title.setObjectName("HeroTitle")
        self.text = QLabel("")
        self.text.setObjectName("HeroText")
        self.text.setWordWrap(True)
        self.layout.addWidget(self.title)
        self.layout.addWidget(self.text)


class Metric(QWidget):
    def __init__(self, label):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.value = QLabel("-")
        self.value.setObjectName("Value")
        caption = QLabel(label)
        caption.setObjectName("Metric")
        layout.addWidget(self.value)
        layout.addWidget(caption)


class TaskSignals(QObject):
    finished = Signal(object, object)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME + " " + APP_VERSION)
        self.setWindowIcon(app_icon())
        self.resize(1120, 720)
        self._allow_exit = False
        self._task_signals = []
        self._busy_dialog = None
        self._build_ui()
        self._remove_focus_frames()
        self._build_tray()
        self.refresh_all()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(8000)

    def _build_ui(self):
        root = QWidget()
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setFixedWidth(220)
        for text in ("首页", "配置管理", "回退点", "设置"):
            QListWidgetItem(text, self.nav)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._switch_page)
        self.stack = QStackedWidget()
        main.addWidget(self.nav)
        main.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.stack.addWidget(self._status_page())
        self.stack.addWidget(self._config_page())
        self.stack.addWidget(self._restore_page())
        self.stack.addWidget(self._settings_page())

    def _page(self, title, subtitle):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)
        h = QLabel(title)
        h.setObjectName("Title")
        s = QLabel(subtitle)
        s.setObjectName("Subtitle")
        layout.addWidget(h)
        layout.addWidget(s)
        return page, layout

    def _status_page(self):
        page, layout = self._page("Codex Gateway", "统一托管 Codex 官方模型和第三方 API 模型")
        self.mode_hero = HeroCard()
        layout.addWidget(self.mode_hero)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        layout.addLayout(grid)
        self.gateway_card = Card("本地网关")
        self.gateway_status = QLabel("检测中")
        self.gateway_status.setObjectName("Pill")
        self.gateway_detail = QLabel("")
        self.gateway_models = QLabel("")
        self.gateway_card.layout.addWidget(self.gateway_status)
        self.gateway_card.layout.addWidget(self.gateway_detail)
        self.gateway_card.layout.addWidget(self.gateway_models)
        btns = QHBoxLayout()
        self.gateway_start_btn = QPushButton("启动网关")
        self.gateway_stop_btn = QPushButton("停止网关")
        self.gateway_restart_btn = QPushButton("重启网关")
        self.gateway_stop_btn.setObjectName("Secondary")
        self.gateway_restart_btn.setObjectName("Secondary")
        self.gateway_start_btn.clicked.connect(lambda: self._run_task("正在启动网关", self._start_gateway, self._gateway_done))
        self.gateway_stop_btn.clicked.connect(lambda: self._run_task("正在停止网关", self._stop_gateway, self._gateway_done))
        self.gateway_restart_btn.clicked.connect(lambda: self._run_task("正在重启网关", self._restart_gateway, self._gateway_done))
        for b in (self.gateway_start_btn, self.gateway_stop_btn, self.gateway_restart_btn):
            btns.addWidget(b)
        self.gateway_card.layout.addLayout(btns)

        self.codex_card = Card("Codex Desktop")
        self.codex_status = QLabel("检测中")
        self.codex_status.setObjectName("Pill")
        self.codex_detail = QLabel("")
        self.codex_card.layout.addWidget(self.codex_status)
        self.codex_card.layout.addWidget(self.codex_detail)
        codex_btns = QHBoxLayout()
        self.codex_toggle_btn = QPushButton("打开 Codex")
        self.codex_restart_btn = QPushButton("重启 Codex")
        self.codex_restart_btn.setObjectName("Secondary")
        self.codex_toggle_btn.clicked.connect(lambda: self._run_task("正在处理 Codex", self._toggle_codex, self._codex_done))
        self.codex_restart_btn.clicked.connect(lambda: self._run_task("正在重启 Codex", self._restart_codex, self._codex_done))
        codex_btns.addWidget(self.codex_toggle_btn)
        codex_btns.addWidget(self.codex_restart_btn)
        self.codex_card.layout.addLayout(codex_btns)

        self.account_card = Card("官方账号")
        self.account_status = QLabel("")
        self.account_status.setTextFormat(Qt.RichText)
        self.account_card.layout.addWidget(self.account_status)
        grid.addWidget(self.gateway_card, 0, 0)
        grid.addWidget(self.codex_card, 0, 1)
        grid.addWidget(self.account_card, 1, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addStretch(1)
        return page

    def _config_page(self):
        page, layout = self._page("配置管理", "内置模型固定为 0 号，用户模型从 1 开始")
        self.config_table = QTableWidget(0, 10)
        self.config_table.setHorizontalHeaderLabels(["序号", "展示名称", "模型ID", "上游模型", "供应商", "类型", "URL", "上下文", "最大输出", "标记"])
        self.config_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.config_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.config_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.config_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.config_table, 1)
        btns = QHBoxLayout()
        for text, fn, obj in [
            ("刷新", self.refresh_config, "Secondary"),
            ("添加模型", self._add_model, ""),
            ("修改", self._modify_model, "Secondary"),
            ("删除", self._remove_model, "Danger"),
            ("查看脱敏配置", self._view_config, "Secondary"),
        ]:
            b = QPushButton(text)
            if obj:
                b.setObjectName(obj)
            b.clicked.connect(fn)
            btns.addWidget(b)
        btns.addStretch(1)
        layout.addLayout(btns)
        return page

    def _restore_page(self):
        page, layout = self._page("回退点", "自动回退和手动回退分开保存，可恢复 Codex 与网关配置")
        self.restore_table = QTableWidget(0, 5)
        self.restore_table.setHorizontalHeaderLabels(["类型", "名称", "时间", "备注", "项目数"])
        self.restore_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.restore_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.restore_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.restore_table, 1)
        btns = QHBoxLayout()
        for text, fn, obj in [
            ("刷新", self.refresh_restore_points, "Secondary"),
            ("新建手动回退点", self._manual_restore_point, ""),
            ("恢复选中回退点", self._restore_selected, "Danger"),
        ]:
            b = QPushButton(text)
            if obj:
                b.setObjectName(obj)
            b.clicked.connect(fn)
            btns.addWidget(b)
        btns.addStretch(1)
        layout.addLayout(btns)
        return page

    def _settings_page(self):
        page, layout = self._page("设置", "登录模式、自启、端口、版本更新")
        status = Card("Codex 登录状态")
        self.mode_label = QLabel("检测中")
        status.layout.addWidget(self.mode_label)
        self.provider_state_label = QLabel("")
        status.layout.addWidget(self.provider_state_label)
        mode_btns = QHBoxLayout()
        for text, fn, obj in [
            ("启动官方登录流程", self._codex_login, ""),
            ("切到纯官方订阅", self._switch_official_only, "Secondary"),
            ("切到官方订阅 + 第三方 API", lambda: self._repair_codex(True), "Secondary"),
            ("切到纯 API + 第三方模型", lambda: self._repair_codex(False), "Secondary"),
        ]:
            b = QPushButton(text)
            if obj:
                b.setObjectName(obj)
            b.clicked.connect(fn)
            mode_btns.addWidget(b)
        status.layout.addLayout(mode_btns)
        layout.addWidget(status)

        auto = Card("开机自启与端口")
        self.auto_label = QLabel("")
        self.port_edit = QLineEdit()
        self.port_edit.setFixedWidth(120)
        pbtn = QPushButton("应用端口并重启")
        pbtn.clicked.connect(self._apply_port)
        row = QHBoxLayout()
        row.addWidget(QLabel("端口"))
        row.addWidget(self.port_edit)
        row.addWidget(pbtn)
        row.addStretch(1)
        auto.layout.addWidget(self.auto_label)
        auto.layout.addLayout(row)
        abtns = QHBoxLayout()
        on = QPushButton("开启自启")
        off = QPushButton("关闭自启")
        off.setObjectName("Secondary")
        on.clicked.connect(self._enable_autostart)
        off.clicked.connect(self._disable_autostart)
        abtns.addWidget(on)
        abtns.addWidget(off)
        abtns.addStretch(1)
        auto.layout.addLayout(abtns)
        layout.addWidget(auto)

        about = Card("关于")
        self.version_label = QLabel(APP_VERSION + "  ·  zhaoxinyi02/codex-gateway-manager")
        about.layout.addWidget(self.version_label)
        up = QPushButton("检查更新")
        up.clicked.connect(lambda: self._run_task("正在检查更新", self._check_update, self._update_done))
        about.layout.addWidget(up)
        layout.addWidget(about)
        layout.addStretch(1)
        return page

    def _remove_focus_frames(self):
        for button in self.findChildren(QPushButton):
            button.setFocusPolicy(Qt.NoFocus)
        for table in self.findChildren(QTableWidget):
            table.setFocusPolicy(Qt.NoFocus)
        self.nav.setFocusPolicy(Qt.NoFocus)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        menu = self.tray.contextMenu()
        if menu is None:
            from PySide6.QtWidgets import QMenu
            menu = QMenu()
            self.tray.setContextMenu(menu)
        show = QAction("显示窗口", self)
        show.triggered.connect(self.show_window)
        start = QAction("启动/重启网关", self)
        start.triggered.connect(lambda: self._run_task("正在重启网关", self._restart_gateway, self._gateway_done))
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.exit_app)
        menu.addAction(show)
        menu.addAction(start)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.activated.connect(lambda reason: self.show_window() if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def _switch_page(self, index):
        self.stack.setCurrentIndex(index)
        if index == 1:
            self.refresh_config()
        elif index == 2:
            self.refresh_restore_points()
        elif index == 3:
            self.refresh_settings()

    def refresh_all(self):
        self.refresh_status()
        self.refresh_config()
        self.refresh_restore_points()
        self.refresh_settings()

    def refresh_status(self):
        s = gateway.get_status()
        if s["running"] and s["responding"]:
            self.gateway_status.setText("运行中 · 正常响应")
        elif s["running"]:
            self.gateway_status.setText("运行中 · 暂无响应")
        else:
            self.gateway_status.setText("已停止")
        self.gateway_detail.setText("PID: {}    地址: {}".format(s.get("pid") or "-", s.get("url") or "-"))
        self.gateway_models.setText("模型数量: " + str(len(s.get("models") or [])))
        self.gateway_start_btn.setEnabled(not s["running"])
        self.gateway_stop_btn.setEnabled(s["running"])
        self.gateway_restart_btn.setEnabled(True)

        cs = codex_control.get_status()
        self.codex_status.setText("运行中" if cs["running"] else "未运行")
        self.codex_detail.setText("进程数: {}".format(cs["count"]))
        self.codex_toggle_btn.setText("停止 Codex" if cs["running"] else "打开 Codex")
        self.codex_restart_btn.setEnabled(cs["running"])

        ai = account_info.get_account_info()
        self.mode_hero.title.setText(ai["mode"])
        desc_map = {
            "pure_official": "当前 Codex 使用官方 provider，没有接入本地 CLIProxyAPI 第三方模型网关。",
            "official_plus_api": "当前 Codex 使用本地 CLIProxyAPI provider，同时保留官方订阅登录，可在同一会话里切换官方模型和第三方 API 模型。",
            "api_only": "当前 Codex 使用本地 CLIProxyAPI provider，不依赖官方订阅登录，适合只用自配 API 的用户。",
            "not_logged_in": "Codex 已安装，但未检测到官方账号登录。",
            "not_installed": "未检测到 Codex Desktop 安装。",
        }
        self.mode_hero.text.setText(desc_map.get(ai["mode_key"], "当前模式需要检查 Codex 配置。"))
        self.account_status.setText(
            "<b>邮箱</b>：{email}<br>"
            "<b>套餐</b>：{plan}<br>"
            "<b>过期</b>：{expired}<br>"
            "<b>第三方模型</b>：{third_party_count}<br>"
            "<b>用量</b>：{usage}".format(**ai)
        )

    def refresh_config(self):
        try:
            summary = config_manager.get_summary()
            entries = sorted(summary["entries"], key=lambda x: (x.get("display_number", x["number"]), x["alias"]))
            self.config_table.setRowCount(len(entries))
            self._entry_by_row = {}
            for row, e in enumerate(entries):
                vals = [
                    e.get("display_number", e["number"]), e["display_name"], e["alias"], e["upstream"],
                    e["provider_name"], e["section"], e["base_url"], e.get("context_window") or "-",
                    e.get("max_output_tokens") or "-", "内置" if e.get("built_in") else "",
                ]
                for col, val in enumerate(vals):
                    item = QTableWidgetItem(str(val))
                    if e.get("built_in"):
                        item.setForeground(Qt.darkGray)
                    self.config_table.setItem(row, col, item)
                self._entry_by_row[row] = e
        except Exception as ex:
            self._error(str(ex))

    def refresh_restore_points(self):
        points = restore_manager.list_restore_points()
        self.restore_table.setRowCount(len(points))
        self._restore_by_row = {}
        for row, p in enumerate(points):
            vals = [("手动" if p["kind"] == "manual" else "自动"), p["name"], p["created_at"], p["notes"], p["items"]]
            for col, val in enumerate(vals):
                self.restore_table.setItem(row, col, QTableWidgetItem(str(val)))
            self._restore_by_row[row] = p

    def refresh_settings(self):
        ai = account_info.get_account_info()
        self.mode_label.setText("当前模式: {mode}\n邮箱: {email}\n套餐: {plan}\n说明: 纯官方订阅 / 官方订阅 + 第三方 API / 纯 API + 第三方模型会在这里明确区分。".format(**ai))
        st = codex_repair.read_effective_provider_state()
        auth = st["requires_openai_auth"]
        if auth is True:
            auth_text = "true（保留官方订阅登录）"
        elif auth is False:
            auth_text = "false（纯 API 模式）"
        else:
            auth_text = "未设置"
        self.provider_state_label.setText(
            "实际配置: model_provider = {model_provider}；requires_openai_auth = {auth}".format(
                model_provider=st["model_provider"], auth=auth_text
            )
        )
        try:
            self.port_edit.setText(str(config_manager.get_port()))
        except Exception:
            self.port_edit.setText(str(GATEWAY_DEFAULT_PORT))
        state = gateway.get_scheduled_task_state()
        self.auto_label.setText("自启状态: " + ("已开启" if state in ("ready", "running") else "未开启"))

    def selected_entry(self):
        row = self.config_table.currentRow()
        return getattr(self, "_entry_by_row", {}).get(row)

    def _after_config_change(self, name):
        config_manager.ensure_builtin_model()
        ok = gateway.restart()
        if gateway.is_responding():
            restore_manager.create_restore_point("auto", name, "配置修改后自动保存")
        return ok

    def _add_model(self):
        dlg = ModelDialog(self)
        if dlg.exec() == QDialog.Accepted:
            r = dlg.result
            def work():
                config_manager.add_model(**r)
                return self._after_config_change("add-model")
            self._run_task("正在添加模型并重启网关", work, lambda ok: self._config_done(ok, "模型已添加。"))

    def _modify_model(self):
        e = self.selected_entry()
        if not e:
            self._warn("请先选择一个模型。")
            return
        if e.get("built_in"):
            self._warn("内置免费模型不可修改。")
            return
        dlg = ModelDialog(self, e)
        if dlg.exec() == QDialog.Accepted:
            def work():
                config_manager.modify_model(e["number"], **dlg.result)
                return self._after_config_change("modify-model")
            self._run_task("正在修改模型并重启网关", work, lambda ok: self._config_done(ok, "模型已修改。"))

    def _remove_model(self):
        e = self.selected_entry()
        if not e:
            self._warn("请先选择一个模型。")
            return
        if e.get("built_in"):
            self._warn("内置免费模型不可删除。")
            return
        if QMessageBox.question(self, "确认删除", "确认删除 {} ?".format(e["display_name"])) == QMessageBox.Yes:
            def work():
                config_manager.remove_model(e["number"])
                return self._after_config_change("remove-model")
            self._run_task("正在删除模型并重启网关", work, lambda ok: self._config_done(ok, "模型已删除。"))

    def _view_config(self):
        dlg = TextDialog("脱敏后的 config.yaml", config_manager.get_redacted_config(), self)
        dlg.exec()

    def _manual_restore_point(self):
        name, ok = QInputDialog.getText(self, "手动回退点", "名称")
        if not ok:
            return
        notes, _ = QInputDialog.getMultiLineText(self, "备注", "备注")
        restore_manager.create_restore_point("manual", name, notes)
        self.refresh_restore_points()

    def _restore_selected(self):
        row = self.restore_table.currentRow()
        p = getattr(self, "_restore_by_row", {}).get(row)
        if not p:
            self._warn("请先选择一个回退点。")
            return
        if QMessageBox.question(self, "确认回退", "回退会覆盖当前 Codex/网关配置，继续?") == QMessageBox.Yes:
            def work():
                restore_manager.restore(p["id"])
                return gateway.restart()
            self._run_task("正在恢复回退点并重启网关", work, lambda ok: self._config_done(ok, "已恢复回退点。"))

    def _repair_codex(self, requires_auth):
        def work():
            restore_manager.create_restore_point("auto", "before-codex-mode-switch", "切换登录模式前自动保存")
            ok, msg = codex_repair.repair_codex_config(requires_auth)
            if ok:
                restore_manager.create_restore_point("auto", "codex-mode-switch", "切换登录模式后自动保存")
            return ok, msg
        self._run_task("正在切换 Codex 登录模式", work, self._mode_switch_done)

    def _switch_official_only(self):
        def work():
            restore_manager.create_restore_point("auto", "before-official-only", "切换纯官方订阅前自动保存")
            ok, msg = codex_repair.switch_to_official_only()
            if ok:
                restore_manager.create_restore_point("auto", "official-only", "切换纯官方订阅后自动保存")
            return ok, msg
        self._run_task("正在切换为纯官方订阅", work, self._mode_switch_done)

    def _codex_login(self):
        if gateway.run_codex_login():
            self._info("已启动 Codex 官方登录流程，请按浏览器提示完成授权。")
        else:
            self._error("无法启动登录流程。")

    def _start_gateway(self):
        return gateway.start()

    def _stop_gateway(self):
        return gateway.stop()

    def _restart_gateway(self):
        return gateway.restart()

    def _toggle_codex(self):
        return codex_control.stop() if codex_control.is_running() else codex_control.start()

    def _restart_codex(self):
        return codex_control.restart()

    def _apply_port(self):
        try:
            port = int(self.port_edit.text().strip())
            if port < 1 or port > 65535:
                raise ValueError()
        except ValueError:
            self._warn("端口必须是 1-65535。")
            return
        restore_manager.create_restore_point("auto", "before-port-change", "修改端口前自动保存")
        config_manager.set_port(port)
        self._run_task("正在应用端口并重启网关", self._restart_gateway, self._gateway_done)

    def _enable_autostart(self):
        self._info("已开启自启。" if gateway.enable_autostart() else "开启自启失败。")
        self.refresh_settings()

    def _disable_autostart(self):
        self._info("已关闭自启。" if gateway.disable_autostart() else "未找到自启任务。")
        self.refresh_settings()

    def _check_update(self):
        return check_update()

    def _run_task(self, title, fn, on_done=None):
        if self._busy_dialog is not None:
            self._warn("已有任务正在执行，请稍等一下。")
            return

        dialog = QProgressDialog(title + "…", None, 0, 0, self)
        dialog.setWindowTitle(APP_NAME)
        dialog.setCancelButton(None)
        dialog.setMinimumDuration(0)
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setValue(0)
        dialog.show()
        self._busy_dialog = dialog
        central = self.centralWidget()
        if central:
            central.setEnabled(False)

        signals = TaskSignals()
        self._task_signals.append(signals)

        def finish(result, error):
            try:
                if self._busy_dialog is dialog:
                    self._busy_dialog = None
                dialog.close()
                if central:
                    central.setEnabled(True)
                try:
                    self.refresh_status()
                except Exception:
                    pass
                if error is not None:
                    self._error(str(error))
                    return
                if on_done:
                    on_done(result)
            finally:
                if signals in self._task_signals:
                    self._task_signals.remove(signals)

        signals.finished.connect(finish)

        def worker():
            try:
                result = fn()
                signals.finished.emit(result, None)
            except Exception as ex:
                signals.finished.emit(None, ex)

        threading.Thread(target=worker, daemon=True).start()

    def _gateway_done(self, ok):
        self.refresh_all()
        if ok:
            self.tray.showMessage(APP_NAME, "网关操作完成。")
        else:
            self._error("网关操作失败，请检查端口是否被占用，或查看配置是否有效。")

    def _codex_done(self, ok):
        self.refresh_all()
        if not ok:
            self._error("Codex 操作失败：没有成功启动/停止 Codex。请确认 Codex Desktop 已安装。")

    def _config_done(self, ok, message):
        self.refresh_all()
        if ok:
            self._info(message)
        else:
            self._error("操作已执行，但网关未正常响应。配置已保留，请检查端口、API 地址或模型配置。")

    def _mode_switch_done(self, result):
        self.refresh_all()
        ok, msg = result
        if ok:
            self._info(msg)
        else:
            self._error(msg)

    def _update_done(self, result):
        if result.get("error"):
            msg = (
                "检查更新失败，但程序不会再卡死。\n\n"
                "原因：{error}\n\n"
                "你也可以手动打开 Release 页面查看：\n{url}"
            ).format(error=result.get("error"), url=result.get("release_url", ""))
            self._warn(msg)
            return
        if result.get("has_update"):
            latest = result.get("latest_version") or "新版"
            current = result.get("current_version") or APP_VERSION
            if QMessageBox.question(
                self,
                "发现新版本",
                "当前版本：{current}\n最新版本：{latest}\n\n是否打开下载页面？".format(current=current, latest=latest),
            ) == QMessageBox.Yes:
                webbrowser.open(result.get("download_url") or result.get("release_url"))
        else:
            self._info("当前已是最新版本：{}".format(result.get("current_version") or APP_VERSION))

    def _info(self, text):
        QMessageBox.information(self, APP_NAME, text)

    def _warn(self, text):
        QMessageBox.warning(self, APP_NAME, text)

    def _error(self, text):
        QMessageBox.critical(self, APP_NAME, text)

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent):
        if self._allow_exit:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.tray.showMessage(APP_NAME, "已最小化到右下角托盘，网关继续运行。")

    def exit_app(self):
        self._allow_exit = True
        QApplication.instance().quit()


class ModelDialog(QDialog):
    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.result = None
        self.entry = entry or {}
        self.setWindowTitle("模型配置")
        self.resize(560, 430)
        form = QFormLayout(self)
        self.api_type = QComboBox()
        self.api_type.addItems(["responses", "openai", "claude"])
        self.base_url = QLineEdit(self.entry.get("base_url", ""))
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.model_id = QComboBox()
        self.model_id.setEditable(True)
        self.model_id.setEditText(self.entry.get("upstream", ""))
        self.alias = QLineEdit(self.entry.get("alias", ""))
        self.display_name = QLineEdit(self.entry.get("display_name", ""))
        self.provider_name = QLineEdit(self.entry.get("provider_name", ""))
        self.ctx = QLineEdit(str(self.entry.get("context_window") or ""))
        self.maxout = QLineEdit(str(self.entry.get("max_output_tokens") or ""))
        form.addRow("接口类型", self.api_type)
        form.addRow("API Base URL", self.base_url)
        form.addRow("API Key", self.api_key)
        row = QHBoxLayout()
        row.addWidget(self.model_id, 1)
        fetch = QPushButton("获取模型列表")
        fetch.clicked.connect(self._fetch_models)
        row.addWidget(fetch)
        form.addRow("上游模型 ID", row)
        form.addRow("Codex 模型 ID", self.alias)
        form.addRow("展示名称", self.display_name)
        form.addRow("供应商名称", self.provider_name)
        form.addRow("上下文 token", self.ctx)
        form.addRow("最大输出 token", self.maxout)
        btns = QHBoxLayout()
        ok = QPushButton("确定")
        cancel = QPushButton("取消")
        cancel.setObjectName("Secondary")
        ok.clicked.connect(self._ok)
        cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        form.addRow(btns)

    def _fetch_models(self):
        base = self.base_url.text().strip().rstrip("/")
        key = self.api_key.text().strip()
        if not base or not key:
            QMessageBox.warning(self, "提示", "请先填写 URL 和 API Key。")
            return
        try:
            req = urllib.request.Request(base + "/models", headers={"Authorization": "Bearer " + key, "User-Agent": APP_NAME})
            data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
            ids = sorted([str(x.get("id") or x.get("name")) for x in data.get("data", []) if isinstance(x, dict) and (x.get("id") or x.get("name"))])
            if not ids:
                raise ValueError("没有返回模型 ID。")
            self.model_id.clear()
            self.model_id.addItems(ids)
        except Exception as ex:
            QMessageBox.warning(self, "获取失败", "可手动填写模型 ID。\n\n" + str(ex))

    def _int_or_none(self, text):
        text = text.strip()
        return int(text) if text.isdigit() else None

    def _ok(self):
        model_id = self.model_id.currentText().strip()
        if not self.entry and (not self.base_url.text().strip() or not self.api_key.text().strip() or not model_id):
            QMessageBox.warning(self, "提示", "URL、Key、模型 ID 不能为空。")
            return
        if self.entry:
            self.result = {
                "base_url": self.base_url.text().strip(),
                "api_key": self.api_key.text().strip() or None,
                "upstream": model_id,
                "alias": self.alias.text().strip() or model_id,
                "display_name": self.display_name.text().strip() or model_id,
                "provider_name": self.provider_name.text().strip() or "Custom",
                "context_window": self._int_or_none(self.ctx.text()),
                "max_output_tokens": self._int_or_none(self.maxout.text()),
            }
        else:
            self.result = {
                "api_type": self.api_type.currentText(),
                "provider_name": self.provider_name.text().strip() or "Custom",
                "base_url": self.base_url.text().strip(),
                "api_key": self.api_key.text().strip(),
                "model_id": model_id,
                "alias": self.alias.text().strip() or model_id,
                "display_name": self.display_name.text().strip() or model_id,
                "context_window": self._int_or_none(self.ctx.text()),
                "max_output_tokens": self._int_or_none(self.maxout.text()),
            }
        self.accept()


class TextDialog(QDialog):
    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 620)
        layout = QVBoxLayout(self)
        editor = QPlainTextEdit()
        editor.setPlainText(text)
        editor.setReadOnly(True)
        layout.addWidget(editor)


def _takeover_if_needed():
    if not gateway.is_running() or gateway.is_managed_running():
        runtime.ensure_all()
        return True
    info = gateway.get_process_info() or {}
    msg = (
        "检测到已有 CLIProxyAPI 正在运行，但不是当前软件托管的实例。\n\n"
        "进程: {pid}\n路径: {path}\n\n"
        "请选择“接管”，软件会停止当前命令行版本，继承现有配置并改由本软件托管；"
        "如果不同意，软件将退出。"
    ).format(pid=info.get("pid", "-"), path=info.get("path", "-"))
    box = QMessageBox()
    box.setWindowIcon(app_icon())
    box.setWindowTitle("接管 CLIProxyAPI")
    box.setText(msg)
    takeover = box.addButton("接管并继承配置", QMessageBox.AcceptRole)
    box.addButton("退出软件", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() != takeover:
        return False
    restore_manager.create_restore_point("auto", "before-takeover", "接管外部 CLIProxyAPI 前自动保存")
    before = account_info.get_account_info()
    requires_auth = before.get("mode_key") != "api_only" and before.get("logged_in")
    config_manager.merge_external_config(gateway.running_config_path())
    gateway.stop()
    runtime.ensure_all()
    runtime.update_cli_proxy_runtime_if_possible()
    codex_repair.repair_codex_config(bool(requires_auth))
    gateway.start()
    restore_manager.create_restore_point("auto", "after-takeover", "接管外部 CLIProxyAPI 后自动保存")
    return True


def run():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    app.setStyleSheet(QSS)
    if not _takeover_if_needed():
        return
    w = MainWindow()
    w.show()
    app.exec()
