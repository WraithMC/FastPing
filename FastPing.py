import customtkinter as ctk
import psutil
import subprocess
import time
import json
import os
import sys
import winreg
import webbrowser
from tkinter import messagebox
from pathlib import Path
import math

CONFIG_FILE = Path("config.json")
LOGO_PATH = Path("logo.png")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_SIZE = "860x560"
ACCENT = "#4A90E2"
ACCENT_HOVER = "#357ABD"
TEXT = "#FFFFFF"
CARD_BG = "#1E1E1E"
BG = "#121212"

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

app = ctk.CTk()
app.geometry(APP_SIZE)
app.title("FastPing — By WraithMC")
app.configure(fg_color=BG)

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

_last_net = None
_last_time = None

def save_config():
    cfg = {
        "smart_packets": smart_packets_var.get(),
        "tuning": tuning_var.get(),
        "priority": priority_var.get(),
        "responsiveness": responsiveness_var.get(),
        "low_latency": low_latency_var.get(),
    }
    try:
        with open(CONFIG_FILE, "w") as f: json.dump(cfg, f, indent=2)
        status_var.set("Settings saved")
    except Exception as e: status_var.set(f"Save failed: {e}")

def load_config():
    if CONFIG_FILE.exists():
        try:
            data = json.load(open(CONFIG_FILE))
            smart_packets_var.set(bool(data.get("smart_packets", False)))
            tuning_var.set(data.get("tuning", "Balanced"))
            priority_var.set(data.get("priority", "Normal"))
            responsiveness_var.set(int(data.get("responsiveness", 50)))
            low_latency_var.set(bool(data.get("low_latency", False)))
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

        current_upload = float(upload_speed_var.get().split()[0])
        current_download = float(download_speed_var.get().split()[0])

        upload_speed_var.set(f"{current_upload + (sent-current_upload)*0.25:.2f} MB/s")
        download_speed_var.set(f"{current_download + (recv-current_download)*0.25:.2f} MB/s")

        _last_net = net
        _last_time = now
    except:
        upload_speed_var.set("0.00 MB/s")
        download_speed_var.set("0.00 MB/s")
    finally:
        app.after(500, update_network_speed_smooth)

def update_resources_smooth():
    try:
        cpu = psutil.cpu_percent(interval=None)/100
        ram = psutil.virtual_memory().percent/100
        smooth_progress(cpu_bar, cpu)
        smooth_progress(ram_bar, ram)
        cpu_usage_var.set(f"{cpu*100:.0f}%")
        ram_usage_var.set(f"{ram*100:.0f}%")
    except:
        cpu_usage_var.set("N/A")
        ram_usage_var.set("N/A")
    finally:
        app.after(500, update_resources_smooth)

def smooth_progress(bar, target, speed=0.02):
    current = bar.get()
    if abs(current - target) < 0.01:
        bar.set(target)
        return
    step = (target-current)*speed
    bar.set(current+step)
    app.after(20, lambda: smooth_progress(bar, target, speed))

def set_java_priority(name: str) -> int:
    if not is_windows(): return 0
    prio = PRIORITY_CLASSES.get(name, psutil.NORMAL_PRIORITY_CLASS)
    changed = 0
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info.get("name","").lower() in ["java.exe","javaw.exe"]:
                proc.nice(prio)
                changed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied): continue
    return changed

def apply_tcp_tweaks(enable: bool):
    if not is_windows(): return 1, "Unsupported"
    level = "normal" if enable else "disabled"
    return run_netsh(f"netsh interface tcp set global autotuninglevel={level}")

def set_low_latency_mode(enable: bool):
    if not is_windows(): return 1, "Unsupported"
    provider = "ctcp" if enable else "ctcp"
    return run_netsh(f"netsh interface tcp set global congestionprovider={provider}")

