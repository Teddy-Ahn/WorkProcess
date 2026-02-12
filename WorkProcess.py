import os
import sys
# 맥: 시스템 Tk 사용 시 deprecated 경고 억제 (tkinter import 전에 설정)
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

# OS 구분 (맥에서 키보드 후크 등 권한 이슈로 예외 처리할 때 사용)
IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# 몬스터 색상 범위(HSV). 다크 틸 핵심색 기준
MONSTER_COLOR_LOWER = (85, 70, 25)
MONSTER_COLOR_UPPER = (95, 140, 90)
MONSTER_MIN_RATIO = 0.002  # 전체 픽셀 대비 감지 비율
MONSTER_MIN_PIXELS = 400   # 최소 감지 픽셀 수
MONSTER_REGION = (620, 260, 1029, 462)  # (x1, y1, x2, y2) 게임창 기준 좌표

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

# 🟢 LOCATION_AREAS를 객체로 변환
AREA_OBJECTS = {name: Area(**values) for name, values in LOCATION_AREAS.items()}

window_title = "MapleStory Worlds-Mapleland"
mini_x, mini_y, mini_w, mini_h = 8, 31, 100, 255  # 미니맵 영역

# 전역 변수 (서칭 결과를 저장할 변수)
stop_event = threading.Event()
pause_event = threading.Event()
position_lock = threading.Lock()
player_position = (None, None)  # (x, y)
current_position = None
last_position = None
new_position = None
elapsed_time = None
position_start_time = None  # 현재 위치에서 머문 시간 기록
skill_count = None
step = None

direction = "left"
macro_running = True  # 매크로 실행 상태
log_text = None
# 미니맵/창 핸들 캐시 (pygetwindow 오버헤드 감소용)
cached_game_window = None

# 현재 상태 표시용 변수 (GUI 업데이트)
status_coord_var = None
status_area_var = None
status_time_var = None
status_monster_var = None
status_buff_var = None
# root = tk.Tk()

# 방향키 상태 변수 (중복 입력 방지)
moving_left = False
moving_right = False
moving_up = False
moving_down = False

# 스킬사용 상태 변수 (중복 입력 방지)
use_ice_strike = False
use_thunder_bolt = False

buff = False
buff_timer_enabled = False
last_buff_time = 0
BUFF_INTERVAL_SEC = 90  # F4 기준 90초
buff_pending = False
manual_pause_until = 0
monster_detected = None

def randomSleep():
    time.sleep(random.uniform(0.1, 0.2))

def press_left():
    global moving_left, moving_right
    if not moving_left:  # 중복 입력 방지
        keyboard.press("left")
        moving_left = True
    if moving_right:  # 오른쪽 이동 중이었다면 중지
        keyboard.release("right")
        moving_right = False

def press_right():
    global moving_left, moving_right
    if not moving_right:
        keyboard.press("right")
        moving_right = True
    if moving_left:  # 왼쪽 이동 중이었다면 중지
        keyboard.release("left")
        moving_left = False

def press_up():
    global moving_up
    if not moving_up:  
        keyboard.press("up")
        moving_up = True

def press_jump():
    keyboard.press("f")
    time.sleep(random.uniform(0.05, 0.09))  # 짧은 입력
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
        time.sleep(random.uniform(0.07, 0.11))  # 짧은 입력

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
    """이동 키를 모두 해제"""
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
    if moving_left or moving_right or moving_up:  # 방향키가 눌려있을 때만 실행
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
    """현재 상태를 고정 영역에 표시 (로그 대신 값 업데이트)"""
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
    grace_period = 1.5  # 🕒 None이 연속으로 나타나도 유지할 최대 시간
    none_start_time = None  # 🕒 None이 최초로 감지된 시간

    # 🔧 자주 쓰는 함수/데이터 로컬 바인딩 (성능 미세 최적화, 동작 동일)
    time_time = time.time
    sleep = time.sleep
    area_items = list(AREA_OBJECTS.items())

    while not stop_event.is_set():  # 🟢 stop_event가 설정되면 루프 종료
        x, y = player_position  # 서칭된 좌표 가져오기

        # 좌표가 None이면 grace_period 내에서는 유지
        if x is None or y is None:
            if none_start_time is None:
                none_start_time = time_time()  # 🕒 None 최초 감지 시간 기록

            elapsed = time_time() - none_start_time
            if elapsed >= grace_period:  # 🕒 grace_period를 넘기면 last_position 초기화
                last_position = None
                position_start_time = None
            update_status_display(None, None, last_position, 0.0 if position_start_time else None, monster_detected)
            sleep(0.2)
            continue  # 다음 루프로 이동

        # None이 아닌 좌표가 감지되면 None 타이머 초기화
        none_start_time = None

        # 현재 좌표가 어느 위치인지 확인
        new_position = None
        for location, area in area_items:
            if area.x_min <= x <= area.x_max and area.y_min <= y <= area.y_max:
                new_position = location
                break

        # 머문 시간 계산
        elapsed_time = time_time() - position_start_time if position_start_time else 0

        # 위치가 변경되었을 때만 시간 기록
        if new_position != last_position:
            if new_position is not None:
                position_start_time = time_time()  # 새로운 위치에서 시간 초기화
                last_position = new_position
        update_status_display(x, y, new_position, elapsed_time, monster_detected)

        sleep(0.1)  # 너무 빠르게 체크하지 않도록 조절

