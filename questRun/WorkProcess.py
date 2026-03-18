import os
import sys
os.environ["TK_SILENCE_DEPRECATION"] = "1"

import threading
import time
import cv2
import numpy as np
import pygetwindow as gw
import mss
import keyboard
import random
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from dataclasses import dataclass
import pytesseract
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

MONSTER_COLOR_LOWER = (85, 70, 25)
MONSTER_COLOR_UPPER = (95, 140, 90)
MONSTER_MIN_RATIO = 0.002
MONSTER_MIN_PIXELS = 400
MONSTER_REGION = (620, 260, 1029, 462)

@dataclass
class Area:
    x_min: int
    x_max: int
    y_min: int
    y_max: int

LOCATION_AREAS = { 
    "floor3": {"x_min": 52, "x_max": 72, "y_min": 101, "y_max": 104},
    "floor3_1": {"x_min": 36, "x_max": 72, "y_min": 98, "y_max": 100},
    "floor3_2": {"x_min": 39, "x_max": 72, "y_min": 93, "y_max": 97},
    "floor3_3": {"x_min": 64, "x_max": 72, "y_min": 75, "y_max": 92},
    "iso_point": {"x_min": 25, "x_max": 36, "y_min": 107, "y_max": 107},
    "right_roof": {"x_min": 68, "x_max": 68, "y_min": 76, "y_max": 91}

}

AREA_OBJECTS = {name: Area(**values) for name, values in LOCATION_AREAS.items()}

window_title = "MapleStory Worlds-Mapleland"
mini_x, mini_y, mini_w, mini_h = 8, 31, 100, 255
MINIMAP_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minimap_region.txt")

# 미니맵 영역은 이 해상도 기준으로 저장·사용 (영역 지정 시 자동으로 이 크기로 맞춤)
MINIMAP_RESOLUTION = (1280, 720)


def load_minimap_region():
    """minimap_region.txt에서 x,y,w,h 로드 (있으면)."""
    global mini_x, mini_y, mini_w, mini_h
    if not os.path.isfile(MINIMAP_CONFIG_PATH):
        return
    try:
        with open(MINIMAP_CONFIG_PATH, "r", encoding="utf-8") as f:
            line = f.read().strip()
        parts = line.split()
        if len(parts) >= 4:
            mini_x = int(parts[0])
            mini_y = int(parts[1])
            mini_w = int(parts[2])
            mini_h = int(parts[3])
    except Exception:
        pass


