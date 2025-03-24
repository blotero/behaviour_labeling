import csv
import os
import tkinter as tk
from tkinter import filedialog, ttk

import cv2
from PIL import Image, ImageTk

from config import BUTTONS_CONFIG


class VideoLabelingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Herramienta de Etiquetado de Comportamientos")
        # self.root.geometry("1920x1080")

        self.behaviors = BUTTONS_CONFIG

        self.video_dir = ""
        self.video_files = []
        self.current_video_index = 0
        self.cap = None
        self.is_playing = False
        self.playback_speed = 1.0
        self.current_behavior = None
        self.behavior_start_time = None
        self.video_duration = 0
        self.video_position = tk.DoubleVar()
        self.behavior_records = []

        self.setup_ui()

    def setup_ui(self):
        self.load_button = ttk.Button(self.root, text="Cargar Videos", command=self.load_videos)
        self.load_button.pack()

        self.video_label = ttk.Label(self.root, text="No hay video cargado")
        self.video_label.pack()

        self.canvas = tk.Canvas(self.root, width=900, height=600)
        self.canvas.pack()

        self.time_frame = ttk.Frame(self.root)
        self.time_frame.pack(fill=tk.X, padx=10)

        self.current_time_label = ttk.Label(self.time_frame, text="00:00")
        self.current_time_label.pack(side=tk.LEFT)

        self.time_slider = ttk.Scale(
            self.root,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.video_position,
            command=self.seek_video,
        )
        self.time_slider.pack(fill=tk.X, padx=10)
        self.total_time_label = ttk.Label(self.time_frame, text="00:00")
        self.total_time_label.pack(side=tk.RIGHT)

        self.controls_frame = ttk.Frame(self.root)
        self.controls_frame.pack()

        self.play_button = ttk.Button(self.controls_frame, text="▶", command=self.toggle_play)
        self.play_button.pack(side=tk.LEFT)

        self.prev_button = ttk.Button(self.controls_frame, text="⏮", command=self.prev_video)
        self.prev_button.pack(side=tk.LEFT)

        self.next_button = ttk.Button(self.controls_frame, text="⏭", command=self.next_video)
        self.next_button.pack(side=tk.LEFT)

        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_menu = ttk.Combobox(
            self.controls_frame,
            textvariable=self.speed_var,
            values=[0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
            state="readonly",
        )
        self.speed_menu.pack(side=tk.LEFT)
        self.speed_menu.bind("<<ComboboxSelected>>", self.change_speed)

        self.tag_var = tk.StringVar()
        self.tag_label = ttk.Label(self.controls_frame, text="Etiqueta: ")
        self.tag_label.pack(side=tk.LEFT)

        self.tag_entry = ttk.Entry(self.controls_frame, textvariable=self.tag_var)
        self.tag_entry.pack(side=tk.LEFT)

        self.save_button = ttk.Button(
            self.controls_frame, text="Guardar Registros💾", command=self.save_behavior_records
        )
        self.save_button.pack(side=tk.LEFT)

        self.behavior_frame = ttk.Frame(self.root)
        self.behavior_frame.pack()

        self.behavior_buttons = {}
        for key, value in self.behaviors.items():
            btn = ttk.Button(
                self.behavior_frame,
                text=value,
                command=lambda k=key: self.toggle_behavior(k),
            )
            btn.pack(side=tk.LEFT)
            self.behavior_buttons[key] = btn

        self.records_frame = ttk.LabelFrame(self.root, text="Registros de comportamiento")
        self.records_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.records_text = tk.Text(self.records_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.records_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(self.records_frame, command=self.records_text.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.records_text.config(yscrollcommand=self.scrollbar.set)

    def load_videos(self):
        self.video_dir = filedialog.askdirectory()
        if self.video_dir:
            self.video_files = sorted(
                [f for f in os.listdir(self.video_dir) if f.lower().endswith(".mp4")]
            )
            self.current_video_index = 0
            self.play_video()

    def play_video(self):
        if self.cap:
            self.cap.release()
        if self.video_files:
            video_path = os.path.join(self.video_dir, self.video_files[self.current_video_index])
            self.video_label.config(text=self.video_files[self.current_video_index])
            self.cap = cv2.VideoCapture(video_path)
            self.video_duration = self.cap.get(cv2.CAP_PROP_FRAME_COUNT) / self.cap.get(
                cv2.CAP_PROP_FPS
            )
            self.time_slider.config(to=self.video_duration)
            self.total_time_label.config(text=self.format_time(self.video_duration))
            self.is_playing = True
            self.behavior_records = []
            self.update_frame()
            self.update_records_display()

    def update_frame(self):
        if self.cap and self.is_playing:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (900, 600))
                img = ImageTk.PhotoImage(Image.fromarray(frame))
                self.canvas.create_image(0, 0, anchor=tk.NW, image=img)
                self.canvas.image = img
                current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                self.video_position.set(current_time)
                self.current_time_label.config(text=self.format_time(current_time))
                self.root.after(int(1000 // (30 * self.playback_speed)), self.update_frame)
            else:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def toggle_play(self):
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.update_frame()

    def next_video(self):
        if self.video_files:
            self.current_video_index = (self.current_video_index + 1) % len(self.video_files)
            self.play_video()

    def prev_video(self):
        if self.video_files:
            self.current_video_index = (self.current_video_index - 1) % len(self.video_files)
            self.play_video()

    def change_speed(self, event):
        self.playback_speed = float(self.speed_var.get())

    def toggle_behavior(self, behavior):
        if self.current_behavior is None:
            self.current_behavior = behavior
            self.behavior_start_time = self.video_position.get()
            for btn_key, btn in self.behavior_buttons.items():
                if btn_key != behavior:
                    btn.config(state=tk.DISABLED)
        else:
            end_time = self.video_position.get()
            duration = end_time - self.behavior_start_time
            self.behavior_records.append(
                [self.tag_var.get(), behavior, self.behavior_start_time, end_time, duration]
            )
            self.current_behavior = None
            self.behavior_start_time = None
            for btn in self.behavior_buttons.values():
                btn.config(state=tk.NORMAL)
            self.update_records_display()

    def update_records_display(self):
        self.records_text.config(state=tk.NORMAL)
        self.records_text.delete(1.0, tk.END)
        for record in self.behavior_records:
            self.records_text.insert(
                tk.END,
                f"TAG: {record[0]} - {record[1]}: {record[2]:.2f}s - {record[3]:.2f}s (Duración: {record[4]:.2f}s)\n",
            )
        self.records_text.config(state=tk.DISABLED)

    def save_behavior_records(self):
        if self.video_files and self.behavior_records:
            video_name = self.video_files[self.current_video_index]
            csv_filename = f"{os.path.splitext(video_name)[0]}.csv"
            csv_path = os.path.join(self.video_dir, csv_filename)
            with open(csv_path, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Etiqueta", "Comportamiento", "Inicio", "Fin", "Duración"])
                writer.writerows(self.behavior_records)
        self.behavior_records = []
        self.update_records_display()

    def seek_video(self, _=None):
        if self.cap:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, self.video_position.get() * 1000)
            self.current_time_label.config(text=self.format_time(self.video_position.get()))

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02}:{seconds:02}"


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoLabelingApp(root)
    root.mainloop()
