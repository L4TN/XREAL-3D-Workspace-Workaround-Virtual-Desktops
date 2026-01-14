import os
import time
import ctypes
from pynput import keyboard

HERE = os.path.dirname(os.path.abspath(__file__))
DLL_PATH = os.path.join(HERE, "VirtualDesktopAccessor.dll")

# Configure seus atalhos aqui:
HOTKEYS = {
    ";+1": 1,
    ";+2": 2,
    ";+3": 3,
    ";+4": 4,
    ";+5": 5,
    ";+6": 6,
    ";+7": 7,
}

# Workaround opcional (reduz "flash" da taskbar em alguns setups)
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_MINIMIZE = 6

user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.FindWindowW.restype  = ctypes.c_void_p
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype  = ctypes.c_void_p;1
user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)];
user32.GetWindowThreadProcessId.restype  = ctypes.c_uint32
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype  = ctypes.c_uint32
user32.AttachThreadInput.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_bool]
user32.AttachThreadInput.restype  = ctypes.c_bool
user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
user32.SetForegroundWindow.restype  = ctypes.c_bool
user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.ShowWindow.restype  = ctypes.c_bool

def _activate_progman_desktop():
    hwnd = user32.FindWindowW("Progman", "Program Manager")
    if not hwnd:
        return None

    dummy = ctypes.c_uint32(0)
    desktop_tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(dummy))

    fg = user32.GetForegroundWindow()
    fg_tid = user32.GetWindowThreadProcessId(fg, ctypes.byref(dummy)) if fg else 0

    cur_tid = kernel32.GetCurrentThreadId()

    if desktop_tid and fg_tid and (fg_tid != cur_tid):
        user32.AttachThreadInput(desktop_tid, cur_tid, True)
        user32.AttachThreadInput(fg_tid, cur_tid, True)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(fg_tid, cur_tid, False)
        user32.AttachThreadInput(desktop_tid, cur_tid, False)
    else:
        user32.SetForegroundWindow(hwnd)

    time.sleep(0.005)
    return hwnd

def _minimize_progman(hwnd):
    if hwnd:
        user32.ShowWindow(hwnd, SW_MINIMIZE)
        time.sleep(0.005)

def load_vda():
    if not os.path.exists(DLL_PATH):
        raise SystemExit("VirtualDesktopAccessor.dll não encontrada na pasta do script.")

    os.add_dll_directory(HERE)
    vda = ctypes.WinDLL(DLL_PATH)

    vda.GetCurrentDesktopNumber.argtypes = []
    vda.GetCurrentDesktopNumber.restype  = ctypes.c_int

    vda.GoToDesktopNumber.argtypes = [ctypes.c_int]
    vda.GoToDesktopNumber.restype  = None

    return vda

def goto_desktop_1based(vda, target_1based: int):
    progman = _activate_progman_desktop()
    vda.GoToDesktopNumber(int(target_1based) - 1)  # DLL usa 0-based
    time.sleep(0.01)
    _minimize_progman(progman)

def main():
    vda = load_vda()

    def make_cb(n):
        return lambda: goto_desktop_1based(vda, n)

    bindings = {hk: make_cb(n) for hk, n in HOTKEYS.items()}

    print("Atalhos ativos:")
    for hk, n in HOTKEYS.items():
        print(f"  {hk}  -> Desktop {n}")
    print("Ctrl+C para sair.")

    with keyboard.GlobalHotKeys(bindings) as h:
        h.join()

if __name__ == "__main__":
    main()