def save_minimap_region():
    """현재 mini_x,y,w,h를 minimap_region.txt에 저장."""
    try:
        with open(MINIMAP_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(f"{mini_x} {mini_y} {mini_w} {mini_h}\n")
    except Exception:
        pass


def start_minimap_region_selector():
    """
    1. 게임 창을 1280x720으로 변경
    2. 캡처 화면을 열고 드래그로 미니맵 영역 지정
    3. 지정한 영역을 mini_x, mini_y, mini_w, mini_h에 반영하고 minimap_region.txt에 저장 (1280x720 기준)
    """
    global mini_x, mini_y, mini_w, mini_h
    win = get_game_window()
    if not win:
        log_message("게임 창을 찾을 수 없습니다. (윈도우/맥 공통)")
        return
    log_message("해상도 1280x720으로 변경 중...")
    resize_game_window()
    time.sleep(0.8)
    win = get_game_window()
    if not win:
        log_message("게임 창을 다시 찾지 못했습니다.")
        return
    try:
        left, top = win.left, win.top
        w, h = win.width, win.height
    except Exception as e:
        log_message(f"창 좌표 조회 실패: {e}")
        return
    if w != MINIMAP_RESOLUTION[0] or h != MINIMAP_RESOLUTION[1]:
        log_message(f"해상도가 {w}x{h}입니다. 1280x720이 아니면 영역이 어긋날 수 있습니다.")
    with mss.mss() as sct:
        region = {"left": left, "top": top, "width": w, "height": h}
        shot = sct.grab(region)
        img_bgra = np.array(shot)
    if img_bgra.size == 0:
        log_message("캡처 실패.")
        return
    scale = 1.0
    if w > 960:
        scale = 960 / w
    disp_w = int(w * scale)
    disp_h = int(h * scale)
    img_rgb = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2RGB)
    if scale != 1.0:
        img_disp = cv2.resize(img_rgb, (disp_w, disp_h), interpolation=cv2.INTER_AREA)
    else:
        img_disp = img_rgb
    if PIL_AVAILABLE:
        from PIL import Image
        photo = ImageTk.PhotoImage(Image.fromarray(img_disp))
    else:
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "eastcanyon_minimap_capture.png")
        cv2.imwrite(tmp, cv2.cvtColor(img_disp, cv2.COLOR_RGB2BGR))
        photo = tk.PhotoImage(file=tmp)
    start_x, start_y = None, None
    rect_id = None

    topwin = tk.Toplevel(root)
    topwin.title("미니맵 영역 지정 (1280x720) — 드래그로 영역 선택 후 놓기")
    topwin.geometry(f"{disp_w + 4}x{disp_h + 4}")
    canvas = tk.Canvas(topwin, width=disp_w, height=disp_h, cursor="cross")
    canvas.pack()
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)
    topwin.image = photo

    def on_press(e):
        nonlocal start_x, start_y, rect_id
        start_x, start_y = e.x, e.y
        if rect_id is not None:
            canvas.delete(rect_id)
        rect_id = canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="lime", width=2)

    def on_drag(e):
        nonlocal rect_id
        if rect_id is not None and start_x is not None:
            canvas.delete(rect_id)
            rect_id = canvas.create_rectangle(start_x, start_y, e.x, e.y, outline="lime", width=2)

    def on_release(e):
        nonlocal rect_id, start_x, start_y
        global mini_x, mini_y, mini_w, mini_h
        if start_x is None:
            return
        ex, ey = e.x, e.y
        x1, x2 = min(start_x, ex), max(start_x, ex)
        y1, y2 = min(start_y, ey), max(start_y, ey)
        if x2 - x1 < 5 or y2 - y1 < 5:
            log_message("영역이 너무 작습니다. 다시 드래그해 주세요.")
            return
        mini_x = int(x1 / scale)
        mini_y = int(y1 / scale)
        mini_w = max(1, int((x2 - x1) / scale))
        mini_h = max(1, int((y2 - y1) / scale))
        save_minimap_region()
        log_message(f"미니맵 영역 설정(1280x720 기준): x={mini_x} y={mini_y} w={mini_w} h={mini_h}")
        topwin.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)

stop_event = threading.Event()
pause_event = threading.Event()
position_lock = threading.Lock()
player_position = (None, None)
current_position = None
last_position = None
new_position = None
elapsed_time = None
position_start_time = None
skill_count = None
step = None

direction = "left"
macro_running = True
log_text = None
cached_game_window = None

frame_lock = threading.Lock()
latest_frame = None
latest_frame_time = 0.0

exp_preview_running = False
exp_preview_window = None
exp_preview_label = None
exp_preview_image = None
exp_ocr_running = False
last_exp_log_time = 0.0
last_exp_value = None
exp_measure_running = False
exp_start_time = None
exp_start_value = None
exp_time_var = None
exp_value_var = None
exp_pred_var = None

status_coord_var = None
status_area_var = None
status_time_var = None
status_monster_var = None
status_buff_var = None

moving_left = False
moving_right = False
moving_up = False
moving_down = False

use_ice_strike = False
use_thunder_bolt = False

buff = False
buff_timer_enabled = False
last_buff_time = 0
BUFF_INTERVAL_SEC = 90
buff_pending = False
manual_pause_until = 0
monster_detected = None

def randomSleep():
    time.sleep(random.uniform(0.1, 0.2))

def press_left():
    global moving_left, moving_right
    if not moving_left:
        keyboard.press("left")
        moving_left = True
    if moving_right:
        keyboard.release("right")
        moving_right = False

def press_right():
    global moving_left, moving_right
    if not moving_right:
        keyboard.press("right")
        moving_right = True
    if moving_left:
        keyboard.release("left")
        moving_left = False

def press_up():
    global moving_up
    if not moving_up:  
        keyboard.press("up")
        moving_up = True

def press_jump():
    keyboard.press("f")
    time.sleep(random.uniform(0.05, 0.09))
    keyboard.release("f")

def press_up_teleport():
    global moving_up
    if not moving_up:
        keyboard.press("up")
        moving_up = True
        time.sleep(random.uniform(0.07, 0.11))
        cast_teleport()
    if moving_up:
        keyboard.release("up")
        moving_up = False
        time.sleep(random.uniform(0.07, 0.11))

