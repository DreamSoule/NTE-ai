import sys
import os
import time
import csv
import threading
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QLabel, QPushButton, QTextEdit, QCheckBox,
                             QComboBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt

import cv2
import numpy as np
import win32gui
from PIL import ImageGrab

# ---------- 配置 ----------
ROI = (605, 61, 1322, 88)              # 钓鱼条区域 (left, top, right, bottom)
GREEN_HSV_LOWER = np.array([60, 100, 150])
GREEN_HSV_UPPER = np.array([90, 255, 255])
YELLOW_MATCH_THRESH = 0.6

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

TEMPLATE_HS = resource_path(os.path.join("fishingimages", "hs.png"))

def get_all_windows():
    windows = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            windows.append((hwnd, win32gui.GetWindowText(hwnd)))
    win32gui.EnumWindows(callback, None)
    return windows

# 获取窗口客户区屏幕矩形
def get_client_rect_screen(hwnd):
    rect = win32gui.GetClientRect(hwnd)
    left_top = win32gui.ClientToScreen(hwnd, (0, 0))
    right_bottom = win32gui.ClientToScreen(hwnd, (rect[2], rect[3]))
    return (left_top[0], left_top[1], right_bottom[0], right_bottom[1])

# ---------- 检测工作线程（使用 ImageGrab）----------
class DetectionWorker(QThread):
    data_signal = pyqtSignal(float, float, float, float, float)  # timestamp, left, right, yellow, speed
    error_signal = pyqtSignal(str)

    def __init__(self, hwnd):
        super().__init__()
        self.hwnd = hwnd
        self.running = True
        self.prev_green_center = None
        self.prev_time = None
        self.speed = 0.0

    def run(self):
        hs_template = cv2.imread(TEMPLATE_HS, cv2.IMREAD_GRAYSCALE)
        if hs_template is None:
            self.error_signal.emit(f"无法加载模板: {TEMPLATE_HS}")
            return

        def detect_green_zone(frame_rgb):
            l, t, r, b = ROI
            h, w = frame_rgb.shape[:2]
            if r > w or b > h or l < 0 or t < 0:
                return None
            roi = frame_rgb[t:b, l:r]
            hsv = cv2.cvtColor(roi, cv2.COLOR_RGB2HSV)
            mask = cv2.inRange(hsv, GREEN_HSV_LOWER, GREEN_HSV_UPPER)
            cols = np.any(mask > 0, axis=0)
            indices = np.where(cols)[0]
            if len(indices) == 0:
                return None
            return (int(indices[0]) + l, int(indices[-1]) + l)

        def detect_yellow_marker(frame_rgb):
            l, t, r, b = ROI
            h, w = frame_rgb.shape[:2]
            if r > w or b > h or l < 0 or t < 0:
                return None
            roi = frame_rgb[t:b, l:r]
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
            th, tw = hs_template.shape[:2]
            if gray.shape[0] < th or gray.shape[1] < tw:
                return None
            res = cv2.matchTemplate(gray, hs_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val < YELLOW_MATCH_THRESH:
                return None
            return max_loc[0] + tw//2 + l

        while self.running:
            try:
                if not win32gui.IsWindow(self.hwnd):
                    self.error_signal.emit("窗口已关闭")
                    break
                # 截取客户区图像
                client_rect = get_client_rect_screen(self.hwnd)
                img = ImageGrab.grab(bbox=client_rect)
                if img is None:
                    continue
                rgb = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                # 注意：上面我转了BGR，但检测函数需要RGB，简单再转回来
                rgb = cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB)

                green = detect_green_zone(rgb)
                yellow = detect_yellow_marker(rgb)
                if green is not None and yellow is not None:
                    timestamp = time.time()
                    left, right = green
                    center = (left + right)//2
                    if self.prev_green_center is not None and self.prev_time is not None:
                        dt = timestamp - self.prev_time
                        if dt > 0:
                            self.speed = abs(center - self.prev_green_center) / dt
                    self.prev_green_center = center
                    self.prev_time = timestamp
                    self.data_signal.emit(timestamp, left, right, yellow, self.speed)
            except Exception as e:
                self.error_signal.emit(str(e))
            time.sleep(0.02)  # 约50fps，可调节

    def stop(self):
        self.running = False
        self.wait()

