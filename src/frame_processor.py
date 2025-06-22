import queue
import threading
import time
from typing import Literal, NotRequired, TypedDict

import cv2
from cv2.typing import MatLike


class FrameQueueElement(TypedDict):
    data: NotRequired[MatLike]
    duration: NotRequired[float]
    fps: NotRequired[float]
    position: NotRequired[float]
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

        # Send initial metadata to the main thread
        self.frame_queue.put(
            {
                "type": "metadata",
                "duration": self.total_frames / self.fps if self.fps > 0 else 0,
                "fps": self.fps,
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
                        self.current_position = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000

                        # Resize and convert the frame
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        frame = cv2.resize(frame, (self.width, self.height))

                        # Put the frame in the queue
                        if (
                            self.frame_queue.qsize() < 2
                        ):  # Limit queue size to prevent memory issues
                            self.frame_queue.put(
                                {"type": "frame", "data": frame, "position": self.current_position}
                            )

                        last_frame_time = current_time
                    else:
                        # End of video, loop back
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        # Send end of video message
                        self.frame_queue.put({"type": "eof"})

            # Small sleep to prevent CPU hogging
            time.sleep(0.001)

        # Clean up
        if self.cap:
            self.cap.release()
