# -*- coding: utf-8 -*-
"""
WorkProcess sub — 1PC/2PC 통신
  실행: python "WorkProcess sub.py" 1  → 1PC (F1/F2/F3 누르면 INI에만 기록)
        python "WorkProcess sub.py" 2  → 2PC (INI 읽어서 메이플에 키 전송)
  F1: 파티초대, F2: 버프사용, F3: 파티강퇴
"""
import os
import sys
import threading
import time
import configparser
from datetime import datetime

os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

import tkinter as tk
from tkinter import ttk, filedialog

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import pygetwindow as gw
import keyboard

# 기본 설정
WINDOW_TITLE = "MapleStory Worlds-Mapleland"  # 2PC: 창 제목에 이 문자열이 있으면 메이플로 인식 (게임 버전에 따라 수정)
POLL_INTERVAL = 0.5  # 2PC: INI 읽기 주기(초)
ALLOWED_KEYS = ("F1", "F2", "F3")  # 파티초대, 버프, 파티강퇴
KEY_LABELS = {"F1": "파티초대", "F2": "버프", "F3": "파티강퇴"}
# F1/F3 시 2PC에서 칠 채팅 문구 (엔터 → 이 텍스트 입력 → 엔터)
PARTY_INVITE_CHAT = "/파티초대 헤이팜"
PARTY_KICK_CHAT = "/파티강퇴 헤이팜"

try:
    import pyperclip  # 한글 채팅 입력용. 없으면: pip install pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False

# 1PC: 파티초대 수락용 OCR+클릭 (선택 의존성)
try:
    import mss
    import numpy as np
    import cv2
    import pytesseract
    import pyautogui
    if IS_WINDOWS:
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    PARTY_ACCEPT_AVAILABLE = True
except ImportError:
    PARTY_ACCEPT_AVAILABLE = False

# 1PC: 파티초대 창 감지 영역(게임 창 기준 상대 좌표) — 실제 창 위치에 맞게 수정 필요
PARTY_INVITE_OCR_REGION = (300, 200, 550, 320)  # (x1, y1, x2, y2) 창 내 영역
PARTY_INVITE_ACCEPT_CLICK = (420, 280)          # 수락 버튼 클릭 위치 (창 내 상대)
PARTY_INVITE_OCR_KEYWORD = "파티초대"             # 이 텍스트가 OCR 결과에 있으면 창으로 간주
PARTY_ACCEPT_POLL_INTERVAL = 0.5                 # OCR 체크 주기(초)
PARTY_ACCEPT_COOLDOWN = 2.0                      # 수락 클릭 후 대기(초, 중복 방지)

# 기본 명령 파일 경로 (1PC와 공유할 INI — 네트워크 경로 가능)
DEFAULT_INI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sub_command.ini")

# 전역
stop_event = threading.Event()
watch_running = False
log_text = None
root = None
status_var = None
ini_path_var = None
mode_1pc_active = False  # 1PC에서 핫키 등록 여부
party_accept_stop_event = threading.Event()
party_accept_thread = None


def write_command(ini_path: str, key: str):
    """1PC: INI에 [Commands] KeyToPress=키 기록 (2PC가 읽어서 수행)"""
    if key not in ALLOWED_KEYS:
        return False
    try:
        cfg = configparser.ConfigParser()
        if os.path.isfile(ini_path):
            cfg.read(ini_path, encoding="utf-8")
        if not cfg.has_section("Commands"):
            cfg.add_section("Commands")
        cfg.set("Commands", "KeyToPress", key)
        with open(ini_path, "w", encoding="utf-8") as f:
            cfg.write(f)
        return True
    except Exception:
        return False


def get_game_window():
    if not IS_WINDOWS:
        return None
    try:
        for w in gw.getWindowsWithTitle(WINDOW_TITLE):
            if WINDOW_TITLE in w.title:
                return w
    except Exception:
        pass
    return None


def focus_game():
    win = get_game_window()
    if not win:
        return False
    try:
        if getattr(win, "isMinimized", False):
            win.restore()
        win.activate()
        return True
    except Exception:
        return False


