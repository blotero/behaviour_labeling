import os
import queue
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any, Callable, cast

import cv2
from cv2.typing import MatLike
from PIL import Image, ImageTk

from .config import BEHAVIOR_DATA
from .frame_processor import (
    CommandQueueElement,
    FrameProcessor,
    FrameQueueElement,
)
from .record import BehaviorRecord, save_as_csv
from .types import GroupType, RecordType, Role, Sex
from .utils import format_time

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 720


def setup_behavior_tree(
    parent: ttk.Frame,
    data: dict[str, Any],
    toggler: Callable[[str, RecordType], None],
) -> None:
    """Create a tree view for behaviors with their types."""
    # Create the main tree view
    tree = ttk.Treeview(parent, selectmode="browse")
    tree.pack(fill="both", expand=True)

    # Add scrollbar
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    scrollbar.pack(side="right", fill="y")
    tree.configure(yscrollcommand=scrollbar.set)

    # Configure columns
    tree["columns"] = ("type",)
    tree.column("#0", width=400, minwidth=400)
    tree.column("type", width=100, minwidth=100)

    # Configure headings
    tree.heading("#0", text="Behavior")
    tree.heading("type", text="Type")

    # Bind double-click event
    tree.bind("<Double-1>", lambda e: on_tree_select(e, tree, toggler))

    # Add parent categories and their behaviors
    for parent_category, behaviors in data.items():
        # Create parent item
        parent_item = tree.insert("", "end", text=parent_category, values=("",))

        # Add behaviors under parent
        for behavior, record_type in behaviors.items():
            tree.insert(
                parent_item, "end", text=behavior, values=(record_type,)
            )