def press_down_jump():
    global moving_down
    if not moving_down:
        keyboard.press("down")
        time.sleep(random.uniform(0.18, 0.25))
        moving_down = True
    time.sleep(random.uniform(0.05, 0.08))
    press_jump()
    if moving_down:
        keyboard.release("down")
        moving_down = False

def release_movement():
    global moving_left, moving_right, moving_up
    if moving_left:
        keyboard.release("left") 
        moving_left = False
    if moving_right:
        keyboard.release("right")
        moving_right = False

def release_up():
    global moving_up
    if moving_up:
        keyboard.release("up")
        moving_up = False

def cast_ice_strike():
    global use_ice_strike
    if not use_ice_strike:
        keyboard.press("d")
        use_ice_strike = True
        time.sleep(random.uniform(0.07, 0.11))
    
    if use_ice_strike:
        keyboard.release("d")
        use_ice_strike = False

def cast_ice_strike_use():
    global use_ice_strike
    if not use_ice_strike:
        keyboard.press("d")
        use_ice_strike = True
        time.sleep(random.uniform(0.07, 0.11))
    
def cast_ice_strike_not_use():
    global use_ice_strike
    if use_ice_strike:
        keyboard.release("d")
        use_ice_strike = False
        time.sleep(random.uniform(0.07, 0.11))

def cast_thunder_bolt():
    keyboard.press("s")
    time.sleep(random.uniform(0.07, 0.11))
    keyboard.release("s")

def cast_teleport():
    if moving_left or moving_right or moving_up:
        keyboard.press("shift")
        time.sleep(random.uniform(0.07, 0.11))
        keyboard.release("shift")

def cast_buff():
        global skill_count, buff
        if not buff:
            buff = True
            keyboard.press("e")
            time.sleep(random.uniform(0.07, 0.11))
            keyboard.release("e")
            time.sleep(0.6)
            keyboard.press("w")
            time.sleep(random.uniform(0.07, 0.11))
            keyboard.release("w")
            time.sleep(0.6)
            keyboard.press("q")
            time.sleep(random.uniform(0.07, 0.11))
            keyboard.release("q")
            time.sleep(0.4)
            keyboard.press_and_release('page up')
            skill_count += 1

def cast_qe_buff():
    keyboard.press("q")
    time.sleep(random.uniform(0.07, 0.11))
    keyboard.release("q")
    time.sleep(0.7)
    keyboard.press("e")
    time.sleep(random.uniform(0.07, 0.11))
    keyboard.release("e")
            

def color_match(color1, color2, tolerance=20):
    return all(abs(c1 - c2) <= tolerance for c1, c2 in zip(color1, color2))

def update_status_display(x, y, area, elapsed, monster):
    if status_coord_var is None or status_area_var is None or status_time_var is None or status_monster_var is None or status_buff_var is None:
        return
    coord_text = f"{x},{y}" if x is not None and y is not None else "-"
    area_text = area if area is not None else "-"
    time_text = f"{elapsed:.1f}초" if elapsed is not None else "-"
    monster_text = "O" if monster else "X"
    if buff_timer_enabled:
        remain = max(0, int(BUFF_INTERVAL_SEC - (time.time() - last_buff_time)))
        buff_text = f"{remain}s"
    else:
        buff_text = "-"

    def apply():
        status_coord_var.set(coord_text)
        status_area_var.set(area_text)
        status_time_var.set(time_text)
        status_monster_var.set(monster_text)
        status_buff_var.set(buff_text)

    try:
        root.after(0, apply)
    except Exception:
        apply()

def location_detector():
    global current_position, last_position, position_start_time, elapsed_time, new_position, monster_detected
    grace_period = 1.5
    none_start_time = None

    time_time = time.time
    sleep = time.sleep
    area_items = list(AREA_OBJECTS.items())

    while not stop_event.is_set():
        x, y = player_position

        if x is None or y is None:
            if none_start_time is None:
                none_start_time = time_time()

            elapsed = time_time() - none_start_time
            if elapsed >= grace_period:
                last_position = None
                position_start_time = None
            update_status_display(None, None, last_position, 0.0 if position_start_time else None, monster_detected)
            sleep(0.2)
            continue

        none_start_time = None

        new_position = None
        for location, area in area_items:
            if area.x_min <= x <= area.x_max and area.y_min <= y <= area.y_max:
                new_position = location
                break

        elapsed_time = time_time() - position_start_time if position_start_time else 0

        if new_position != last_position:
            if new_position is not None:
                position_start_time = time_time()
                last_position = new_position
        update_status_display(x, y, new_position, elapsed_time, monster_detected)

        sleep(0.1)

