"""
╔══════════════════════════════════════════════════════════════╗
║       PROJECT 9: Simple Attendance System (Face Recognition) ║
║──────────────────────────────────────────────────────────────║
║  INSTALLATION:                                               ║
║    pip install face-recognition opencv-python pillow         ║
║    On Linux: sudo apt install cmake build-essential          ║
║                                                              ║
║  SETUP:                                                      ║
║    Create a folder called 'known_faces/'                     ║
║    Add photos named after the person, e.g.:                  ║
║      known_faces/Alice.jpg                                   ║
║      known_faces/Bob.png                                     ║
║                                                              ║
║  RUN:                                                        ║
║    python project9_attendance.py                            ║
╚══════════════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import threading
import csv
import datetime
import os

KNOWN_DIR    = "known_faces"
LOG_FILE     = "attendance.csv"
COOLDOWN_SEC = 30     # seconds before same person is re-logged


class AttendanceApp:
    BG      = "#0f0f23"
    SURFACE = "#1a1a3e"
    ACCENT  = "#7c3aed"
    TEXT    = "#e2e8f0"
    MUTED   = "#64748b"
    GREEN   = "#22c55e"
    RED     = "#ef4444"

    def __init__(self, root):
        self.root = root
        self.root.title("📋 Attendance System")
        self.root.configure(bg=self.BG)
        self.root.geometry("900x620")

        self.cap = None
        self.running = False
        self.known_encodings = []
        self.known_names = []
        self.last_seen = {}    # name → datetime

        self._ensure_csv()
        self._build_ui()
        self._load_known_faces()

    def _ensure_csv(self):
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", newline="") as f:
                csv.writer(f).writerow(["Name", "Date", "Time"])

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=self.SURFACE)
        hdr.pack(fill="x")
        tk.Label(hdr, text="ATTENDANCE SYSTEM",
                 font=("Helvetica", 15, "bold"),
                 fg=self.ACCENT, bg=self.SURFACE, pady=10).pack(side="left", padx=20)
        self.today_var = tk.StringVar(
            value=datetime.datetime.now().strftime("%A, %B %d %Y")
        )
        tk.Label(hdr, textvariable=self.today_var,
                 font=("Helvetica", 10), fg=self.MUTED, bg=self.SURFACE).pack(side="right", padx=20)

        # Body
        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill="both", expand=True, padx=12, pady=8)

        # Left — camera
        left = tk.Frame(body, bg=self.SURFACE,
                        highlightthickness=1, highlightbackground="#2d2d5e")
        left.pack(side="left", fill="both", expand=True)

        self.video_lbl = tk.Label(left, bg="#050514",
                                  width=60, height=22,
                                  text="Camera feed will appear here",
                                  font=("Helvetica", 10), fg=self.MUTED)
        self.video_lbl.pack(padx=2, pady=2, fill="both", expand=True)

        # Right — log
        right = tk.Frame(body, bg=self.SURFACE, width=280,
                         highlightthickness=1, highlightbackground="#2d2d5e")
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)

        tk.Label(right, text="ATTENDANCE LOG",
                 font=("Helvetica", 10, "bold"),
                 fg=self.ACCENT, bg=self.SURFACE, pady=8).pack(anchor="w", padx=12)

        cols = ("Name", "Time")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=20)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=self.SURFACE, foreground=self.TEXT,
                        rowheight=28, fieldbackground=self.SURFACE,
                        borderwidth=0)
        style.configure("Treeview.Heading",
                        background="#2d2d5e", foreground=self.TEXT,
                        relief="flat")
        self.tree.heading("Name", text="Name")
        self.tree.heading("Time", text="Time")
        self.tree.column("Name", width=160)
        self.tree.column("Time", width=80)
        self.tree.pack(fill="both", expand=True, padx=4)

        # Controls
        ctrl = tk.Frame(self.root, bg=self.SURFACE)
        ctrl.pack(fill="x", padx=12, pady=(0, 8))

        self.start_btn = tk.Button(
            ctrl, text="▶  START CAMERA",
            font=("Helvetica", 11, "bold"),
            bg=self.GREEN, fg="#000",
            activebackground="#16a34a",
            bd=0, padx=20, pady=8, cursor="hand2",
            command=self.start
        )
        self.start_btn.pack(side="left", padx=8, pady=8)

        self.stop_btn = tk.Button(
            ctrl, text="■  STOP",
            font=("Helvetica", 11, "bold"),
            bg=self.SURFACE, fg=self.RED,
            activebackground="#27272a",
            bd=0, padx=20, pady=8, cursor="hand2",
            command=self.stop, state="disabled"
        )
        self.stop_btn.pack(side="left")

        tk.Button(ctrl, text="📂 Export CSV",
                  font=("Helvetica", 10),
                  bg="#2d2d5e", fg=self.TEXT,
                  activebackground="#3d3d7e",
                  bd=0, padx=16, pady=8, cursor="hand2",
                  command=self._open_csv).pack(side="right", padx=8, pady=8)

        self.status_var = tk.StringVar(value="Loading known faces…")
        tk.Label(ctrl, textvariable=self.status_var,
                 font=("Helvetica", 9), fg=self.MUTED, bg=self.SURFACE).pack(side="left", padx=12)

    def _load_known_faces(self):
        def _load():
            import face_recognition
            os.makedirs(KNOWN_DIR, exist_ok=True)
            loaded = 0
            for fn in os.listdir(KNOWN_DIR):
                if not fn.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                path = os.path.join(KNOWN_DIR, fn)
                img = face_recognition.load_image_file(path)
                encs = face_recognition.face_encodings(img)
                if encs:
                    name = os.path.splitext(fn)[0]
                    self.known_encodings.append(encs[0])
                    self.known_names.append(name)
                    loaded += 1
            msg = f"✓ {loaded} face(s) loaded" if loaded else \
                  f"⚠ No faces found in '{KNOWN_DIR}/' — add photos to register people"
            self.root.after(0, self.status_var.set, msg)
            self.root.after(0, self.start_btn.configure, {"state": "normal"})
        self.start_btn.configure(state="disabled")
        threading.Thread(target=_load, daemon=True).start()

    def start(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.status_var.set("⚠ Cannot open camera")
            return
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        threading.Thread(target=self._video_loop, daemon=True).start()

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._show_placeholder()

    def _show_placeholder(self):
        img = Image.new("RGB", (540, 380), "#050514")
        imgtk = ImageTk.PhotoImage(img)
        self._imgtk = imgtk
        self.video_lbl.configure(image=imgtk, text="")

    def _video_loop(self):
        import face_recognition
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break

            small = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

            locs  = face_recognition.face_locations(rgb_small)
            encs  = face_recognition.face_encodings(rgb_small, locs)

            for (top, right, bottom, left), enc in zip(locs, encs):
                top*=4; right*=4; bottom*=4; left*=4
                name = "Unknown"
                if self.known_encodings:
                    matches = face_recognition.compare_faces(self.known_encodings, enc, tolerance=0.5)
                    dists   = face_recognition.face_distance(self.known_encodings, enc)
                    best    = int(dists.argmin()) if dists.size else -1
                    if best >= 0 and matches[best]:
                        name = self.known_names[best]
                        self._log_attendance(name)

                color = (34, 197, 94) if name != "Unknown" else (239, 68, 68)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.rectangle(frame, (left, bottom-24), (right, bottom), color, -1)
                cv2.putText(frame, name, (left+4, bottom-6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,0), 1)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            img.thumbnail((540, 380))
            imgtk = ImageTk.PhotoImage(img)
            self.root.after(0, self._update_frame, imgtk)

    def _update_frame(self, imgtk):
        self._imgtk = imgtk
        self.video_lbl.configure(image=imgtk, text="")

    def _log_attendance(self, name: str):
        now = datetime.datetime.now()
        last = self.last_seen.get(name)
        if last and (now - last).total_seconds() < COOLDOWN_SEC:
            return
        self.last_seen[name] = now
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        with open(LOG_FILE, "a", newline="") as f:
            csv.writer(f).writerow([name, date_str, time_str])
        self.root.after(0, self._add_log_row, name, time_str)

    def _add_log_row(self, name: str, time_str: str):
        self.tree.insert("", 0, values=(name, time_str))

    def _open_csv(self):
        import subprocess, sys
        if sys.platform == "win32":
            os.startfile(LOG_FILE)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", LOG_FILE])
        else:
            subprocess.Popen(["xdg-open", LOG_FILE])

    def on_close(self):
        self.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AttendanceApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
