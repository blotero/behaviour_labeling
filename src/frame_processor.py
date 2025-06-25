import queue
import threading
import time
from typing import Literal, NotRequired, TypedDict

import cv2
from cv2.typing import MatLike

MAX_QUEUE_SIZE = 5


class FrameQueueElement(TypedDict):
    data: NotRequired[MatLike]
    duration: NotRequired[float]
    fps: NotRequired[float]
    position: NotRequired[float]
    original_width: NotRequired[int]
    original_height: NotRequired[int]
    type: Literal["metadata", "frame", "eof"]


class CommandQueueElement(TypedDict):
    type: Literal["stop", "pause", "play", "seek", "speed"]
    value: NotRequired[float]
    position: NotRequired[float]


class FrameProcessor(threading.Thread):
    def __init__(
        self,
        video_path: str,
        frame_queue: queue.Queue[FrameQueueElement],
        command_queue: queue.Queue[CommandQueueElement],
        width: int,
        height: int,
    ) -> None:
        threading.Thread.__init__(self, daemon=True)
        self.video_path = video_path
        self.frame_queue = frame_queue
        self.command_queue = command_queue
        self.width = width
        self.height = height
        self.running = True
        self.paused = False
        self.cap: cv2.VideoCapture = cv2.VideoCapture(self.video_path)
        self.playback_speed = 1.0
        self.current_position = 0.0
        self.total_frames = 0
        self.fps = 0

    def run(self) -> None:
        self.cap = cv2.VideoCapture(self.video_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Get original video dimensions
        original_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        original_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Send initial metadata to the main thread
        self.frame_queue.put(
            {
                "type": "metadata",
                "duration": self.total_frames / self.fps if self.fps > 0 else 0,
                "fps": self.fps,
                "original_width": original_width,
                "original_height": original_height,
            }
        )

        last_frame_time = time.time()

        while self.running:
            # Check for commands
            try:
                cmd = self.command_queue.get_nowait()
                if cmd["type"] == "stop":
                    self.running = False
                elif cmd["type"] == "pause":
                    self.paused = True
                elif cmd["type"] == "play":
                    self.paused = False
                elif cmd["type"] == "seek":
                    position = cmd["position"]
                    self.cap.set(cv2.CAP_PROP_POS_MSEC, position * 1000)
                    self.command_queue.put({"type": "play"})
                    time.sleep(0.01)
                    self.command_queue.put({"type": "pause"})
                elif cmd["type"] == "speed":
                    self.playback_speed = cmd["value"]
            except queue.Empty:
                pass

            if not self.paused:
                # Calculate the time to wait based on playback speed
                target_frame_time = 1.0 / (self.fps * self.playback_speed)
                current_time = time.time()
                elapsed = current_time - last_frame_time

                # Only process a new frame if enough time has elapsed
                if elapsed >= target_frame_time:
                    ret, frame = self.cap.read()

                    if ret:
                        # Get current position
                        self.current_position = (
                            self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                        )

                        # Convert color space but keep original resolution
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        # Remove the resize operation - send full resolution frame

                        # Put the frame in the queue
                        if (
                            self.frame_queue.qsize() < MAX_QUEUE_SIZE
                        ):  # Limit queue size to prevent memory issues
                            self.frame_queue.put(
                                {
                                    "type": "frame",
                                    "data": frame,
                                    "position": self.current_position,
                                }
                            )

                        last_frame_time = current_time
                    else:
                        # End of video, loop back
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        # Send end of video message
                        self.frame_queue.put({"type": "eof"})

            # Small sleep to prevent CPU hogging
            time.sleep(0.0001)

        # Clean up
        if self.cap:
            self.cap.release()
