"""Genera grupos/<grupo>/secuenciacion.md de IPE I: la secuenciación de cada grupo.

El calendario de las UD es común a todos los grupos (tres sesiones semanales:
lunes, miércoles y jueves). La FFEOE de cada grupo lo interrumpe donde cae, entre
dos unidades o en mitad de una, y a la vuelta se sigue donde se dejó.

Si cambian las horas de una UD, un festivo o el periodo de FFEOE de un grupo,
se actualizan las constantes de abajo y se vuelve a ejecutar:

    python3 scripts/secuenciacion.py
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INICIO, FIN = date(2026, 9, 15), date(2027, 6, 23)
VACACIONES = [(date(2026, 12, 23), date(2027, 1, 8)),   # Navidad
              (date(2027, 3, 22), date(2027, 3, 28))]   # Semana Santa
# 12/10, 7/12 y 8/12; 2/11 y 1/03 como traslado del 1/11 y del 28/02. Sin festivos locales.
FESTIVOS = {date(2026, 10, 12), date(2026, 11, 2), date(2026, 12, 7), date(2026, 12, 8), date(2027, 3, 1)}
DIAS = (0, 2, 3)  # lunes, miércoles y jueves

UNIDADES = [("UD1", 4), ("UD2", 9), ("UD3", 10), ("UD4", 6), ("UD5", 5),
            ("UD6", 9), ("UD7", 11), ("UD8", 11), ("UD9", 6), ("UD10", 7)]
HORAS_FFEOE = 18
FFEOE = {
    "1ga-a": (date(2027, 3, 11), date(2027, 4, 23)),
    "1ga-b": (date(2027, 4, 27), date(2027, 6, 3)),
    "1af-a": (date(2027, 3, 17), date(2027, 4, 29)),
    "1af-b": (date(2027, 5, 4), date(2027, 6, 9)),
}

# Fin de la 1.ª y de la 2.ª evaluación (último día lectivo antes de Navidad y de Semana Santa)
EVALUACIONES = (date(2026, 12, 23), date(2027, 3, 22))


def lectivo(d: date) -> bool:
    return (INICIO <= d <= FIN and d not in FESTIVOS
            and not any(a <= d <= b for a, b in VACACIONES))


def sesiones() -> list[date]:
    dias = (INICIO + timedelta(n) for n in range((FIN - INICIO).days + 1))
    return [d for d in dias if d.weekday() in DIAS and lectivo(d)]


def evaluacion(d: date) -> int:
    return 1 if d < EVALUACIONES[0] else 2 if d < EVALUACIONES[1] else 3


def evaluaciones(a: date, b: date) -> str:
    ea, eb = evaluacion(a), evaluacion(b)
    return f"{ea}.ª ev." if ea == eb else f"{ea}.ª–{eb}.ª ev."


def rango(a: date, b: date) -> str:
    if a == b:
        return a.strftime("%d/%m/%Y")
    inicio = a.strftime("%d/%m") if a.year == b.year else a.strftime("%d/%m/%Y")
    return f"{inicio}–{b.strftime('%d/%m/%Y')}"


def filas(desde: date, hasta: date) -> list[str]:
    """Filas de la tabla de un grupo cuya FFEOE va de «desde» a «hasta»."""
    libres = [s for s in sesiones() if not desde <= s <= hasta]
    ffeoe = f"| **FFEOE** | **{HORAS_FFEOE}** | **{evaluaciones(desde, hasta)} · {rango(desde, hasta)}** |"
    out, i, puesta = [], 0, False
    for ud, horas in UNIDADES:
        tramo = libres[i:i + horas]
        i += horas
        antes = [s for s in tramo if s < desde]
        despues = [s for s in tramo if s > hasta]
        if not puesta and antes and despues:
            out.append(f"| {ud} (inicio) | {len(antes)} | {evaluaciones(antes[0], antes[-1])} · {rango(antes[0], antes[-1])} |")
            out.append(ffeoe)
            out.append(f"| {ud} (continuación) | {len(despues)} | {evaluaciones(despues[0], despues[-1])} · {rango(despues[0], despues[-1])} |")
            puesta = True
            continue
        if not puesta and tramo[0] > hasta:
            out.append(ffeoe)
            puesta = True
        out.append(f"| {ud} | {horas} | {evaluaciones(tramo[0], tramo[-1])} · {rango(tramo[0], tramo[-1])} |")
    if not puesta:
        out.append(ffeoe)
    return out


def main() -> int:
    for grupo, (desde, hasta) in FFEOE.items():
        texto = (
            "#### Grupo {{letra}}\n\n"
            "<!-- Por grupo. Calendario común de las UD; la FFEOE lo interrumpe donde cae y, "
            "a la vuelta, se sigue donde se dejó. Se genera con scripts/secuenciacion.py. -->\n\n"
            f"Formación en empresa del {desde.strftime('%d/%m')} al {hasta.strftime('%d/%m/%Y')}.\n\n"
            "| UD | Horas | Periodo |\n|---|---|---|\n" + "\n".join(filas(desde, hasta)) + "\n"
        )
        destino = ROOT / "grupos" / grupo / "secuenciacion.md"
        destino.write_text(texto, encoding="utf-8")
        print(destino.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