def _type_chat_text(text: str):
    """한글 등 유니코드 채팅 입력: 클립보드에 넣고 Ctrl+V (pyperclip 있으면 사용)"""
    if PYPERCLIP_AVAILABLE:
        try:
            pyperclip.copy(text)
            time.sleep(0.05)
            keyboard.press("ctrl")
            keyboard.press_and_release("v")
            keyboard.release("ctrl")
            return True
        except Exception:
            pass
    # 폴백: keyboard.write (한글은 안 될 수 있음)
    try:
        keyboard.write(text, delay=0.03)
        return True
    except Exception:
        return False


def send_key(key: str):
    """2PC: F1=채팅(파티초대), F2=버프(e→g), F3=채팅(파티강퇴)"""
    if key not in ALLOWED_KEYS:
        return False
    if IS_WINDOWS and not focus_game():
        log_message("게임 창을 찾을 수 없습니다.")
        return False
    time.sleep(0.05)
    try:
        if key == "F1":
            # 엔터 → /파티초대 헤이팜 → 엔터
            keyboard.press_and_release("enter")
            time.sleep(0.12)
            _type_chat_text(PARTY_INVITE_CHAT)
            time.sleep(0.08)
            keyboard.press_and_release("enter")
        elif key == "F2":
            # 버프: e → g
            keyboard.press_and_release("e")
            time.sleep(0.08)
            keyboard.press_and_release("g")
        elif key == "F3":
            # 엔터 → /파티강퇴 헤이팜 → 엔터
            keyboard.press_and_release("enter")
            time.sleep(0.12)
            _type_chat_text(PARTY_KICK_CHAT)
            time.sleep(0.08)
            keyboard.press_and_release("enter")
        else:
            keyboard.press_and_release(key)
    except Exception as e:
        log_message(f"키/채팅 전송 실패: {e}")
        return False
    return True


def read_and_clear_command(ini_path: str):
    """
    INI [Commands] KeyToPress 값을 읽고, F1/F2/F3이면 반환한 뒤 해당 키를 삭제.
    없으면 None 반환.
    """
    if not os.path.isfile(ini_path):
        return None
    try:
        cfg = configparser.ConfigParser()
        cfg.read(ini_path, encoding="utf-8")
        if not cfg.has_section("Commands"):
            return None
        val = cfg.get("Commands", "KeyToPress", fallback=None)
        if not val:
            return None
        val = val.strip().upper()
        if val not in ALLOWED_KEYS:
            return None
        # 읽은 뒤 삭제 (한 번만 실행되도록)
        cfg.remove_option("Commands", "KeyToPress")
        with open(ini_path, "w", encoding="utf-8") as f:
            cfg.write(f)
        return val
    except Exception:
        return None


