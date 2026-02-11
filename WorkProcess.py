
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
import sys
import os
from dataclasses import dataclass
import pytesseract

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
FLOOR3_TO_3_2_DELAY_SEC = 60
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

def location_detector():
    global current_position, last_position, position_start_time, elapsed_time, new_position, monster_detected
    grace_period = 1.5  # 🕒 None이 연속으로 나타나도 유지할 최대 시간
    none_start_time = None  # 🕒 None이 최초로 감지된 시간

    while not stop_event.is_set():  # 🟢 stop_event가 설정되면 루프 종료
        x, y = player_position  # 서칭된 좌표 가져오기

        # 좌표가 None이면 grace_period 내에서는 유지
        if x is None or y is None:
            if none_start_time is None:  
                none_start_time = time.time()  # 🕒 None 최초 감지 시간 기록

            elapsed = time.time() - none_start_time
            if elapsed >= grace_period:  # 🕒 grace_period를 넘기면 last_position 초기화
                log_message("⚠ 위치 확인 불가, 일정 시간 None 유지 → 위치 초기화")
                last_position = None
                position_start_time = None
            else:
                log_message(f"⚠ 좌표 확인 불가, {grace_period - elapsed:.1f}초 유지 중...")

            time.sleep(0.2)
            continue  # 다음 루프로 이동

        # None이 아닌 좌표가 감지되면 None 타이머 초기화
        none_start_time = None

        # 현재 좌표가 어느 위치인지 확인
        new_position = None
        for location, area in AREA_OBJECTS.items():
            if area.x_min <= x <= area.x_max and area.y_min <= y <= area.y_max:
                new_position = location
                break

        # 머문 시간 계산
        elapsed_time = time.time() - position_start_time if position_start_time else 0

        # 위치가 변경되었을 때만 시간 기록
        if new_position != last_position:
            if new_position is not None:
                position_start_time = time.time()  # 새로운 위치에서 시간 초기화        
                last_position = new_position
                log_message(f"🟢 위치 변경: {new_position}")

            
        # 현재 좌표와 머문 시간 출력
        monster_icon = "O" if monster_detected else "X"
        log_message(f"Coord:{x},{y} | Area:{new_position} | Time:{elapsed_time:.1f}초 | Monster:{monster_icon}")

        time.sleep(0.1)  # 너무 빠르게 체크하지 않도록 조절

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

    with mss.mss() as sct:
        while not stop_event.is_set(): # 🟢 stop_event가 설정되면 루프 종료
            game_window = get_game_window()
            if not game_window:
                log_message("게임 창을 찾을 수 없습니다.")
                time.sleep(0.5)
                continue

            win_x, win_y = game_window.left, game_window.top
            region = {"top": win_y + mini_y, "left": win_x + mini_x, "width": mini_w, "height": mini_h}
            screenshot = sct.grab(region)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)  # BGRA → BGR 변환

            # mask = cv2.inRange(img, (0, 255, 255), (0, 255, 255))      # 0xFFFF00
            mask = cv2.inRange(img, (136, 255, 255), (136, 255, 255))  # 0xFFFF88
            coords = cv2.findNonZero(mask)  # 노란색 픽셀 좌표 찾기

            if coords is not None:  # 둘 중 하나라도 탐지되면 즉시 반영
                x, y = coords[0][0]  # 첫 번째 검출된 좌표 사용
                with position_lock:
                    player_position = (x, y)

            time.sleep(0.1)  # 너무 빠르게 실행되지 않도록 제한

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