def apply_settings():
    try:
        save_config()
        rc1, out1 = apply_tcp_tweaks(smart_packets_var.get())
        rc2, out2 = set_low_latency_mode(low_latency_var.get())
        changed = set_java_priority(priority_var.get())
        msg = [
            f"Tuning: {tuning_var.get()}",
            f"Smart Packets: {'On' if smart_packets_var.get() else 'Off'}",
            f"Low Latency: {'On' if low_latency_var.get() else 'Off'}",
            f"Responsiveness: {responsiveness_var.get()}",
            f"Java Priority: {priority_var.get()}",
            f"Processes changed: {changed}"
        ]
        status_var.set("Settings applied")
        messagebox.showinfo("Settings Applied", "\n".join(msg))
    except Exception as e:
        status_var.set(f"Apply failed: {e}")
        messagebox.showerror("Error", str(e))

def add_to_startup():
    if not is_windows():
        messagebox.showwarning("Unsupported", "Windows-only feature.")
        return
    try:
        path = os.path.realpath(sys.argv[0])
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "FastPing", 0, winreg.REG_SZ, path)
        winreg.CloseKey(key)
        status_var.set("Added to startup")
        messagebox.showinfo("Added", "FastPing will start with Windows")
    except Exception as e:
        status_var.set(f"Startup failed: {e}")
        messagebox.showerror("Error", str(e))

def open_discord():
    webbrowser.open("https://discord.gg/T8GFc6ryGy")

main_frame = ctk.CTkFrame(app, fg_color=BG, corner_radius=12)
main_frame.pack(fill="both", expand=True, padx=20, pady=20)

header = ctk.CTkFrame(main_frame, fg_color=BG, corner_radius=8)
header.pack(fill="x", padx=8, pady=(8,12))

left_h = ctk.CTkFrame(header, fg_color=BG, corner_radius=6)
left_h.pack(side="left", padx=6, pady=6)

if LOGO_PATH.exists():
    try:
        logo = ctk.CTkImage(LOGO_PATH, size=(48,48))
        ctk.CTkLabel(left_h, image=logo, text="").pack(side="left", padx=(0,12))
    except: pass

ctk.CTkLabel(left_h, text="FastPing", font=("Segoe UI", 24, "bold"), text_color=ACCENT).pack(side="left")
ctk.CTkLabel(left_h, text="— Network & Java Tuning", font=("Segoe UI", 11), text_color=TEXT).pack(side="left", padx=(6,0))

right_h = ctk.CTkFrame(header, fg_color=BG, corner_radius=6)
right_h.pack(side="right", padx=6, pady=6)
ctk.CTkButton(right_h, text="Join Discord", command=open_discord,
              fg_color="#5865F2", hover_color="#4752C4", corner_radius=12).pack(side="right", padx=8)
ctk.CTkButton(right_h, text="Apply Settings", command=apply_settings,
              fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=12).pack(side="right", padx=8)

content = ctk.CTkFrame(main_frame, fg_color=BG, corner_radius=12)
content.pack(fill="both", expand=True, padx=6, pady=6)

left = ctk.CTkFrame(content, fg_color=CARD_BG, corner_radius=12)
left.pack(side="left", fill="both", expand=True, padx=(6,3), pady=6)
right = ctk.CTkFrame(content, fg_color=CARD_BG, corner_radius=12)
right.pack(side="right", fill="both", expand=True, padx=(3,6), pady=6)

ctk.CTkLabel(left, text="Network Status", font=("Segoe UI", 16, "bold"), text_color=TEXT).pack(anchor="w", padx=12, pady=(6,6))

net_frame = ctk.CTkFrame(left, fg_color=BG, corner_radius=10)
net_frame.pack(fill="x", padx=12, pady=6)
ctk.CTkLabel(net_frame, text="Download", text_color=TEXT).grid(row=0, column=0, sticky="w", padx=12, pady=6)
ctk.CTkLabel(net_frame, textvariable=download_speed_var, text_color=ACCENT).grid(row=0, column=1, sticky="e", padx=12, pady=6)
ctk.CTkLabel(net_frame, text="Upload", text_color=TEXT).grid(row=1, column=0, sticky="w", padx=12, pady=6)
ctk.CTkLabel(net_frame, textvariable=upload_speed_var, text_color=ACCENT).grid(row=1, column=1, sticky="e", padx=12, pady=6)

