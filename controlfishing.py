import cv2
import numpy as np
import pydirectinput
import win32gui
import time
import threading
import queue
from PIL import ImageGrab
import sys
import os

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

IMG_DIR = "fishingimages"
TEMPLATE_HS = resource_path(os.path.join(IMG_DIR, "hs.png"))
TEMPLATE_DDS = resource_path(os.path.join(IMG_DIR, "dds.png"))

WINDOW_TITLE = "异环"
ROI = (597, 61, 1328, 85)          # 根据实际窗口调整
MATCH_THRESH = 0.6
CAPTURE_DELAY = 0.0

pos_queue = queue.Queue(maxsize=1)

def get_hwnd():
    """备用自动查找（不使用 PID 比较，仅通过标题排除自身）"""
    def cb(hwnd, lst):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "异环" in title and "异环薄荷AI" not in title:
                lst.append(hwnd)
    lst = []
    win32gui.EnumWindows(cb, lst)
    return lst[0] if lst else None

def find_center(gray, tpl, th):
    res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
    _, maxv, _, maxloc = cv2.minMaxLoc(res)
    if maxv >= th:
        h, w = tpl.shape
        return (maxloc[0] + w//2, maxloc[1] + h//2)
    return None

def capture_worker(hwnd, hs_tpl, dds_tpl, stop_event):
    l, t, r, b = ROI
    while not stop_event.is_set():
        try:
            left_top = win32gui.ClientToScreen(hwnd, (l, t))
            right_bottom = win32gui.ClientToScreen(hwnd, (r, b))
            bbox = (left_top[0], left_top[1], right_bottom[0], right_bottom[1])
            img = ImageGrab.grab(bbox=bbox)
            gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
            hs = find_center(gray, hs_tpl, MATCH_THRESH)
            dds = find_center(gray, dds_tpl, MATCH_THRESH)
            if hs and dds:
                hs_x = hs[0] + l
                dds_x = dds[0] + l
                try:
                    pos_queue.put_nowait((hs_x, dds_x))
                except queue.Full:
                    try:
                        pos_queue.get_nowait()
                        pos_queue.put_nowait((hs_x, dds_x))
                    except:
                        pass
        except:
            pass

def control_worker(stop_event):
    DEAD_ZONE = 2
    PULSE_VERY_SHORT = 0.005
    PULSE_SHORT = 0.010
    PULSE_MEDIUM = 0.020
    PULSE_LONG = 0.035
    BRAKE_PULSE = 0.015

    last_dds_x = None
    static_cnt = 0
    last_hs_x = None
    key_a = False
    key_d = False

    def release_all():
        nonlocal key_a, key_d
        if key_a:
            pydirectinput.keyUp('a')
            key_a = False
        if key_d:
            pydirectinput.keyUp('d')
            key_d = False

    while not stop_event.is_set():
        try:
            hs_x, dds_x = pos_queue.get_nowait()
        except queue.Empty:
            continue

        if last_dds_x is not None and abs(dds_x - last_dds_x) <= 1:
            static_cnt += 1
        else:
            static_cnt = 0
        last_dds_x = dds_x

        diff = hs_x - dds_x
        abs_diff = abs(diff)

        if static_cnt >= 3:
            release_all()
            if abs_diff > DEAD_ZONE:
                for _ in range(2):
                    if diff > 0:
                        pydirectinput.keyDown('a')
                        time.sleep(BRAKE_PULSE)
                        pydirectinput.keyUp('a')
                    else:
                        pydirectinput.keyDown('d')
                        time.sleep(BRAKE_PULSE)
                        pydirectinput.keyUp('d')
            time.sleep(0.05)
            continue

        if last_hs_x is not None:
            prev_diff = last_hs_x - dds_x
            if prev_diff * diff < 0 and abs_diff > DEAD_ZONE:
                release_all()
                if diff > 0:
                    pydirectinput.keyDown('a')
                    time.sleep(BRAKE_PULSE)
                    pydirectinput.keyUp('a')
                else:
                    pydirectinput.keyDown('d')
                    time.sleep(BRAKE_PULSE)
                    pydirectinput.keyUp('d')
                time.sleep(0.005)
                try:
                    hs_x2, dds_x2 = pos_queue.get_nowait()
                    diff2 = hs_x2 - dds_x2
                except queue.Empty:
                    diff2 = diff
                if diff2 > DEAD_ZONE and hs_x2 > dds_x2:
                    pydirectinput.keyDown('a')
                    time.sleep(PULSE_LONG)
                    pydirectinput.keyUp('a')
                elif diff2 < -DEAD_ZONE and hs_x2 < dds_x2:
                    pydirectinput.keyDown('d')
                    time.sleep(PULSE_LONG)
                    pydirectinput.keyUp('d')
                last_hs_x = hs_x
                continue

        can_press_a = (diff > 0) and (hs_x > dds_x)
        can_press_d = (diff < 0) and (hs_x < dds_x)

        if abs_diff <= DEAD_ZONE:
            release_all()
        else:
            if abs_diff > 20:
                pulse = PULSE_LONG
            elif abs_diff > 12:
                pulse = PULSE_MEDIUM
            elif abs_diff > 6:
                pulse = PULSE_SHORT
            else:
                pulse = PULSE_VERY_SHORT

            if can_press_a:
                release_all()
                pydirectinput.keyDown('a')
                time.sleep(pulse)
                pydirectinput.keyUp('a')
            elif can_press_d:
                release_all()
                pydirectinput.keyDown('d')
                time.sleep(pulse)
                pydirectinput.keyUp('d')
            else:
                release_all()

        last_hs_x = hs_x

    release_all()

def start_follow(stop_event, target_hwnd=None):
    if target_hwnd is None:
        hwnd = get_hwnd()
    else:
        hwnd = target_hwnd
    if not hwnd:
        print("找不到窗口")
        return False
    print(f"找到窗口句柄: {hwnd}")
    hs = cv2.imread(TEMPLATE_HS, cv2.IMREAD_GRAYSCALE)
    dds = cv2.imread(TEMPLATE_DDS, cv2.IMREAD_GRAYSCALE)
    if hs is None or dds is None:
        print("模板图片不存在，请检查 fishingimages 文件夹")
        return False
    t1 = threading.Thread(target=capture_worker, args=(hwnd, hs, dds, stop_event), daemon=True)
    t2 = threading.Thread(target=control_worker, args=(stop_event,), daemon=True)
    t1.start()
    t2.start()
    return True