# 2. 커맨더 로직 (플레이어 위치에 따라 방향키 입력)
def command_player():
    global new_position, elapsed_time, player_position, skill_count, buff, step, monster_detected
    global buff_timer_enabled, last_buff_time, manual_pause_until, buff_pending
    global moving_up, moving_down, moving_left, moving_right, direction

    # floor3 관련 구역만 사용
    floor3 = AREA_OBJECTS["floor3"]
    
    eventX = 0
    last_face_time = 0
    last_skill_time = 0
    in_target_range = False
    floor3_2_in_range = False
    floor3_2_face_time = 0
    floor3_2_hunt_start = None
    floor3_2_move_to_64 = False
    floor3_2_drop_done = False
    floor3_2_at64_start = None
    floor3_2_at64_locked = False
    floor3_2_44_hunt_start = None
    floor3_2_drop_pending = False
    floor3_2_last_drop_try = 0
    floor3_1_drop_done = False
    floor3_1_enter_time = None
    floor3_1_drop_ready = False
    floor3_1_to_3_2_done = False
    floor3_2_44_locked = False
    floor3_2_move_skill_used = False
    floor3_hold_start = None
    step = 0
    skill_count = 0

    while not stop_event.is_set(): # 🟢 stop_event가 설정되면 루프 종료
        if time.time() < manual_pause_until:
            cast_ice_strike_not_use()
            release_movement()
            time.sleep(0.05)
            continue
        if pause_event.is_set():  # 일시 정지 상태면
            time.sleep(0.1)
            continue

        x, y = player_position  # 서칭된 좌표 가져오기

        if new_position != "floor3_2":
            floor3_2_hunt_start = None
            floor3_2_move_to_64 = False
            floor3_2_in_range = False
            floor3_2_drop_done = False
            floor3_2_at64_start = None
            floor3_2_at64_locked = False
            floor3_2_drop_pending = False
            floor3_2_last_drop_try = 0
            floor3_2_44_locked = False
            floor3_2_44_hunt_start = None
            floor3_2_move_skill_used = False
        if new_position != "floor3":
            floor3_hold_start = None

        if new_position != "floor3_1":
            floor3_1_drop_done = False
            floor3_1_enter_time = None
            floor3_1_drop_ready = False
            floor3_1_to_3_2_done = False

        if new_position == "iso_point":
            # 외딴발판: 잠깐 멈춘 뒤 우측 점프로 복귀
            release_movement()
            cast_ice_strike_not_use()
            time.sleep(0.1)
            press_right()
            time.sleep(random.uniform(0.08, 0.12))
            press_jump()
        elif new_position == "floor3_1":
            if floor3_1_enter_time is None:
                floor3_1_enter_time = time.time()
            if floor3_2_drop_pending:
                floor3_1_drop_ready = True
            # 3_1(36~40)에서 우측 점프 + 스킬로 3_2 복귀
            if not floor3_1_to_3_2_done and 36 <= x <= 40:
                release_movement()
                press_right()
                time.sleep(random.uniform(0.08, 0.12))
                press_jump()
                cast_ice_strike_use()
                time.sleep(random.uniform(0.05, 0.08))
                cast_ice_strike_not_use()
                floor3_1_to_3_2_done = True
            if floor3_1_drop_ready and not floor3_1_drop_done and time.time() - floor3_1_enter_time >= 0.3:
                release_movement()
                press_down_jump()
                floor3_1_drop_done = True
                floor3_2_drop_pending = False
                floor3_1_drop_ready = False
        elif new_position == "floor3_2":
            if floor3_2_drop_pending and 63 <= x <= 65 and not monster_detected:
                if time.time() - floor3_2_last_drop_try >= 0.6:
                    cast_ice_strike_not_use()
                    time.sleep(0.05)
                    press_down_jump()
                    floor3_2_last_drop_try = time.time()
            if floor3_2_hunt_start is None:
                floor3_2_hunt_start = time.time()
                floor3_2_move_to_64 = False
                floor3_2_at64_start = None
                floor3_2_at64_locked = False
                floor3_2_44_hunt_start = None
                floor3_2_move_skill_used = False

            # 10초 사냥 후 x64로 이동
            if time.time() - floor3_2_hunt_start >= 10:
                floor3_2_move_to_64 = True
                floor3_2_at64_locked = False

            if floor3_2_move_to_64:
                if monster_detected:
                    if floor3_2_at64_locked and 62 <= x <= 66:
                        release_movement()
                    elif x < 63 and not floor3_2_at64_locked:
                        press_right()
                    elif x > 65 and not floor3_2_at64_locked:
                        press_left()
                    if not floor3_2_move_skill_used:
                        cast_teleport()
                        floor3_2_move_skill_used = True
                else:
                    cast_ice_strike_not_use()
                    if floor3_2_at64_locked and 62 <= x <= 66:
                        release_movement()
                    elif x < 63 and not floor3_2_at64_locked:
                        press_right()
                    elif x > 65 and not floor3_2_at64_locked:
                        press_left()
                    else:
                        release_movement()
                        if not floor3_2_at64_locked and time.time() - floor3_2_face_time >= 0.5:
                            keyboard.press("left")
                            time.sleep(random.uniform(0.05, 0.09))
                            keyboard.release("left")
                            floor3_2_face_time = time.time()
                        floor3_2_at64_locked = True

                if floor3_2_at64_locked:
                    if floor3_2_at64_start is None:
                        floor3_2_at64_start = time.time()
                    # 64에서 5초 사냥
                    if time.time() - floor3_2_at64_start < 5:
                        # 몬스터 O일 때 스킬 사용
                        if monster_detected:
                            cast_ice_strike_use()
                        else:
                            cast_ice_strike_not_use()
                    else:
                        if not monster_detected:
                            cast_ice_strike_not_use()
                            time.sleep(0.05)
                            press_down_jump()
                            floor3_2_drop_pending = True
                            floor3_2_last_drop_try = time.time()
                        else:
                            floor3_2_drop_pending = True
                            floor3_2_last_drop_try = time.time()
            else:
                # 진입 범위: 45~47, 유지 범위: 44~48
                if floor3_2_44_locked and 44 <= x <= 48:
                    release_movement()
                    cast_ice_strike_not_use()
                elif x < 45:
                    floor3_2_in_range = False
                    floor3_2_44_locked = False
                    press_right()
                elif x > 47:
                    floor3_2_in_range = False
                    floor3_2_44_locked = False
                    press_left()
                else:
                    release_movement()
                    if not floor3_2_44_locked and time.time() - floor3_2_face_time >= 0.5:
                        keyboard.press("right")
                        time.sleep(random.uniform(0.05, 0.09))
                        keyboard.release("right")
                        floor3_2_face_time = time.time()
                    floor3_2_44_locked = True
                    floor3_2_in_range = True
                    if floor3_2_44_hunt_start is None:
                        floor3_2_44_hunt_start = time.time()

                # 44에서 5초 사냥
                if floor3_2_44_hunt_start and time.time() - floor3_2_44_hunt_start < 5:
                    if monster_detected:
                        cast_ice_strike_use()
                    else:
                        cast_ice_strike_not_use()
                else:
                    cast_ice_strike_not_use()
        elif new_position == "floor3":
            target_x = 64
            eventX = x - target_x
            if abs(eventX) <= 2:
                release_movement()
                if not in_target_range and time.time() - last_face_time >= 0.5:
                    keyboard.press("left")
                    time.sleep(random.uniform(0.05, 0.09))
                    keyboard.release("left")
                    last_face_time = time.time()
                    log_message("floor3: x=64 도착, 왼쪽 바라봄")
                in_target_range = True
                if floor3_hold_start is None:
                    floor3_hold_start = time.time()
            elif eventX > 2:
                in_target_range = False
                press_left()
            else:
                in_target_range = False
                press_right()

            if floor3_hold_start and time.time() - floor3_hold_start >= FLOOR3_TO_3_2_DELAY_SEC:
                if not monster_detected:
                    press_left()
                    press_jump()
                    floor3_hold_start = None
                else:
                    # 몬스터가 있으면 계속 사냥
                    pass
            
            # 몬스터 O일 때 스킬 사용
            if monster_detected and eventX >= -2:
                cast_ice_strike_use()
            else:
                cast_ice_strike_not_use()

            # 몬스터 없을 때만 버프(Q,E) 사용
            if buff_timer_enabled:
                if time.time() - last_buff_time >= BUFF_INTERVAL_SEC:
                    buff_pending = True
                if buff_pending and not monster_detected:
                    cast_qe_buff()
                    last_buff_time = time.time()
                    buff_pending = False

        time.sleep(0.1)  # 일정 주기마다 실행

