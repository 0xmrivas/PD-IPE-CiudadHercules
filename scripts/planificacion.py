"""Tablas de planificación derivadas de las UD y del contexto de los criterios.

El profesorado mantiene la asignación de criterios en las UD y el contexto en
la tabla de evaluación. Las vistas de RA y FFEOE se calculan al ensamblar.
"""

import re

from coherencia import CRITERION, RA_CODE, cells, ra_key, ra_table, table, tables

RELACION = "<!-- tabla-relacion-ra -->"
REPARTO = "<!-- tabla-reparto-ffeoE -->"


def criteria_rows(text):
    found = tables(text)
    selected = table(found, ["RA", "Criterio", "Descripción", "Peso dentro del RA"])
    selected = selected or table(found, ["RA", "Criterio", "Descripción", "Peso en el RA"])
    return selected[1] if selected else []


def criterion_contexts(text):
    return {f"RA{a}.{b}": row[4].strip().lower()
            for row in criteria_rows(text) if len(row) > 4
            for a, b in CRITERION.findall(row[1])}


def phase(contexts):
    contexts = list(contexts)
    if not contexts or any(c not in {"centro", "empresa", "ambos"} for c in contexts):
        return "[Fase por concretar]"
    centre = any(c in {"centro", "ambos"} for c in contexts)
    company = any(c in {"empresa", "ambos"} for c in contexts)
    return "Centro y empresa" if centre and company else "Centro" if centre else "Empresa"


def md_table(header, rows):
    return "\n".join(["| " + " | ".join(header) + " |",
                      "|" + "---|" * len(header)]
                     + ["| " + " | ".join(row) + " |" for row in rows])


def relation_table(text):
    units = table(tables(text), ["UD", "Título"])
    contexts = criterion_contexts(text)
    result = []
    covered = set()
    represented = set()
    if units:
        header, rows = units
        columns = {name.lower(): i for i, name in enumerate(header)}
        def get(row, name):
            i = columns.get(name)
            return row[i] if i is not None and i < len(row) else ""
        for row in rows:
            ras = [f"RA{n}" for n in RA_CODE.findall(get(row, "ra"))]
            cell = get(row, "criterios de evaluación")
            cited = [f"RA{a}.{b}" for a, b in CRITERION.findall(cell)]
            if re.search(r"(?i)todos", cell):
                cited = [code for code in contexts if code.split(".")[0] in ras]
            # Se conservan también referencias incorrectas: el validador las avisa.
            ras = sorted(set(ras) | {c.split(".")[0] for c in cited}, key=ra_key)
            for ra in ras:
                codes = [c for c in cited if c.split(".")[0] == ra]
                covered.update(codes)
                represented.add(ra)
                result.append([ra, ", ".join(codes) or "[Criterios por asignar]",
                               get(row, "ud") or "[UD por asignar]",
                               get(row, "periodo") or "[Periodo por concretar]",
                               phase(contexts.get(c, "") for c in codes)])
    ra_rows = ra_table(tables(text))
    known = {f"RA{n}" for row in ra_rows[1] for n in RA_CODE.findall(row[0])} if ra_rows else set()
    known |= {code.split(".")[0] for code in contexts}
    for ra in sorted(known, key=ra_key):
        missing = [c for c in contexts if c.split(".")[0] == ra and c not in covered]
        if missing or ra not in represented:
            result.append([ra, ", ".join(missing) or "[Criterios por completar]",
                           "[UD por asignar]", "[Periodo por concretar]",
                           phase(contexts[c] for c in missing)])
    if not result:
        result = [["[RA por asignar]", "[Criterios por asignar]", "[UD por asignar]",
                   "[Periodo por concretar]", "[Fase por concretar]"]]
    return md_table(["RA", "Criterios", "UD", "Periodo", "Fase"], result)


def company_table(text):
    contexts = criterion_contexts(text)
    ras_table = ra_table(tables(text))
    ras = {f"RA{n}" for row in ras_table[1] for n in RA_CODE.findall(row[0])} if ras_table else set()
    ras |= {c.split(".")[0] for c in contexts}
    result = []
    observations = table(tables(text), ["RA", "Observaciones de la FFEOE"])
    notes = {row[0]: row[1] for row in observations[1] if len(row) > 1} if observations else {}
    for ra in sorted(ras, key=ra_key):
        codes = [c for c in contexts if c.split(".")[0] == ra]
        centre = [c for c in codes if contexts[c] in {"centro", "ambos"}]
        company = [c for c in codes if contexts[c] in {"empresa", "ambos"}]
        pending = [c for c in codes if contexts[c] not in {"centro", "empresa", "ambos"}]
        note = notes.get(ra, "Se trabaja íntegramente en el aula" if codes and not company and not pending else "—")
        if pending:
            note = (note + "; " if note != "—" else "") + "[Contexto por concretar: " + ", ".join(pending) + "]"
        if not codes:
            note = "[Criterios y contextos por completar]"
        result.append([ra, ", ".join(centre) or "—", ", ".join(company) or "—", note])
    return md_table(["RA", "Criterios en centro", "Criterios en empresa", "Observaciones"],
                    result or [["[RA]", "[Criterios]", "[Criterios]", "[Observaciones]"]])