def write_processed_to_ini(ini_path: str, cmd: str):
    """2PC: 수신·처리 완료를 INI에 기록 (1PC가 확인용으로 읽을 수 있음)"""
    try:
        cfg = configparser.ConfigParser()
        if os.path.isfile(ini_path):
            cfg.read(ini_path, encoding="utf-8")
        if not cfg.has_section("Commands"):
            cfg.add_section("Commands")
        cfg.set("Commands", "ProcessedCommand", cmd)
        cfg.set("Commands", "ProcessedTime", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        with open(ini_path, "w", encoding="utf-8") as f:
            cfg.write(f)
    except Exception:
        pass


def watch_loop(ini_path: str):
    global watch_running
    while not stop_event.is_set() and watch_running:
        cmd = read_and_clear_command(ini_path)
        if cmd:
            if send_key(cmd):
                log_message(f"[수행] {cmd} — {KEY_LABELS.get(cmd, cmd)}")
                write_processed_to_ini(ini_path, cmd)  # 1PC가 수신·처리 확인할 수 있도록 INI 기록
        stop_event.wait(timeout=POLL_INTERVAL)


def log_message(msg: str):
    if log_text is None:
        print(msg)
        return

    def do():
        try:
            log_text.insert(tk.END, msg + "\n")
            log_text.see(tk.END)
            n = int(log_text.index("end-1c").split(".")[0])
            if n > 300:
                log_text.delete("1.0", f"{n - 299}.0")
        except Exception:
            pass

    try:
        root.after(0, do)
    except Exception:
        print(msg)


# ---------- 1PC: 파티초대 창 OCR 후 수락 클릭 스레드 ----------
def party_invite_accept_loop():
    """1PC: 특정 영역 OCR → '파티초대' 감지 시 수락 버튼 위치 클릭 (임시 구현, 좌표 조정 필요)"""
    global mode_1pc_active
    if not PARTY_ACCEPT_AVAILABLE:
        return
    x1, y1, x2, y2 = PARTY_INVITE_OCR_REGION
    cw, ch = x2 - x1, y2 - y1
    click_rel_x, click_rel_y = PARTY_INVITE_ACCEPT_CLICK
    with mss.mss() as sct:
        while not party_accept_stop_event.is_set() and mode_1pc_active:
            win = get_game_window()
            if not win:
                party_accept_stop_event.wait(timeout=PARTY_ACCEPT_POLL_INTERVAL)
                continue
            left = win.left + x1
            top = win.top + y1
            region = {"left": left, "top": top, "width": cw, "height": ch}
            try:
                shot = sct.grab(region)
                img = np.array(shot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                text = pytesseract.image_to_string(img, lang="kor+eng", config="--psm 6")
                if PARTY_INVITE_OCR_KEYWORD in text:
                    click_x = win.left + click_rel_x
                    click_y = win.top + click_rel_y
                    pyautogui.click(click_x, click_y)
                    log_message("[파티초대] 수락 클릭")
                    party_accept_stop_event.wait(timeout=PARTY_ACCEPT_COOLDOWN)
            except Exception:
                pass
            party_accept_stop_event.wait(timeout=PARTY_ACCEPT_POLL_INTERVAL)


# ---------- 1PC: F1/F2/F3 누르면 INI에만 기록 ----------
_hotkey_handles = []  # keyboard.remove_hotkey용


def _on_1pc_key(key: str):
    path = (ini_path_var.get() or "").strip()
    if not path:
        log_message("명령 파일 경로를 설정한 뒤 [시작] 하세요.")
        return
    if write_command(path, key):
        log_message(f"[전송] {key} — {KEY_LABELS.get(key, key)}")


def start_1pc():
    global mode_1pc_active, _hotkey_handles
    path = (ini_path_var.get() or "").strip()
    if not path:
        log_message("명령 파일 경로를 입력하세요.")
        return
    if mode_1pc_active:
        log_message("이미 1PC 모드로 동작 중.")
        return
    # 파일 없으면 생성
    if not os.path.isfile(path):
        try:
            cfg = configparser.ConfigParser()
            cfg.add_section("Commands")
            with open(path, "w", encoding="utf-8") as f:
                cfg.write(f)
            log_message(f"명령 파일 생성: {path}")
        except Exception as e:
            log_message(f"파일 생성 실패: {e}")
            return
    try:
        for k in ALLOWED_KEYS:
            # suppress=True: 키를 INI에만 기록하고 게임/다른 창으로는 전달 안 함
            h = keyboard.add_hotkey(k, lambda kk=k: _on_1pc_key(kk), suppress=True)
            _hotkey_handles.append(h)
        mode_1pc_active = True
        status_var.set("On (F1/F2/F3 입력 대기)")
        log_message("1PC 시작 — F1/F2/F3 누르면 INI에 기록됩니다.")
        # 파티초대 수락 스레드 시작 (OCR+클릭)
        if PARTY_ACCEPT_AVAILABLE:
            party_accept_stop_event.clear()
            party_accept_thread = threading.Thread(target=party_invite_accept_loop, daemon=True)
            party_accept_thread.start()
            log_message("파티초대 수락 감시 시작 (OCR).")
        else:
            log_message("파티초대 수락 비활성 (mss/cv2/pytesseract/pyautogui 필요).")
    except Exception as e:
        log_message(f"핫키 등록 실패: {e}")


def stop_1pc():
    global mode_1pc_active, _hotkey_handles
    if not mode_1pc_active:
        return
    party_accept_stop_event.set()
    try:
        for h in _hotkey_handles:
            try:
                keyboard.remove_hotkey(h)
            except Exception:
                pass
        _hotkey_handles.clear()
        # 혹시 키 이름으로 제거 (버전에 따라 handle이 아닌 경우)
        for k in ALLOWED_KEYS:
            try:
                keyboard.remove_hotkey(k)
            except Exception:
                pass
    except Exception:
        pass
    mode_1pc_active = False
    status_var.set("Off")
    log_message("1PC 중지.")


def start_watch():
    global watch_running
    path = (ini_path_var.get() or "").strip()
    if not path:
        log_message("명령 파일 경로를 입력하세요.")
        return
    # 파일 없으면 빈 INI 생성 (로컬 테스트용). 네트워크 경로는 1PC가 만들면 됨.
    if not os.path.isfile(path):
        try:
            cfg = configparser.ConfigParser()
            cfg.add_section("Commands")
            with open(path, "w", encoding="utf-8") as f:
                cfg.write(f)
            log_message(f"명령 파일 생성: {path}")
        except Exception as e:
            log_message(f"파일 생성 실패(1PC가 만든 경로인지 확인): {e}")
            return
    watch_running = True
    stop_event.clear()
    status_var.set("On (대기 중)")
    log_message("Sub 시작 — 명령 파일 감시 중.")
    t = threading.Thread(target=watch_loop, args=(path,), daemon=True)
    t.start()


def stop_watch():
    global watch_running
    watch_running = False
    stop_event.set()
    status_var.set("Off")
    log_message("Sub 중지.")


def on_closing_2pc():
    stop_watch()
    root.destroy()


def on_closing_1pc():
    stop_1pc()
    root.destroy()


def build_gui_1pc():
    """1PC: F1/F2/F3 입력 시 INI에만 기록하는 GUI"""
    global root, log_text, status_var, ini_path_var
    root = tk.Tk()
    root.title("WorkProcess Sub (1PC)")
    root.geometry("420x300")
    root.minsize(380, 260)
    root.protocol("WM_DELETE_WINDOW", on_closing_1pc)

    main = ttk.Frame(root, padding=8)
    main.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main, text="F1=파티초대, F2=버프, F3=파티강퇴 — 키 입력 시 2PC로 전달됩니다.", font=("", 9)).pack(anchor=tk.W, pady=(0, 4))

    row0 = ttk.Frame(main)
    row0.pack(fill=tk.X, pady=4)
    ttk.Label(row0, text="상태:").pack(side=tk.LEFT, padx=(0, 4))
    status_var = tk.StringVar(value="Off")
    ttk.Label(row0, textvariable=status_var).pack(side=tk.LEFT)

    row1 = ttk.Frame(main)
    row1.pack(fill=tk.X, pady=4)
    ttk.Label(row1, text="명령파일(INI):").pack(side=tk.LEFT, padx=(0, 4))
    ini_path_var = tk.StringVar(value=DEFAULT_INI)
    entry = ttk.Entry(row1, textvariable=ini_path_var, width=36)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

    def browse():
        p = filedialog.asksaveasfilename(
            title="명령 INI 경로 (1PC·2PC 공유)",
            defaultextension=".ini",
            filetypes=[("INI", "*.ini"), ("All", "*.*")]
        )
        if p:
            ini_path_var.set(p)

    ttk.Button(row1, text="찾아보기", command=browse).pack(side=tk.LEFT)

    row2 = ttk.Frame(main)
    row2.pack(fill=tk.X, pady=6)
    ttk.Button(row2, text="시작 (F1/F2/F3 입력 받기)", command=start_1pc).pack(side=tk.LEFT, padx=(0, 4))
    ttk.Button(row2, text="중지", command=stop_1pc).pack(side=tk.LEFT)

    ttk.Label(main, text="로그").pack(anchor=tk.W)
    log_frame = ttk.Frame(main)
    log_frame.pack(fill=tk.BOTH, expand=True, pady=4)
    log_text = tk.Text(log_frame, height=10, width=50, wrap=tk.WORD, font=("Consolas", 9))
    scroll = ttk.Scrollbar(log_frame, command=log_text.yview)
    log_text.configure(yscrollcommand=scroll.set)
    log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    log_text.insert(tk.END, "명령파일 경로 설정 후 [시작] 하면 F1/F2/F3가 INI에 기록됩니다.\n")
    log_text.insert(tk.END, "[안내] 2PC와 같은 INI 경로(공유 폴더 등)를 사용하세요.\n")
    log_text.see(tk.END)

    root.mainloop()


def build_gui_2pc():
    """2PC: INI를 읽어서 메이플에 F1/F2/F3 전송하는 GUI"""
    global root, log_text, status_var, ini_path_var
    root = tk.Tk()
    root.title("WorkProcess Sub (2PC)")
    root.geometry("420x320")
    root.minsize(380, 280)
    root.protocol("WM_DELETE_WINDOW", on_closing_2pc)

    main = ttk.Frame(root, padding=8)
    main.pack(fill=tk.BOTH, expand=True)

    # 상태
    row0 = ttk.Frame(main)
    row0.pack(fill=tk.X, pady=(0, 4))
    ttk.Label(row0, text="상태:").pack(side=tk.LEFT, padx=(0, 4))
    status_var = tk.StringVar(value="Off")
    ttk.Label(row0, textvariable=status_var).pack(side=tk.LEFT)

    # 명령 파일 경로
    row1 = ttk.Frame(main)
    row1.pack(fill=tk.X, pady=4)
    ttk.Label(row1, text="명령파일(INI):").pack(side=tk.LEFT, padx=(0, 4))
    ini_path_var = tk.StringVar(value=DEFAULT_INI)
    entry = ttk.Entry(row1, textvariable=ini_path_var, width=36)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

    def browse():
        p = filedialog.askopenfilename(
            title="명령 INI 선택",
            filetypes=[("INI", "*.ini"), ("All", "*.*")]
        )
        if p:
            ini_path_var.set(p)

    ttk.Button(row1, text="찾아보기", command=browse).pack(side=tk.LEFT)

    # 시작/중지
    row2 = ttk.Frame(main)
    row2.pack(fill=tk.X, pady=6)
    ttk.Button(row2, text="Sub 시작 (감시)", command=start_watch).pack(side=tk.LEFT, padx=(0, 4))
    ttk.Button(row2, text="Sub 중지", command=stop_watch).pack(side=tk.LEFT)

    # 로그
    ttk.Label(main, text="로그").pack(anchor=tk.W)
    log_frame = ttk.Frame(main)
    log_frame.pack(fill=tk.BOTH, expand=True, pady=4)
    log_text = tk.Text(log_frame, height=12, width=50, wrap=tk.WORD, font=("Consolas", 9))
    scroll = ttk.Scrollbar(log_frame, command=log_text.yview)
    log_text.configure(yscrollcommand=scroll.set)
    log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    log_text.insert(tk.END, "F1=파티초대, F2=버프, F3=파티강퇴 — 명령파일 경로 설정 후 [Sub 시작] 하세요.\n")
    if not PYPERCLIP_AVAILABLE:
        log_text.insert(tk.END, "[안내] 한글 채팅 입력을 위해 pip install pyperclip 권장.\n")
    log_text.see(tk.END)

    root.mainloop()


def print_usage():
    print('Usage: python "WorkProcess sub.py" 1   → 1PC (F1/F2/F3 입력만 INI에 기록)')
    print('       python "WorkProcess sub.py" 2   → 2PC (INI 읽어서 메이플에 수행)')


if __name__ == "__main__":
    mode = None
    if len(sys.argv) >= 2:
        a = sys.argv[1].strip()
        if a == "1":
            mode = 1
        elif a == "2":
            mode = 2
    if mode == 1:
        build_gui_1pc()
    elif mode == 2:
        build_gui_2pc()
    else:
        print_usage()
        print()
        sys.exit(1)
