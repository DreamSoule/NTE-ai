import sys
import os
import subprocess
import tempfile
import shutil
import urllib.request
import json
from PyQt5.QtWidgets import QMessageBox, QProgressDialog
from PyQt5.QtCore import Qt
from config import REPO_OWNER, REPO_NAME, VERSION

class AutoUpdater:
    def __init__(self):
        self.repo_owner = REPO_OWNER
        self.repo_name = REPO_NAME
        self.current_version = VERSION
        self.raw_base = f"https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}/main/"
        self.release_api = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"

    def get_remote_version(self):
        try:
            url = self.raw_base + "version.txt"
            with urllib.request.urlopen(url, timeout=10) as resp:
                return resp.read().decode('utf-8').strip()
        except Exception as e:
            print(f"[更新] 获取远程版本失败: {e}")
            return None

    def get_download_url(self):
        """获取最新 Release 中的 exe 下载链接"""
        try:
            with urllib.request.urlopen(self.release_api, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for asset in data.get("assets", []):
                    if asset["name"].endswith(".exe"):
                        return asset["browser_download_url"]
        except Exception as e:
            print(f"[更新] 获取下载链接失败: {e}")
        return None

    def download_file(self, url, dest_path, progress_callback=None):
        with urllib.request.urlopen(url) as response:
            total = int(response.info().get('Content-Length', 0))
            downloaded = 0
            chunk = 8192
            with open(dest_path, 'wb') as f:
                while True:
                    data = response.read(chunk)
                    if not data:
                        break
                    f.write(data)
                    downloaded += len(data)
                    if progress_callback and total:
                        progress_callback(int(downloaded * 100 / total))
        return True

    def apply_update(self, new_exe_path, parent_window):
        """创建更新脚本，覆盖当前 exe 并重启"""
        current_exe = sys.executable
        script_path = os.path.join(tempfile.gettempdir(), "update_script.bat")
        with open(script_path, "w", encoding='ansi') as f:
            f.write('@echo off\n')
            f.write('timeout /t 2 /nobreak >nul\n')
            f.write(f'copy /Y "{new_exe_path}" "{current_exe}"\n')
            f.write('if errorlevel 1 (\n')
            f.write('  echo 更新失败，文件被占用\n')
            f.write('  pause\n')
            f.write('  exit\n')
            f.write(')\n')
            f.write(f'start "" "{current_exe}"\n')
            f.write('del "%~f0"\n')
        subprocess.Popen([script_path], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        parent_window.close()
        sys.exit(0)

    def check_and_update(self, parent_window):
        remote_ver = self.get_remote_version()
        if remote_ver is None:
            QMessageBox.information(parent_window, "检查更新", "无法获取远程版本，请检查网络。")
            return
        if remote_ver > self.current_version:
            reply = QMessageBox.question(parent_window, "发现新版本",
                                         f"当前版本: {self.current_version}\n最新版本: {remote_ver}\n是否立即自动更新？",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                download_url = self.get_download_url()
                if not download_url:
                    QMessageBox.warning(parent_window, "更新失败", "无法获取下载链接，请稍后重试。")
                    return
                progress = QProgressDialog("正在下载更新...", "取消", 0, 100, parent_window)
                progress.setWindowModality(Qt.WindowModal)
                progress.show()
                def on_progress(percent):
                    if progress.wasCanceled():
                        raise Exception("用户取消")
                    progress.setValue(percent)
                temp_exe = os.path.join(tempfile.gettempdir(), "异环薄荷AI_new.exe")
                try:
                    self.download_file(download_url, temp_exe, on_progress)
                    progress.setValue(100)
                    QMessageBox.information(parent_window, "下载完成", "即将自动更新并重启。")
                    self.apply_update(temp_exe, parent_window)
                except Exception as e:
                    QMessageBox.warning(parent_window, "更新失败", f"错误: {str(e)}")
        else:
            QMessageBox.information(parent_window, "检查更新", f"当前已是最新版本 ({self.current_version})")