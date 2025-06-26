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

type Stage = Literal["cria", "adulto", "juvenil", "indefinido"]
