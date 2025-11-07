import ctypes, sys, os, json, subprocess, time, psutil, winreg, webbrowser
from pathlib import Path
from PIL import Image
import customtkinter as ctk
from tkinter import messagebox

def run_as_admin():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True
    try:
        params = " ".join([f'"{arg}"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit()
    except:
        return False

run_as_admin()

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

CONFIG_DIR = Path(os.getenv("APPDATA")) / ".minecraft" / "FastPing"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"

LOGO_PATH = resource_path("logo.png")
if not os.path.exists(LOGO_PATH):
    LOGO_PATH = resource_path("logo.ico")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

APP_SIZE = "960x640"
ACCENT = "#00FFA3"
ACCENT_HOVER = "#00CC84"
TEXT = "#FFFFFF"
CARD_BG = "#1C1C1C"
BG = "#0F0F0F"
HEADER_BG = "#161616"

PRIORITY_CLASSES = {
    "Idle": psutil.IDLE_PRIORITY_CLASS,
    "Below Normal": psutil.BELOW_NORMAL_PRIORITY_CLASS,
    "Normal": psutil.NORMAL_PRIORITY_CLASS,
    "Above Normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
    "High": psutil.HIGH_PRIORITY_CLASS,
}

def is_windows(): return sys.platform.startswith("win")

def run_netsh(cmd: str):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return out.returncode, (out.stdout + out.stderr).strip()
    except Exception as e:
        return 1, str(e)

def apply_tcp_tweaks(enable: bool):
    if not is_windows(): return 1, "Unsupported"
    level = "normal" if enable else "disabled"
    run_netsh(f"netsh interface tcp set global autotuninglevel={level}")
    run_netsh(f"netsh interface tcp set global ecncapability={'enabled' if enable else 'disabled'}")
    run_netsh(f"netsh interface tcp set global rss={'enabled' if enable else 'disabled'}")
    run_netsh(f"netsh interface tcp set global dca={'enabled' if enable else 'disabled'}")
    return 0, "Smart packet tuning applied" if enable else "Smart packet reverted"

def set_low_latency_mode(enable: bool):
    if not is_windows(): return 1, "Unsupported"
    try:
        if enable:
            run_netsh("netsh interface tcp set global congestionprovider=ctcp")
            run_netsh("netsh interface tcp set global timestamps=disabled")
            subprocess.run(
                'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TcpAckFrequency /t REG_DWORD /d 1 /f',
                shell=True
            )
            subprocess.run(
                'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TCPNoDelay /t REG_DWORD /d 1 /f',
                shell=True
            )
        else:
            run_netsh("netsh interface tcp set global congestionprovider=none")
            run_netsh("netsh interface tcp set global timestamps=enabled")
            subprocess.run(
                'reg delete "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TcpAckFrequency /f',
                shell=True
            )
            subprocess.run(
                'reg delete "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TCPNoDelay /f',
                shell=True
            )
        return 0, "Low latency enabled" if enable else "Low latency disabled"
    except Exception as e:
        return 1, str(e)

def set_java_priority(name: str) -> int:
    if not is_windows(): return 0
    prio = PRIORITY_CLASSES.get(name, psutil.NORMAL_PRIORITY_CLASS)
    changed = 0
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info.get("name","").lower() in ["java.exe","javaw.exe"]:
                proc.nice(prio)
                changed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return changed

def change_dns(region: str):
    dns_map = {"US":"8.8.8.8","EU":"1.1.1.1","ASIA":"8.8.4.4"}
    dns = dns_map.get(region.upper(), "8.8.8.8")
    interfaces = subprocess.run('netsh interface show interface', shell=True, capture_output=True, text=True).stdout
    for line in interfaces.splitlines():
        if "Connected" in line:
            name = line.split()[-1]
            subprocess.run(f'netsh interface ip set dns name="{name}" static {dns}', shell=True)

_last_net = None
_last_time = None

def save_config():
    cfg = {
        "smart_packets": smart_packets_var.get(),
        "tuning": tuning_var.get(),
        "priority": priority_var.get(),
        "responsiveness": responsiveness_var.get(),
        "low_latency": low_latency_var.get(),
        "region_dns": region_var.get()
    }
    try:
        with open(CONFIG_FILE, "w") as f: json.dump(cfg, f, indent=2)
        status_var.set("Settings saved")
    except Exception as e:
        status_var.set(f"Save failed: {e}")

def load_config():
    if CONFIG_FILE.exists():
        try:
            data = json.load(open(CONFIG_FILE))
            smart_packets_var.set(bool(data.get("smart_packets", False)))
            tuning_var.set(data.get("tuning", "Balanced"))
            priority_var.set(data.get("priority", "Normal"))
            responsiveness_var.set(int(data.get("responsiveness", 50)))
            low_latency_var.set(bool(data.get("low_latency", False)))
            region_var.set(data.get("region_dns", "US"))
            status_var.set("Config loaded")
        except Exception as e:
            status_var.set(f"Load failed: {e}")

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
        upload_speed_var.set(f"{sent:.2f} MB/s")
        download_speed_var.set(f"{recv:.2f} MB/s")
        _last_net = net
        _last_time = now
    except:
        upload_speed_var.set("0.00 MB/s")
        download_speed_var.set("0.00 MB/s")
    finally:
        app.after(400, update_network_speed_smooth)

def smooth_progress(bar, target, speed=0.08):
    current = bar.get()
    if abs(current - target) < 0.005:
        bar.set(target)
        return
    bar.set(current + (target-current)*speed)
    app.after(16, lambda: smooth_progress(bar, target, speed))

def update_resources_smooth():
    try:
        cpu = psutil.cpu_percent(interval=None)/100
        ram = psutil.virtual_memory().percent/100
        smooth_progress(cpu_bar, cpu)
        smooth_progress(ram_bar, ram)
        cpu_usage_var.set(f"{cpu*100:.0f}%")
        ram_usage_var.set(f"{ram*100:.0f}%")
    finally:
        app.after(400, update_resources_smooth)

def apply_settings():
    save_config()
    apply_tcp_tweaks(smart_packets_var.get())
    set_low_latency_mode(low_latency_var.get())
    set_java_priority(priority_var.get())
    change_dns(region_var.get())
    status_var.set("Settings applied")

def add_to_startup():
    if not is_windows(): return
    path = os.path.realpath(sys.argv[0])
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, "FastPing", 0, winreg.REG_SZ, path)
    winreg.CloseKey(key)
    status_var.set("Added to startup")

def open_discord():
    webbrowser.open("https://discord.gg/T8GFc6ryGy")

app = ctk.CTk()
app.geometry(APP_SIZE)
app.title("FastPing — By WraithMC")
app.configure(fg_color=BG)
try: app.iconbitmap(LOGO_PATH)
except: pass

upload_speed_var = ctk.StringVar(value="0.00 MB/s")
download_speed_var = ctk.StringVar(value="0.00 MB/s")
cpu_usage_var = ctk.StringVar(value="0%")
ram_usage_var = ctk.StringVar(value="0%")
smart_packets_var = ctk.BooleanVar(value=False)
tuning_var = ctk.StringVar(value="Balanced")
priority_var = ctk.StringVar(value="Normal")
responsiveness_var = ctk.IntVar(value=50)
low_latency_var = ctk.BooleanVar(value=False)
region_var = ctk.StringVar(value="US")
status_var = ctk.StringVar(value="Ready")

main_frame = ctk.CTkFrame(app, fg_color=BG, corner_radius=20)
main_frame.pack(fill="both", expand=True, padx=15, pady=15)

header = ctk.CTkFrame(main_frame, fg_color=HEADER_BG, corner_radius=15)
header.pack(fill="x", padx=10, pady=(10,12))

left_h = ctk.CTkFrame(header, fg_color=HEADER_BG)
left_h.pack(side="left", padx=10)

if os.path.exists(LOGO_PATH):
    try:
        logo_img = ctk.CTkImage(light_image=Image.open(LOGO_PATH), dark_image=Image.open(LOGO_PATH), size=(40, 40))
        ctk.CTkLabel(left_h, image=logo_img, text="").pack(side="left", padx=(0,10))
    except: pass

ctk.CTkLabel(left_h, text="FastPing", font=("Segoe UI", 28, "bold"), text_color=ACCENT).pack(side="left")

right_h = ctk.CTkFrame(header, fg_color=HEADER_BG)
right_h.pack(side="right", padx=10)

ctk.CTkButton(right_h, text="Join Discord", command=open_discord, fg_color="#5865F2", hover_color="#4752C4", text_color="white", corner_radius=12, width=130).pack(side="right", padx=8)
ctk.CTkButton(right_h, text="Apply Settings", command=apply_settings, fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="white", corner_radius=12, width=150).pack(side="right", padx=8)

content = ctk.CTkFrame(main_frame, fg_color=BG, corner_radius=15)
content.pack(fill="both", expand=True, padx=8, pady=8)

left = ctk.CTkFrame(content, fg_color=CARD_BG, corner_radius=16)
left.pack(side="left", fill="both", expand=True, padx=(8,4), pady=8)

right = ctk.CTkFrame(content, fg_color=CARD_BG, corner_radius=16)
right.pack(side="right", fill="both", expand=True, padx=(4,8), pady=8)

ctk.CTkLabel(left, text="Network Status", font=("Segoe UI", 18, "bold"), text_color=TEXT).pack(anchor="w", padx=12, pady=(12,6))
net_frame = ctk.CTkFrame(left, fg_color=HEADER_BG, corner_radius=12)
net_frame.pack(fill="x", padx=12, pady=8)
ctk.CTkLabel(net_frame, text="Download", text_color=TEXT).grid(row=0, column=0, sticky="w", padx=12, pady=6)
ctk.CTkLabel(net_frame, textvariable=download_speed_var, text_color=ACCENT).grid(row=0, column=1, sticky="e", padx=12, pady=6)
ctk.CTkLabel(net_frame, text="Upload", text_color=TEXT).grid(row=1, column=0, sticky="w", padx=12, pady=6)
ctk.CTkLabel(net_frame, textvariable=upload_speed_var, text_color=ACCENT).grid(row=1, column=1, sticky="e", padx=12, pady=6)

ctk.CTkLabel(left, text="Responsiveness", text_color=TEXT).pack(anchor="w", padx=12, pady=(10,0))
ctk.CTkSlider(left, from_=0, to=100, variable=responsiveness_var, progress_color=ACCENT, button_color=ACCENT).pack(fill="x", padx=12, pady=(4,10))
ctk.CTkCheckBox(left, text="Smart Packets", variable=smart_packets_var, hover_color=ACCENT, text_color=TEXT, fg_color="#222222").pack(anchor="w", padx=12, pady=4)
ctk.CTkCheckBox(left, text="Low Latency Mode", variable=low_latency_var, hover_color=ACCENT, text_color=TEXT, fg_color="#222222").pack(anchor="w", padx=12, pady=4)
ctk.CTkLabel(left, text="Region DNS", text_color=TEXT).pack(anchor="w", padx=12, pady=(10,0))
ctk.CTkOptionMenu(left, values=["US","EU","ASIA"], variable=region_var, fg_color="#222222", text_color="white", button_color=ACCENT).pack(fill="x", padx=12, pady=(4,10))

actions = ctk.CTkFrame(left, fg_color=HEADER_BG, corner_radius=12)
actions.pack(fill="x", padx=12, pady=(12,6))
ctk.CTkButton(actions, text="Test Netsh", command=lambda: messagebox.showinfo("Netsh test", str(run_netsh("netsh interface tcp show global"))), fg_color="#333333", hover_color="#444444", text_color="white").pack(side="left", padx=6)
ctk.CTkButton(actions, text="Save Settings", command=save_config, fg_color="#333333", hover_color="#444444", text_color="white").pack(side="left", padx=6)

ctk.CTkLabel(right, text="System Info", font=("Segoe UI", 18, "bold"), text_color=TEXT).pack(anchor="w", padx=12, pady=(12,6))
sys_frame = ctk.CTkFrame(right, fg_color=HEADER_BG, corner_radius=12)
sys_frame.pack(fill="x", padx=12, pady=8)
ctk.CTkLabel(sys_frame, text="CPU", text_color=TEXT).grid(row=0,column=0, sticky="w", padx=12, pady=6)
ctk.CTkLabel(sys_frame, textvariable=cpu_usage_var, text_color=ACCENT).grid(row=0,column=1, sticky="e", padx=12, pady=6)
ctk.CTkLabel(sys_frame, text="RAM", text_color=TEXT).grid(row=1,column=0, sticky="w", padx=12, pady=6)
ctk.CTkLabel(sys_frame, textvariable=ram_usage_var, text_color=ACCENT).grid(row=1,column=1, sticky="e", padx=12, pady=6)

cpu_bar = ctk.CTkProgressBar(right, width=200, progress_color=ACCENT)
cpu_bar.pack(fill="x", padx=18, pady=(8,8))
ram_bar = ctk.CTkProgressBar(right, width=200, progress_color=ACCENT)
ram_bar.pack(fill="x", padx=18, pady=(0,10))

ctk.CTkLabel(right, text="Java Priority", text_color=TEXT).pack(anchor="w", padx=12, pady=(10,0))
ctk.CTkOptionMenu(right, values=list(PRIORITY_CLASSES.keys()), variable=priority_var, fg_color="#222222", text_color="white", button_color=ACCENT).pack(fill="x", padx=12, pady=6)
ctk.CTkLabel(right, text="Tuning Level", text_color=TEXT).pack(anchor="w", padx=12, pady=(10,0))
ctk.CTkOptionMenu(right, values=["Restricted","Balanced","Aggressive"], variable=tuning_var, fg_color="#222222", text_color="white", button_color=ACCENT).pack(fill="x", padx=12, pady=6)
ctk.CTkButton(right, text="Add to Startup", command=add_to_startup, fg_color="#333333", hover_color="#444444", text_color="white").pack(padx=12, pady=(12,8))

footer = ctk.CTkFrame(main_frame, fg_color=HEADER_BG, corner_radius=12)
footer.pack(fill="x", padx=12, pady=(8,12))
ctk.CTkLabel(footer, textvariable=status_var, anchor="w", text_color="#AAAAAA").pack(side="left", padx=8)
ctk.CTkLabel(footer, text="v2.3", anchor="e", text_color="#777777").pack(side="right", padx=8)

load_config()
init_net_counters()
update_network_speed_smooth()
update_resources_smooth()
app.mainloop()