def get_floor_name(location: str):
    return location.partition("_")[0] if location else None

def detect_location(x, y):
    for location, area in AREA_OBJECTS.items():
        if area.x_min <= x <= area.x_max and area.y_min <= y <= area.y_max:
            return location
    return None

def capture_loop():
    global latest_frame, latest_frame_time, cached_game_window
    time_sleep = time.sleep
    time_time = time.time
    with mss.mss() as sct:
        grab = sct.grab
        while not stop_event.is_set():
            if cached_game_window is None:
                cached_game_window = get_game_window()
            game_window = cached_game_window
            if not game_window:
                time_sleep(0.2)
                cached_game_window = None
                continue
            win_x, win_y = game_window.left, game_window.top
            win_w, win_h = game_window.width, game_window.height
            if win_w <= 0 or win_h <= 0:
                time_sleep(0.2)
                cached_game_window = None
                continue
            region = {"top": win_y, "left": win_x, "width": win_w, "height": win_h}
            screenshot = grab(region)
            img = np.array(screenshot)
            with frame_lock:
                latest_frame = img
                latest_frame_time = time_time()
            time_sleep(0.1)

def get_exp_region_from_frame(frame):
    h, w = frame.shape[:2]
    y1 = int(h * 0.9)
    y2 = h
    x1 = int(w * 0.46)
    x2 = int(w * 0.55)
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return roi
    rh = roi.shape[0]
    top = int(rh * 0.30)
    bottom = int(rh * 0.60)
    return roi[top:bottom, :]

def start_exp_preview():
    global exp_preview_running, exp_ocr_running
    global exp_measure_running, exp_start_time, exp_start_value
    if exp_preview_running:
        return
    exp_preview_running = True
    exp_ocr_running = True
    exp_measure_running = True
    exp_start_time = time.time()
    exp_start_value = None

def exp_ocr_loop():
    global last_exp_log_time, last_exp_value
    global exp_measure_running, exp_start_time, exp_start_value
    time_sleep = time.sleep
    time_time = time.time
    while not stop_event.is_set():
        if not exp_ocr_running:
            time_sleep(0.2)
            continue
        with frame_lock:
            frame = latest_frame
        if frame is None:
            time_sleep(0.2)
            continue
        roi = get_exp_region_from_frame(frame)
        if roi is None or roi.size == 0:
            time_sleep(0.2)
            continue
        roi = cv2.resize(roi, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_LINEAR)
        roi = cv2.cvtColor(roi, cv2.COLOR_BGRA2GRAY)
        _, roi = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text = pytesseract.image_to_string(roi, config="--psm 7")
        text = text.replace("EXP", "").replace("exp", "").strip()
        for sep in ("[", "(", " {", "{"):
            if sep in text:
                text = text.split(sep)[0].strip()
                break
        digits = "".join(ch for ch in text if ch.isdigit() or ch == ",")
        digits = digits.replace(",", "")
        if digits:
            try:
                exp_value = int(digits)
            except ValueError:
                exp_value = None
            now = time_time()
            if exp_value is not None:
                if exp_value != last_exp_value or (now - last_exp_log_time) >= 1.0:
                    last_exp_value = exp_value
                    last_exp_log_time = now
                if exp_measure_running and exp_start_time is not None:
                    if exp_start_value is None:
                        exp_start_value = exp_value
                    elapsed = max(0, int(now - exp_start_time))
                    gained = exp_value - (exp_start_value or exp_value)
                    per_hour = int(gained * 3600 / elapsed) if elapsed > 0 else 0
                    mm = elapsed // 60
                    ss = elapsed % 60
                    if exp_time_var is not None:
                        exp_time_var.set(f"{mm:02d}:{ss:02d}")
                    if exp_value_var is not None:
                        exp_value_var.set(f"{gained:,}")
                    if exp_pred_var is not None:
                        exp_pred_var.set(f"{per_hour:,}")
        time_sleep(1.0)

