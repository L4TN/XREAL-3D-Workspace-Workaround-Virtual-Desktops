import socket, struct, binascii
import os, time, ctypes
import subprocess

# =========================
# CONFIG
# =========================
PORT = 4242  # IGUAL ao Phoenix (como no seu teste)

ENABLE_DESKTOP_SWITCH = True  # True => troca desktop via VirtualDesktopAccessor.dll
HYST_DEG = 4.0                # histerese pra não “tremer” na borda
COOLDOWN_MS = 250             # evita spam de troca

# --- CONFIRMAÇÃO DE PERMANÊNCIA (DWELL) ---
DWELL_CONFIRM_MS = 500        # precisa ficar X ms no range antes de QUALQUER troca

# --- centraliza só quando chegar o primeiro pacote ---
CENTER_ON_FIRST_PACKET = True
CENTER_DESKTOP = 2            # desktop central
CENTER_SWITCH_RETRIES = 3      # tentativas pra centralizar
CENTER_SWITCH_VERIFY_DELAY = 0.03  # seg entre tentativa e verificação

# --- NOVO: auto-start do PhoenixHeadTracker.exe ---
AUTO_START_PHOENIX = True
PHOENIX_EXE_NAME = "PhoenixHeadTracker.exe"
PHOENIX_ARGS = []                 # se precisar passar args, coloque aqui
PHOENIX_START_DELAY_SEC = 0.20    # pequeno delay pós-start (não bloqueia muito)
PHOENIX_DETACH = True             # True = não “prende” no console do Python

ANGLE = 30.0
RIGHT_ENTER = -ANGLE
LEFT_ENTER  =  ANGLE
RIGHT_EXIT  = RIGHT_ENTER + HYST_DEG
LEFT_EXIT   = LEFT_ENTER  - HYST_DEG

DEBUG_PRINTS = True

# =========================
# Win32 helpers (anti "taskbar flashing")
# =========================
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_MINIMIZE = 6

# protótipos (pra não dar cast errado em x64)
user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.FindWindowW.restype  = ctypes.c_void_p

user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype  = ctypes.c_void_p

user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
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
    """
    Foca o 'desktop window' (Progman / 'Program Manager') antes de trocar.
    """
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

# =========================
# VirtualDesktopAccessor (opcional)
# =========================
HERE = os.path.dirname(os.path.abspath(__file__))
VDA_DLL_PATH = os.path.join(HERE, "VirtualDesktopAccessor.dll")


def load_vda():
    if not os.path.exists(VDA_DLL_PATH):
        raise SystemExit("❌ VirtualDesktopAccessor.dll não encontrada na pasta do script.")
    os.add_dll_directory(HERE)

    vda = ctypes.WinDLL(VDA_DLL_PATH)

    vda.GetCurrentDesktopNumber.argtypes = []
    vda.GetCurrentDesktopNumber.restype = ctypes.c_int

    vda.GoToDesktopNumber.argtypes = [ctypes.c_int]
    vda.GoToDesktopNumber.restype = None

    return vda


def get_current_desktop_1based(vda) -> int:
    return int(vda.GetCurrentDesktopNumber()) + 1


def goto_desktop_1based(vda, target: int):
    """
    Switch desktop via VDA (rápido) + workaround anti-flash:
      1) foca Progman (desktop)
      2) troca desktop
      3) minimiza Progman
    """
    progman = _activate_progman_desktop()
    vda.GoToDesktopNumber(int(target) - 1)  # API é 0-based
    time.sleep(0.01)
    _minimize_progman(progman)

# =========================
# decisão (3 estados com histerese)
# =========================
def decide_desktop(current: int, yaw: float) -> int:
    # 1=esq, 2=centro, 3=dir
    if current == 2:
        if yaw <= RIGHT_ENTER:
            return 3
        if yaw >= LEFT_ENTER:
            return 1
        return 2

    if current == 3:
        if yaw > RIGHT_EXIT:
            return 2
        return 3

    if current == 1:
        if yaw < LEFT_EXIT:
            return 2
        return 1

    return 2

