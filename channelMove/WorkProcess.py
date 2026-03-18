# -*- coding: utf-8 -*-
"""
채널 이동 매크로 (channelMove)
- 미니맵 OCR로 사람 없는 채널을 찾을 때까지 채널 변경
- 캐릭터 이동/사냥/버프/경험치 로직 없음
"""
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
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import pytesseract

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except Exception:
    PYAUTOGUI_AVAILABLE = False

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# 미니맵 영역 (게임창 기준). "미니맵 영역 지정"으로 드래그해 지정 가능
# 창 제목에 이 문자열이 "포함"되면 게임 창으로 인식함
window_title = "MapleStory Worlds"
mini_x, mini_y, mini_w, mini_h = 8, 31, 100, 255
MINIMAP_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minimap_region.txt")

# 채널 변경용 버튼 영역 (게임창 기준): 메뉴 버튼, 채널 변경 버튼
menu_btn_x = menu_btn_y = menu_btn_w = menu_btn_h = 0
channel_btn_x = channel_btn_y = channel_btn_w = channel_btn_h = 0
CHANNEL_BTN_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "channel_buttons.txt")

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


def load_channel_button_regions():
    """channel_buttons.txt에서 메뉴/채널 버튼 x,y,w,h 로드 (있으면)."""
    global menu_btn_x, menu_btn_y, menu_btn_w, menu_btn_h
    global channel_btn_x, channel_btn_y, channel_btn_w, channel_btn_h
    if not os.path.isfile(CHANNEL_BTN_CONFIG_PATH):
        return
    try:
        with open(CHANNEL_BTN_CONFIG_PATH, "r", encoding="utf-8") as f:
            line = f.read().strip()
        parts = line.split()
        if len(parts) >= 8:
            menu_btn_x = int(parts[0])
            menu_btn_y = int(parts[1])
            menu_btn_w = int(parts[2])
            menu_btn_h = int(parts[3])
            channel_btn_x = int(parts[4])
            channel_btn_y = int(parts[5])
            channel_btn_w = int(parts[6])
            channel_btn_h = int(parts[7])
    except Exception:
        pass