def get_floor_name(location: str):
    return location.partition("_")[0] if location else None  # "_" 앞부분만 추출

def detect_location(x, y):
    for location, area in AREA_OBJECTS.items():  # AREA_OBJECTS를 사용
        if area.x_min <= x <= area.x_max and area.y_min <= y <= area.y_max:
            return location
    return None  # 범위에 없는 경우

# 1. 서칭 로직 (미니맵에서 플레이어 위치 찾기)
def search_player():
    global player_position
    global log_text
    global window_title
    global mini_x, mini_y, mini_w, mini_h
    global cached_game_window

    # 🔧 자주 쓰는 함수/모듈 로컬 바인딩 (동작 동일, 호출 비용 감소)
    time_sleep = time.sleep
    cvt_color = cv2.cvtColor
    in_range = cv2.inRange

    with mss.mss() as sct:
        grab = sct.grab
        while not stop_event.is_set():  # 🟢 stop_event가 설정되면 루프 종료
            # 🔧 창 핸들 캐시: 이미 찾은 창이 있으면 그대로 사용, 없을 때만 검색
            if cached_game_window is None:
                cached_game_window = get_game_window()

            game_window = cached_game_window
            if not game_window:
                log_message("게임 창을 찾을 수 없습니다.")
                time_sleep(0.5)
                # 다음 루프에서 다시 검색 시도
                cached_game_window = None
                continue

            win_x, win_y = game_window.left, game_window.top
            region = {"top": win_y + mini_y, "left": win_x + mini_x, "width": mini_w, "height": mini_h}
            screenshot = grab(region)
            img = np.array(screenshot)
            img = cvt_color(img, cv2.COLOR_BGRA2BGR)  # BGRA → BGR 변환

            # mask = cv2.inRange(img, (0, 255, 255), (0, 255, 255))      # 0xFFFF00
            mask = in_range(img, (136, 255, 255), (136, 255, 255))  # 0xFFFF88
            coords = cv2.findNonZero(mask)  # 노란색 픽셀 좌표 찾기

            if coords is not None:  # 둘 중 하나라도 탐지되면 즉시 반영
                x, y = coords[0][0]  # 첫 번째 검출된 좌표 사용
                with position_lock:
                    player_position = (x, y)

            time_sleep(0.1)  # 너무 빠르게 실행되지 않도록 제한

def steerage(x_min, x_max):
    global player_position, direction
    x, y = player_position

    if direction == "left":
        if x > x_min:
            press_left()
        else:
            direction = "right"  # 🔄 방향 전환
    elif direction == "right":
        if x < x_max:
            press_right()
        else:
            direction = "left"  # 🔄 방향 전환

# 2. 커맨더 로직 (플레이어 위치에 따라 방향키 입력) — 3층(floor3)에서만 동작
def command_player():
    global new_position, elapsed_time, player_position, skill_count, buff, step, monster_detected
    global buff_timer_enabled, last_buff_time, manual_pause_until, buff_pending
    global moving_up, moving_down, moving_left, moving_right, direction

    # 🔧 자주 쓰는 함수 로컬 바인딩
    time_time = time.time
    sleep = time.sleep

    last_face_time = 0
    in_target_range = False
    step = 0
    skill_count = 0

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

        # 3층(floor3) 외에는 키만 풀고 동작 없음
        if new_position != "floor3":
            release_movement()
            cast_ice_strike_not_use()
            sleep(0.1)
            continue

        # 3층: x=64로 이동, 왼쪽 바라보기, 사냥·버프
        target_x = 64
        eventX = x - target_x
        if abs(eventX) <= 2:
            release_movement()
            if not in_target_range and time_time() - last_face_time >= 0.5:
                keyboard.press("left")
                sleep(random.uniform(0.05, 0.09))
                keyboard.release("left")
                last_face_time = time_time()
                log_message("floor3: x=64 도착, 왼쪽 바라봄")
            in_target_range = True
        elif eventX > 2:
            in_target_range = False
            press_left()
        else:
            in_target_range = False
            press_right()

        if monster_detected and eventX >= -2:
            cast_ice_strike_use()
        else:
            cast_ice_strike_not_use()

        if buff_timer_enabled:
            if time_time() - last_buff_time >= BUFF_INTERVAL_SEC:
                buff_pending = True
            if buff_pending and not monster_detected:
                cast_qe_buff()
                last_buff_time = time_time()
                buff_pending = False

        sleep(0.1)

