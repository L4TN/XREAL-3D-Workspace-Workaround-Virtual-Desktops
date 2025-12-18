# XREAL-3D-Workspace-Workaround-Virtual-Desktops

A **Nebula / VertoXR alternative** for Windows — *not* a true XR 3D space.  
This project prioritizes **stability, performance, and visual fidelity** over full 3D environments.

It keeps the display as a **native HDMI output (100% original resolution, no scaling)** and uses **head yaw + Windows Virtual Desktops** to simulate a multi-monitor setup with **lower CPU/GPU usage and zero render-quality loss**.

> ✅ Unlike some 3D workspace environments, this approach preserves **native HDMI resolution and sharpness**, avoiding the slight clarity loss that can occur in rendered XR desktops.

---

## What is this?

XREAL glasses on Windows behave like a normal external monitor (HDMI).  
This project turns that single screen into a **multi-screen illusion**:

- Create **N Windows Virtual Desktops** (commonly 3: Left / Center / Right)
- Place apps across desktops
- Use head yaw (gyro) to **switch desktops** when you look left / center / right

Result: a “3D workspace” feeling using **Windows’ own desktops** (lightweight & stable).

---

## Why this approach? (Stability + Performance + Image Quality)

Full 3D workspaces can:
- consume more CPU/GPU,
- introduce rendering latency,
- slightly reduce image sharpness due to reprojection or scaling,
- be more sensitive to tracking glitches.

This project:
- uses **native HDMI resolution** (no reprojection, no rescaling),
- does **no 3D rendering**,
- keeps text and UI **pixel-perfect**,
- offloads “multi-monitor behavior” to **Windows Virtual Desktops**.

---

## Features

- ✅ Head-yaw driven switching (Left / Center / Right…)
- ✅ Native HDMI resolution (no visual degradation)
- ✅ Works on a static HDMI display (XREAL as a monitor)
- ✅ Hysteresis + cooldown to reduce flicker / spam switching
- ✅ Optional auto-start of the tracker EXE
- ✅ Supports **N desktops** (most people start with 3)

---

## How it works

1. A head tracker (example: `PhoenixHeadTracker.exe`) outputs **UDP packets** with yaw/pitch/roll.
2. The Python script listens on a UDP port, extracts **yaw**.
3. Yaw is mapped into zones (Left / Center / Right).
4. When you enter a zone (with hysteresis + cooldown), the script switches Windows desktops via:
   - `VirtualDesktopAccessor.dll` (recommended)

---

## Requirements

- Windows 10/11
- Python 3.10+ recommended
- XREAL glasses connected as a display (HDMI / adapter)
- Windows Virtual Desktops enabled
- A head-tracking source that sends yaw over UDP (example: PhoenixHeadTracker)

---

## Project files

Typical folder (example):

```
.
├─ AirAPI_Windows.dll
├─ hidapi.dll
├─ PhoenixHeadTracker.exe
├─ VirtualDesktopAccessor.dll
└─ main_udp_yaw_desktop_switcher.py
```

> Tip: keep the EXE/DLLs in the same folder as the Python script (simplest path handling).

---

## Quick start

### 1) Create your Virtual Desktops
- `Win + Ctrl + D` → create a new desktop
- `Win + Ctrl + ← / →` → switch desktops

Create 3 desktops (recommended to start):
- Desktop 1 = Left
- Desktop 2 = Center
- Desktop 3 = Right

### 2) Organize your apps
Example setup:
- Desktop 1: Browser / Docs
- Desktop 2: IDE
- Desktop 3: Terminal / Monitoring

### 3) Start the head tracker
Run:
- `PhoenixHeadTracker.exe`

Make sure the UDP port configured in the tracker matches the script’s `PORT`.

### 4) Run the Python switcher
Open a terminal in the project folder:

```bash
python main_udp_yaw_desktop_switcher.py
```

Now look left/right — the script should switch desktops as you cross thresholds.

---

## Configuration

Open `main_udp_yaw_desktop_switcher.py` and adjust the values (names may vary):

| Setting | Meaning | Typical |
|---|---|---|
| `PORT` | UDP port to listen | `4242` (must match tracker) |
| `NR_DESKTOPS` | number of desktops | `3` |
| `ENABLE_DESKTOP_SWITCH` | real switching vs simulation | `True/False` |
| `ANGLE` | degrees to trigger left/right | `25–40` |
| `HYST_DEG` | hysteresis to avoid threshold jitter | `4–10` |
| `COOLDOWN_MS` | min time between switches | `250–800` |
| `IGNORE_FIRST_SECONDS` | warm-up time | `3–8` |

---

## Third-party components / Credits

- VirtualDesktopAccessor.dll — https://github.com/Ciantic/VirtualDesktopAccessor  
- AirAPI_Windows.dll — https://github.com/MSmithDev/AirAPI_Windows  
- hidapi.dll — https://github.com/libusb/hidapi  
- PhoenixHeadTracker.exe — https://github.com/iVideoGameBoss/PhoenixHeadTracker  

---

## Disclaimer

This project is **not affiliated** with XREAL, Nebula, VertoXR, or Microsoft.

---

## License

GNU GPL v3.0 — see `LICENSE`.
