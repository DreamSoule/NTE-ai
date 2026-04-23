import sys
import os
from urllib.request import urlopen
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from config import REPO_OWNER, REPO_NAME, VERSION

class AutoUpdater:
    def __init__(self):
        self.repo_owner = REPO_OWNER
        self.repo_name = REPO_NAME
        self.current_version = VERSION
        self.raw_base = f"https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}/main/"

    def get_remote_version(self):
        if not self.repo_owner or not self.repo_name:
            return None
        try:
            version_url = self.raw_base + "version.txt"
            with urlopen(version_url, timeout=5) as resp:
                remote_version = resp.read().decode('utf-8').strip()
                return remote_version
        except Exception as e:
            print(f"[更新] 获取远程版本失败: {e}")
            return None

    def check_and_update(self, parent_window):
        remote_ver = self.get_remote_version()
        if remote_ver is None:
            # 静默失败，不弹窗
            return
        if remote_ver > self.current_version:
            reply = QMessageBox.question(
                parent_window,
                "发现新版本",
                f"当前版本 {self.current_version}\n最新版本 {remote_ver}\n\n是否前往 GitHub 下载更新？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                url = f"https://github.com/{self.repo_owner}/{self.repo_name}/releases"
                QDesktopServices.openUrl(QUrl(url))