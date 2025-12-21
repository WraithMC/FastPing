import ctypes, sys, os, math, subprocess, time, json, winreg, webbrowser
from pathlib import Path
from PIL import Image
import customtkinter as ctk
import psutil
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

CONFIG_DIR = Path(os.getenv("APPDATA", "")) / ".minecraft" / "FastPing" / "config" / "Config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"

LOGO_PATH = resource_path("logo.png")
if not os.path.exists(LOGO_PATH):
    LOGO_PATH = resource_path("logo.ico")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

APP_SIZE = "980x620"
BG = "#000000"
TEXT = "#FFFFFF"
ACCENT = "#FFFFFF"
BUTTON_BG = "#111111"
BUTTON_HOVER = "#222222"
BUTTON_BORDER = "#333333"

PANEL = BG
SUBPANEL = BG
ACCENT_A = ACCENT
ACCENT_B = ACCENT
MUTED = "#AAAAAA"
CARD = BG
SHADOW = BG

PRIORITY_CLASSES = {
    "Idle": getattr(psutil, "IDLE_PRIORITY_CLASS", 64),
    "Below Normal": getattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS", 16384),
    "Normal": getattr(psutil, "NORMAL_PRIORITY_CLASS", 32),
    "Above Normal": getattr(psutil, "ABOVE_NORMAL_PRIORITY_CLASS", 32768),
    "High": getattr(psutil, "HIGH_PRIORITY_CLASS", 128),
    "Realtime": getattr(psutil, "REALTIME_PRIORITY_CLASS", 256),
}

def is_windows(): return sys.platform.startswith("win")

def run_netsh(cmd: str, timeout=6):
    try:
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, (out or "").strip()
    except subprocess.TimeoutExpired:
        p.kill()
        return 1, "Timed out"
    except Exception as e:
        return 1, str(e)

def apply_tcp_tweaks(enable: bool):
    if not is_windows(): return 1, "Unsupported"
    level = "normal" if enable else "disabled"
    run_netsh(f'netsh interface tcp set global autotuninglevel={level}')
    run_netsh(f'netsh interface tcp set global ecncapability={"enabled" if enable else "disabled"}')
    run_netsh(f'netsh interface tcp set global rss={"enabled" if enable else "disabled"}')
    run_netsh(f'netsh interface tcp set global dca={"enabled" if enable else "disabled"}')
    return 0, "Applied" if enable else "Reverted"

def set_low_latency_mode(enable: bool):
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

def set_java_priority(name: str) -> int:
    if not is_windows(): return 0
    prio = PRIORITY_CLASSES.get(name, PRIORITY_CLASSES.get("Normal", 32))
    changed = 0
    for proc in psutil.process_iter(attrs=("name","pid")):
        try:
            nm = (proc.info.get("name") or "").lower()
            if nm in ("java.exe","javaw.exe"):
                p = psutil.Process(proc.info["pid"])
                p.nice(prio)
                changed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return changed

_last_net = None
_last_time = None

def save_config():
    cfg = {
        "smart_packets": bool(smart_packets_var.get()),
        "tuning": tuning_var.get(),
        "priority": priority_var.get(),
        "responsiveness": int(responsiveness_var.get()),
        "low_latency": bool(low_latency_var.get()),
        "connection": connection_var.get()
    }
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
            smart_packets_var.set(bool(data.get("smart_packets", False)))
            tuning_var.set(data.get("tuning", "Balanced"))
            priority_var.set(data.get("priority", "Normal"))
            responsiveness_var.set(int(data.get("responsiveness", 50)))
            low_latency_var.set(bool(data.get("low_latency", False)))
            connection_var.set(data.get("connection", "Fiber"))
            status_var.set("Config loaded")
    except Exception:
        status_var.set("Config load failed")

def init_net_counters():
    global _last_net, _last_time
    _last_net = psutil.net_io_counters()
    _last_time = time.time()

def update_network_speed_smooth():
    global _last_net, _last_time
    try:
        now = time.time()
        net = psutil.net_io_counters()
        elapsed = max(now - _last_time, 0.0001)
        sent = (net.bytes_sent - _last_net.bytes_sent) / (1024*1024) / elapsed
        recv = (net.bytes_recv - _last_net.bytes_recv) / (1024*1024) / elapsed
        try:
            current_upload = float(upload_speed_var.get().split()[0])
            current_download = float(download_speed_var.get().split()[0])
        except Exception:
            current_upload, current_download = 0.0, 0.0
        resp = max(0.05, (100 - responsiveness_var.get()) / 150)
        upload_speed_var.set(f"{current_upload + (sent-current_upload)*resp:.2f} MB/s")
        download_speed_var.set(f"{current_download + (recv-current_download)*resp:.2f} MB/s")
        _last_net = net
        _last_time = now
    except Exception:
        upload_speed_var.set("0.00 MB/s")
        download_speed_var.set("0.00 MB/s")
    finally:
        app.after(700, update_network_speed_smooth)