# ---------- 主窗口 ----------
class MonitorWindow(QMainWindow):
    # ... (UI部分与之前基本相同，只是调用了新的DetectionWorker)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("钓鱼跟随检测工具(稳定版) - 选择窗口后开始")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setGeometry(100, 100, 600, 500)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        sel_layout = QHBoxLayout()
        sel_layout.addWidget(QLabel("目标窗口:"))
        self.window_combo = QComboBox()
        self.window_combo.setMinimumWidth(350)
        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.clicked.connect(self.refresh_windows)
        sel_layout.addWidget(self.window_combo)
        sel_layout.addWidget(self.refresh_btn)
        layout.addLayout(sel_layout)

        self.info_label = QLabel("请选择窗口并点击「开始监控」")
        layout.addWidget(self.info_label)

        self.status_label = QLabel("等待数据...")
        layout.addWidget(self.status_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始监控")
        self.stop_btn = QPushButton("停止监控")
        self.stop_btn.setEnabled(False)
        self.save_btn = QPushButton("保存数据")
        self.clear_btn = QPushButton("清空日志")
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout)

        self.record_cb = QCheckBox("记录数据到CSV")
        layout.addWidget(self.record_cb)

        self.start_btn.clicked.connect(self.start_monitor)
        self.stop_btn.clicked.connect(self.stop_monitor)
        self.save_btn.clicked.connect(self.save_data)
        self.clear_btn.clicked.connect(self.clear_log)

        self.worker = None
        self.data_buffer = []
        self.refresh_windows()

    def refresh_windows(self):
        self.window_combo.clear()
        windows = get_all_windows()
        if not windows:
            self.log("未找到任何可见窗口")
            return
        for hwnd, title in windows:
            self.window_combo.addItem(f"{title} (0x{hwnd:X})", hwnd)
        self.log(f"刷新窗口列表，共 {len(windows)} 个窗口")

    def get_selected_hwnd(self):
        hwnd = self.window_combo.currentData()
        if hwnd is None:
            return None
        if win32gui.IsWindow(hwnd):
            return hwnd
        else:
            self.log("所选窗口已失效，请刷新列表")
            return None

    def start_monitor(self):
        if self.worker is not None:
            self.log("监控已在运行")
            return
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            self.log("请先选择一个有效的窗口")
            return
        self.log(f"开始监控，窗口句柄: {hwnd}")
        self.worker = DetectionWorker(hwnd)
        self.worker.data_signal.connect(self.on_data)
        self.worker.error_signal.connect(lambda e: self.log(f"错误: {e}"))
        self.worker.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.info_label.setText(f"监控中 - {self.window_combo.currentText()}")

    def stop_monitor(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.info_label.setText("已停止")

    def on_data(self, ts, left, right, yellow, speed):
        center = (left + right)//2
        dev = yellow - center
        width = right - left
        line = (f"[{datetime.fromtimestamp(ts).strftime('%H:%M:%S.%f')[:-3]}] "
                f"绿区:[{left},{right}] 宽={width}  黄:{yellow}  "
                f"偏差={dev:+.1f}  速度={speed:.1f} px/s")
        self.log_text.append(line)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        self.status_label.setText(f"偏差: {dev:+.1f}  速度: {speed:.1f} px/s")
        if self.record_cb.isChecked():
            self.data_buffer.append((ts, left, right, yellow, speed))

    def save_data(self):
        if not self.data_buffer:
            self.log("没有数据可保存")
            return
        filename = f"fishing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "green_left", "green_right", "yellow_center", "speed_px_per_sec"])
            writer.writerows(self.data_buffer)
        self.log(f"已保存 {len(self.data_buffer)} 条数据到 {filename}")
        self.data_buffer.clear()

    def clear_log(self):
        self.log_text.clear()
        self.data_buffer.clear()
        self.log("日志已清空")

    def log(self, msg):
        self.log_text.append(f"[系统] {msg}")

    def closeEvent(self, event):
        self.stop_monitor()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MonitorWindow()
    win.show()
    sys.exit(app.exec_())