def monster_detector():
    global monster_detected
    # 🔧 자주 쓰는 함수/모듈 로컬 바인딩 + 상수 캐싱
    time_sleep = time.sleep
    cvt_color = cv2.cvtColor
    in_range = cv2.inRange
    count_nonzero = np.count_nonzero

    x1, y1, x2, y2 = MONSTER_REGION
    region_width = max(1, x2 - x1)
    region_height = max(1, y2 - y1)
    total_pixels = float(region_width * region_height)

    with mss.mss() as sct:
        while not stop_event.is_set():
            game_window = get_game_window()
            if not game_window:
                time_sleep(0.5)
                continue

            region = {
                "top": game_window.top + y1,
                "left": game_window.left + x1,
                "width": region_width,
                "height": region_height
            }
            screenshot = sct.grab(region)
            img = np.array(screenshot)
            bgr = cvt_color(img, cv2.COLOR_BGRA2BGR)
            hsv = cvt_color(bgr, cv2.COLOR_BGR2HSV)
            mask = in_range(hsv, MONSTER_COLOR_LOWER, MONSTER_COLOR_UPPER)
            match_pixels = int(count_nonzero(mask))
            match_ratio = match_pixels / total_pixels
            found = (match_ratio >= MONSTER_MIN_RATIO) and (match_pixels >= MONSTER_MIN_PIXELS)

            monster_detected = found

            time_sleep(0.5)

# GUI 로그 출력 (맥: Listbox 사용 시 글자 렌더링 이슈 회피)
def trim_log_listbox():
    """맥 전용: Listbox 로그 최대 300줄 유지"""
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
    """윈도우 전용: ScrolledText 로그 최대 300줄 유지"""
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
    os._exit(1)  # 🛑 강제 종료 (GUI 응답 없음 방지)

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

    # 🔧 혹시 남아 있을 수 있는 보조키/모디파이어도 함께 해제 (윈도우 핫키 안정성용)
    for key in ("shift", "ctrl", "alt", "alt gr", "win", "left windows", "right windows"):
        try:
            keyboard.release(key)
        except Exception:
            # 해당 키가 실제로 눌려있지 않을 수 있으므로 예외는 무시
            pass

def on_closing():
    log_message("프로그램 종료 중...")
    stop_event.set()  # 🔴 스레드 종료 신호 보내기

    timeout = 3  # ⏳ 최대 대기 시간 (초)

    # 종료될 때 눌린 키를 모두 해제함
    all_clear()

    for thread, name in [(search_thread, "search_thread"),
                          (location_thread, "location_thread"),
                          (command_thread, "command_thread"),
                          (monster_thread, "monster_thread")]:
        if thread and thread.is_alive():
            log_message(f"🔴 {name} 종료 대기 (최대 {timeout}초)...")
            thread.join(timeout)  # ⏳ 최대 대기 시간 후 강제 종료 체크
            if thread.is_alive():
                log_message(f"❌ {name} 종료 실패! 강제 종료 실행.")
                force_kill()

    log_message("✅ 모든 스레드 종료 완료, 프로그램 종료")
    root.destroy()  # 🔴 GUI 종료


def start_command():
    global pause_event
    if pause_event.is_set():
        all_clear()
        pause_event.clear()  # 재개
        focus_game_window()
        log_message("▶️ 자동 움직임 재개")
    else:
        log_message("▶️ 이미 실행중")

def pause_command():
    global pause_event
    if not pause_event.is_set():
        all_clear()
        pause_event.set()  # 정지
        log_message("⏸️ 자동 움직임 일시정지")
    else:
        all_clear()
        log_message("⏸️ 이미 일시정지 상태")

def get_game_window():
    """게임 창 핸들 반환. Windows에서만 pygetwindow 사용, 맥에서는 미지원으로 None."""
    if not IS_WINDOWS:
        return None  # pygetwindow.getWindowsWithTitle는 Windows 전용
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