def smooth_progress(bar, target, speed=0.06):
    current = bar.get()
    if abs(current - target) < 0.004:
        bar.set(target)
        return
    step = (target - current) * speed
    bar.set(max(0.0, min(1.0, current + step)))
    app.after(18, lambda: smooth_progress(bar, target, speed))

def update_resources_smooth():
    try:
        cpu = psutil.cpu_percent(interval=None)/100.0
        ram = psutil.virtual_memory().percent/100.0
        smooth_progress(cpu_bar, cpu, speed=0.08)
        smooth_progress(ram_bar, ram, speed=0.08)
        cpu_usage_var.set(f"{cpu*100:.0f}%")
        ram_usage_var.set(f"{ram*100:.0f}%")
    except Exception:
        cpu_usage_var.set("N/A")
        ram_usage_var.set("N/A")
    finally:
        app.after(500, update_resources_smooth)

def apply_connection_profile(profile: str):
    if not is_windows():
        return 1, "Unsupported"
    try:
        if profile == "Fiber":
            run_netsh('netsh interface tcp set global autotuninglevel=normal')
            run_netsh('netsh interface tcp set global ecncapability=enabled')
            run_netsh('netsh interface tcp set global rss=enabled')
            run_netsh('netsh interface tcp set global dca=enabled')
            run_netsh('netsh interface tcp set global congestionprovider=ctcp')
            subprocess.run('reg delete "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TcpAckFrequency /f', shell=True)
            subprocess.run('reg delete "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TCPNoDelay /f', shell=True)
            run_netsh('netsh interface tcp set global timestamps=disabled')
        elif profile == "DSL":
            run_netsh('netsh interface tcp set global autotuninglevel=disabled')
            run_netsh('netsh interface tcp set global ecncapability=disabled')
            run_netsh('netsh interface tcp set global rss=disabled')
            run_netsh('netsh interface tcp set global dca=disabled')
            run_netsh('netsh interface tcp set global congestionprovider=none')
            subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TcpAckFrequency /t REG_DWORD /d 2 /f', shell=True)
            subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TCPNoDelay /t REG_DWORD /d 0 /f', shell=True)
            run_netsh('netsh interface tcp set global timestamps=enabled')
        elif profile == "Cable":
            run_netsh('netsh interface tcp set global autotuninglevel=normal')
            run_netsh('netsh interface tcp set global ecncapability=enabled')
            run_netsh('netsh interface tcp set global rss=enabled')
            run_netsh('netsh interface tcp set global dca=disabled')
            run_netsh('netsh interface tcp set global congestionprovider=none')
            subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TcpAckFrequency /t REG_DWORD /d 1 /f', shell=True)
            subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TCPNoDelay /t REG_DWORD /d 1 /f', shell=True)
            run_netsh('netsh interface tcp set global timestamps=disabled')
        elif profile == "Satellite":
            run_netsh('netsh interface tcp set global autotuninglevel=disabled')
            run_netsh('netsh interface tcp set global ecncapability=disabled')
            run_netsh('netsh interface tcp set global rss=disabled')
            run_netsh('netsh interface tcp set global dca=disabled')
            run_netsh('netsh interface tcp set global congestionprovider=none')
            subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TcpAckFrequency /t REG_DWORD /d 1 /f', shell=True)
            subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TCPNoDelay /t REG_DWORD /d 0 /f', shell=True)
            run_netsh('netsh interface tcp set global timestamps=enabled')
        elif profile == "Mobile":
            run_netsh('netsh interface tcp set global autotuninglevel=normal')
            run_netsh('netsh interface tcp set global ecncapability=disabled')
            run_netsh('netsh interface tcp set global rss=enabled')
            run_netsh('netsh interface tcp set global dca=disabled')
            run_netsh('netsh interface tcp set global congestionprovider=none')
            subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TcpAckFrequency /t REG_DWORD /d 1 /f', shell=True)
            subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TCPNoDelay /t REG_DWORD /d 1 /f', shell=True)
            run_netsh('netsh interface tcp set global timestamps=disabled')
        else:
            return 1, "Unknown profile"
        return 0, "Profile applied"
    except Exception as e:
        return 1, str(e)

def apply_settings():
    try:
        save_config()
        apply_connection_profile(connection_var.get())
        apply_tcp_tweaks(bool(smart_packets_var.get()))
        set_low_latency_mode(bool(low_latency_var.get()))
        set_java_priority(priority_var.get())
        status_var.set("Settings applied")
    except Exception:
        status_var.set("Apply failed")