def save_channel_button_regions():
    """현재 메뉴/채널 버튼 영역을 channel_buttons.txt에 저장."""
    try:
        with open(CHANNEL_BTN_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(
                f"{menu_btn_x} {menu_btn_y} {menu_btn_w} {menu_btn_h} "
                f"{channel_btn_x} {channel_btn_y} {channel_btn_w} {channel_btn_h}\n"
            )
    except Exception:
        pass

# 미니맵 점 색상 (BGR). 노란=본인, 빨강=다른 플레이어. 픽셀 수가 이 값 이상이면 "있음"으로 간주
MIN_DOT_PIXELS = 5
# 노란색: 본인 캐릭터 (기존 WorkProcess에서 쓰던 단일 색과 동일)
YELLOW_BGR_LOWER = (136, 255, 255)
YELLOW_BGR_UPPER = (136, 255, 255)
# 빨간색: 다른 플레이어 (미니맵)
RED_BGR_LOWER = (0, 0, 160)
RED_BGR_UPPER = (90, 90, 255)

# 채널창 인식용 채널 슬롯 노란색 범위 및 최소 픽셀 수 (중앙 창 내부의 많은 노란 점)
CHANNEL_WINDOW_YELLOW_LOWER = (0, 200, 200)
CHANNEL_WINDOW_YELLOW_UPPER = (80, 255, 255)
CHANNEL_WINDOW_MIN_YELLOW_PIXELS = 800

# 채널창에서 "내 채널" 그레이 블록 색 범위 (HSV) 및 최소 픽셀 수
MY_CHANNEL_GRAY_LOWER = (0, 0, 160)     # 어두운 회색~중간 회색
MY_CHANNEL_GRAY_UPPER = (179, 40, 235)  # 채도 낮은 밝은 회색까지
MY_CHANNEL_MIN_PIXELS = 200

# 채널창 내 "채널변경" 버튼이 활성화되었을 때의 주황색 범위 (HSV) 및 최소 픽셀 수
CHANNEL_CHANGE_BTN_LOWER = (5, 150, 150)
CHANNEL_CHANGE_BTN_UPPER = (25, 255, 255)
CHANNEL_CHANGE_BTN_MIN_PIXELS = 200

stop_event = threading.Event()
log_text = None
cached_game_window = None
root = None

frame_lock = threading.Lock()
latest_frame = None
latest_frame_time = 0.0

# 채널 체크 루프용
channel_check_running = False
channel_check_stop_event = threading.Event()
_last_state = None  # "no_yellow" | "yellow_red" | "yellow_ok"
_last_log_time = 0.0
LOG_THROTTLE = 2.0  # 같은 상태 로그 최소 간격(초)

# 채널창 열림 상태 캐시 및 "내 채널" 탐지 상태
channel_window_open = False
my_channel_found = False


def get_game_window():
    """
    현재 게임 창 핸들 반환.
    - Windows / macOS 모두 pygetwindow.getWindowsWithTitle로 검색
    - 실패 시 None
    """
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
        log_message("게임 창을 찾을 수 없습니다.")
        return False
    try:
        if getattr(game_window, "isMinimized", False):
            game_window.restore()
        game_window.activate()
        return True
    except Exception as e:
        log_message(f"게임 창 포커스 실패: {e}")
        return False


def capture_loop():
    """게임 화면 캡처 (미니맵/OCR용)"""
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


def get_minimap_region(frame):
    """게임 전체 프레임에서 미니맵 영역만 잘라 반환 (BGRA)."""
    if frame is None or frame.size == 0:
        return None
    h, w = frame.shape[:2]
    x2 = mini_x + mini_w
    y2 = mini_y + mini_h
    if x2 > w or y2 > h:
        return None
    return frame[mini_y:y2, mini_x:x2].copy()


def check_minimap_dots(minimap_bgra):
    """
    미니맵 이미지에서 노란(본인), 빨강(다른 플레이어) 픽셀 수 확인.
    Returns: (has_yellow, has_red)  # 픽셀 수 >= MIN_DOT_PIXELS 이면 True
    """
    if minimap_bgra is None or minimap_bgra.size == 0:
        return False, False
    bgr = cv2.cvtColor(minimap_bgra, cv2.COLOR_BGRA2BGR)
    yellow_mask = cv2.inRange(bgr, YELLOW_BGR_LOWER, YELLOW_BGR_UPPER)
    red_mask = cv2.inRange(bgr, RED_BGR_LOWER, RED_BGR_UPPER)
    yellow_count = int(np.count_nonzero(yellow_mask))
    red_count = int(np.count_nonzero(red_mask))

    return yellow_count >= MIN_DOT_PIXELS, red_count >= MIN_DOT_PIXELS


def is_channel_window_open(frame_bgra):
    """
    채널 변경 창이 열려 있는지 대략적으로 판단.
    - 전체 게임 창 중앙 영역에서 채널 슬롯 노란 점 픽셀 수를 기준으로 판별.
    - 1280x720 기준으로 설계됨.
    """
    global channel_window_open, my_channel_found
    if frame_bgra is None or frame_bgra.size == 0:
        return False
    try:
        h, w = frame_bgra.shape[:2]
        # 화면 중앙 영역 (채널창이 위치하는 부분 대략)
        x1 = int(w * 0.18)
        x2 = int(w * 0.82)
        y1 = int(h * 0.12)
        y2 = int(h * 0.80)
        if x2 <= x1 or y2 <= y1:
            return False
        roi = frame_bgra[y1:y2, x1:x2]
        if roi.size == 0:
            return False
        bgr = cv2.cvtColor(roi, cv2.COLOR_BGRA2BGR)
        mask = cv2.inRange(bgr, CHANNEL_WINDOW_YELLOW_LOWER, CHANNEL_WINDOW_YELLOW_UPPER)
        yellow_count = int(np.count_nonzero(mask))

        open_now = yellow_count >= CHANNEL_WINDOW_MIN_YELLOW_PIXELS

        # 상태가 바뀌었을 때만 로그 출력
        if open_now != channel_window_open:
            channel_window_open = open_now
            state = "열림" if open_now else "닫힘"
            log_message(f"[채널창] {state} (yellow_pixels={yellow_count})")
            if not open_now:
                my_channel_found = False

        # 채널창이 열려 있을 때는 내 채널(그레이 블록) 및 자동 채널 변경도 처리
        if channel_window_open:
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
            gray_mask = cv2.inRange(hsv, MY_CHANNEL_GRAY_LOWER, MY_CHANNEL_GRAY_UPPER)
            gray_count = int(np.count_nonzero(gray_mask))
            found_now = gray_count >= MY_CHANNEL_MIN_PIXELS
            if found_now and not my_channel_found:
                my_channel_found = True
                log_message(f"[채널창] 내 채널 그레이 블록 탐지 (gray_pixels={gray_count})")

                # 1) 내 채널 블록 오른쪽에 있는 블록 클릭 (가능할 때만)
                try:
                    if PYAUTOGUI_AVAILABLE:
                        coords = cv2.findNonZero(gray_mask)
                        if coords is not None:
                            gx, gy, gw_, gh_ = cv2.boundingRect(coords)
                            target_local_x = gx + gw_ + gw_ // 2
                            if target_local_x < roi.shape[1]:
                                target_local_y = gy + gh_ // 2
                                win = get_game_window()
                                if win:
                                    click_x = win.left + x1 + target_local_x
                                    click_y = win.top + y1 + target_local_y
                                    pyautogui.click(click_x, click_y)
                                    log_message(f"[채널창] 다음 채널 슬롯 클릭 ({click_x}, {click_y})")
                                    time.sleep(0.3)
                            else:
                                log_message("[채널창] 내 채널이 오른쪽 끝이라 다음 슬롯이 없습니다.")
                    else:
                        log_message("[채널창] pyautogui 없음 — 채널 슬롯 자동 클릭 불가.")
                except Exception as e:
                    log_message(f"[채널창] 다음 채널 슬롯 클릭 실패: {e}")

                # 2) 채널창 하단의 '채널변경' 주황 버튼이 활성화되었으면 클릭
                try:
                    if PYAUTOGUI_AVAILABLE:
                        h2, w2 = frame_bgra.shape[:2]
                        bx1 = int(w2 * 0.55)
                        bx2 = int(w2 * 0.90)
                        by1 = int(h2 * 0.84)
                        by2 = int(h2 * 0.96)
                        if bx2 > bx1 and by2 > by1:
                            btn_roi = frame_bgra[by1:by2, bx1:bx2]
                            if btn_roi.size > 0:
                                btn_bgr = cv2.cvtColor(btn_roi, cv2.COLOR_BGRA2BGR)
                                btn_hsv = cv2.cvtColor(btn_bgr, cv2.COLOR_BGR2HSV)
                                btn_mask = cv2.inRange(btn_hsv, CHANNEL_CHANGE_BTN_LOWER, CHANNEL_CHANGE_BTN_UPPER)
                                btn_pixels = int(np.count_nonzero(btn_mask))
                                if btn_pixels >= CHANNEL_CHANGE_BTN_MIN_PIXELS:
                                    btn_coords = cv2.findNonZero(btn_mask)
                                    if btn_coords is not None:
                                        bx, by, bw_, bh_ = cv2.boundingRect(btn_coords)
                                        btn_local_x = bx + bw_ // 2
                                        btn_local_y = by + bh_ // 2
                                        win = get_game_window()
                                        if win:
                                            click_x = win.left + bx1 + btn_local_x
                                            click_y = win.top + by1 + btn_local_y
                                            pyautogui.click(click_x, click_y)
                                            log_message(f"[채널창] '채널변경' 버튼 클릭 ({click_x}, {click_y})")
                                            time.sleep(0.3)
                                else:
                                    log_message(f"[채널창] '채널변경' 버튼 활성 주황색 픽셀 부족 (pixels={btn_pixels})")
                    else:
                        log_message("[채널창] pyautogui 없음 — '채널변경' 자동 클릭 불가.")
                except Exception as e:
                    log_message(f"[채널창] '채널변경' 버튼 클릭 실패: {e}")

        return open_now
    except Exception:
        return False


def find_yellow_coord(minimap_bgra):
    """
    미니맵 이미지에서 노란 점(본인) 하나의 좌표를 반환.
    좌표는 미니맵 영역 기준 (x,y).
    """
    if minimap_bgra is None or minimap_bgra.size == 0:
        return None
    try:
        bgr = cv2.cvtColor(minimap_bgra, cv2.COLOR_BGRA2BGR)
        mask = cv2.inRange(bgr, YELLOW_BGR_LOWER, YELLOW_BGR_UPPER)
        coords = cv2.findNonZero(mask)
        if coords is None:
            return None
        x, y = coords[0][0]
        return int(x), int(y)
    except Exception:
        return None


def go_to_next_channel():
    """
    현재 채널에서 다음 채널로 이동하는 동작.
    1. 메뉴 버튼 영역 중심 클릭
    2. 채널 변경 버튼 영역 중심 클릭
    """
    global menu_btn_x, menu_btn_y, menu_btn_w, menu_btn_h
    global channel_btn_x, channel_btn_y, channel_btn_w, channel_btn_h

    if not PYAUTOGUI_AVAILABLE:
        log_message("pyautogui 모듈이 없습니다. 채널 변경 클릭을 수행할 수 없습니다.")
        return

    if menu_btn_w <= 0 or menu_btn_h <= 0 or channel_btn_w <= 0 or channel_btn_h <= 0:
        log_message("채널 변경 버튼 영역이 설정되지 않았습니다. [채널 버튼 지정]으로 먼저 영역을 지정하세요.")
        return

    win = get_game_window()
    if not win:
        log_message("게임 창을 찾을 수 없습니다. (채널 변경 실패)")
        return

    try:
        all_clear()
        focus_game_window()
        time.sleep(0.1)

        # 메뉴 버튼 중심 클릭
        menu_cx = win.left + menu_btn_x + menu_btn_w // 2
        menu_cy = win.top + menu_btn_y + menu_btn_h // 2
        pyautogui.click(menu_cx, menu_cy)
        log_message(f"[채널이동] 메뉴 버튼 클릭 ({menu_cx}, {menu_cy})")
        time.sleep(0.5)

        # 채널 변경 버튼 중심 클릭
        ch_cx = win.left + channel_btn_x + channel_btn_w // 2
        ch_cy = win.top + channel_btn_y + channel_btn_h // 2
        pyautogui.click(ch_cx, ch_cy)
        log_message(f"[채널이동] 채널 변경 버튼 클릭 ({ch_cx}, {ch_cy})")
        time.sleep(0.5)
    except Exception as e:
        log_message(f"[채널이동] 채널 변경 클릭 실패: {e}")


def _throttled_log(msg, state_key):
    """같은 상태는 LOG_THROTTLE 초 이내에 한 번만 로그."""
    global _last_state, _last_log_time
    now = time.time()
    if _last_state == state_key and (now - _last_log_time) < LOG_THROTTLE:
        return
    _last_state = state_key
    _last_log_time = now
    log_message(msg)


def channel_check_loop():
    """
    1. 노란 점 없음 → 채널 이동 중 (미니맵 비표시), 대기
    2. 노란 점 있음 + 빨간 점 있음 → 다른 플레이어 있음 → 다음 채널로 이동
    3. 노란 점 있음 + 빨간 점 없음 → 빈 채널 (대기)
    """
    global channel_check_running
    time_sleep = time.sleep
    while not channel_check_stop_event.is_set() and channel_check_running:
        with frame_lock:
            frame = latest_frame
        if frame is None:
            time_sleep(0.2)
            continue
        # 채널창 열림 여부 로그 (상태 변경 시 1회 출력)
        open_now = is_channel_window_open(frame)

        # 채널창이 열려 있으면 미니맵 판정을 잠시 멈춤
        if open_now:
            _throttled_log("[미니맵] 채널창 열림 — 미니맵 판정 일시중지", "channel_window")
            time_sleep(0.5)
            continue

        minimap = get_minimap_region(frame)
        has_yellow, has_red = check_minimap_dots(minimap)

        if has_yellow:
            coord = find_yellow_coord(minimap)
            if coord is not None:
                try:
                    _throttled_log(f"[미니맵] 내 위치 x={coord[0]}, y={coord[1]}", "coord")
                except Exception:
                    pass

        if not has_yellow:
            _throttled_log("[미니맵] 채널 이동 중 (미니맵 비표시) — 대기", "no_yellow")
        elif has_red:
            _throttled_log("[미니맵] 다른 플레이어 있음 → 다음 채널로 이동 필요", "yellow_red")
            go_to_next_channel()
            time_sleep(1.0)  # 한 번 이동 요청 후 잠시 대기 (연타 방지)
        else:
            _throttled_log("[미니맵] 빈 채널 (본인만 있음) — 대기", "yellow_ok")
        time_sleep(0.5)


def start_channel_check():
    """채널 체크(미니맵 감지) 루프 시작. 저장된 미니맵 영역은 1280x720 기준이므로 창 크기를 맞춤."""
    global channel_check_running
    if channel_check_running:
        log_message("이미 채널 체크 실행 중.")
        return
    resize_game_window()
    time.sleep(0.3)
    channel_check_running = True
    channel_check_stop_event.clear()
    t = threading.Thread(target=channel_check_loop, daemon=True)
    t.start()
    log_message("채널 체크 시작 (1280x720 기준, 노란=본인, 빨강=다른 플레이어).")


def stop_channel_check():
    """채널 체크 루프 중지."""
    global channel_check_running
    channel_check_running = False
    channel_check_stop_event.set()
    log_message("채널 체크 중지.")


def trim_log_listbox():
    try:
        if not IS_MAC or log_text is None:
            return
        MAX_LOG_LINES = 300
        n = log_text.size()
        if n > MAX_LOG_LINES:
            log_text.delete(0, n - MAX_LOG_LINES - 1)
    except Exception as e:
        print(f"[ERROR] 로그 정리: {e}")


def trim_log_lines():
    try:
        if IS_MAC:
            return
        MAX_LOG_LINES = 300
        total_lines = int(log_text.index("end-1c").split(".")[0])
        if total_lines > MAX_LOG_LINES:
            lines_to_delete = total_lines - MAX_LOG_LINES
            log_text.delete("1.0", f"{lines_to_delete + 1}.0")
    except Exception as e:
        print(f"[ERROR] 로그 정리: {e}")


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

    try:
        root.after(0, update_log)
    except Exception:
        print(msg)


def force_kill():
    log_message("⚠ 강제 종료")
    os._exit(1)


def all_clear():
    """누를 수 있는 키 해제 (채널 변경 등 입력 시 안전용)"""
    for key in ("shift", "ctrl", "alt", "alt gr", "win", "left windows", "right windows"):
        try:
            keyboard.release(key)
        except Exception:
            pass


def on_closing():
    log_message("프로그램 종료 중...")
    stop_channel_check()
    stop_event.set()
    all_clear()
    timeout = 3
    if capture_thread and capture_thread.is_alive():
        log_message("캡처 스레드 종료 대기...")
        capture_thread.join(timeout)
        if capture_thread.is_alive():
            force_kill()
    log_message("종료 완료.")
    root.destroy()


def resize_game_window():
    game_window = get_game_window()
    if not game_window:
        log_message("게임 창을 찾을 수 없습니다.")
        return
    try:
        game_window.resizeTo(1280, 720)
        focus_game_window()
        log_message("게임 창 1280x720으로 조정.")
    except Exception as e:
        log_message(f"리사이즈 실패: {e}")


# 미니맵 영역은 이 해상도 기준으로 저장·사용 (영역 지정 시 자동으로 이 크기로 맞춤)
MINIMAP_RESOLUTION = (1280, 720)


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
    # 1. 해상도를 1280x720으로 고정 (다른 해상도/재실행 시에도 좌표가 맞도록)
    log_message("해상도 1280x720으로 변경 중...")
    resize_game_window()
    time.sleep(0.8)  # 리사이즈 반영 대기
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
    # 표시용 축소 (최대 960px 폭)
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
        tmp = os.path.join(tempfile.gettempdir(), "channelmove_capture.png")
        cv2.imwrite(tmp, cv2.cvtColor(img_disp, cv2.COLOR_RGB2BGR))
        photo = tk.PhotoImage(file=tmp)
    # 선택 상태
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
        # 표시 좌표 → 게임 창 좌표
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


def start_channel_button_selector():
    """
    1. 게임 창을 1280x720으로 변경
    2. 캡처 화면을 열고
       - 첫 번째 드래그: 메뉴 버튼 영역
       - 두 번째 드래그: 채널 변경 버튼 영역
    3. 두 영역의 중심을 이후 채널 변경 시 클릭 위치로 사용
    """
    global menu_btn_x, menu_btn_y, menu_btn_w, menu_btn_h
    global channel_btn_x, channel_btn_y, channel_btn_w, channel_btn_h

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
        photo = ImageTk.PhotoImage(Image.fromarray(img_disp))
    else:
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "channelmove_capture_buttons.png")
        cv2.imwrite(tmp, cv2.cvtColor(img_disp, cv2.COLOR_RGB2BGR))
        photo = tk.PhotoImage(file=tmp)

    start_x, start_y = None, None
    rect_id = None
    step = 1  # 1: 메뉴 버튼, 2: 채널 변경 버튼

    topwin = tk.Toplevel(root)
    topwin.title("채널 버튼 지정 — 1) 메뉴, 2) 채널변경 순서로 드래그")
    topwin.geometry(f"{disp_w + 4}x{disp_h + 4}")
    canvas = tk.Canvas(topwin, width=disp_w, height=disp_h, cursor="cross")
    canvas.pack()
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)
    topwin.image = photo

    def on_press_btn(e):
        nonlocal start_x, start_y, rect_id
        start_x, start_y = e.x, e.y
        if rect_id is not None:
            canvas.delete(rect_id)
        rect_id = canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="yellow", width=2)

    def on_drag_btn(e):
        nonlocal rect_id
        if rect_id is not None and start_x is not None:
            canvas.delete(rect_id)
            rect_id = canvas.create_rectangle(start_x, start_y, e.x, e.y, outline="yellow", width=2)

    def on_release_btn(e):
        nonlocal rect_id, start_x, start_y, step
        global menu_btn_x, menu_btn_y, menu_btn_w, menu_btn_h
        global channel_btn_x, channel_btn_y, channel_btn_w, channel_btn_h
        if start_x is None:
            return
        ex, ey = e.x, e.y
        x1, x2 = min(start_x, ex), max(start_x, ex)
        y1, y2 = min(start_y, ey), max(start_y, ey)
        if x2 - x1 < 3 or y2 - y1 < 3:
            log_message("영역이 너무 작습니다. 다시 드래그해 주세요.")
            return

        gx = int(x1 / scale)
        gy = int(y1 / scale)
        gw_ = max(1, int((x2 - x1) / scale))
        gh_ = max(1, int((y2 - y1) / scale))

        if step == 1:
            menu_btn_x, menu_btn_y, menu_btn_w, menu_btn_h = gx, gy, gw_, gh_
            log_message(f"메뉴 버튼 영역 설정: x={gx} y={gy} w={gw_} h={gh_}")
            step = 2
            start_x = start_y = None
        else:
            channel_btn_x, channel_btn_y, channel_btn_w, channel_btn_h = gx, gy, gw_, gh_
            log_message(f"채널 변경 버튼 영역 설정: x={gx} y={gy} w={gw_} h={gh_}")
            save_channel_button_regions()
            log_message("채널 버튼 영역 저장 완료.")
            topwin.destroy()

    canvas.bind("<ButtonPress-1>", on_press_btn)
    canvas.bind("<B1-Motion>", on_drag_btn)
    canvas.bind("<ButtonRelease-1>", on_release_btn)