def search_player():
    global player_position
    global log_text
    global window_title
    global mini_x, mini_y, mini_w, mini_h
    global cached_game_window

    time_sleep = time.sleep
    cvt_color = cv2.cvtColor
    in_range = cv2.inRange

    while not stop_event.is_set():
        with frame_lock:
            frame = latest_frame
        if frame is None:
            time_sleep(0.05)
            continue
        y1 = mini_y
        y2 = mini_y + mini_h
        x1 = mini_x
        x2 = mini_x + mini_w
        if y2 > frame.shape[0] or x2 > frame.shape[1]:
            time_sleep(0.05)
            continue
        img = frame[y1:y2, x1:x2]
        img = cvt_color(img, cv2.COLOR_BGRA2BGR)

        mask = in_range(img, (136, 255, 255), (136, 255, 255))
        coords = cv2.findNonZero(mask)

        if coords is not None:
            x, y = coords[0][0]
            with position_lock:
                player_position = (x, y)

        time_sleep(0.1)

def steerage(x_min, x_max):
    global player_position, direction
    x, y = player_position

    if direction == "left":
        if x > x_min:
            press_left()
        else:
            direction = "right"
    elif direction == "right":
        if x < x_max:
            press_right()
        else:
            direction = "left"

def command_player():
    global new_position, elapsed_time, player_position, skill_count, buff, step
    global buff_timer_enabled, last_buff_time, manual_pause_until, buff_pending
    global moving_up, moving_down, moving_left, moving_right, direction

    time_time = time.time
    sleep = time.sleep

    step = 0
    skill_count = 0
    next_switch_time = 0.0
    next_skill_tap_time = 0.0
    force_turn_until = 0.0
    PRE_SWITCH_STOP_SKILL_SEC = 0.5
    FORCE_TURN_HOLD_SEC_NORMAL = 0.25
    # 몬스터 감지는 명령 로직에서 제외 (항상 몹이 있다고 가정)

    while not stop_event.is_set():
        if time_time() < manual_pause_until:
            cast_ice_strike_not_use()
            release_movement()
            sleep(0.05)
            continue
        if pause_event.is_set():
            sleep(0.1)
            continue

        x, y = player_position

        if x is None:
            release_movement()
            cast_ice_strike_not_use()
            sleep(0.1)
            continue

        # 미니맵 x좌표를 3등분해서 "가운데(중앙) 범위" 유지
        center_left = int(mini_w / 3)
        center_right = int(mini_w * 2 / 3)
        now = time_time()

        in_center = center_left <= x <= center_right

        if not in_center:
            # 중앙 범위를 벗어나면 중앙으로 복귀: 방향키는 누르고 있는 동안
            # 스킬은 약 1.5초에 한 번만 "딸깍"(탭) 사용
            cast_ice_strike_not_use()
            if x < center_left:
                press_right()
            else:
                press_left()

            if now >= next_skill_tap_time:
                cast_ice_strike()
                next_skill_tap_time = now + 1.5
        else:
            # 중앙 범위에 있으면: 좌/우 2~8초 랜덤으로 번갈아 이동하며 스킬은 지속 사용(홀드)
            next_skill_tap_time = 0.0
            # 방향 전환 직전(0.5초 전)에는 스킬 홀드를 미리 끊어서 전환을 안정화
            if next_switch_time > now and (next_switch_time - now) <= PRE_SWITCH_STOP_SKILL_SEC:
                cast_ice_strike_not_use()

            if now >= next_switch_time:
                direction = "right" if direction == "left" else "left"
                next_switch_time = now + random.uniform(2.0, 8.0)
                force_turn_until = now + FORCE_TURN_HOLD_SEC_NORMAL
                log_message(f"방향 전환 → {direction} (다음 전환까지 {max(0.0, next_switch_time - now):.1f}초)")

            if direction == "left":
                press_left()
            else:
                press_right()

            # 몬스터 피격 등으로 방향 전환이 씹히는 경우가 있어,
            # 전환 직후에는 일정 시간(기본 0.8초) 스킬 없이 방향키를 더 오래 밀어줌
            if now < force_turn_until:
                cast_ice_strike_not_use()
            else:
                cast_ice_strike_use()

        if buff_timer_enabled:
            if time_time() - last_buff_time >= BUFF_INTERVAL_SEC:
                buff_pending = True
            if buff_pending:
                cast_qe_buff()
                last_buff_time = time_time()
                buff_pending = False

        sleep(0.1)