# GUI: grid로 로그 영역이 항상 공간을 갖도록 (윈도우·맥 공통)
root = tk.Tk()
root.title("WorkProcess")
root.geometry("420x248")
root.minsize(400, 238)
root.protocol("WM_DELETE_WINDOW", on_closing)
root.grid_rowconfigure(3, weight=1, minsize=120)  # 맥에서 로그 영역 최소 높이 보장
root.grid_columnconfigure(0, weight=1, uniform="col")
root.grid_columnconfigure(1, weight=1, uniform="col")
root.grid_columnconfigure(2, weight=1, uniform="col")

# 맥: Text/ScrolledText가 테마 때문에 글자가 안 보이는 경우 방지 (옵션 DB 강제)
if IS_MAC:
    root.option_add("*Text.background", "white")
    root.option_add("*Text.foreground", "black")
    root.option_add("*Text.font", "Menlo 11")
    root.option_add("*Text.selectBackground", "#0a84ff")
    root.option_add("*Text.selectForeground", "white")

# 제어 버튼 (맥에서는 키보드 후크 미동작이므로 필수, 윈도우에서도 보조용)
btn_frame = tk.Frame(root)
btn_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=4, pady=2)
btn_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

btn_resume = tk.Button(btn_frame, text="재개(F1)", command=start_command, width=9)
btn_pause = tk.Button(btn_frame, text="일시정지(F2)", command=pause_command, width=10)
btn_resize = tk.Button(btn_frame, text="1280x720(F3)", command=resize_game_window, width=11)
btn_buff = tk.Button(btn_frame, text="버프 타이머(F4)", command=start_buff_timer, width=12)

btn_resume.grid(row=0, column=0, padx=3, pady=1, sticky="ew")
btn_pause.grid(row=0, column=1, padx=3, pady=1, sticky="ew")
btn_resize.grid(row=0, column=2, padx=3, pady=1, sticky="ew")
btn_buff.grid(row=0, column=3, padx=3, pady=1, sticky="ew")

# 상태 프레임 (현재 위치/시간/몬스터 상태 표시)
status_frame = tk.LabelFrame(root, text="상태", font=("Arial", 9))
status_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=(4, 2), pady=2)
status_frame.grid_columnconfigure(1, weight=1)
status_frame.grid_columnconfigure(3, weight=1)

status_coord_var = tk.StringVar(value="-")
status_area_var = tk.StringVar(value="-")
status_time_var = tk.StringVar(value="-")
status_monster_var = tk.StringVar(value="X")
status_buff_var = tk.StringVar(value="-")

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

# 경험치 프레임 (추후 연동 예정: 표시만)
exp_frame = tk.LabelFrame(root, text="경험치", font=("Arial", 9))
exp_frame.grid(row=1, column=2, sticky="nsew", padx=(2, 4), pady=2)
exp_frame.grid_columnconfigure(1, weight=1)

tk.Label(exp_frame, text="측정시간:", width=7, anchor="w").grid(row=0, column=0, sticky="w", padx=2, pady=1)
tk.Label(exp_frame, text="-", anchor="w").grid(row=0, column=1, sticky="w", padx=2, pady=1)
tk.Label(exp_frame, text="경험치:", width=7, anchor="w").grid(row=1, column=0, sticky="w", padx=2, pady=1)
tk.Label(exp_frame, text="-", anchor="w").grid(row=1, column=1, sticky="w", padx=2, pady=1)
tk.Label(exp_frame, text="예상(h):", width=7, anchor="w").grid(row=2, column=0, sticky="w", padx=2, pady=1)
tk.Label(exp_frame, text="-", anchor="w").grid(row=2, column=1, sticky="w", padx=2, pady=1)

# 로그: 맥은 Text 렌더링 버그 회피를 위해 Listbox, 윈도우는 ScrolledText
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

# 시작 시 테스트 로그 (텍스트가 “정말로 안 보이는지” 바로 확인용)
if IS_MAC:
    root.update()

# GUI 생성 후 스레드 시작
search_thread = threading.Thread(target=search_player, daemon=True)
location_thread = threading.Thread(target=location_detector, daemon=True)
command_thread = threading.Thread(target=command_player, daemon=True)
monster_thread = threading.Thread(target=monster_detector, daemon=True)
search_thread.start()
command_thread.start()
location_thread.start()
monster_thread.start()

# 전역 키 등록 (맥에서는 후크 스레드가 권한 오류로 크래시하므로 등록 생략)
if IS_WINDOWS:
    keyboard.add_hotkey("F1", start_command)
    keyboard.add_hotkey("F2", pause_command)
    keyboard.add_hotkey("F3", resize_game_window)
    keyboard.add_hotkey("F4", start_buff_timer)
    keyboard.on_press_key("w", on_w_pressed)
else:
    log_message("[INFO] 맥: F1~F4·W 키보드 후크 미등록 (위 버튼으로 제어)")

root.mainloop()