# --- GUI ---
root = tk.Tk()
root.title("WorkProcess — 채널 이동")
root.geometry("400x280")
root.minsize(360, 240)
root.protocol("WM_DELETE_WINDOW", on_closing)
root.grid_rowconfigure(1, weight=1, minsize=120)
root.grid_columnconfigure(0, weight=1)

if IS_MAC:
    root.option_add("*Text.background", "white")
    root.option_add("*Text.foreground", "black")
    root.option_add("*Text.font", "Menlo 11")

btn_frame = tk.Frame(root)
btn_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=2)
btn_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

tk.Button(btn_frame, text="미니맵 영역 지정", command=start_minimap_region_selector, width=14).grid(row=0, column=0, padx=2, pady=1, sticky="ew")
tk.Button(btn_frame, text="채널 버튼 지정", command=start_channel_button_selector, width=12).grid(row=0, column=1, padx=2, pady=1, sticky="ew")
tk.Button(btn_frame, text="채널 체크 시작", command=start_channel_check, width=12).grid(row=0, column=2, padx=2, pady=1, sticky="ew")
tk.Button(btn_frame, text="채널 체크 중지", command=stop_channel_check, width=12).grid(row=0, column=3, padx=2, pady=1, sticky="ew")

if IS_MAC:
    log_frame = tk.Frame(root)
    log_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)
    log_frame.grid_rowconfigure(0, weight=1)
    log_frame.grid_columnconfigure(0, weight=1)
    log_text = tk.Listbox(
        log_frame, height=10, width=50,
        bg="white", fg="black", font=("Menlo", 11),
        highlightthickness=1, highlightbackground="#ccc",
    )
    log_scroll = tk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
    log_text.configure(yscrollcommand=log_scroll.set)
    log_text.grid(row=0, column=0, sticky="nsew")
    log_scroll.grid(row=0, column=1, sticky="ns")
