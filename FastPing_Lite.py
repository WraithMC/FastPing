import ctypes, sys, os, subprocess, json, winreg, webbrowser
from pathlib import Path
from PIL import Image, ImageTk
import customtkinter as ctk
from tkinter import messagebox

def run_as_admin():
    if getattr(ctypes, "windll", None) and ctypes.windll.shell32.IsUserAnAdmin():
        return True
    try:
        params = " ".join([f'"{arg}"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit()
    except Exception:
        return False

run_as_admin()

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

CONFIG_DIR = Path(os.getenv("APPDATA", "")) / ".minecraft" / "FastPing" / "Lite_config" / "Lite_Config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"

LOGO_PATH = resource_path("assets/logo.png")
if not os.path.exists(LOGO_PATH):
    LOGO_PATH = resource_path("assets/logo.ico")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG = "#000000"
TEXT = "#FFFFFF"
ACCENT = "#FFFFFF"
BUTTON_BG = "#111111"
BUTTON_HOVER = "#222222"
BUTTON_BORDER = "#333333"

def is_windows(): return sys.platform.startswith("win")

def run_netsh(cmd, timeout=6):
    try:
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, (out or "").strip()
    except subprocess.TimeoutExpired:
        p.kill()
        return 1, "Timed out"
    except Exception as e:
        return 1, str(e)

def apply_tcp_tweaks(enable):
    if not is_windows(): return 1, "Unsupported"
    level = "normal" if enable else "disabled"
    run_netsh(f'netsh interface tcp set global autotuninglevel={level}')
    run_netsh(f'netsh interface tcp set global ecncapability={"enabled" if enable else "disabled"}')
    run_netsh(f'netsh interface tcp set global rss={"enabled" if enable else "disabled"}')
    run_netsh(f'netsh interface tcp set global dca={"enabled" if enable else "disabled"}')
    return 0, "Applied" if enable else "Reverted"

def set_low_latency_mode(enable):
    if not is_windows(): return 1, "Unsupported"
    try:
        if enable:
            run_netsh("netsh interface tcp set global congestionprovider=ctcp")
            run_netsh("netsh interface tcp set global timestamps=disabled")
            subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TcpAckFrequency /t REG_DWORD /d 1 /f', shell=True)
            subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TCPNoDelay /t REG_DWORD /d 1 /f', shell=True)
        else:
            run_netsh("netsh interface tcp set global congestionprovider=none")
            run_netsh("netsh interface tcp set global timestamps=enabled")
            subprocess.run('reg delete "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TcpAckFrequency /f', shell=True)
            subprocess.run('reg delete "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TCPNoDelay /f', shell=True)
        return 0, "Done"
    except Exception as e:
        return 1, str(e)

def save_config():
    cfg = {"low_latency": bool(low_latency_var.get())}
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        status_var.set("Settings saved")
    except Exception:
        status_var.set("Save failed")

def load_config():
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            low_latency_var.set(bool(data.get("low_latency", False)))
            status_var.set("Config loaded")
    except Exception:
        status_var.set("Config load failed")

def apply_settings():
    try:
        save_config()
        apply_tcp_tweaks(True)
        set_low_latency_mode(True)
        status_var.set("Optimized connection applied")
        messagebox.showinfo("FastPing", "Connection optimized successfully.")
    except Exception:
        status_var.set("Apply failed")

def reset_settings():
    try:
        apply_tcp_tweaks(False)
        set_low_latency_mode(False)
        status_var.set("Settings reverted")
        messagebox.showinfo("FastPing", "Settings have been reset.")
    except Exception:
        status_var.set("Reset failed")

def open_discord():
    webbrowser.open("https://discord.gg/T8GFc6ryGy")

app = ctk.CTk()
app.geometry("600x400")
app.title("FastPing Lite -By WraithMC")
app.configure(fg_color=BG)
try:
    app.iconbitmap(LOGO_PATH)
except Exception:
    pass

low_latency_var = ctk.BooleanVar(value=False)
status_var = ctk.StringVar(value="Ready")

main = ctk.CTkFrame(app, fg_color=BG, corner_radius=0)
main.pack(fill="both", expand=True)

try:
    logo_img = Image.open(LOGO_PATH).resize((90, 90))
    logo = ImageTk.PhotoImage(logo_img)
    ctk.CTkLabel(main, image=logo, text="", fg_color=BG).pack(pady=(40, 10))
except Exception:
    ctk.CTkLabel(main, text="FASTPING", font=("Segoe UI", 36, "bold"), text_color=TEXT).pack(pady=(60, 20))

ctk.CTkLabel(main, text="Lite Version Of FastPing", font=("Segoe UI", 14), text_color=TEXT).pack(pady=(0, 30))

button_style = {"corner_radius": 12, "height": 45, "width": 240, "fg_color": BUTTON_BG, "hover_color": BUTTON_HOVER, "border_width": 1, "border_color": BUTTON_BORDER, "text_color": TEXT, "font": ("Segoe UI", 14, "bold")}

ctk.CTkButton(main, text="Optimize", command=apply_settings, **button_style).pack(pady=10)
ctk.CTkButton(main, text="Reset Settings", command=reset_settings, **button_style).pack(pady=10)
ctk.CTkButton(main, text="Discord", command=open_discord, **button_style).pack(pady=10)

ctk.CTkLabel(main, textvariable=status_var, text_color="#666666", font=("Segoe UI", 11)).pack(side="bottom", pady=10)

load_config()
app.mainloop()