def replace_table(text, first_columns, replacement):
    """Sustituye una tabla concreta sin afectar al resto del documento."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        header = cells(line)
        if header[:len(first_columns)] != first_columns:
            continue
        end = i + 1
        while end < len(lines) and lines[end].lstrip().startswith("|"):
            end += 1
        lines[i:end] = replacement.splitlines() if replacement else []
        break
    return "\n".join(lines)


def render_course_planning(text, modules):
    """Completa los criterios conocidos; las actividades requieren coordinación dual."""
    selected = table(tables(text), ["Módulo", "RA y criterios", "Actividad formativa", "Lugar"])
    if not selected:
        return text
    participants = table(tables(text), ["Módulo", "Horas totales", "Dual (sí/no)"])
    excluded = {row[0].split()[0].upper() for row in participants[1]
                if len(row) > 2 and row[2].lower().startswith("no")} if participants else set()
    result = []
    for row in selected[1]:
        if len(row) != 4:
            result.append(row)
            continue
        code = row[0].split()[0].upper()
        # Una fila cumplimentada se conserva para que una discrepancia sea revisable.
        generic = not CRITERION.search(row[1]) and row[1].startswith("[")
        if generic and code in excluded:
            continue
        if not generic or code not in modules:
            result.append(row)
            continue
        contexts = criterion_contexts(modules[code])
        codes = [c for c in contexts if contexts[c] in {"empresa", "ambos"}]
        ras = sorted({c.split(".")[0] for c in codes}, key=ra_key)
        for ra in ras:
            group = [c for c in codes if c.split(".")[0] == ra]
            place = "Ambos" if any(contexts[c] == "ambos" for c in group) else "Empresa"
            result.append([row[0], ", ".join(group), row[2], place])
        if not ras:
            result.append([row[0], "[Criterios de empresa por concretar]", row[2], row[3]])
    return replace_table(text, selected[0], md_table(selected[0], result))


def check_company_activities(text, modules):
    """Comprueba las referencias ya concretadas, sin aprobar propuestas de actividad."""
    selected = table(tables(text), ["Módulo", "RA y criterios", "Actividad formativa", "Lugar"])
    if not selected:
        return []
    issues, covered = [], {}
    for row in selected[1]:
        if len(row) < 4:
            continue
        code = row[0].split()[0].upper()
        cited = {f"RA{a}.{b}" for a, b in CRITERION.findall(row[1])}
        if code not in modules:
            if cited:
                issues.append(f"actividad de empresa de un módulo no declarado: {code}")
            continue
        contexts = criterion_contexts(modules[code])
        covered.setdefault(code, set()).update(cited)
        for criterion in sorted(cited):
            if contexts.get(criterion) not in {"empresa", "ambos"}:
                issues.append(f"{code}/{criterion}: la actividad no coincide con un criterio de empresa o ambos")
        if cited and row[3].lower() not in {"empresa", "ambos"}:
            issues.append(f"{code}: confirmar el lugar de la actividad vinculada a criterios de empresa")
    for code, source in modules.items():
        expected = {c for c, context in criterion_contexts(source).items() if context in {"empresa", "ambos"}}
        missing = expected - covered.get(code, set())
        if missing:
            issues.append(f"{code}: criterios de empresa sin actividad vinculada: {', '.join(sorted(missing))}")
    return issues


def render_planning(text):
    """Sustituye marcadores y muestra las UD con las seis columnas de jefatura."""
    # Ambas vistas deben leer el origen completo antes de ocultar la columna.
    text = text.replace(RELACION, relation_table(text)).replace(REPARTO, company_table(text))
    text = replace_table(text, ["RA", "Observaciones de la FFEOE"], "")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        header = cells(line)
        if header[:2] != ["UD", "Título"] or "Criterios de evaluación" not in header:
            continue
        remove = header.index("Criterios de evaluación")
        j = i
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            row = cells(lines[j])
            if len(row) == len(header):
                del row[remove]
                lines[j] = "| " + " | ".join(row) + " |"
            j += 1
    return "\n".join(lines)