def add_to_startup():
    if not is_windows():
        status_var.set("Startup only for Windows")
        return
    try:
        path = os.path.realpath(sys.argv[0])
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "FastPing", 0, winreg.REG_SZ, path)
        winreg.CloseKey(key)
        status_var.set("Added to startup")
    except Exception:
        status_var.set("Startup failed")

def open_discord():
    webbrowser.open("https://discord.gg/T8GFc6ryGy")

def load_logo(path, size):
    try:
        img = Image.open(path).convert("RGBA")
        img = ctk.CTkImage(img, size=size)
        return img
    except Exception:
        return None

app = ctk.CTk()
app.geometry(APP_SIZE)
app.title("FastPing — By WraithMC")
app.configure(fg_color=BG)
try:
    app.iconbitmap(LOGO_PATH)
except Exception:
    pass

upload_speed_var = ctk.StringVar(value="0.00 MB/s")
download_speed_var = ctk.StringVar(value="0.00 MB/s")
cpu_usage_var = ctk.StringVar(value="0%")
ram_usage_var = ctk.StringVar(value="0%")
smart_packets_var = ctk.BooleanVar(value=False)
tuning_var = ctk.StringVar(value="Balanced")
priority_var = ctk.StringVar(value="Normal")
responsiveness_var = ctk.IntVar(value=50)
low_latency_var = ctk.BooleanVar(value=False)
status_var = ctk.StringVar(value="Ready")
connection_var = ctk.StringVar(value="Fiber")

main = ctk.CTkFrame(app, fg_color=BG, corner_radius=14)
main.pack(fill="both", expand=True, padx=18, pady=18)

header = ctk.CTkFrame(main, fg_color=SUBPANEL, corner_radius=12)
header.pack(fill="x", padx=6, pady=(6,12))

logo_img = load_logo(LOGO_PATH, (44,44))
left_h = ctk.CTkFrame(header, fg_color=SUBPANEL, corner_radius=8)
left_h.pack(side="left", padx=12, pady=8)
if logo_img:
    ctk.CTkLabel(left_h, image=logo_img, text="").pack(side="left", padx=(0,10))
ctk.CTkLabel(left_h, text="FastPing", font=("Segoe UI", 22, "bold"), text_color=TEXT).pack(side="left")

center_h = ctk.CTkFrame(header, fg_color=SUBPANEL)
center_h.pack(side="left", padx=6, pady=8, expand=True, fill="x")
ctk.CTkLabel(center_h, text="", font=("Segoe UI", 11), text_color=MUTED).pack(anchor="w")

right_h = ctk.CTkFrame(header, fg_color=SUBPANEL)
right_h.pack(side="right", padx=12, pady=8)
ctk.CTkButton(right_h, text="Join Discord", command=open_discord, fg_color=BUTTON_BG, hover_color=BUTTON_HOVER, text_color=TEXT, corner_radius=10, width=120, border_width=1, border_color=BUTTON_BORDER).pack(side="right", padx=8)
ctk.CTkButton(right_h, text="Apply", command=apply_settings, fg_color=ACCENT, hover_color=ACCENT, text_color=BG, corner_radius=10, width=120).pack(side="right", padx=8)

content = ctk.CTkFrame(main, fg_color=BG, corner_radius=12)
content.pack(fill="both", expand=True, padx=6, pady=6)

left = ctk.CTkFrame(content, fg_color=CARD, corner_radius=12)
left.pack(side="left", fill="both", expand=True, padx=(6,3), pady=6)

right = ctk.CTkFrame(content, fg_color=CARD, corner_radius=12)
right.pack(side="right", fill="both", expand=True, padx=(3,6), pady=6)

ctk.CTkLabel(left, text="Network", font=("Segoe UI", 15, "bold"), text_color=TEXT).pack(anchor="w", padx=12, pady=(12,6))
net_card = ctk.CTkFrame(left, fg_color=SUBPANEL, corner_radius=10)
net_card.pack(fill="x", padx=12, pady=6)
ctk.CTkLabel(net_card, text="Download", text_color=MUTED).grid(row=0, column=0, sticky="w", padx=12, pady=10)
ctk.CTkLabel(net_card, textvariable=download_speed_var, text_color=ACCENT).grid(row=0, column=1, sticky="e", padx=12, pady=10)
ctk.CTkLabel(net_card, text="Upload", text_color=MUTED).grid(row=1, column=0, sticky="w", padx=12, pady=(0,12))
ctk.CTkLabel(net_card, textvariable=upload_speed_var, text_color=ACCENT).grid(row=1, column=1, sticky="e", padx=12, pady=(0,12))