def monster_detector():
    global monster_detected
    time_sleep = time.sleep
    cvt_color = cv2.cvtColor
    in_range = cv2.inRange
    count_nonzero = np.count_nonzero

    x1, y1, x2, y2 = MONSTER_REGION
    region_width = max(1, x2 - x1)
    region_height = max(1, y2 - y1)
    total_pixels = float(region_width * region_height)

    while not stop_event.is_set():
        with frame_lock:
            frame = latest_frame
        if frame is None:
            time_sleep(0.1)
            continue
        if y2 > frame.shape[0] or x2 > frame.shape[1]:
            time_sleep(0.1)
            continue
        img = frame[y1:y2, x1:x2]
        bgr = cvt_color(img, cv2.COLOR_BGRA2BGR)
        hsv = cvt_color(bgr, cv2.COLOR_BGR2HSV)
        mask = in_range(hsv, MONSTER_COLOR_LOWER, MONSTER_COLOR_UPPER)
        match_pixels = int(count_nonzero(mask))
        match_ratio = match_pixels / total_pixels
        found = (match_ratio >= MONSTER_MIN_RATIO) and (match_pixels >= MONSTER_MIN_PIXELS)

        monster_detected = found

        time_sleep(0.3)

def trim_log_listbox():
    try:
        if not IS_MAC or log_text is None:
            return
        MAX_LOG_LINES = 300
        n = log_text.size()
        if n > MAX_LOG_LINES:
            log_text.delete(0, n - MAX_LOG_LINES - 1)
    except Exception as e:
        print(f"[ERROR] 로그 정리 중 오류 발생: {e}")

def trim_log_lines():
    try:
        if IS_MAC:
            return
        MAX_LOG_LINES = 300
        total_lines = int(log_text.index('end-1c').split('.')[0])
        if total_lines > MAX_LOG_LINES:
            lines_to_delete = total_lines - MAX_LOG_LINES
            log_text.delete('1.0', f'{lines_to_delete + 1}.0')
    except Exception as e:
        print(f"[ERROR] 로그 정리 중 오류 발생: {e}")

def log_message(msg):
    if log_text is None or not log_text.winfo_exists():
        print(f"[WARNING] 로그 기록 실패: {msg}")
        return
    def update_log():
        if IS_MAC:
            log_text.insert(tk.END, msg)
            trim_log_listbox()
        else:
            log_text.insert(tk.END, msg + "\n")
            trim_log_lines()
        log_text.see(tk.END)
    root.after(0, update_log)

def force_kill():
    log_message("⚠ 강제 종료 수행")
    os._exit(1)

def all_clear():
    global moving_down, moving_up, moving_right, moving_left, use_ice_strike
    if moving_left:
        keyboard.release("left")
        moving_left = False
    if moving_right:
        keyboard.release("right")
        moving_right = False
    if moving_up:
        keyboard.release("up")
        moving_up = False
    if moving_down:
        keyboard.release("down")
        moving_down = False
    if use_ice_strike:
        keyboard.release("d")
        use_ice_strike = False

    for key in ("shift", "ctrl", "alt", "alt gr", "win", "left windows", "right windows"):
        try:
            keyboard.release(key)
        except Exception:
            pass

def on_closing():
    log_message("프로그램 종료 중...")
    stop_event.set()
    global exp_preview_running, exp_preview_window
    exp_preview_running = False
    global exp_ocr_running
    exp_ocr_running = False
    global exp_measure_running
    exp_measure_running = False
    if exp_preview_window is not None and exp_preview_window.winfo_exists():
        try:
            exp_preview_window.destroy()
        except Exception:
            pass

    timeout = 3

    all_clear()

    for thread, name in [(capture_thread, "capture_thread"),
                          (search_thread, "search_thread"),
                          (location_thread, "location_thread"),
                          (command_thread, "command_thread"),
                          (monster_thread, "monster_thread")]:
        if thread and thread.is_alive():
            log_message(f"🔴 {name} 종료 대기 (최대 {timeout}초)...")
            thread.join(timeout)
            if thread.is_alive():
                log_message(f"❌ {name} 종료 실패! 강제 종료 실행.")
                force_kill()

    log_message("✅ 모든 스레드 종료 완료, 프로그램 종료")
    root.destroy()


def start_command():
    global pause_event
    if pause_event.is_set():
        all_clear()
        pause_event.clear()
        focus_game_window()
        log_message("▶️ 자동 움직임 재개")
    else:
        log_message("▶️ 이미 실행중")

def pause_command():
    global pause_event
    if not pause_event.is_set():
        all_clear()
        pause_event.set()
        log_message("⏸️ 자동 움직임 일시정지")
    else:
        all_clear()
        log_message("⏸️ 이미 일시정지 상태")

