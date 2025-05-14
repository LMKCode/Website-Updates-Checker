import tkinter as tk
from tkinter import messagebox
import threading
import hashlib
import requests
import time
import os
import json

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

CONFIG_FILE = "monitor_config.json"
monitoring_active = False
tray_icon = None

# Telegram-Nachricht senden
def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, data=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Fehler beim Senden an Telegram: {e}")
        return False

# Countdown vor nächster Prüfung
def countdown(seconds, label):
    while seconds > 0 and monitoring_active:
        label.config(text=f"\u23f3 Nächste Prüfung in {seconds} Sekunden", fg="orange")
        time.sleep(1)
        seconds -= 1

# Website überwachen
def monitor_website(url, interval, token, chat_id, status_label):
    global monitoring_active
    last_hash = ""
    monitoring_active = True
    while monitoring_active:
        try:
            status_label.config(text="\u23f3 Prüfe Website...", fg="orange")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            content = response.text
            hash_now = hashlib.sha256(content.encode('utf-8')).hexdigest()

            if last_hash and hash_now != last_hash:
                send_telegram_message(token, chat_id, f"🔔 Änderung erkannt auf:\n{url}")
            last_hash = hash_now
            status_label.config(
                text=f"✅ Letzte Prüfung: {time.strftime('%H:%M:%S')} – nächste in {interval} Min",
                fg="green")
        except Exception as e:
            status_label.config(text=f"❌ Fehler: {str(e)}", fg="red")
        if interval >= 1:
            time.sleep((interval - 1) * 60)
            countdown(60, status_label)
        else:
            countdown(int(interval * 60), status_label)

# Start-Button

def start_monitoring(entries, status_label, start_button, stop_button):
    global monitoring_active
    if monitoring_active:
        messagebox.showinfo("Bereits aktiv", "Monitoring läuft bereits.")
        return
    try:
        url = entries["url"].get().strip()
        interval = float(entries["interval"].get())
        token = entries["token"].get().strip()
        chat_id = entries["chat_id"].get().strip()

        if not url.startswith("http"):
            raise ValueError("Ungültige URL")

        status_label.config(text="🔄 Monitoring wird gestartet...", fg="blue")
        start_button.config(state="disabled")
        stop_button.config(state="normal")
        threading.Thread(
            target=monitor_website,
            args=(url, interval, token, chat_id, status_label),
            daemon=True
        ).start()
    except Exception as e:
        messagebox.showerror("Fehler", str(e))

# Stop-Button
def stop_monitoring(status_label, start_button, stop_button):
    global monitoring_active
    monitoring_active = False
    status_label.config(text="⛔ Monitoring gestoppt", fg="gray")
    start_button.config(state="normal")
    stop_button.config(state="disabled")

# Testnachricht senden
def send_test_message(token_entry, chat_id_entry):
    token = token_entry.get().strip()
    chat_id = chat_id_entry.get().strip()
    success = send_telegram_message(token, chat_id, "✅ Testnachricht vom Website-Monitor.")
    if success:
        messagebox.showinfo("Erfolg", "Testnachricht gesendet.")
    else:
        messagebox.showerror("Fehler", "Konnte keine Nachricht senden.")

# Minimieren in Tray
def minimize_to_tray(window):
    if not TRAY_AVAILABLE:
        window.withdraw()
        return

    def on_click(icon, item):
        icon.stop()
        window.after(0, window.deiconify)

    def create_image():
        image = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 16, 48, 48), fill='blue')
        return image

    global tray_icon
    window.withdraw()
    tray_icon = pystray.Icon("WebsiteMonitor", icon=create_image(), title="Website Monitor")
    tray_icon.menu = pystray.Menu(pystray.MenuItem("Öffnen", on_click))
    threading.Thread(target=tray_icon.run, daemon=True).start()

# Einstellungen speichern/lesen
def save_config(entries):
    config_data = {
        "url": entries["url"].get().strip(),
        "interval": entries["interval"].get().strip(),
        "token": entries["token"].get().strip(),
        "chat_id": entries["chat_id"].get().strip()
    }
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f)
        messagebox.showinfo("Gespeichert", "Konfiguration gespeichert.")
    except Exception as e:
        messagebox.showerror("Fehler beim Speichern", str(e))

def load_config(entries):
    if not os.path.exists(CONFIG_FILE):
        return
    try:
        with open(CONFIG_FILE, "r") as f:
            config_data = json.load(f)
            for key in ["url", "interval", "token", "chat_id"]:
                entries[key].delete(0, tk.END)
                entries[key].insert(0, config_data.get(key, ""))
    except Exception as e:
        messagebox.showerror("Fehler beim Laden", str(e))

# GUI aufbauen
def create_gui():
    root = tk.Tk()
    root.title("Website Monitor mit Telegram")
    root.geometry("450x480")
    root.resizable(False, False)

    entries = {}

    def add_labeled_entry(label, key):
        tk.Label(root, text=label).pack(pady=(8, 0))
        entry = tk.Entry(root, width=50)
        entry.pack()
        entries[key] = entry

    add_labeled_entry("Website-URL:", "url")
    add_labeled_entry("Intervall (Minuten):", "interval")
    add_labeled_entry("Telegram Bot Token:", "token")
    add_labeled_entry("Telegram Chat ID:", "chat_id")

    load_config(entries)

    status_label = tk.Label(root, text="Status: Noch nicht gestartet", fg="blue")
    status_label.pack(pady=10)

    button_frame = tk.Frame(root)
    button_frame.pack(pady=10)

    start_button = tk.Button(button_frame, text="Monitoring starten")
    stop_button = tk.Button(button_frame, text="Monitoring stoppen", state="disabled")

    start_button.config(command=lambda: start_monitoring(entries, status_label, start_button, stop_button))
    stop_button.config(command=lambda: stop_monitoring(status_label, start_button, stop_button))

    start_button.grid(row=0, column=0, padx=10)
    stop_button.grid(row=0, column=1, padx=10)

    action_frame = tk.Frame(root)
    action_frame.pack(pady=5)

    tk.Button(action_frame, text="Testnachricht senden", command=lambda: send_test_message(entries["token"], entries["chat_id"])).grid(row=0, column=0, padx=5)
    tk.Button(action_frame, text="Einstellungen speichern", command=lambda: save_config(entries)).grid(row=0, column=1, padx=5)

    if TRAY_AVAILABLE:
        tk.Button(root, text="Minimieren in Tray", command=lambda: minimize_to_tray(root)).pack(pady=5)

    root.protocol("WM_DELETE_WINDOW", lambda: minimize_to_tray(root))
    root.mainloop()

create_gui()