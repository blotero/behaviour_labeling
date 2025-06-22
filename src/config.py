from typing import Any, Literal

type RecordType = Literal["STATE", "EVENT"]

BEHAVIOR_DATA = {
    "Individuales": {
        "Comportamientos en fondo": {
            "Comportamientos en fondo": "EVENT",
        },
        "Respiración": {
            "Respiración": "EVENT",
            "Respiración con desprendimiento de lodo": "EVENT",
            "Respiración con expulsión de agua": "EVENT",
        },
        "Buceo": {
            "Buceo exponiendo la cola": "EVENT",
            "Buceo sin exponer la cola": "EVENT",
        },
        "Desplazamiento": {
            "Desplazamiento": "STATE",
            "Alejarse": "EVENT",
            "Acercarse": "EVENT",
            "Persecución": "EVENT",
            "Nado formando espejo de agua": "EVENT",
        },
    },
    "Sociales": {
        "Comportamientos en fondo": {
            "Comportamientos en fondo": "EVENT",
            "Interacción en fondo (Indefinido)": "EVENT",
        },
        "Respiración": {
            "Respiración sincronizada": "EVENT",
        },
        "Agrupación": {
            "Romping": "EVENT",
            "Grouping": "EVENT",
        },
        "Desplazamiento": {
            "Desplazamiento sincronizado": "STATE",
            "Nado uno sobre otro": "STATE",
            "Desplazamiento en fila": "STATE",
            "Arqueo de cuerpo para cambio de dirección": "EVENT",
        },
        "Interacciones": {
            "Persecución": "EVENT",
        },
    },
    "Reproductivo": {
        "Comportamientos en fondo": {
            "Comportamientos en fondo": "EVENT",
            "Reposo en fondo": "EVENT",
        },
        "Respiración": {
            "Respiración": "EVENT",
            "Respiración sincronizada": "EVENT",
            "Respiración con expulsión de agua": "EVENT",
        },
        "Desplazamiento": {
            "Desplazamiento en fila": "STATE",
            "Aproximación": "EVENT",
            "Aproximación rápida": "EVENT",
            "Alejarse": "EVENT",
        },
        "Posicionamiento": {
            "Posicionamiento sobre dorso de la hembra (alineado)": "EVENT",
            "Posicionamiento sobre dorso de la hembra (de lado)": "EVENT",
            "Montaje en cruz sobre dorso o pedúnculo": "EVENT",
        },
        "Sujeción": {
            "Sujeción": "EVENT",
            "Sujeción de pedúnculo": "EVENT",
            "Sujeción ventral (o vientre- vientre)": "EVENT",
            "Sujeción dorsal": "EVENT",
            "Sujeción lateral o de costado": "EVENT",
        },
        "Liberación": {
            "Giros de liberación": "EVENT",
            "Movimientos de liberación": "EVENT",
            "Golpeteo caudal": "EVENT",
            "Cabezazo": "EVENT",
            "Empuje de rotación": "EVENT",
            "Liberación": "EVENT",
        },
    },
    "Madre-cria": {
        "Comportamientos en fondo": {
            "Comportamientos en fondo": "EVENT",
            "Interacción en fondo (Indefinido)": "EVENT",
        },
        "Respiración": {
            "Respiración sincronizada": "EVENT",
        },
        "Buceo": {
            "Buceo exponiendo la cola": "EVENT",
            "Buceo sin exponer la cola": "EVENT",
        },
        "Desplazamiento": {
            "Aproximación": "EVENT",
            "Alejarse": "EVENT",
            "Nado uno sobre otro": "EVENT",
        },
        "Contacto": {
            "Contacto aleta- aleta": "EVENT",
            "Contacto hocico- hocico": "EVENT",
            "Contacto hocico- cabeza": "EVENT",
            "Contacto hocico- dorso": "EVENT",
        },
        "Giros": {
            "Giro de 360° sobre el propio eje": "EVENT",
            "Giro en ángulo agudo (cambio dirección)": "EVENT",
            "Giro 90° para cambio de dirección": "EVENT",
            "Arqueo de cuerpo para cambio de dirección": "EVENT",
        },
    },
    "Embarcaciones": {
        "Respiración": {
            "Respiración": "EVENT",
        },
        "Desplazamiento": {
            "Aproximación": "EVENT",
            "Huida": "EVENT",
            "Cambio de dirección": "EVENT",
            "Arqueo de cuerpo para cambio de dirección": "EVENT",
        },
        "Buceo": {
            "Buceo": "EVENT",
        },
        "Comportamientos en fondo": {
            "Comportamientos de fondo": "EVENT",
            "Parar comportamiento de fondo": "EVENT",
        },
        "Agrupación": {
            "Reagrupación": "EVENT",
        },
    },
    "Interespecíficas": {
        "Interacción con peces": "EVENT",
    },
}


def get_recursive_parents(
    target: str, data: dict[str, Any], parents: list[str] | None = None
) -> list[str]:
    if parents is None:
        parents = []

    for key, value in data.items():
        if isinstance(value, dict):
            if target in value:
                return [key] + parents
            result = get_recursive_parents(target, value, [key] + parents)
            if result:
                return result

    return []
