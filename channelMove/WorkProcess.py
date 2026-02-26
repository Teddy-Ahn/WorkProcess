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

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# 미니맵 영역 (게임창 기준). "미니맵 영역 지정"으로 드래그해 지정 가능
# 창 제목에 이 문자열이 "포함"되면 게임 창으로 인식함
window_title = "MapleStory Worlds"
mini_x, mini_y, mini_w, mini_h = 8, 31, 100, 255
MINIMAP_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minimap_region.txt")

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

# 미니맵 점 색상 (BGR). 노란=본인, 빨강=다른 플레이어. 픽셀 수가 이 값 이상이면 "있음"으로 간주
MIN_DOT_PIXELS = 50
# 노란색: 본인 캐릭터 (기존 WorkProcess와 동일한 계열)
YELLOW_BGR_LOWER = (120, 250, 250)
YELLOW_BGR_UPPER = (150, 255, 255)
# 빨간색: 다른 플레이어
RED_BGR_LOWER = (0, 0, 180)
RED_BGR_UPPER = (80, 80, 255)

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


def go_to_next_channel():
    """
    현재 채널에서 다음 채널로 이동하는 동작.
    사용자가 나중에 키 입력 등으로 구현할 예정. 여기서는 플레이스홀더만.
    """
    # TODO: 사용자 정의 — 예) 채널 변경 UI 열기 → 다음 채널 선택 등
    log_message("[채널이동] 다음 채널로 이동 (go_to_next_channel 구현 예정)")


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
        minimap = get_minimap_region(frame)
        has_yellow, has_red = check_minimap_dots(minimap)
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

tk.Button(btn_frame, text="1280x720", command=resize_game_window, width=10).grid(row=0, column=0, padx=2, pady=1, sticky="ew")
tk.Button(btn_frame, text="미니맵 영역 지정", command=start_minimap_region_selector, width=14).grid(row=0, column=1, padx=2, pady=1, sticky="ew")
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
    log_text.insert(tk.END, "[INFO] 1280x720 맞춘 뒤 [채널 체크 시작]. go_to_next_channel()에 이동 로직 구현 예정.")
else:
    log_text.insert(tk.END, "[INFO] 1280x720 맞춘 뒤 [채널 체크 시작]. go_to_next_channel()에 이동 로직 구현 예정.\n")
log_text.see(tk.END)

root.update_idletasks()
if IS_MAC:
    root.update()

load_minimap_region()

# 스레드: 캡처만. 채널 체크는 [채널 체크 시작] 시 별도 스레드로 동작
capture_thread = threading.Thread(target=capture_loop, daemon=True)
capture_thread.start()

log_message("[INFO] 캡처 스레드 시작.")

root.mainloop()
