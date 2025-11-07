import ctypes, sys, os

def run_as_admin():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True
    try:
        params = " ".join([f'"{arg}"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit()
    except Exception:
        return False

run_as_admin()

import customtkinter as ctk
import psutil, subprocess, threading, time, json, os, sys, winreg
from tkinter import messagebox
from pynput import keyboard

CONFIG_FILE = "fastping_config.json"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")

app = ctk.CTk()
app.geometry("600x520")
app.title("FastPing - Network Optimizer")

app.configure(fg_color="#F9F9F9")

ACCENT_COLOR = "#4CAF50"
TEXT_COLOR = "#1E1E1E"

def is_windows():
    return os.name == "nt"

def run_netsh(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode, result.stdout.strip()
    except Exception as e:
        return 1, str(e)

def apply_tcp_tweaks(enable: bool):
    if not is_windows():
        return 1, "Unsupported"
    try:
        if enable:
            cmds = [
                "netsh interface tcp set global autotuninglevel=normal",
                "netsh interface tcp set global ecncapability=enabled",
                "netsh interface tcp set global rss=enabled",
                "netsh interface tcp set global dca=enabled"
            ]
        else:
            cmds = [
                "netsh interface tcp set global autotuninglevel=disabled",
                "netsh interface tcp set global ecncapability=disabled",
                "netsh interface tcp set global rss=disabled",
                "netsh interface tcp set global dca=disabled"
            ]
        results = [run_netsh(c) for c in cmds]
        return 0, "Smart packet tuning applied" if enable else "Smart packet tuning reverted"
    except Exception as e:
        return 1, str(e)

def set_low_latency_mode(enable: bool):
    if not is_windows():
        return 1, "Unsupported"
    try:
        cmds = []
        if enable:
            cmds += [
                "netsh interface tcp set global congestionprovider=ctcp",
                "netsh interface tcp set global timestamps=disabled"
            ]
            subprocess.run(
                'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TcpAckFrequency /t REG_DWORD /d 1 /f',
                shell=True
            )
            subprocess.run(
                'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TCPNoDelay /t REG_DWORD /d 1 /f',
                shell=True
            )
        else:
            cmds += [
                "netsh interface tcp set global congestionprovider=none",
                "netsh interface tcp set global timestamps=enabled"
            ]
            subprocess.run(
                'reg delete "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TcpAckFrequency /f',
                shell=True
            )
            subprocess.run(
                'reg delete "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" /v TCPNoDelay /f',
                shell=True
            )
        for c in cmds:
            run_netsh(c)
        return 0, "Low latency mode enabled" if enable else "Low latency mode disabled"
    except Exception as e:
        return 1, str(e)

def optimize_network():
    status_label.configure(text="Optimizing network...", text_color="orange")
    app.update_idletasks()
    time.sleep(1)
    apply_tcp_tweaks(True)
    set_low_latency_mode(True)
    status_label.configure(text="Optimization Complete!", text_color=ACCENT_COLOR)

def restore_defaults():
    status_label.configure(text="Restoring settings...", text_color="orange")
    app.update_idletasks()
    time.sleep(1)
    apply_tcp_tweaks(False)
    set_low_latency_mode(False)
    status_label.configure(text="Restored to default settings.", text_color=ACCENT_COLOR)

title_label = ctk.CTkLabel(app, text="FastPing Optimizer", text_color=TEXT_COLOR, font=("Poppins", 26, "bold"))
title_label.pack(pady=25)

optimize_btn = ctk.CTkButton(app, text="Enable Smart Packets + Low Latency", fg_color=ACCENT_COLOR, text_color="white",
                             font=("Poppins", 16, "bold"), width=300, height=40, command=optimize_network)
optimize_btn.pack(pady=10)

restore_btn = ctk.CTkButton(app, text="Restore Default Settings", fg_color="#E74C3C", text_color="white",
                            font=("Poppins", 16, "bold"), width=300, height=40, command=restore_defaults)
restore_btn.pack(pady=10)

status_label = ctk.CTkLabel(app, text="Ready.", text_color=TEXT_COLOR, font=("Poppins", 14))
status_label.pack(pady=40)

footer_label = ctk.CTkLabel(app, text="Made by WraithMC", text_color="#666666", font=("Poppins", 12))
footer_label.pack(side="bottom", pady=10)

app.mainloop()