ctk.CTkLabel(left, text="Features", text_color=TEXT).pack(anchor="w", padx=12, pady=(6,0))
feat = ctk.CTkFrame(left, fg_color=SUBPANEL, corner_radius=10)
feat.pack(fill="x", padx=12, pady=8)
ctk.CTkCheckBox(feat, text="Smart Packets", variable=smart_packets_var, hover_color=ACCENT, text_color=TEXT, fg_color=BG).pack(anchor="w", padx=12, pady=8)
ctk.CTkCheckBox(feat, text="Low Latency Mode", variable=low_latency_var, hover_color=ACCENT, text_color=TEXT, fg_color=BG).pack(anchor="w", padx=12, pady=(0,8))

actions = ctk.CTkFrame(left, fg_color=SUBPANEL, corner_radius=10)
actions.pack(fill="x", padx=12, pady=(6,12))
ctk.CTkButton(actions, text="Test Netsh", command=lambda: messagebox.showinfo("Netsh", str(run_netsh("netsh interface tcp show global"))), fg_color=BUTTON_BG, hover_color=BUTTON_HOVER, text_color=TEXT, corner_radius=8, border_width=1, border_color=BUTTON_BORDER).pack(side="left", padx=8, pady=8)
ctk.CTkButton(actions, text="Save", command=save_config, fg_color=BUTTON_BG, hover_color=BUTTON_HOVER, text_color=TEXT, corner_radius=8, border_width=1, border_color=BUTTON_BORDER).pack(side="left", padx=8, pady=8)
ctk.CTkButton(actions, text="Startup", command=add_to_startup, fg_color=BUTTON_BG, hover_color=BUTTON_HOVER, text_color=TEXT, corner_radius=8, border_width=1, border_color=BUTTON_BORDER).pack(side="left", padx=8, pady=8)

ctk.CTkLabel(right, text="System", font=("Segoe UI", 15, "bold"), text_color=TEXT).pack(anchor="w", padx=12, pady=(12,6))
sys_card = ctk.CTkFrame(right, fg_color=SUBPANEL, corner_radius=10)
sys_card.pack(fill="x", padx=12, pady=6)
ctk.CTkLabel(sys_card, text="CPU", text_color=MUTED).grid(row=0, column=0, sticky="w", padx=12, pady=10)
ctk.CTkLabel(sys_card, textvariable=cpu_usage_var, text_color=ACCENT).grid(row=0, column=1, sticky="e", padx=12, pady=10)
ctk.CTkLabel(sys_card, text="RAM", text_color=MUTED).grid(row=1, column=0, sticky="w", padx=12, pady=(0,12))
ctk.CTkLabel(sys_card, textvariable=ram_usage_var, text_color=ACCENT).grid(row=1, column=1, sticky="e", padx=12, pady=(0,12))

cpu_bar = ctk.CTkProgressBar(right, width=240, progress_color=ACCENT)
cpu_bar.pack(fill="x", padx=18, pady=(8,8))
ram_bar = ctk.CTkProgressBar(right, width=240, progress_color=ACCENT)
ram_bar.pack(fill="x", padx=18, pady=(0,12))

ctk.CTkLabel(right, text="Java Priority", text_color=TEXT).pack(anchor="w", padx=12, pady=(6,0))
ctk.CTkOptionMenu(right, values=list(PRIORITY_CLASSES.keys()), variable=priority_var, fg_color=BUTTON_BG, text_color=TEXT, button_color=BUTTON_BG).pack(fill="x", padx=12, pady=8)
ctk.CTkLabel(right, text="Tuning", text_color=TEXT).pack(anchor="w", padx=12, pady=(6,0))
ctk.CTkOptionMenu(right, values=["Restricted","Balanced","Aggressive"], variable=tuning_var, fg_color=BUTTON_BG, text_color=TEXT, button_color=BUTTON_BG).pack(fill="x", padx=12, pady=8)
ctk.CTkLabel(right, text="Connection Profile", text_color=TEXT).pack(anchor="w", padx=12, pady=(6,0))
ctk.CTkOptionMenu(right, values=["Fiber","DSL","Cable","Satellite","Mobile"], variable=connection_var, fg_color=BUTTON_BG, text_color=TEXT, button_color=BUTTON_BG).pack(fill="x", padx=12, pady=8)

ctk.CTkLabel(left, text="Responsiveness", text_color=TEXT).pack(anchor="w", padx=12, pady=(6,0))
ctk.CTkSlider(left, from_=0, to=100, variable=responsiveness_var, progress_color=ACCENT, button_color=ACCENT).pack(fill="x", padx=12, pady=(4,10))

footer = ctk.CTkFrame(main, fg_color=SUBPANEL, corner_radius=10)
footer.pack(fill="x", padx=6, pady=(8,6))
ctk.CTkLabel(footer, textvariable=status_var, anchor="w", text_color=MUTED).pack(side="left", padx=12)
ctk.CTkLabel(footer, text="v2.6", anchor="e", text_color=MUTED).pack(side="right", padx=12)

load_config()
init_net_counters()
update_network_speed_smooth()
update_resources_smooth()
app.mainloop()
