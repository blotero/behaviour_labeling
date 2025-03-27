from typing import Any, Literal

type RecordType = Literal["STATE", "EVENT"]

BEHAVIOR_DATA = {
    "Superficie": {
        "Desplazamiento": {
            "Desplazamiento solo": "STATE",
            "Aproximación": "STATE",
            "Giro": "STATE",
            "Arqueo de cuerpo para cambio de rumbo": "STATE",
        },
        "Desplazamiento sincronizado": {
            "Nadar juntos": "STATE",
            "Nadar juntos en fila": "STATE",
            "Nadar sobre otro (corto o largo)": "STATE",
            "Nado en círculo juntos (es)": "STATE",
            "Giro juntos (para cambiar de rumbo)": "STATE",
        },
        "Respiración": {
            "Respiración": "STATE",
            "Respiración sincronizada": "STATE",
        },
        "Eliminación": {
            "Gases por la boca": "STATE",
        },
    },
    "De buceo": {
        "Sumergirse": {
            "Inmersión": "STATE",
        }
    },
    "De fondo": {
        "Escape o evasión": {
            "Huida de lancha": "STATE",
            "Huida de otro individuo": "STATE",
        },
        "Contacto táctil": {
            "Contacto hocico-aleta": "STATE",
            "Contacto hocico-costado": "STATE",
            "Contacto hocico-dorso": "STATE",
            "Contacto hocico-cola": "STATE",
            "Contacto hocico-hocico": "STATE",
            "Contacto aleta-aleta": "STATE",
            "Contacto aleta-pedúnculo": "STATE",
        },
    },
    "Social": {
        "Romping": {
            "Agrupación": "STATE",
        }
    },
    "Interacciones interespecíficas": {
        "Interacciones interespecíficas": {
            "¿Comensalismo?": "STATE",
        },
        "Sumergidos": {
            "¿No determinado?": "STATE",
        },
        "Agonísticos": {
            "Persecución": "STATE",
        },
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
