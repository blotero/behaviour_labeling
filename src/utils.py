import csv
import os

from .types import BehaviourRecord


def format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02}:{seconds:02}"


def save_as_csv(
    video_files: list[str],
    current_video_index: int,
    video_dir: str,
    behavior_records: list[BehaviourRecord],
) -> None:
    if video_files and behavior_records:
        video_name = video_files[current_video_index]
        csv_filename = f"{os.path.splitext(video_name)[0]}.csv"
        csv_path = os.path.join(video_dir, csv_filename)
        with open(csv_path, "w", newline="", encoding="utf-8") as file:
            fieldnames = BehaviourRecord.__annotations__.keys()
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for record in behavior_records:
                writer.writerow(record.__dict__)
