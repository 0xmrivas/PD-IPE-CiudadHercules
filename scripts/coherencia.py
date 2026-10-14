"""Comprobaciones de coherencia de un módulo con la estructura de plantillas/modulo.md.

Solo miran lo que ya está escrito: una celda sin rellenar ("[Peso]", "[Horas]"…)
no es una incoherencia, es un campo por completar, y la comprobación que
dependa de ella se omite hasta que se rellene.
"""

from __future__ import annotations

import re

RA_CODE = re.compile(r"\bRA\s*(\d+)\b")
CRITERION = re.compile(r"\bRA(\d+)\.([a-zñ])\b")
PLACEHOLDER = re.compile(r"\[[^\]\n]{3,}\]")


def pending_fields(text: str) -> int:
    """Campos de la plantilla ("[…]") sin rellenar; los enlaces [texto](url) no cuentan."""
    return len(PLACEHOLDER.findall(re.sub(r"\[[^\]\n]*\]\([^)]*\)", "", text)))


def number(cell: str) -> float | None:
    """"18,18 %" → 18.18; None si la celda no es solo un número."""
    match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(?:%|h|horas)?\s*", cell)
    return float(match.group(1).replace(",", ".")) if match else None


def fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    """Tablas Markdown del texto como (cabecera, filas)."""
    found = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            header = cells(lines[i])
            rows = []
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            found.append((header, rows))
        else:
            i += 1
    return found


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def table(found, first_columns: list[str]):
    """Filas de la primera tabla cuya cabecera empieza por `first_columns`."""
    for header, rows in found:
        if [h.lower() for h in header[: len(first_columns)]] == [c.lower() for c in first_columns]:
            return header, rows
    return None


def ra_table(found):
    """Tabla de resultados de aprendizaje: «RA | Resultado de aprendizaje» o la forma larga «RA | Logro…»."""
    return table(found, ["RA", "Resultado de aprendizaje"]) or table(found, ["RA", "Logro"])


def ra_key(code: str) -> int:
    return int(re.sub(r"\D", "", code) or 0)


def structure_issues(text: str) -> list[str]:
    """Tablas de la plantilla que no se reconocen: sin ellas no se comprueba ni se genera nada."""
    issues = []
    found = tables(text)
    criteria = (table(found, ["RA", "Criterio", "Descripción", "Peso dentro del RA"])
                or table(found, ["RA", "Criterio", "Descripción", "Peso en el RA"]))
    if not criteria:
        issues.append("la tabla de criterios no tiene la cabecera de la plantilla "
                      "(RA | Criterio | Descripción | Peso en el RA | Contexto | Evidencias e instrumentos): "
                      "no se comprueban los pesos ni se generan la relación y el reparto")
    elif len(criteria[0]) < 5 or criteria[0][4].lower() != "contexto":
        issues.append("en la tabla de criterios la quinta columna debe ser «Contexto»: "
                      "no se pueden generar la relación ni el reparto")
    if "<!-- tabla-relacion-ra -->" not in text:
        issues.append("falta la marca <!-- tabla-relacion-ra -->: la relación de RA y criterios "
                      "se genera sola, no se escribe a mano")
    if "<!-- tabla-reparto-ffeoE -->" not in text and "### reparto de ra" in text.lower():
        issues.append("falta la marca <!-- tabla-reparto-ffeoE -->: el reparto entre centro y empresa "
                      "se genera solo, no se escribe a mano")
    return issues