def get_game_window():
    if not IS_WINDOWS:
        return None
    try:
        for window in gw.getWindowsWithTitle(window_title):
            if window_title in window.title:
                return window
    except Exception:
        pass
    return None

def focus_game_window():
    game_window = get_game_window()
    if not game_window:
        log_message("게임 창을 찾을 수 없습니다. (포커스)")
        return False
    try:
        if game_window.isMinimized:
            game_window.restore()
        game_window.activate()
        return True
    except Exception as e:
        log_message(f"게임 창 포커스 실패: {e}")
        return False

def resize_game_window():
    game_window = get_game_window()
    if not game_window:
        log_message("게임 창을 찾을 수 없습니다. (크기 조절)")
        return

    game_window.resizeTo(1280, 720)
    focus_game_window()
    log_message("게임 창 크기를 1280x720으로 조정했습니다.")

def start_buff_timer():
    global buff_timer_enabled, last_buff_time, buff_pending
    cast_qe_buff()
    buff_timer_enabled = True
    last_buff_time = time.time()
    buff_pending = False
    log_message("버프 즉시 사용 + 타이머 시작 (90초)")

def on_w_pressed(_event):
    global manual_pause_until
    manual_pause_until = time.time() + 1.0
    log_message("수동 W 감지: 1초간 자동동작 일시정지")


root = tk.Tk()
root.title("WorkProcess")
root.geometry("420x248")
root.minsize(400, 238)
root.protocol("WM_DELETE_WINDOW", on_closing)
root.grid_rowconfigure(3, weight=1, minsize=120)
root.grid_columnconfigure(0, weight=1, uniform="col")
root.grid_columnconfigure(1, weight=1, uniform="col")
root.grid_columnconfigure(2, weight=1, uniform="col")

if IS_MAC:
    root.option_add("*Text.background", "white")
    root.option_add("*Text.foreground", "black")
    root.option_add("*Text.font", "Menlo 11")
    root.option_add("*Text.selectBackground", "#0a84ff")
    root.option_add("*Text.selectForeground", "white")

btn_frame = tk.Frame(root)
btn_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=4, pady=2)
btn_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

btn_start = tk.Button(btn_frame, text="F1 시작", command=start_command, width=8)
btn_stop = tk.Button(btn_frame, text="F2 정지", command=pause_command, width=8)
btn_resize = tk.Button(btn_frame, text="F3 조정", command=resize_game_window, width=8)
btn_buff = tk.Button(btn_frame, text="F4 버프", command=start_buff_timer, width=8)
btn_minimap = tk.Button(btn_frame, text="F5 미니맵", command=start_minimap_region_selector, width=8)
btn_exp = tk.Button(btn_frame, text="경험치", command=start_exp_preview, width=8)

btn_start.grid(row=0, column=0, padx=2, pady=1, sticky="ew")
btn_stop.grid(row=0, column=1, padx=2, pady=1, sticky="ew")
btn_resize.grid(row=0, column=2, padx=2, pady=1, sticky="ew")
btn_buff.grid(row=0, column=3, padx=2, pady=1, sticky="ew")
btn_minimap.grid(row=0, column=4, padx=2, pady=1, sticky="ew")
btn_exp.grid(row=0, column=5, padx=2, pady=1, sticky="ew")

status_frame = tk.LabelFrame(root, text="상태", font=("Arial", 9))
status_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=4, pady=2)
status_frame.grid_columnconfigure(1, weight=1)
status_frame.grid_columnconfigure(3, weight=1)

status_coord_var = tk.StringVar(value="-")
status_area_var = tk.StringVar(value="-")
status_time_var = tk.StringVar(value="-")
status_monster_var = tk.StringVar(value="X")
status_buff_var = tk.StringVar(value="-")
exp_time_var = tk.StringVar(value="-")
exp_value_var = tk.StringVar(value="-")
exp_pred_var = tk.StringVar(value="-")

tk.Label(status_frame, text="좌표:", width=5, anchor="w").grid(row=0, column=0, sticky="w", padx=2, pady=1)
tk.Label(status_frame, textvariable=status_coord_var, anchor="w").grid(row=0, column=1, sticky="w", padx=2, pady=1)
tk.Label(status_frame, text="버프:", width=5, anchor="w").grid(row=0, column=2, sticky="w", padx=2, pady=1)
tk.Label(status_frame, textvariable=status_buff_var, anchor="w").grid(row=0, column=3, sticky="w", padx=2, pady=1)

