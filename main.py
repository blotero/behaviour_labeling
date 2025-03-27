import csv
import os
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, ttk
from typing import Any, Callable, Literal

import cv2
from PIL import Image, ImageTk

from config import BEHAVIOR_DATA, RecordType, get_recursive_parents

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 720

type Role = Literal["Indiv", "escolta", "cría", "mamá", "mamá - cría", "Adulto - adulto", "Grupo"]


@dataclass(frozen=True)
class BehaviourRecord:
    session: int
    role: Role
    behaviour: str
    parent_behaviour: str
    grand_father_behaviour: str
    start_time: float
    duration: float
    record_type: RecordType
    tag: str
    end_time: float | None = None
    observations: str | None = None

    def as_str(self) -> str:
        return (
            f"Rol: {self.role} - Comportamiento: {self.behaviour}: {self.start_time:.2f}s"
            f" - {self.end_time:.2f}s (Duración: {self.duration:.2f}s) - Tag:{self.tag} "
        )


def recursive_setup_buttons(
    data: dict[str, Any],
    parent_frame: ttk.Frame,
    behavior_buttons: dict[str, ttk.Button],
    toggle_behavior: Callable[[str, RecordType], None],
) -> None:
    for key, value in data.items():
        if isinstance(value, dict):
            frame = ttk.LabelFrame(parent_frame, text=key, width=30)
            frame.pack(side=tk.TOP, padx=5, pady=2, anchor="w")
            recursive_setup_buttons(value, frame, behavior_buttons, toggle_behavior)
        else:
            record_type = value
            btn = ttk.Button(
                parent_frame,
                text=key,
                command=lambda k=key: toggle_behavior(k, record_type),
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            behavior_buttons[key] = btn  # Store reference


class VideoLabelingApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Herramienta de Etiquetado de Comportamientos")

        self.behaviors = BEHAVIOR_DATA

        self.video_dir = ""
        self.video_files: list[str] = []
        self.current_video_index = 0
        self.cap = None
        self.is_playing = False
        self.playback_speed = 1.0
        self.current_behavior: str | None = None
        self.behavior_start_time: float | None = None
        self.video_duration = 0
        self.video_position = tk.DoubleVar()
        self.behavior_records: list[BehaviourRecord] = []
        self.behavior_buttons: dict[str, Any] = {}

        self.setup_ui()

    def setup_behaviour_buttons(self, target_frame: ttk.Frame) -> None:
        recursive_setup_buttons(
            self.behaviors, target_frame, self.behavior_buttons, self.toggle_behavior
        )

    def setup_ui(self) -> None:
        self.top_frame = ttk.Frame(self.root)
        self.top_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.top_sub_frame = ttk.Frame(self.top_frame)
        self.top_sub_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.load_button = ttk.Button(
            self.top_sub_frame, text="Cargar Videos", command=self.load_videos
        )
        self.load_button.pack()

        self.video_label = ttk.Label(self.top_sub_frame, text="No hay video cargado")
        self.video_label.pack()

        self.canvas = tk.Canvas(self.top_sub_frame, width=VIDEO_WIDTH, height=VIDEO_HEIGHT)
        self.canvas.pack(side=tk.LEFT)

        self.records_frame = ttk.LabelFrame(
            self.top_sub_frame, text="Registros de comportamiento", width=50
        )
        self.records_frame.pack(side=tk.LEFT, fill=tk.BOTH)

        self.time_frame = ttk.Frame(self.top_frame)
        self.time_frame.pack(fill=tk.X, padx=10)

        self.current_time_label = ttk.Label(self.time_frame, text="00:00")
        self.current_time_label.pack(side=tk.LEFT)

        self.time_slider = ttk.Scale(
            self.top_frame,
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
        # role selector
        self.role_var = tk.StringVar()
        self.role_label = ttk.Label(self.controls_frame, text="Rol: ")
        self.role_label.pack(side=tk.LEFT)

        self.role_selector = ttk.Combobox(
            self.controls_frame,
            textvariable=self.role_var,
            values=["Indiv", "escolta", "cría", "mamá", "mamá - cría", "Adulto - adulto", "Grupo"],
            state="readonly",
        )
        self.role_selector.pack(side=tk.LEFT)

        self.save_button = ttk.Button(
            self.controls_frame, text="Guardar Registros💾", command=self.save_behavior_records
        )
        self.save_button.pack(side=tk.LEFT)

        self.records_text = tk.Text(self.records_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.records_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(self.records_frame, command=self.records_text.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.records_text.config(yscrollcommand=self.scrollbar.set)

        self.behaviour_window = tk.Toplevel(self.root)
        self.behaviour_window.title("Comportamientos")

        self.behavior_frame = ttk.Frame(self.behaviour_window)
        self.behavior_frame.pack()

        self.setup_behaviour_buttons(self.behavior_frame)

    def load_videos(self) -> None:
        self.video_dir = filedialog.askdirectory()
        if self.video_dir:
            self.video_files = sorted(
                [f for f in os.listdir(self.video_dir) if f.lower().endswith(".mp4")]
            )
            self.current_video_index = 0
            self.play_video()

    def play_video(self) -> None:
        if self.cap:
            self.cap.release()
        if self.video_files:
            video_path = os.path.join(self.video_dir, self.video_files[self.current_video_index])
            self.video_label.config(text=self.video_files[self.current_video_index])
            self.cap = cv2.VideoCapture(video_path)
            self.video_duration = (
                self.cap.get(cv2.CAP_PROP_FRAME_COUNT) / self.cap.get(cv2.CAP_PROP_FPS)
                if self.cap.get(cv2.CAP_PROP_FPS) != 0
                else 0
            )
            self.time_slider.config(to=self.video_duration)
            self.total_time_label.config(text=self.format_time(self.video_duration))
            self.is_playing = True
            self.behavior_records = []
            self.update_frame()
            self.update_records_display()

    def update_frame(self) -> None:
        if self.cap and self.is_playing:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (VIDEO_WIDTH, VIDEO_HEIGHT))
                img = ImageTk.PhotoImage(Image.fromarray(frame))
                self.canvas.create_image(0, 0, anchor=tk.NW, image=img)
                self.canvas.image = img
                current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                self.video_position.set(current_time)
                self.current_time_label.config(text=self.format_time(current_time))
                self.root.after(int(1000 // (30 * self.playback_speed)), self.update_frame)
            else:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def toggle_play(self) -> None:
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.update_frame()

    def next_video(self) -> None:
        if self.video_files:
            self.current_video_index = (self.current_video_index + 1) % len(self.video_files)
            self.play_video()

    def prev_video(self) -> None:
        if self.video_files:
            self.current_video_index = (self.current_video_index - 1) % len(self.video_files)
            self.play_video()

    def change_speed(self, _: Any) -> None:
        self.playback_speed = float(self.speed_var.get())

    def toggle_behavior(self, behavior: str, record_type: RecordType) -> None:
        [parent, grand_father] = get_recursive_parents(behavior, self.behaviors)
        match record_type:
            case "EVENT":
                self.behavior_records.append(
                    BehaviourRecord(
                        session=1,
                        role="Indiv",
                        behaviour=behavior,
                        parent_behaviour=parent,
                        grand_father_behaviour=grand_father,
                        start_time=self.video_position.get(),
                        duration=0,
                        record_type=record_type,
                        tag=self.tag_var.get(),
                    )
                )
                self.update_records_display()
            case "STATE":
                if self.current_behavior is None:
                    self.current_behavior = behavior
                    self.behavior_start_time = self.video_position.get()
                    for btn_key, btn in self.behavior_buttons.items():
                        if btn_key != behavior:
                            btn.config(state=tk.DISABLED)
                else:
                    end_time = self.video_position.get()
                    duration = end_time - self.behavior_start_time
                    if self.behavior_start_time is None:
                        raise ValueError("Behavior start time is None")
                    self.behavior_records.append(
                        BehaviourRecord(
                            session=1,
                            role="Indiv",
                            behaviour=self.current_behavior,
                            parent_behaviour=parent,
                            grand_father_behaviour=grand_father,
                            start_time=self.behavior_start_time,
                            end_time=end_time,
                            duration=duration,
                            record_type=record_type,
                            tag=self.tag_var.get(),
                        )
                    )
                    self.current_behavior = None
                    self.behavior_start_time = None
                    for btn in self.behavior_buttons.values():
                        btn.config(state=tk.NORMAL)
                    self.update_records_display()

    def update_records_display(self) -> None:
        self.records_text.config(state=tk.NORMAL)
        self.records_text.delete(1.0, tk.END)
        for record in self.behavior_records:
            self.records_text.insert(
                tk.END,
                ">>> " + record.as_str() + "\n\n",
            )
        self.records_text.config(state=tk.DISABLED)

    def save_behavior_records(self) -> None:
        if self.video_files and self.behavior_records:
            video_name = self.video_files[self.current_video_index]
            csv_filename = f"{os.path.splitext(video_name)[0]}.csv"
            csv_path = os.path.join(self.video_dir, csv_filename)
            with open(csv_path, "w", newline="", encoding="utf-8") as file:
                fieldnames = BehaviourRecord.__annotations__.keys()
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for record in self.behavior_records:
                    writer.writerow(record.__dict__)
        self.behavior_records = []
        self.update_records_display()

    def seek_video(self, event: str) -> None:
        if self.cap:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, self.video_position.get() * 1000)
            self.current_time_label.config(text=self.format_time(self.video_position.get()))

    def format_time(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02}:{seconds:02}"


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoLabelingApp(root)
    root.mainloop()
