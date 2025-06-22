import csv
import os
import queue
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, ttk
from typing import Any, Literal, cast

import cv2
from cv2.typing import MatLike
from PIL import Image, ImageTk

from .config import BEHAVIOR_DATA, RecordType, get_recursive_parents
from .frame_processor import CommandQueueElement, FrameProcessor, FrameQueueElement

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
    parent: ttk.Frame,
    data: dict[str, Any],
    parent_path: str = "",
    tree: ttk.Treeview | None = None,
    parent_item: str = "",
) -> None:
    """Recursively create buttons for each behavior in the data dictionary."""
    if tree is None:
        # Create the main tree view
        tree = ttk.Treeview(parent, selectmode="browse")
        tree.pack(fill="both", expand=True)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)

        # Configure columns
        tree["columns"] = ("type",)
        tree.column("#0", width=200, minwidth=200)
        tree.column("type", width=100, minwidth=100)

        # Configure headings
        tree.heading("#0", text="Behavior")
        tree.heading("type", text="Type")

        # Bind double-click event
        tree.bind("<Double-1>", lambda e: on_tree_select(e, tree))

    for key, value in data.items():
        current_path = f"{parent_path}/{key}" if parent_path else key

        if isinstance(value, dict):
            # Create parent item
            item = tree.insert(parent_item, "end", text=key, values=("",))
            # Recursively add children
            recursive_setup_buttons(parent, value, current_path, tree, item)
        else:
            # Create leaf item with behavior type
            tree.insert(parent_item, "end", text=key, values=(value,))


def on_tree_select(event: tk.Event, tree: ttk.Treeview) -> None:
    """Handle selection of a behavior in the tree."""
    item = tree.selection()[0]
    behavior_path = get_full_path(tree, item)
    behavior_type = tree.item(item)["values"][0]

    if behavior_type:  # Only handle leaf nodes (actual behaviors)
        print(f"Selected behavior: {behavior_path} ({behavior_type})")
        # Add your behavior selection handling here


def get_full_path(tree: ttk.Treeview, item: str) -> str:
    """Get the full path of a tree item."""
    path: list[str] = []
    while item:
        path.append(tree.item(item)["text"])
        item = tree.parent(item)
    return "/".join(reversed(path))


class VideoLabelingApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Herramienta de Etiquetado de Comportamientos")

        self.behaviors = BEHAVIOR_DATA

        self.video_dir = ""
        self.video_files: list[str] = []
        self.current_video_index = 0
        self.is_playing = False
        self.playback_speed = 1.0
        self.current_behavior: str | None = None
        self.behavior_start_time: float | None = None
        self.video_duration = 0.0
        self.video_position = tk.DoubleVar()
        self.behavior_records: list[BehaviourRecord] = []
        self.behavior_buttons: dict[str, ttk.Button] = {}

        # Threading related attributes
        self.frame_processor: FrameProcessor | None = None
        self.frame_queue: queue.Queue[FrameQueueElement] = queue.Queue(maxsize=10)
        self.command_queue: queue.Queue[CommandQueueElement] = queue.Queue()

        # For UI updates
        self.current_frame: MatLike | None = None
        self.photo_image: ImageTk.PhotoImage | None = None

        self.setup_ui()

        # Schedule frame updates
        self.root.after(10, self.check_frame_queue)

    def setup_behaviour_buttons(self, target_frame: ttk.Frame) -> None:
        recursive_setup_buttons(target_frame, self.behaviors)

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
            command=self.update_time_label,  # Just update the label during dragging
        )
        self.time_slider.bind("<ButtonRelease-1>", self.slider_released)
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

        self.speed_var = tk.StringVar(value="1.0")
        self.speed_menu = ttk.Combobox(
            self.controls_frame,
            textvariable=self.speed_var,
            values=["0.5", "0.75", "1.0", "1.25", "1.5", "2.0"],
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

        # Ensure proper cleanup when the app is closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self) -> None:
        # Stop the frame processor thread if it's running
        if self.frame_processor and self.frame_processor.is_alive():
            self.command_queue.put({"type": "stop"})
            # Give thread time to clean up
            self.frame_processor.join(timeout=1.0)
        self.root.destroy()

    def check_frame_queue(self) -> None:
        try:
            if not self.frame_queue.empty():
                message = self.frame_queue.get_nowait()

                if message["type"] == "frame":
                    # Update the frame on the canvas
                    frame = message["data"]
                    self.current_frame = frame
                    self.photo_image = ImageTk.PhotoImage(Image.fromarray(frame))
                    self.canvas.delete("all")
                    self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)

                    # Update the time display and slider
                    current_time = message["position"]
                    self.video_position.set(current_time)
                    self.current_time_label.config(text=self.format_time(current_time))

                elif message["type"] == "metadata":
                    # Update video duration and slider
                    self.video_duration = message["duration"]
                    self.time_slider.config(to=self.video_duration)
                    self.total_time_label.config(text=self.format_time(self.video_duration))

                elif message["type"] == "eof":
                    # Reached end of file, could handle specially if needed
                    pass
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error processing frame: {e}")

        # Schedule the next check
        self.root.after(10, self.check_frame_queue)

    def load_videos(self) -> None:
        self.video_dir = filedialog.askdirectory()
        if self.video_dir:
            self.video_files = sorted(
                [f for f in os.listdir(self.video_dir) if f.lower().endswith(".mp4")]
            )
            self.current_video_index = 0
            self.play_video()

    def play_video(self) -> None:
        # Stop existing frame processor if running
        if self.frame_processor and self.frame_processor.is_alive():
            self.command_queue.put({"type": "stop"})
            self.frame_processor.join(timeout=1.0)

        # Clear the queues
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
            except queue.Empty:
                break

        if self.video_files:
            video_path = os.path.join(self.video_dir, self.video_files[self.current_video_index])

            # Start the frame processor
            self.frame_processor = FrameProcessor(
                video_path, self.frame_queue, self.command_queue, VIDEO_WIDTH, VIDEO_HEIGHT
            )
            self.frame_processor.start()

            self.is_playing = True
            self.behavior_records = []
            self.update_records_display()

            composed_text = (
                f"{self.video_files[self.current_video_index]}"
                f" ({self.frame_processor.cap.get(cv2.CAP_PROP_FRAME_WIDTH):.0f}x"
                f"{self.frame_processor.cap.get(cv2.CAP_PROP_FRAME_HEIGHT):.0f})"
            )
            self.video_label.config(text=composed_text)

    def trigger_play_video(self) -> None:
        self.command_queue.put({"type": "play"})
        self.play_button.config(text="⏸")

    def trigger_pause_video(self) -> None:
        self.command_queue.put({"type": "pause"})
        self.play_button.config(text="▶")

    def toggle_play(self) -> None:
        self.is_playing = not self.is_playing
        if self.frame_processor and self.frame_processor.is_alive():
            if self.is_playing:
                self.play_video()
            else:
                self.trigger_pause_video()

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
        if self.frame_processor and self.frame_processor.is_alive():
            self.command_queue.put({"type": "speed", "value": self.playback_speed})

    def toggle_behavior(self, behavior: str, record_type: RecordType) -> None:
        [parent, grand_father] = get_recursive_parents(behavior, self.behaviors)

        # Get the current role from the selector or default to "Indiv"
        current_role = self.role_var.get() if self.role_var.get() else "Indiv"

        match record_type:
            case "EVENT":
                self.behavior_records.append(
                    BehaviourRecord(
                        session=1,
                        role=cast(Role, current_role),
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
                    if self.behavior_start_time is None:
                        raise ValueError("Behavior start time is None")
                    end_time = self.video_position.get()
                    duration = end_time - self.behavior_start_time
                    self.behavior_records.append(
                        BehaviourRecord(
                            session=1,
                            role=cast(Role, current_role),
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

    def update_time_label(self, event: str) -> None:
        self.trigger_pause_video()
        self.current_time_label.config(text=self.format_time(self.video_position.get()))

    def slider_released(self, event: tk.Event) -> None:
        if self.frame_processor and self.frame_processor.is_alive():
            print(f"Seeking to {self.video_position.get()}")
            self.command_queue.put({"type": "seek", "position": self.video_position.get()})

    def format_time(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02}:{seconds:02}"