# =========================
# dwell confirm helpers (X ms para QUALQUER troca)
# =========================
def needs_dwell_confirm(current: int, desired: int) -> bool:
    return DWELL_CONFIRM_MS > 0 and desired != current

# =========================
# PhoenixHeadTracker auto-start
# =========================
def _is_process_running(image_name: str) -> bool:
    """
    Checa via tasklist (Windows). Evita abrir múltiplas instâncias do Phoenix.
    """
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}"],
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        return image_name.lower() in out.lower()
    except Exception:
        return False


def start_phoenix_if_needed():
    if not AUTO_START_PHOENIX:
        return

    phoenix_path = os.path.join(HERE, PHOENIX_EXE_NAME)

    if not os.path.exists(phoenix_path):
        print(f"[PHOENIX] ❌ Não encontrei {PHOENIX_EXE_NAME} em: {HERE}")
        return

    if _is_process_running(PHOENIX_EXE_NAME):
        print(f"[PHOENIX] Já está rodando: {PHOENIX_EXE_NAME}")
        return

    try:
        creationflags = 0
        if PHOENIX_DETACH:
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(
            [phoenix_path] + list(PHOENIX_ARGS),
            cwd=HERE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )
        print(f"[PHOENIX] Iniciado: {PHOENIX_EXE_NAME}")
        if PHOENIX_START_DELAY_SEC > 0:
            time.sleep(PHOENIX_START_DELAY_SEC)
    except Exception as e:
        print(f"[PHOENIX] ❌ Falha ao iniciar {PHOENIX_EXE_NAME}: {e}")

# =========================
# main
# =========================
start_phoenix_if_needed()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))

print(f"Escutando UDP em 0.0.0.0:{PORT} ...")

last_switch_t = 0.0

# estado do "pedido pendente" (dwell)
pending_target = None
pending_since = 0.0

vda = load_vda() if ENABLE_DESKTOP_SWITCH else None

# Não troca nada ao iniciar — só lê o desktop REAL (sem clamp)
if ENABLE_DESKTOP_SWITCH:
    actual_desktop_start = get_current_desktop_1based(vda)
    print(f"[INIT] Desktop REAL ao iniciar (sem trocar): {actual_desktop_start}")
else:
    actual_desktop_start = CENTER_DESKTOP

# Estado interno do autômato (1/2/3). Só fixamos no 1º pacote.
current_desktop = CENTER_DESKTOP

# marcação para centralizar só quando chegar o 1º pacote
received_first_packet = False

