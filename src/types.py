from dataclasses import dataclass
from typing import Literal

Role = Literal[
    "madre",
    "cria",
    "escolta",
    "macho",
    "hembra",
    "macho-reproductor",
    "indefinido",
]

type GroupType = Literal["individual", "grupal"]

type Sex = Literal["macho", "hembra", "indefinido"]

type RecordType = Literal["STATE", "EVENT"]


@dataclass(frozen=True)
class BehaviourRecord:
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

    def as_str(self) -> str:
        observations_str = (
            f" - Observaciones: {self.observations}"
            if self.observations
            else ""
        )
        if self.record_type == "EVENT":
            return (
                f"{self.record_type} -- Rol: {self.role} - Comportamiento: {self.behaviour}: {self.start_time:.2f}s"
                f" - Tag:{self.tag} - Tipo:{self.group_type} - Sexo:{self.sex}{observations_str}"
            )
        else:
            return (
                f"{self.record_type} -- Rol: {self.role} - Comportamiento: {self.behaviour}: {self.start_time:.2f}s"
                f" - {self.end_time:.2f}s (Duración: {self.duration:.2f}s) - Tag:{self.tag} - Tipo:{self.group_type} - Sexo:{self.sex}{observations_str}"
            )
