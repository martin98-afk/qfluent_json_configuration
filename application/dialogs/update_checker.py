import os
import subprocess
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox, QProgressDialog, QWidget
from loguru import logger
from qfluentwidgets import Dialog, InfoBar, InfoBarPosition, InfoBarIcon, MessageBox

from application.utils.threading_utils import DownloadThread, AsyncUpdateChecker
from application.utils.utils import resource_path, get_button_style_sheet, get_icon


class UpdateChecker(QWidget):
    """支持 GitHub 和 Gitee 的独立更新检查类"""

    def __init__(self, parent=None, home=None):
        """
        :param parent: 父级窗口
        :param repo: 仓库名（格式：owner/repo）
        :param platform: 支持 "github" 或 "gitee"
        """
        super().__init__(parent)
        self.parent = parent
        self.home = home
        self.platform = self.parent.config.patch_info.get("版本管理方式")
        self.repo = self.parent.config.patch_info.get(self.platform).get("项目名称")
        self.token = self.parent.config.patch_info.get(self.platform).get("令牌", None)
        self.progress_dialog = None
        self.download_thread = None
        self.current_version = self._get_current_version()

    def _get_current_version(self):
        """获取当前版本号"""
        try:
            import json
            with open(resource_path("versions.json"), "r", encoding="utf-8") as f:
                release_list = json.load(f)
                release_list = sorted(release_list, key=lambda x: x['publishDate'], reverse=True)
                return release_list[0]['version']
        except Exception as e:
            print(f"获取版本失败：{e}")
            return "0.0.0"

    def check_update(self):
        """检查更新入口方法（支持 GitHub/Gitee）"""
        self.async_checker = AsyncUpdateChecker(self)
        self.async_checker.finished.connect(self._on_check_finished)
        self.async_checker.error.connect(self.create_errorbar)
        self.async_checker.start()

    def _on_check_finished(self, latest_release):
        """异步请求完成回调"""
        if latest_release:
            latest_version = latest_release.get("tag_name")
            if (
                latest_version
                and self._compare_versions(latest_version, self.current_version) > 0
            ):
                self._show_update_dialog(latest_release)
            else:
                self.create_infobar("当前已是最新版本")
        else:
            self.create_errorbar("未获取到最新版本号")

    def create_infobar(self, title: str, content: str = "", duration: int = 5000):
        info = InfoBar(
            icon=InfoBarIcon.INFORMATION,
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM,
            duration=duration,  # won't disappear automatically
            parent=self.home
        )
        info.show()

    def create_errorbar(self, title: str, content: str = "", duration: int = 5000):
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM,
            duration=duration,  # won't disappear automatically
            parent=self.home
        )

    def _compare_versions(self, v1, v2):
        """版本号比较逻辑（适用于 GitHub/Gitee）"""
        try:
            parts1 = list(map(int, v1.split('.')))
            parts2 = list(map(int, v2.split('.')))
            return (parts1 > parts2) - (parts1 < parts2)
        except ValueError:
            return (v1 > v2) - (v1 < v2)

    def _show_update_dialog(self, latest_release):
        update_notes = latest_release.get("body", "无更新说明")  # 获取更新说明
        msg_box = Dialog(
            "版本更新",
            f"发现新版本 {latest_release['tag_name']}，当前版本 {self.current_version}，是否更新？\n\n更新内容：\n{update_notes}",
            self
        )
        msg_box.yesButton.setText("更新")
        msg_box.cancelButton.setText("取消")

        if msg_box.exec():
            self._start_download(latest_release)

    def _start_download(self, latest_release):
        """开始下载更新包"""
        tag_name = latest_release["tag_name"]
        for asset in latest_release["assets"]:
            if asset["name"].endswith(".exe"):
                update_url = asset["browser_download_url"]
        # 单独处理gitcode下载链接
        if self.platform == "gitcode":
            update_url = f"https://gitcode.com/api/v5/repos/{self.repo}/releases/{tag_name}/attach_files/{update_url.split('/')[-1]}/download"
        self.update_path = f"参数配置工具V{latest_release['tag_name']}.exe"
        # 创建进度条
        self.progress_dialog = QProgressDialog("正在下载更新...", "取消", 0, 100, self)
        self.progress_dialog.setWindowTitle("更新进度")
        self.progress_dialog.setWindowModality(2)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)
        self.progress_dialog.canceled.connect(self._cancel_download)

        # 启动下载线程
        self.download_thread = DownloadThread(update_url, self.update_path, self.token)
        self.download_thread.progress_signal.connect(self.progress_dialog.setValue)
        self.download_thread.finished_signal.connect(self._handle_download_finished)
        self.download_thread.error_signal.connect(self._handle_download_error)
        self.download_thread.start()

    def _cancel_download(self):
        if self.download_thread:
            self.download_thread.is_canceled = True
            self.download_thread.canceled_signal.connect(
                self._on_download_canceled
            )  # 新增信号连接
            self.download_thread = None

    def _on_download_canceled(self):
        self.progress_dialog.close()

    def _handle_download_finished(self, file_path):
        """处理下载完成"""
        self.progress_dialog.close()
        if self.download_thread:
            self.download_thread.deleteLater()
            self.download_thread = None

        script = """@echo off
timeout /t 10 >nul
:: 清理旧的临时目录
rmdir /s /q "{resouce_path}" 2>nul
:: 替换原程序
del /f /q "{main_exe}"
""".format(
            resouce_path=resource_path("./"), main_exe=os.path.abspath(sys.argv[0]), update_path=file_path
        )
        script_path = "update.bat"

        with open(script_path, "w") as f:
            f.write(script)

        subprocess.Popen([script_path], shell=True)
        self.create_successbar("更新成功", "已成功更新，当前工具将稍后关闭！")
        subprocess.Popen([file_path])  # 自动启动新程序
        sys.exit()

    def _handle_download_error(self, error_msg):
        """处理下载错误"""
        self.progress_dialog.close()
        if self.download_thread:
            self.download_thread.deleteLater()
            self.download_thread = None

        self.create_errorbar(title="下载失败", content=error_msg)

        if os.path.exists(self.update_path):
            try:
                os.remove(self.update_path)
            except:
                pass

    def _show_error(self, title, message):
        """显示错误提示"""
        QMessageBox.critical(None, title, message)

    def create_successbar(self, title: str, content: str = "", duration: int = 5000):
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM,
            duration=duration,  # won't disappear automatically
            parent=self
        )