try:
    while True:
        data, addr = sock.recvfrom(4096)

        if DEBUG_PRINTS:
            print(f"\nRecebi {len(data)} bytes de {addr}")
            print("hex:", binascii.hexlify(data[:64]).decode())

        if len(data) >= 48:
            x, y, z, yaw, pitch, roll = struct.unpack("<6d", data[:48])  # 6 float64
            if DEBUG_PRINTS:
                print(f"[6d] yaw={yaw:.2f} pitch={pitch:.2f} roll={roll:.2f} | x={x:.2f} y={y:.2f} z={z:.2f}")
        elif len(data) >= 24:
            x, y, z, yaw, pitch, roll = struct.unpack("<6f", data[:24])  # 6 float32
            if DEBUG_PRINTS:
                print(f"[6f] yaw={yaw:.2f} pitch={pitch:.2f} roll={roll:.2f} | x={x:.2f} y={y:.2f} z={z:.2f}")
        else:
            if DEBUG_PRINTS:
                print("Pacote pequeno demais pra 6 valores (>=24).")
            continue

        yaw = float(yaw)
        now = time.monotonic()

        # =========================
        # Ao receber o 1º pacote: centraliza no desktop 2
        # (sem dwell e sem cooldown), com verificação + retry
        # =========================
        if not received_first_packet:
            received_first_packet = True

            if ENABLE_DESKTOP_SWITCH:
                actual_desktop = get_current_desktop_1based(vda)
            else:
                actual_desktop = CENTER_DESKTOP

            print(f"[INIT] 1º pacote OK. Desktop REAL agora: {actual_desktop}")

            if CENTER_ON_FIRST_PACKET and ENABLE_DESKTOP_SWITCH and actual_desktop != CENTER_DESKTOP:
                ok = False
                for attempt in range(1, CENTER_SWITCH_RETRIES + 1):
                    if DEBUG_PRINTS:
                        print(f"[INIT] Centralizando tentativa {attempt}/{CENTER_SWITCH_RETRIES}: {actual_desktop} -> {CENTER_DESKTOP}")
                    goto_desktop_1based(vda, CENTER_DESKTOP)
                    time.sleep(CENTER_SWITCH_VERIFY_DELAY)
                    actual_after = get_current_desktop_1based(vda)
                    if DEBUG_PRINTS:
                        print(f"[INIT] Verificação pós-switch: desktop REAL = {actual_after}")
                    if actual_after == CENTER_DESKTOP:
                        ok = True
                        break

                if not ok:
                    print("[WARN] Tentei centralizar no desktop 2, mas a verificação não confirmou. Vou continuar mesmo assim.")
                else:
                    print(f"[INIT] Centralizado com sucesso: {actual_desktop} -> {CENTER_DESKTOP}")

                current_desktop = CENTER_DESKTOP
                last_switch_t = now
                pending_target = None
                pending_since = 0.0
                continue  # evita processar o mesmo pacote durante/apos o switch

            # Se já estava no 2 (ou modo simulação), fixa o estado interno em 2
            current_desktop = CENTER_DESKTOP
            pending_target = None
            pending_since = 0.0

        # =========================
        # lógica normal (após centralização)
        # =========================
        desired = decide_desktop(current_desktop, yaw)

        cooldown_ok = (now - last_switch_t) * 1000.0 >= COOLDOWN_MS

        if DEBUG_PRINTS:
            print(f"[STATE] yaw={yaw:+.2f} => desired={desired} | current={current_desktop}")

        # se não quer trocar, cancela pendência e segue
        if desired == current_desktop:
            if pending_target is not None and DEBUG_PRINTS:
                print(f"[DWELL] cancelado (voltou ao current={current_desktop})")
            pending_target = None
            pending_since = 0.0
            continue

        # dwell para qualquer troca
        if needs_dwell_confirm(current_desktop, desired):
            # começou um novo alvo?
            if pending_target != desired:
                pending_target = desired
                pending_since = now
                if DEBUG_PRINTS:
                    print(f"[DWELL] iniciado alvo={pending_target} por {DWELL_CONFIRM_MS}ms")
                continue

            elapsed_ms = (now - pending_since) * 1000.0
            if DEBUG_PRINTS:
                print(f"[DWELL] alvo={pending_target} elapsed={elapsed_ms:.0f}ms / {DWELL_CONFIRM_MS}ms")

            if elapsed_ms < DWELL_CONFIRM_MS:
                continue  # ainda não confirmou

            # dwell confirmou, agora respeita cooldown
            if not cooldown_ok:
                continue

            if ENABLE_DESKTOP_SWITCH:
                goto_desktop_1based(vda, desired)

            print(f"[SWITCH] {current_desktop} -> {desired} (dwell OK {elapsed_ms:.0f}ms)")
            current_desktop = desired
            last_switch_t = now
            pending_target = None
            pending_since = 0.0
            continue

        # fallback (na prática nunca cai aqui porque needs_dwell_confirm cobre desired!=current)
        if desired != current_desktop and cooldown_ok:
            if ENABLE_DESKTOP_SWITCH:
                goto_desktop_1based(vda, desired)

            print(f"[SWITCH] {current_desktop} -> {desired}")
            current_desktop = desired
            last_switch_t = now

except KeyboardInterrupt:
    print("\nEncerrado (Ctrl+C).")
finally:
    try:
        sock.close()
    except:
        pass