tk.Label(status_frame, text="위치:", width=5, anchor="w").grid(row=1, column=0, sticky="w", padx=2, pady=1)
tk.Label(status_frame, textvariable=status_area_var, anchor="w").grid(row=1, column=1, sticky="w", padx=2, pady=1)
tk.Label(status_frame, text="시간:", width=5, anchor="w").grid(row=1, column=2, sticky="w", padx=2, pady=1)
tk.Label(status_frame, textvariable=status_time_var, anchor="w").grid(row=1, column=3, sticky="w", padx=2, pady=1)

tk.Label(status_frame, text="몬스터:", width=5, anchor="w").grid(row=2, column=0, sticky="w", padx=2, pady=1)
tk.Label(status_frame, textvariable=status_monster_var, anchor="w").grid(row=2, column=1, sticky="w", padx=2, pady=1)

exp_frame = tk.LabelFrame(root, text="경험치", font=("Arial", 9))
exp_frame.grid(row=1, column=2, sticky="nsew", padx=4, pady=2)
exp_frame.grid_columnconfigure(1, weight=1)

tk.Label(exp_frame, text="측정시간:", width=7, anchor="w").grid(row=0, column=0, sticky="w", padx=2, pady=1)
tk.Label(exp_frame, textvariable=exp_time_var, anchor="w").grid(row=0, column=1, sticky="w", padx=2, pady=1)
tk.Label(exp_frame, text="경험치:", width=7, anchor="w").grid(row=1, column=0, sticky="w", padx=2, pady=1)
tk.Label(exp_frame, textvariable=exp_value_var, anchor="w").grid(row=1, column=1, sticky="w", padx=2, pady=1)
tk.Label(exp_frame, text="예상(h):", width=7, anchor="w").grid(row=2, column=0, sticky="w", padx=2, pady=1)
tk.Label(exp_frame, textvariable=exp_pred_var, anchor="w").grid(row=2, column=1, sticky="w", padx=2, pady=1)

if IS_MAC:
    log_frame = tk.Frame(root)
    log_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=4, pady=2)
    log_frame.grid_rowconfigure(0, weight=1)
    log_frame.grid_columnconfigure(0, weight=1)
    log_text = tk.Listbox(
        log_frame, height=10, width=60,
        bg="white", fg="black", font=("Menlo", 11),
        highlightthickness=1, highlightbackground="#ccc",
        selectbackground="#0a84ff", selectforeground="white",
    )
    log_scroll = tk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
    log_text.configure(yscrollcommand=log_scroll.set)
    log_text.grid(row=0, column=0, sticky="nsew")
    log_scroll.grid(row=0, column=1, sticky="ns")
    log_text.insert(tk.END, "[INFO] 로그 준비됨.")
else:
    log_text = ScrolledText(
        root, height=7, width=48,
        bg="white", fg="black", insertbackground="black",
        font=("Consolas", 9),
        highlightthickness=1, highlightbackground="#ccc",
        wrap=tk.WORD,
    )
    log_text.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=4, pady=2)
    log_text.insert(tk.END, "[INFO] 로그 준비됨.\n")
    log_text.see(tk.END)

root.update_idletasks()

if IS_MAC:
    root.update()

load_minimap_region()

pause_event.set()
log_message("⏸️ 자동 움직임 시작 상태: OFF")

capture_thread = threading.Thread(target=capture_loop, daemon=True)
search_thread = threading.Thread(target=search_player, daemon=True)
location_thread = threading.Thread(target=location_detector, daemon=True)
command_thread = threading.Thread(target=command_player, daemon=True)
monster_thread = threading.Thread(target=monster_detector, daemon=True)
exp_thread = threading.Thread(target=exp_ocr_loop, daemon=True)
capture_thread.start()
search_thread.start()
command_thread.start()
location_thread.start()
monster_thread.start()
exp_thread.start()

if IS_WINDOWS:
    keyboard.add_hotkey("F1", start_command)
    keyboard.add_hotkey("F2", pause_command)
    keyboard.add_hotkey("F3", resize_game_window)
    keyboard.add_hotkey("F4", start_buff_timer)
    keyboard.add_hotkey("F5", start_minimap_region_selector)
    keyboard.on_press_key("w", on_w_pressed)
else:
    log_message("[INFO] 맥: F1~F4·W 키보드 후크 미등록 (위 버튼으로 제어)")

root.mainloop()