else:
    log_text = ScrolledText(
        root, height=10, width=50,
        bg="white", fg="black", font=("Consolas", 9),
        wrap=tk.WORD,
    )
    log_text.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)

if IS_MAC:
    log_text.insert(tk.END, "[INFO] F1=미니맵 지정, F2=채널 버튼 지정, F3=채널 체크 시작, F4=채널 체크 중지.\n")
else:
    log_text.insert(tk.END, "[INFO] F1=미니맵 지정, F2=채널 버튼 지정, F3=채널 체크 시작, F4=채널 체크 중지.\n")
log_text.see(tk.END)

root.update_idletasks()
if IS_MAC:
    root.update()

load_minimap_region()
load_channel_button_regions()

# 스레드: 캡처만. 채널 체크는 [채널 체크 시작] 시 별도 스레드로 동작
capture_thread = threading.Thread(target=capture_loop, daemon=True)
capture_thread.start()

log_message("[INFO] 캡처 스레드 시작.")

# 전역 핫키 (Windows 전용)
if IS_WINDOWS:
    try:
        keyboard.add_hotkey("F1", start_minimap_region_selector)
        keyboard.add_hotkey("F2", start_channel_button_selector)
        keyboard.add_hotkey("F3", start_channel_check)
        keyboard.add_hotkey("F4", stop_channel_check)
        log_message("[INFO] F1~F4 핫키 등록 완료.")
    except Exception as e:
        log_message(f"[WARN] F1~F4 핫키 등록 실패: {e}")

root.mainloop()