def check_module(text: str) -> list[str]:
    """Incoherencias de un módulo, en frases cortas para el profesorado."""
    issues: list[str] = []
    found = tables(text)

    ra_rows = ra_table(found)
    ras = [f"RA{m.group(1)}" for r in ra_rows[1] if (m := RA_CODE.search(r[0]))] if ra_rows else []

    # --- Ponderación de los RA
    weights = table(found, ["RA", "Peso en la calificación del módulo"])
    weights = weights or table(found, ["RA", "Peso en el módulo (sobre los RA impartidos)"])
    if weights:
        values = {f"RA{m.group(1)}": number(r[1]) for r in weights[1] if len(r) > 1 and (m := RA_CODE.search(r[0]))}
        if values and all(v is not None for v in values.values()):
            total = sum(values.values())
            if abs(total - 100) > 0.5:
                issues.append(f"los pesos de los RA suman {fmt(total)} % (deben sumar 100 %)")
        missing = [ra for ra in ras if ra not in values]
        if missing:
            issues.append(f"sin peso en la ponderación: {', '.join(missing)}")

    # --- Criterios: peso dentro de cada RA
    criteria_table = table(found, ["RA", "Criterio", "Descripción", "Peso dentro del RA"])
    criteria_table = criteria_table or table(found, ["RA", "Criterio", "Descripción", "Peso en el RA"])
    criteria: list[str] = []
    if criteria_table:
        by_ra: dict[str, list[float | None]] = {}
        for row in criteria_table[1]:
            match = CRITERION.search(row[1]) if len(row) > 1 else None
            # fila de ejemplo de la plantilla (sin descripción ni peso): aún no hay criterios
            if not match or len(row) < 4 or (PLACEHOLDER.fullmatch(row[2]) and PLACEHOLDER.fullmatch(row[3])):
                continue
            ra = f"RA{match.group(1)}"
            criteria.append(f"{ra}.{match.group(2)}")
            by_ra.setdefault(ra, []).append(number(row[3]) if len(row) > 3 else None)
        for ra, values in sorted(by_ra.items(), key=lambda item: ra_key(item[0])):
            if ras and ra not in ras:
                issues.append(f"la tabla de criterios usa {ra}, que no está en los resultados de aprendizaje")
            if values and all(v is not None for v in values):
                total = sum(values)
                # Margen según la precisión impresa: no ocultar diferencias de 0,41 %.
                rows = [r for r in criteria_table[1] if len(r) > 3 and CRITERION.search(r[1])
                        and f"RA{CRITERION.search(r[1]).group(1)}" == ra]
                precision = [len(m.group(1)) if (m := re.search(r"[.,](\d+)", r[3])) else 0 for r in rows]
                tolerance = sum(0.5 * 10 ** -digits for digits in precision) + 1e-8
                if abs(total - 100) > min(tolerance, 0.5):
                    issues.append(f"los criterios de {ra} suman {fmt(total)} % (deben sumar 100 % dentro del RA)")

    if criteria_table:
        for row in criteria_table[1]:
            if (len(row) > 5 and row[4].lower() in {"empresa", "ambos"}
                    and (row[5].strip() in {"", "-", "—"} or PLACEHOLDER.search(row[5]))):
                issues.append(f"{row[1]} se trabaja en empresa y no tiene evidencias e instrumentos")

    # --- Unidades didácticas
    units = table(found, ["UD", "Título"])
    if not units:
        return issues
    header, rows = units
    col = {name.lower(): i for i, name in enumerate(header)}
    get = lambda row, name: row[col[name]] if name in col and col[name] < len(row) else ""

    hours = [number(get(row, "horas")) for row in rows]
    duration = re.search(r"^- \*\*Duración:\*\*\s*(\d+)\s*horas", text, flags=re.MULTILINE)
    if duration and hours and all(h is not None for h in hours):
        total = float(duration.group(1))
        in_centre = re.search(r"(\d+)\s*horas en el centro", text)
        allowed = {total} | ({float(in_centre.group(1))} if in_centre else set())
        units_sum = sum(hours)
        if all(abs(units_sum - value) > 0.5 for value in allowed):
            detail = f" ({fmt(float(in_centre.group(1)))} h en el centro)" if in_centre else ""
            issues.append(f"las unidades suman {fmt(units_sum)} h y la duración es de {fmt(total)} h{detail}")

    used_ras: set[str] = set()
    used_criteria: set[str] = set()
    all_explicit = True
    for row in rows:
        unit = get(row, "ud") or "una unidad"
        unit_ras = {f"RA{n}" for n in RA_CODE.findall(get(row, "ra"))}
        used_ras |= unit_ras
        cell = get(row, "criterios de evaluación")
        cited = {f"RA{a}.{b}" for a, b in CRITERION.findall(cell)}
        if re.search(r"(?i)todos", cell):
            used_criteria |= {c for c in criteria if c.split(".")[0] in unit_ras}
        elif not cited:
            all_explicit = False
        used_criteria |= cited
        foreign = sorted(unit_ras - set(ras), key=ra_key) if ras else []
        if foreign:
            issues.append(f"{unit} cita {', '.join(foreign)}, que no está en los resultados de aprendizaje")
        if criteria:
            unknown = sorted(cited - set(criteria))
            if unknown:
                issues.append(f"{unit} cita criterios que no están en la tabla de criterios: {', '.join(unknown)}")
    unused = [ra for ra in ras if ra not in used_ras]
    if unused:
        issues.append(f"sin ninguna unidad didáctica: {', '.join(unused)}")
    if criteria and all_explicit:
        orphan = [c for c in criteria if c not in used_criteria and c.split(".")[0] in used_ras]
        if orphan:
            issues.append(f"criterios que no se trabajan en ninguna unidad: {', '.join(orphan)}")
    return issues


def check_shared_curriculum(modules):
    """Contrasta RA y criterios de módulos repetidos, sin elegir una copia por inferencia."""
    groups = {}
    for key, (code, text) in modules.items():
        found = tables(text)
        ras = ra_table(found)
        criteria = table(found, ["RA", "Criterio", "Descripción", "Peso en el RA"])
        criteria = criteria or table(found, ["RA", "Criterio", "Descripción", "Peso dentro del RA"])
        curriculum = (tuple(tuple(" ".join(cell.split()).lower() for cell in row) for row in ras[1]) if ras else (),
                      tuple(sorted((row[1], " ".join(row[2].split()).lower()) for row in criteria[1]
                                   if len(row) > 2 and CRITERION.fullmatch(row[1]))) if criteria else ())
        groups.setdefault(str(code).upper(), []).append((key, curriculum))
    issues = {}
    for code, copies in groups.items():
        if len(copies) > 1 and len({curriculum for _, curriculum in copies}) > 1:
            names = ", ".join(key for key, _ in copies)
            for key, _ in copies:
                issues[key] = [f"coordinar el contenido de {code}: los RA o criterios difieren entre {names}"]
    return issues