def monster_detector():
    global monster_detected
    with mss.mss() as sct:
        while not stop_event.is_set():
            game_window = get_game_window()
            if not game_window:
                time.sleep(0.5)
                continue

            x1, y1, x2, y2 = MONSTER_REGION
            region = {
                "top": game_window.top + y1,
                "left": game_window.left + x1,
                "width": max(1, x2 - x1),
                "height": max(1, y2 - y1)
            }
            screenshot = sct.grab(region)
            img = np.array(screenshot)
            bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, MONSTER_COLOR_LOWER, MONSTER_COLOR_UPPER)
            match_pixels = int(np.count_nonzero(mask))
            match_ratio = float(match_pixels) / (mask.shape[0] * mask.shape[1])
            found = (match_ratio >= MONSTER_MIN_RATIO) and (match_pixels >= MONSTER_MIN_PIXELS)

            monster_detected = found

            time.sleep(0.5)

# GUI 로그 출력 함수
def log_message(msg):
    if log_text is None or not log_text.winfo_exists():
        print(f"[WARNING] 로그 기록 실패: {msg}")  # 디버깅용
        return  
    
    def update_log():
        log_text.insert(tk.END, msg + "\n")
        trim_log_lines()
        log_text.see(tk.END)

    root.after(0, update_log)  # 한 번만 실행, 함수로 묶어서 깔끔하게!

def trim_log_lines():
    try:
        MAX_LOG_LINES = 1000
        total_lines = int(log_text.index('end-1c').split('.')[0])
        if total_lines > MAX_LOG_LINES:
            lines_to_delete = total_lines - MAX_LOG_LINES
            log_text.delete('1.0', f'{lines_to_delete + 1}.0')
    except Exception as e:
        print(f"[ERROR] 로그 정리 중 오류 발생: {e}")

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
    for window in gw.getWindowsWithTitle(window_title):
        if window_title in window.title:
            return window
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


# 쓰레드 실행
search_thread = threading.Thread(target=search_player, daemon=True)
location_thread = threading.Thread(target=location_detector, daemon=True)
command_thread = threading.Thread(target=command_player, daemon=True)
monster_thread = threading.Thread(target=monster_detector, daemon=True)

search_thread.start()
command_thread.start()
location_thread.start()
monster_thread.start()

keyboard.add_hotkey("F1", start_command)
keyboard.add_hotkey("F2", pause_command)
keyboard.add_hotkey("F3", resize_game_window)
keyboard.add_hotkey("F4", start_buff_timer)
keyboard.on_press_key("w", on_w_pressed)

# GUI 설정
root = tk.Tk()
root.title("WorkProcess")
root.geometry("450x190")
root.protocol("WM_DELETE_WINDOW", on_closing)

status_label = tk.Label(root, text="상태: 실행 중", font=("Arial", 10))
status_label.pack()

log_text = ScrolledText(root, height=12, width=60)
log_text.pack()

root.mainloop()