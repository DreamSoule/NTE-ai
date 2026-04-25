# buy_bait.py
import time
import random
import pydirectinput
import win32gui
from PIL import ImageGrab
import cv2
import numpy as np
import sys
import os

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

IMG_DIR = "fishingimages"
PATH_WANNGENYUER = resource_path(os.path.join(IMG_DIR, "wannengyuer.png"))
PATH_YUERLAMAN = resource_path(os.path.join(IMG_DIR, "yuerlaman.png"))
PATH_GOUMAIYUER = resource_path(os.path.join(IMG_DIR, "goumaiyuer.png"))
PATH_QUEREN = resource_path(os.path.join(IMG_DIR, "queren.png"))
PATH_YUERTISHIQUEREN = resource_path(os.path.join(IMG_DIR, "yueertishiqueren.png"))
PATH_DIANJIKONGBAI = resource_path(os.path.join(IMG_DIR, "dianjikongbai.png"))
PATH_GENGHUANWANNGYUER = resource_path(os.path.join(IMG_DIR, "genghuanwannnegyuer.png"))
PATH_GENGHUAN = resource_path(os.path.join(IMG_DIR, "genghuan.png"))
PATH_PANDUANDIAOYU = resource_path(os.path.join(IMG_DIR, "panduandiaoyu.png"))
MATCH_THRESH = 0.7

def find_image_in_window(template_path, hwnd, timeout=0, interval=0.2):
    if not hwnd:
        return None
    rect = win32gui.GetClientRect(hwnd)
    left_top = win32gui.ClientToScreen(hwnd, (0, 0))
    right_bottom = win32gui.ClientToScreen(hwnd, (rect[2], rect[3]))
    client_rect = (left_top[0], left_top[1], right_bottom[0], right_bottom[1])
    start = time.time()
    while timeout <= 0 or (time.time() - start) < timeout:
        try:
            img = ImageGrab.grab(bbox=client_rect)
            gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                return None
            res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= MATCH_THRESH:
                h, w = template.shape
                return (max_loc[0] + w//2, max_loc[1] + h//2)
        except:
            pass
        time.sleep(interval)
    return None

def random_click_screen(pos, offset=10):
    x = pos[0] + random.randint(-offset, offset)
    y = pos[1] + random.randint(-offset, offset)
    pydirectinput.moveTo(x, y)
    time.sleep(0.02)
    pydirectinput.click()
    time.sleep(0.02)

def click_in_window(pos, hwnd, offset=10):
    """点击窗口客户区内的相对坐标"""
    rect = win32gui.GetClientRect(hwnd)
    left_top = win32gui.ClientToScreen(hwnd, (0, 0))
    screen_x = left_top[0] + pos[0] + random.randint(-offset, offset)
    screen_y = left_top[1] + pos[1] + random.randint(-offset, offset)
    pydirectinput.moveTo(screen_x, screen_y)
    time.sleep(0.02)
    pydirectinput.click()
    time.sleep(0.02)

def click_image_in_window(template_path, hwnd, wait=0.5, timeout=2):
    pos = find_image_in_window(template_path, hwnd, timeout=timeout)
    if pos:
        click_in_window(pos, hwnd)
        time.sleep(wait)
        return True
    return False

def do_buy_bait(hwnd):
    """执行完整购买+更换流程，返回是否成功"""
    print("[购买] 开始购买鱼饵流程")
    # 1. 按R进入购买界面
    pydirectinput.press('r')
    time.sleep(1)
    # 2. 选择万能鱼饵
    if not click_image_in_window(PATH_WANNGENYUER, hwnd, wait=0.5, timeout=3):
        print("[购买] 未找到万能鱼饵选项，没有解锁？")
        pydirectinput.press('esc')
        return False
    # 3. 鱼饵拉满
    click_image_in_window(PATH_YUERLAMAN, hwnd, wait=0.5, timeout=3)
    # 4. 点击购买
    click_image_in_window(PATH_GOUMAIYUER, hwnd, wait=1, timeout=3)
    # 5. 确认购买
    click_image_in_window(PATH_QUEREN, hwnd, wait=1, timeout=3)
    # 6. 鱼饵提示确认
    click_image_in_window(PATH_YUERTISHIQUEREN, hwnd, wait=1, timeout=3)
    # 7. 点击空白关闭
    click_image_in_window(PATH_DIANJIKONGBAI, hwnd, wait=0.5, timeout=3)
    time.sleep(1)
    pydirectinput.press('esc')
    print("[购买] 购买完成，开始更换鱼饵")
    # 更换鱼饵
    # 等待回到钓鱼界面
    if not find_image_in_window(PATH_PANDUANDIAOYU, hwnd, timeout=5):
        print("[更换] 未回到钓鱼界面")
        return False
    pydirectinput.press('e')
    time.sleep(1)
    # if not click_image_in_window(PATH_GENGHUANWANNGYUER, hwnd, wait=1, timeout=3):
    #     print("[更换] 未找到万能鱼饵选项，可能已更换过")
    #     pydirectinput.press('esc')
    #     return True
    click_image_in_window(PATH_GENGHUAN, hwnd, wait=1, timeout=3)
    time.sleep(1)
    # pydirectinput.press('esc')
    if find_image_in_window(PATH_PANDUANDIAOYU, hwnd, timeout=5):
        print("[更换] 更换成功")
    return True