def on_tree_select(
    event: Any, tree: ttk.Treeview, toggler: Callable[[str, RecordType], None]
) -> None:
    """Handle selection of a behavior in the tree."""
    item = tree.selection()[0]
    behavior_path = get_full_path(tree, item)
    behavior_type: RecordType = cast(RecordType, tree.item(item)["values"][0])

    if behavior_type:  # Only handle leaf nodes (actual behaviors)
        print(f"Selected behavior: {behavior_path} ({behavior_type})")
        toggler(behavior_path, behavior_type)


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
        self.behavior_records: list[BehaviorRecord] = []
        self.behavior_buttons: dict[str, ttk.Button] = {}

        # Zoom-related attributes
        self.zoom_level = 1.0
        self.min_zoom = 0.25
        self.max_zoom = 4.0
        self.zoom_step = 0.25
        self.original_image: Image.Image | None = None

        # Video dimensions
        self.original_video_width = 0
        self.original_video_height = 0
        self.display_width = VIDEO_WIDTH
        self.display_height = VIDEO_HEIGHT

        # Variables for drag panning
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False

        # Threading related attributes
        self.frame_processor: FrameProcessor | None = None
        self.frame_queue: queue.Queue[FrameQueueElement] = queue.Queue(
            maxsize=10
        )
        self.command_queue: queue.Queue[CommandQueueElement] = queue.Queue()

        # For UI updates
        self.current_frame: MatLike | None = None
        self.photo_image: ImageTk.PhotoImage | None = None

        self.setup_ui()

        # Schedule frame updates
        self.root.after(10, self.check_frame_queue)

    def setup_behaviour_buttons(self, target_frame: ttk.Frame) -> None:
        setup_behavior_tree(
            target_frame,
            self.behaviors,
            toggler=self.toggle_behavior,
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

        self.video_label = ttk.Label(
            self.top_sub_frame, text="No hay video cargado"
        )
        self.video_label.pack()

        # Create a frame to hold the canvas and scrollbars
        self.canvas_frame = ttk.Frame(self.top_sub_frame)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create canvas with scrollbars
        self.canvas = tk.Canvas(
            self.canvas_frame,
            width=VIDEO_WIDTH,
            height=VIDEO_HEIGHT,
            scrollregion=(0, 0, VIDEO_WIDTH, VIDEO_HEIGHT),
        )

        # Create scrollbars
        self.h_scrollbar = ttk.Scrollbar(
            self.canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview
        )
        self.v_scrollbar = ttk.Scrollbar(
            self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview
        )

        # Configure canvas to work with scrollbars
        self.canvas.configure(
            xscrollcommand=self.h_scrollbar.set,
            yscrollcommand=self.v_scrollbar.set,
        )

        # Pack canvas and scrollbars
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")

        # Configure grid weights
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)

        # Bind mouse wheel to canvas for zooming
        self.canvas.bind("<Control-MouseWheel>", self.on_mouse_wheel_zoom)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel_scroll)

        # Bind mouse drag events for panning
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

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

        self.play_button = ttk.Button(
            self.controls_frame, text="▶", command=self.toggle_play
        )
        self.play_button.pack(side=tk.LEFT)

        self.prev_button = ttk.Button(
            self.controls_frame, text="⏮", command=self.prev_video
        )
        self.prev_button.pack(side=tk.LEFT)

        self.next_button = ttk.Button(
            self.controls_frame, text="⏭", command=self.next_video
        )
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

        # Add zoom controls
        ttk.Separator(self.controls_frame, orient="vertical").pack(
            side=tk.LEFT, fill=tk.Y, padx=5
        )

        self.zoom_out_button = ttk.Button(
            self.controls_frame, text="🔍−", command=self.zoom_out
        )
        self.zoom_out_button.pack(side=tk.LEFT, padx=2)

        self.zoom_level_label = ttk.Label(
            self.controls_frame, text="100%", width=5
        )
        self.zoom_level_label.pack(side=tk.LEFT, padx=2)

        self.zoom_in_button = ttk.Button(
            self.controls_frame, text="🔍+", command=self.zoom_in
        )
        self.zoom_in_button.pack(side=tk.LEFT, padx=2)

        self.zoom_reset_button = ttk.Button(
            self.controls_frame, text="🔍⌂", command=self.zoom_reset
        )
        self.zoom_reset_button.pack(side=tk.LEFT, padx=2)

        # Create secondary window for behavior controls and records
        self.secondary_window = tk.Toplevel(self.root)
        self.secondary_window.title("Comportamientos")

        # Create a frame for the behavior tree
        self.behavior_frame = ttk.Frame(self.secondary_window)
        self.behavior_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.setup_behaviour_buttons(self.behavior_frame)

        # Create a frame for the controls in secondary window
        self.secondary_controls_frame = ttk.Frame(self.secondary_window)
        self.secondary_controls_frame.pack(fill=tk.X, padx=10, pady=5)

        # Configure grid weights for flexible resizing
        self.secondary_controls_frame.grid_columnconfigure(1, weight=1)
        self.secondary_controls_frame.grid_columnconfigure(3, weight=1)
        self.secondary_controls_frame.grid_columnconfigure(5, weight=1)
        self.secondary_controls_frame.grid_columnconfigure(7, weight=1)
        self.secondary_controls_frame.grid_columnconfigure(
            9, weight=2
        )  # Observations gets more space

        # Tag controls - Row 0
        self.tag_var = tk.StringVar()
        self.tag_label = ttk.Label(
            self.secondary_controls_frame, text="Etiqueta: "
        )
        self.tag_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 5), pady=2)

        self.tag_entry = ttk.Entry(
            self.secondary_controls_frame, textvariable=self.tag_var
        )
        self.tag_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 10), pady=2)

        # Role selector - Row 0
        self.role_var = tk.StringVar()
        self.role_label = ttk.Label(self.secondary_controls_frame, text="Rol: ")
        self.role_label.grid(row=0, column=2, sticky=tk.W, padx=(0, 5), pady=2)

        self.role_selector = ttk.Combobox(
            self.secondary_controls_frame,
            textvariable=self.role_var,
            values=[
                "madre",
                "cria",
                "escolta",
                "macho",
                "hembra",
                "macho-reproductor",
                "indefinido",
            ],
            state="readonly",
        )
        self.role_selector.grid(
            row=0, column=3, sticky=tk.EW, padx=(0, 10), pady=2
        )

        # Group type selector - Row 1
        self.group_type_var = tk.StringVar()
        self.group_type_label = ttk.Label(
            self.secondary_controls_frame, text="Tipo: "
        )
        self.group_type_label.grid(
            row=1, column=0, sticky=tk.W, padx=(0, 5), pady=2
        )

        self.group_type_selector = ttk.Combobox(
            self.secondary_controls_frame,
            textvariable=self.group_type_var,
            values=[
                "individual",
                "grupal",
            ],
            state="readonly",
        )
        self.group_type_selector.grid(
            row=1, column=1, sticky=tk.EW, padx=(0, 10), pady=2
        )

        # Sex selector - Row 1
        self.sex_var = tk.StringVar()
        self.sex_label = ttk.Label(self.secondary_controls_frame, text="Sexo: ")
        self.sex_label.grid(row=1, column=2, sticky=tk.W, padx=(0, 5), pady=2)

        self.sex_selector = ttk.Combobox(
            self.secondary_controls_frame,
            textvariable=self.sex_var,
            values=[
                "macho",
                "hembra",
                "indefinido",
            ],
            state="readonly",
        )
        self.sex_selector.grid(
            row=1, column=3, sticky=tk.EW, padx=(0, 10), pady=2
        )

        # Group size spinner - Row 1
        self.group_size_var = tk.StringVar()
        self.group_size_label = ttk.Label(
            self.secondary_controls_frame, text="Tamaño grupal: "
        )
        self.group_size_label.grid(
            row=1, column=4, sticky=tk.W, padx=(0, 5), pady=2
        )

        self.group_size_spinner = ttk.Spinbox(
            self.secondary_controls_frame,
            textvariable=self.group_size_var,
            from_=1,
            to=100,
            width=10,
            state="normal",
        )
        self.group_size_spinner.grid(
            row=1, column=5, sticky=tk.EW, padx=(0, 10), pady=2
        )

        # Observations text box - Row 2 (spans multiple columns)
        self.observations_label = ttk.Label(
            self.secondary_controls_frame, text="Observaciones: "
        )
        self.observations_label.grid(
            row=2, column=0, sticky=tk.W, padx=(0, 5), pady=2
        )

        self.observations_entry = ttk.Entry(self.secondary_controls_frame)
        self.observations_entry.grid(
            row=2, column=1, columnspan=5, sticky=tk.EW, padx=(0, 10), pady=2
        )

        # State feedback label - Row 3
        self.state_feedback_label = ttk.Label(
            self.secondary_controls_frame,
            text="",
            font=("TkDefaultFont", 10, "normal"),
            foreground="gray",
        )
        self.state_feedback_label.grid(
            row=3, column=0, columnspan=6, sticky=tk.W, padx=(0, 10), pady=5
        )

        # Save button - Row 2
        self.save_button = ttk.Button(
            self.secondary_controls_frame,
            text="Guardar Registros💾",
            command=self.save_behavior_records,
        )
        self.save_button.grid(
            row=2, column=6, sticky=tk.E, padx=(10, 0), pady=2
        )

        # Create a frame for records in secondary window
        self.secondary_records_frame = ttk.LabelFrame(
            self.secondary_window, text="Registros de comportamiento"
        )
        self.secondary_records_frame.pack(
            fill=tk.BOTH, expand=True, padx=10, pady=5
        )

        # Create a canvas with scrollbar for records
        self.records_canvas = tk.Canvas(self.secondary_records_frame)
        self.records_scrollbar = ttk.Scrollbar(
            self.secondary_records_frame,
            orient="vertical",
            command=self.records_canvas.yview,
        )
        self.records_scrollable_frame = ttk.Frame(self.records_canvas)

        self.records_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.records_canvas.configure(
                scrollregion=self.records_canvas.bbox("all")
            ),
        )

        self.records_canvas.create_window(
            (0, 0), window=self.records_scrollable_frame, anchor="nw"
        )
        self.records_canvas.configure(yscrollcommand=self.records_scrollbar.set)

        # Pack the canvas and scrollbar
        self.records_canvas.pack(side="left", fill="both", expand=True)
        self.records_scrollbar.pack(side="right", fill="y")

        # Bind mouse wheel to canvas
        self.records_canvas.bind("<Enter>", self._bind_mouse_wheel)
        self.records_canvas.bind("<Leave>", self._unbind_mouse_wheel)

        # Store record frames for easy cleanup
        self.record_frames: list[ttk.Frame] = []

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

                    # Convert to PIL Image (this is now full resolution)
                    pil_image = Image.fromarray(frame)
                    self.original_image = pil_image

                    # Calculate the display size based on zoom level
                    # At zoom level 1.0, we want to fit the video to display size
                    # At higher zoom levels, we want to show more detail from original

                    if self.zoom_level <= 1.0:
                        # When zoomed out or at 1.0, scale to fit display area
                        scale_factor = (
                            min(
                                self.display_width / pil_image.width,
                                self.display_height / pil_image.height,
                            )
                            * self.zoom_level
                        )
                    else:
                        # When zoomed in, calculate scale to show original detail
                        # Base scale to fit display, then multiply by zoom
                        base_scale = min(
                            self.display_width / pil_image.width,
                            self.display_height / pil_image.height,
                        )
                        scale_factor = base_scale * self.zoom_level

                    # Calculate final dimensions
                    final_width = int(pil_image.width * scale_factor)
                    final_height = int(pil_image.height * scale_factor)

                    # Resize the image
                    if scale_factor != 1.0:
                        pil_image = pil_image.resize(
                            (final_width, final_height),
                            Image.Resampling.LANCZOS,
                        )

                    # Convert back to PhotoImage
                    self.photo_image = ImageTk.PhotoImage(pil_image)

                    # Update canvas
                    self.canvas.delete("all")
                    self.canvas.create_image(
                        0, 0, anchor=tk.NW, image=self.photo_image
                    )

                    # Update scroll region
                    self.canvas.configure(
                        scrollregion=(0, 0, pil_image.width, pil_image.height)
                    )

                    # Update the time display and slider
                    current_time = message["position"]
                    self.video_position.set(current_time)
                    self.current_time_label.config(
                        text=format_time(current_time)
                    )

                elif message["type"] == "metadata":
                    # Update video duration and slider
                    self.video_duration = message["duration"]
                    self.time_slider.config(to=self.video_duration)
                    self.total_time_label.config(
                        text=format_time(self.video_duration)
                    )

                    # Store original video dimensions
                    if (
                        "original_width" in message
                        and "original_height" in message
                    ):
                        self.original_video_width = message["original_width"]
                        self.original_video_height = message["original_height"]
                        self.update_video_label()

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
                [
                    f
                    for f in os.listdir(self.video_dir)
                    if f.lower().endswith(".mp4")
                ]
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
            video_path = os.path.join(
                self.video_dir, self.video_files[self.current_video_index]
            )

            # Start the frame processor
            self.frame_processor = FrameProcessor(
                video_path,
                self.frame_queue,
                self.command_queue,
                VIDEO_WIDTH,
                VIDEO_HEIGHT,
            )
            self.frame_processor.start()

            self.is_playing = True
            self.behavior_records = []
            self.update_records_display()

            # Clear any active state
            self.current_behavior = None
            self.behavior_start_time = None
            self.state_feedback_label.config(
                text="", font=("TkDefaultFont", 10, "normal"), foreground="gray"
            )

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
                self.trigger_play_video()
            else:
                self.trigger_pause_video()

    def next_video(self) -> None:
        if self.video_files:
            self.current_video_index = (self.current_video_index + 1) % len(
                self.video_files
            )
            self.play_video()

    def prev_video(self) -> None:
        if self.video_files:
            self.current_video_index = (self.current_video_index - 1) % len(
                self.video_files
            )
            self.play_video()

    def change_speed(self, _: Any) -> None:
        self.playback_speed = float(self.speed_var.get())
        if self.frame_processor and self.frame_processor.is_alive():
            self.command_queue.put(
                {"type": "speed", "value": self.playback_speed}
            )

    def toggle_behavior(
        self, embedded_behavior: str, record_type: RecordType
    ) -> None:
        [parent, behavior] = embedded_behavior.split("/")[:2]

        # Get the current values from the selectors or default values
        current_role = (
            self.role_var.get() if self.role_var.get() else "indefinido"
        )
        current_group_type = (
            self.group_type_var.get()
            if self.group_type_var.get()
            else "individual"
        )
        current_sex = self.sex_var.get() if self.sex_var.get() else "indefinido"
        current_observations = self.observations_entry.get()

        # Get group size value, convert to int if not empty, otherwise None
        group_size_str = self.group_size_var.get()
        current_group_size = None
        if group_size_str.strip():
            try:
                current_group_size = int(group_size_str)
            except ValueError:
                # If conversion fails, keep as None
                pass

        match record_type:
            case "EVENT":
                self.behavior_records.append(
                    BehaviorRecord(
                        session=1,
                        role=cast(Role, current_role),
                        behaviour=behavior,
                        parent_behaviour=parent,
                        start_time=self.video_position.get(),
                        duration=0,
                        record_type=record_type,
                        tag=self.tag_var.get(),
                        group_type=cast(GroupType, current_group_type),
                        sex=cast(Sex, current_sex),
                        observations=current_observations
                        if current_observations
                        else None,
                        group_size=current_group_size,
                    )
                )
                self.update_records_display()
            case "STATE":
                if self.current_behavior is None:
                    # Starting a new state
                    self.current_behavior = behavior
                    self.behavior_start_time = self.video_position.get()

                    # Show state feedback label
                    self.state_feedback_label.config(
                        text=f"🔄 Estado activo: {behavior}",
                        font=("TkDefaultFont", 10, "bold"),
                        foreground="green",
                    )

                    for btn_key, btn in self.behavior_buttons.items():
                        if btn_key != behavior:
                            btn.config(state=tk.DISABLED)
                else:
                    # Ending the current state
                    if self.behavior_start_time is None:
                        raise ValueError("Behavior start time is None")
                    end_time = self.video_position.get()
                    duration = end_time - self.behavior_start_time
                    self.behavior_records.append(
                        BehaviorRecord(
                            session=1,
                            role=cast(Role, current_role),
                            behaviour=self.current_behavior,
                            parent_behaviour=parent,
                            start_time=self.behavior_start_time,
                            end_time=end_time,
                            duration=duration,
                            record_type=record_type,
                            tag=self.tag_var.get(),
                            group_type=cast(GroupType, current_group_type),
                            sex=cast(Sex, current_sex),
                            observations=current_observations
                            if current_observations
                            else None,
                            group_size=current_group_size,
                        )
                    )
                    self.current_behavior = None
                    self.behavior_start_time = None

                    # Hide state feedback label
                    self.state_feedback_label.config(
                        text="",
                        font=("TkDefaultFont", 10, "normal"),
                        foreground="gray",
                    )

                    for btn in self.behavior_buttons.values():
                        btn.config(state=tk.NORMAL)
                    self.update_records_display()

    def update_records_display(self) -> None:
        # Clear existing record frames
        for frame in self.record_frames:
            frame.destroy()
        self.record_frames.clear()

        # Create new record entries
        for i, record in enumerate(self.behavior_records):
            # Create a frame for this record
            record_frame = ttk.Frame(self.records_scrollable_frame)
            record_frame.pack(fill=tk.X, padx=5, pady=2)
            self.record_frames.append(record_frame)

            # Create label for record text
            record_label = ttk.Label(
                record_frame,
                text=f">>> {record.as_str()}",
                wraplength=400,
                justify=tk.LEFT,
            )
            record_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Create delete button
            delete_button = ttk.Button(
                record_frame,
                text="🗑️",
                width=3,
                command=lambda idx=i: self.delete_record(idx),  # type: ignore
            )
            delete_button.pack(side=tk.RIGHT, padx=(5, 0))

        # Update canvas scroll region
        self.records_canvas.update_idletasks()
        self.records_canvas.configure(
            scrollregion=self.records_canvas.bbox("all")
        )

    def save_behavior_records(self) -> None:
        save_as_csv(
            self.video_files,
            self.current_video_index,
            self.video_dir,
            self.behavior_records,
        )
        self.behavior_records = []
        self.update_records_display()

    def update_time_label(self, event: str) -> None:
        self.trigger_pause_video()
        self.current_time_label.config(
            text=format_time(self.video_position.get())
        )

    def slider_released(self, event: Any) -> None:
        if self.frame_processor and self.frame_processor.is_alive():
            print(f"Seeking to {self.video_position.get()}")
            self.command_queue.put(
                {"type": "seek", "position": self.video_position.get()}
            )

    def _bind_mouse_wheel(self, event: Any) -> None:
        def _on_mouse_wheel(event: Any) -> None:
            self.records_canvas.yview_scroll(
                int(-1 * (event.delta / 120)), "units"
            )

        self.records_canvas.bind_all("<MouseWheel>", _on_mouse_wheel)

    def _unbind_mouse_wheel(self, event: Any) -> None:
        self.records_canvas.unbind_all("<MouseWheel>")

    def delete_record(self, record_index: int) -> None:
        """Delete a record at the specified index."""
        if 0 <= record_index < len(self.behavior_records):
            del self.behavior_records[record_index]
            self.update_records_display()

    def on_mouse_wheel_zoom(self, event: Any) -> None:
        """Handle Ctrl+MouseWheel for zooming."""
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def on_mouse_wheel_scroll(self, event: Any) -> None:
        """Handle MouseWheel for scrolling."""
        # Scroll vertically by default
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def zoom_out(self) -> None:
        self.zoom_level = max(self.min_zoom, self.zoom_level - self.zoom_step)
        self.update_zoom_level()

    def zoom_in(self) -> None:
        self.zoom_level = min(self.max_zoom, self.zoom_level + self.zoom_step)
        self.update_zoom_level()

    def zoom_reset(self) -> None:
        self.zoom_level = 1.0
        self.update_zoom_level()

    def update_zoom_level(self) -> None:
        """Update zoom level display and refresh current frame."""
        self.zoom_level_label.config(text=f"{int(self.zoom_level * 100)}%")

        # Refresh current frame with new zoom level
        if self.original_image is not None:
            pil_image = self.original_image.copy()

            # Use the same scaling logic as check_frame_queue
            if self.zoom_level <= 1.0:
                # When zoomed out or at 1.0, scale to fit display area
                scale_factor = (
                    min(
                        self.display_width / pil_image.width,
                        self.display_height / pil_image.height,
                    )
                    * self.zoom_level
                )
            else:
                # When zoomed in, calculate scale to show original detail
                # Base scale to fit display, then multiply by zoom
                base_scale = min(
                    self.display_width / pil_image.width,
                    self.display_height / pil_image.height,
                )
                scale_factor = base_scale * self.zoom_level

            # Calculate final dimensions
            final_width = int(pil_image.width * scale_factor)
            final_height = int(pil_image.height * scale_factor)

            # Resize the image
            if scale_factor != 1.0:
                pil_image = pil_image.resize(
                    (final_width, final_height), Image.Resampling.LANCZOS
                )

            # Convert back to PhotoImage
            self.photo_image = ImageTk.PhotoImage(pil_image)

            # Update canvas
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)

            # Update scroll region
            self.canvas.configure(
                scrollregion=(0, 0, pil_image.width, pil_image.height)
            )

    def on_canvas_click(self, event: Any) -> None:
        """Start dragging operation."""
        self.drag_start_x = self.canvas.canvasx(event.x)
        self.drag_start_y = self.canvas.canvasy(event.y)
        self.is_dragging = True
        # Change cursor to indicate dragging mode
        self.canvas.config(cursor="fleur")

    def on_canvas_drag(self, event: Any) -> None:
        """Handle canvas dragging for panning."""
        if self.is_dragging and self.zoom_level > 1.0:
            current_x = self.canvas.canvasx(event.x)
            current_y = self.canvas.canvasy(event.y)

            dx = -(current_x - self.drag_start_x)
            dy = -(current_y - self.drag_start_y)

            # Get current scroll position
            scroll_x = self.canvas.canvasx(0)
            scroll_y = self.canvas.canvasy(0)

            # Calculate new scroll position
            new_x = scroll_x + dx
            new_y = scroll_y + dy

            # Get scroll region bounds
            scroll_region = self.canvas.cget("scrollregion").split()
            if len(scroll_region) == 4:
                min_x, min_y, max_x, max_y = map(float, scroll_region)
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()

                # Constrain scrolling within bounds
                new_x = max(min_x, min(new_x, max_x - canvas_width))
                new_y = max(min_y, min(new_y, max_y - canvas_height))

                # Apply scrolling
                self.canvas.xview_moveto(new_x / max_x if max_x > 0 else 0)
                self.canvas.yview_moveto(new_y / max_y if max_y > 0 else 0)

            self.drag_start_x = current_x
            self.drag_start_y = current_y

    def on_canvas_release(self, event: Any) -> None:
        """End dragging operation."""
        self.is_dragging = False
        # Reset cursor
        self.canvas.config(cursor="")

    def update_video_label(self) -> None:
        if self.video_files and self.current_video_index < len(
            self.video_files
        ):
            composed_text = (
                f"{self.video_files[self.current_video_index]}"
                f" ({self.original_video_width}x{self.original_video_height})"
            )
            self.video_label.config(text=composed_text)