ctk.CTkLabel(left, text="Responsiveness", text_color=TEXT).pack(anchor="w", padx=12, pady=(8,0))
ctk.CTkSlider(left, from_=0, to=100, variable=responsiveness_var,
              progress_color=ACCENT, button_color=ACCENT).pack(fill="x", padx=12, pady=(2,8))

ctk.CTkCheckBox(left, text="Smart Packets", variable=smart_packets_var, hover_color=ACCENT).pack(anchor="w", padx=12, pady=6)
ctk.CTkCheckBox(left, text="Low Latency Mode", variable=low_latency_var, hover_color=ACCENT).pack(anchor="w", padx=12, pady=6)

actions = ctk.CTkFrame(left, fg_color=BG, corner_radius=8)
actions.pack(fill="x", padx=12, pady=(10,6))
ctk.CTkButton(actions, text="Test Netsh", command=lambda: messagebox.showinfo("Netsh test", str(run_netsh("netsh interface tcp show global")))).pack(side="left", padx=6)
ctk.CTkButton(actions, text="Save Settings", command=save_config, fg_color="#333333", hover_color="#444444").pack(side="left", padx=6)

ctk.CTkLabel(right, text="System Info", font=("Segoe UI", 16, "bold"), text_color=TEXT).pack(anchor="w", padx=12, pady=(6,6))

sys_frame = ctk.CTkFrame(right, fg_color=BG, corner_radius=10)
sys_frame.pack(fill="x", padx=12, pady=6)
ctk.CTkLabel(sys_frame, text="CPU", text_color=TEXT).grid(row=0,column=0, sticky="w", padx=12, pady=6)
ctk.CTkLabel(sys_frame, textvariable=cpu_usage_var, text_color=ACCENT).grid(row=0,column=1, sticky="e", padx=12, pady=6)
ctk.CTkLabel(sys_frame, text="RAM", text_color=TEXT).grid(row=1,column=0, sticky="w", padx=12, pady=6)
ctk.CTkLabel(sys_frame, textvariable=ram_usage_var, text_color=ACCENT).grid(row=1,column=1, sticky="e", padx=12, pady=6)

cpu_bar = ctk.CTkProgressBar(right, width=200)
cpu_bar.pack(fill="x", padx=18, pady=(6,8))
ram_bar = ctk.CTkProgressBar(right, width=200)
ram_bar.pack(fill="x", padx=18, pady=(0,8))

ctk.CTkLabel(right, text="Java Priority", text_color=TEXT).pack(anchor="w", padx=12, pady=(8,0))
ctk.CTkOptionMenu(right, values=list(PRIORITY_CLASSES.keys()), variable=priority_var).pack(fill="x", padx=12, pady=6)

ctk.CTkLabel(right, text="Tuning Level", text_color=TEXT).pack(anchor="w", padx=12, pady=(8,0))
ctk.CTkOptionMenu(right, values=["Restricted","Balanced","Aggressive"], variable=tuning_var).pack(fill="x", padx=12, pady=6)

ctk.CTkButton(right, text="Add to Startup", command=add_to_startup, fg_color="#333333", hover_color="#444444").pack(padx=12, pady=(10,6))

footer = ctk.CTkFrame(main_frame, fg_color=BG, corner_radius=6)
footer.pack(fill="x", padx=12, pady=(6,12))
ctk.CTkLabel(footer, textvariable=status_var, anchor="w").pack(side="left", padx=8)
ctk.CTkLabel(footer, text="v2.0", anchor="e", text_color=TEXT).pack(side="right", padx=8)

load_config()
init_net_counters()
update_network_speed_smooth()
update_resources_smooth()

app.mainloop()
