import csv
from dataclasses import dataclass
from pathlib import Path

from .types import GroupType, RecordType, Role, Sex, Stage
from .utils import format_time


@dataclass(frozen=True)
class BehaviorRecord:
    session: int
    role: Role
    behaviour: str
    parent_behaviour: str
    start_time: float
    duration: float
    record_type: RecordType
    tag: str
    group_type: GroupType
    sex: Sex
    end_time: float | None = None
    observations: str | None = None
    stage: Stage | None = None
    group_size: int | None = None
    mother_and_calf: int | None = None
    calves: int | None = None

    @property
    def start_time_str(self) -> str:
        return format_time(self.start_time)

    @property
    def end_time_str(self) -> str | None:
        return format_time(self.end_time) if self.end_time else None

    def as_str(self) -> str:
        observations_str = (
            f" - Observaciones: {self.observations}"
            if self.observations
            else ""
        )

        base_str = (
            f">> {self.start_time_str} - {self.record_type} -- "
            f"Rol: {self.role} - Comportamiento: {self.behaviour}: s - "
            f"Tag: {self.tag} - Tipo: {self.group_type} - Sexo: {self.sex} - "
            f"Estadio: {self.stage} - "
            f"Tamaño grupal: {self.group_size}{observations_str} - "
            f"Madres con cría: {self.mother_and_calf} - Crias: {self.calves}"
        )

        if self.record_type == "STATE" and self.end_time_str:
            return (
                f"{base_str} - Fin: {self.end_time_str} "
                f"(Duración: {self.duration:.2f}s)"
            )
        return base_str


def save_as_csv(
    video_files: list[str],
    current_video_index: int,
    video_dir: str,
    behavior_records: list[BehaviorRecord],
) -> None:
    if video_files and behavior_records:
        video_name = video_files[current_video_index]
        csv_root = f"{Path(video_name).stem}"
        csv_filename = f"{csv_root}.csv"
        csv_path = Path(video_dir) / csv_filename

        suffix_counter = 0

        while csv_path.exists():
            suffix_counter += 1
            csv_path = (
                Path(csv_path.parent)
                / f"{csv_root}_{suffix_counter}{csv_path.suffix}"
            )

        with open(csv_path, "w", newline="", encoding="utf-8") as file:
            fieldnames = list(BehaviorRecord.__annotations__.keys()) + [
                "start_time_str",
                "end_time_str",
            ]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for record in behavior_records:
                row_data = record.__dict__.copy()
                row_data["start_time_str"] = record.start_time_str
                row_data["end_time_str"] = record.end_time_str
                writer.writerow(row_data)
