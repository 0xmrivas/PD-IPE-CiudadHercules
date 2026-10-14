#!/usr/bin/env python3
"""Valida y ensambla las programaciones didácticas de IPE.

Cada programación del manifiesto es un documento para todos sus grupos y da
un Markdown en build/PD-<módulo>-<nivel>.md, que build-pdf.sh convierte en
PDF. Los apartados se resuelven por capas (ver manifest.yml):
pd → módulo → ciclo → común; lo de cada grupo, con <!-- por-grupo: … -->.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coherencia import check_module, pending_fields, structure_issues  # noqa: E402
from planificacion import render_planning  # noqa: E402
from texto import indented_code_lines, normalize_markdown, table_breaks  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build"
STATUS_FILE = ROOT / "docs" / "estado.md"
SCHEMA_VERSION = 2

INCLUDE = re.compile(r"^[ \t]*<!--\s*incluir:\s*([a-z0-9][a-z0-9-]*)\s*-->[ \t]*$", re.MULTILINE)
GROUP_TABLE = re.compile(r"^[ \t]*<!--\s*tabla-grupos:\s*([a-z0-9][a-z0-9-]*)\s*-->[ \t]*$", re.MULTILINE)
PER_GROUP = re.compile(r"^[ \t]*<!--\s*por-grupo:\s*([a-z0-9][a-z0-9-]*)\s*-->[ \t]*$", re.MULTILINE)
VARIABLE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
FICHA = "<!-- ficha-modulo -->"
ORDINAL = {1: "1.º", 2: "2.º"}


class ValidationError(Exception):
    pass


def letters(groups: list[str]) -> str:
    return groups[0] if len(groups) == 1 else ", ".join(groups[:-1]) + " y " + groups[-1]


@dataclass
class Programacion:
    entry: dict[str, Any]
    module: dict[str, Any]
    cycle: dict[str, Any]
    variables: dict[str, str]
    layers: list[tuple[str, Path]]
    groups: list[dict[str, Any]]
    used: set[Path] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)
    pending: int = 0
    issues: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.entry["id"]

    @property
    def output_name(self) -> str:
        return f"PD-{self.module['corto'].replace(' ', '-')}-{self.cycle['nivel']}"


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValidationError(f"No existe {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"manifest.yml no es YAML válido: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError(f"manifest.yml debe declarar schema_version: {SCHEMA_VERSION}")
    for key in ("documento", "apartados", "modulos", "ciclos", "programaciones"):
        if not data.get(key):
            raise ValidationError(f"Falta «{key}» en manifest.yml")
    for key in ("centro", "departamento", "docente", "curso_academico", "version"):
        if not data["documento"].get(key):
            raise ValidationError(f"Falta documento.{key} en manifest.yml")
    ids = [p.get("id") for p in data["programaciones"]]
    if len(set(ids)) != len(ids) or not all(isinstance(i, str) and re.fullmatch(r"[a-z0-9-]+", i) for i in ids):
        raise ValidationError("Cada programación necesita un «id» único en minúsculas (p. ej. ipe1-gm)")
    return data


def make_programacion(manifest: dict[str, Any], entry: dict[str, Any]) -> Programacion:
    for key in ("id", "modulo", "ciclo", "curso", "horas", "grupos"):
        if entry.get(key) in (None, "", []):
            raise ValidationError(f"La programación {entry.get('id', '?')} no tiene «{key}»")
    module = manifest["modulos"].get(entry["modulo"])
    cycle = manifest["ciclos"].get(entry["ciclo"])
    if not module or not cycle:
        raise ValidationError(f"{entry['id']}: módulo o ciclo no declarado en manifest.yml")
    doc = manifest["documento"]
    course = ORDINAL.get(entry["curso"], f"{entry['curso']}.º")
    weekly = entry.get("horas_semana")
    group_letters = [str(g) for g in entry["grupos"]]
    plural = "grupos" if len(group_letters) > 1 else "grupo"
    variables = {
        "centro": doc["centro"],
        "codigo_centro": str(doc.get("codigo_centro", "")),
        "localidad": doc.get("localidad", ""),
        "departamento": doc["departamento"],
        "docente": doc["docente"],
        "jefatura": doc.get("jefatura", "[Jefatura de departamento]"),
        "familia": doc.get("familia", ""),
        "curso_academico": doc["curso_academico"],
        "modulo": module["titulo"],
        "modulo_corto": module["corto"],
        "codigo": str(module["codigo"]),
        "horas": str(entry["horas"]),
        "horas_semana": str(weekly) if weekly else "[Horas semanales]",
        "ciclo": cycle["corto"],
        "titulo_ciclo": cycle["titulo"],
        "grado": cycle["grado"],
        "curso": course,
        "grupos": f"{plural} {letters(group_letters)}",
        "grupo": f"{course} {cycle['corto']} ({plural} {letters(group_letters)})",
        "letra": "",
    }
    groups = []
    for letter in group_letters:
        folder = ROOT / "grupos" / f"{entry['curso']}{entry['ciclo']}-{letter.lower()}"
        groups.append({
            "letra": letter,
            "carpeta": folder,
            "variables": {**variables, "letra": letter, "grupo": f"{course} {cycle['corto']} {letter}"},
        })
    layers = [
        ("pd", ROOT / "pd" / entry["id"]),
        ("modulo", ROOT / "modulos" / entry["modulo"]),
        ("ciclo", ROOT / "ciclos" / entry["ciclo"]),
        ("comun", ROOT / "comun"),
    ]
    return Programacion(entry, module, cycle, variables, layers, groups)


def resolve(prog: Programacion, name: str) -> Path | None:
    """Primera capa que tiene <name>.md."""
    for _, folder in prog.layers:
        candidate = folder / f"{name}.md"
        if candidate.is_file():
            return candidate
    return None


def substitute(prog: Programacion, text: str, variables: dict[str, str]) -> str:
    def value(match: re.Match) -> str:
        key = match.group(1)
        if key not in variables:
            prog.warnings.append(f"variable desconocida {{{{{key}}}}}")
            return match.group(0)
        return variables[key]

    return VARIABLE.sub(value, text)


def expand(prog: Programacion, text: str, chain: tuple[str, ...], variables: dict[str, str]) -> str:
    """Resuelve inclusiones y fragmentos por grupo; luego sustituye las variables."""

    def include(match: re.Match) -> str:
        name = match.group(1)
        if name in chain:
            raise ValidationError(f"{prog.id}: inclusión circular {' → '.join(chain + (name,))}")
        path = resolve(prog, name)
        if not path:
            prog.warnings.append(f"no existe el fragmento «{name}» en ninguna capa")
            return f"[Fragmento «{name}» por redactar]"
        prog.used.add(path)
        return expand(prog, path.read_text(encoding="utf-8").strip(), chain + (name,), variables)

    def per_group(match: re.Match) -> str:
        name = match.group(1)
        parts = []
        for group in prog.groups:
            path = group["carpeta"] / f"{name}.md"
            if not path.is_file():
                prog.warnings.append(f"falta {path.relative_to(ROOT)}")
                parts.append(f"[{name} del grupo {group['letra']} por redactar]")
                continue
            prog.used.add(path)
            parts.append(expand(prog, path.read_text(encoding="utf-8").strip(), chain + (name,), group["variables"]))
        return "\n\n".join(parts)

    def group_table(match: re.Match) -> str:
        """Une la tabla «Dato | Valor» de cada grupo en una sola, con una columna por grupo."""
        name = match.group(1)
        labels: list[str] = []
        values: list[dict[str, str]] = []
        for group in prog.groups:
            path = group["carpeta"] / f"{name}.md"
            rows: dict[str, str] = {}
            if path.is_file():
                prog.used.add(path)
                text = substitute(prog, COMMENT.sub("", path.read_text(encoding="utf-8")), group["variables"])
                for line in text.splitlines():
                    cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.lstrip().startswith("|") else []
                    if len(cells) >= 2 and cells[0] not in ("Dato", "") and not re.fullmatch(r"[-: ]+", cells[0]):
                        rows[cells[0]] = cells[1]
                        if cells[0] not in labels:
                            labels.append(cells[0])
            else:
                prog.warnings.append(f"falta {path.relative_to(ROOT)}")
            values.append(rows)
        header = "| Dato | " + " | ".join(f"Grupo {g['letra']}" for g in prog.groups) + " |"
        lines = [header, "|---|" + "---|" * len(prog.groups)]
        for label in labels:
            lines.append(f"| {label} | " + " | ".join(v.get(label, "—") for v in values) + " |")
        return "\n".join(lines)

    text = PER_GROUP.sub(per_group, GROUP_TABLE.sub(group_table, INCLUDE.sub(include, text)))
    return substitute(prog, text, variables)


def ficha(prog: Programacion) -> str:
    v = prog.variables
    weekly = f" ({v['horas_semana']} horas semanales)" if prog.entry.get("horas_semana") else " ([Horas semanales])"
    lines = [
        f"- **Módulo profesional:** {v['codigo']}. {v['modulo']}",
        f"- **Familia profesional:** {v['familia']}" if v["familia"] else "",
        f"- **Ciclo formativo:** {v['titulo_ciclo']} ({v['grado'].lower()})",
        f"- **Curso y grupos:** {v['curso']} curso, {v['grupos']}",
        f"- **Duración:** {v['horas']} horas{weekly}",
        f"- **Equivalencia en créditos ECTS:** {prog.entry['ects']}" if prog.entry.get("ects") else "",
        f"- **Docente:** {v['docente']}",
        f"- **Departamento:** {v['departamento']} (jefatura: {v['jefatura']})",
        f"- **Curso académico:** {v['curso_academico']}",
    ]
    return "\n".join(line for line in lines if line)


def section_text(prog: Programacion, name: str) -> str:
    path = resolve(prog, name)
    if not path:
        raise ValidationError(
            f"{prog.id}: no existe el apartado «{name}» (búscalo como {name}.md en pd/, modulos/, ciclos/ o comun/)"
        )
    prog.used.add(path)
    text = path.read_text(encoding="utf-8").strip()
    headings = re.findall(r"^# +(.+)$", text, flags=re.MULTILINE)
    if len(headings) != 1 or not text.startswith("# "):
        raise ValidationError(f"{path.relative_to(ROOT)}: debe empezar por un único título «# …»")
    if re.match(r"^\d+[.) ]", headings[0]):
        raise ValidationError(f"{path.relative_to(ROOT)}: el título no lleva numeración (la pone la maquetación)")
    return expand(prog, text, (name,), prog.variables).replace(FICHA, ficha(prog))


def front_matter(manifest: dict[str, Any], prog: Programacion) -> dict[str, Any]:
    doc, v = manifest["documento"], prog.variables
    groups = f"{v['grupos'][0].upper()}{v['grupos'][1:]}"
    return {
        "title": f"Programación Didáctica · {v['modulo']} · {v['grupo']}",
        "lang": "es",
        "cover-title": "Programación Didáctica",
        "cover-subtitle": v["modulo"],
        "cover-detail": f"Módulo {v['codigo']} · {v['curso']} {v['ciclo']}",
        "cover-groups": groups,
        "teacher": doc["docente"],
        "department": doc["departamento"],
        "institution": doc["centro"],
        "city": doc.get("localidad", ""),
        "academic-year": doc["curso_academico"],
        "version": str(doc["version"]),
        "header-title": f"{v['modulo_corto']} · {v['curso']} {v['ciclo']} · {groups}",
        "module-level": 0,
    }


def version_register(manifest: dict[str, Any], prog: Programacion) -> str:
    """Tabla final de control de versiones con las filas de manifest.yml que afectan a esta PD."""
    rows = [v for v in manifest.get("versiones", []) if prog.id in v.get("programaciones", [prog.id])]
    if not rows:
        return ""
    lines = [
        "# Registro de versiones {.unnumbered}",
        "",
        "| Responsable | Acción (Redactado, Revisado) | Fecha | Versión |",
        "|---|---|---|---|",
    ]
    for v in rows:
        people = v.get("responsables", [])
        people = "<br>".join(people) if isinstance(people, list) else str(people)
        lines.append(f"| {people} | {v.get('accion', '')} | {v.get('fecha', '')} | {v.get('version', '')} |")
    return "\n".join(lines)


def assemble(manifest: dict[str, Any], prog: Programacion) -> str:
    source = "\n\n".join(section_text(prog, name) for name in manifest["apartados"])
    source = f"{source}\n\n{version_register(manifest, prog)}"
    # Las marcas de las tablas generadas se comprueban antes de sustituirlas
    prog.issues = structure_issues(source) + check_module(source)
    # Los comentarios de instrucciones no llegan al documento
    body = re.sub(r"\n{3,}", "\n\n", COMMENT.sub("", render_planning(source)))
    prog.pending = pending_fields(body)
    code = indented_code_lines(body)
    if code:
        prog.warnings.append(f"texto sangrado con 4 espacios (saldrá como código) en {len(code)} líneas")
    meta = yaml.safe_dump(front_matter(manifest, prog), allow_unicode=True, sort_keys=False).strip()
    return table_breaks(normalize_markdown(f"---\n{meta}\n---\n\n{body}")).rstrip() + "\n"


# ---------- Estado ----------

PIECE_GROUPS = [
    ("comun", "Común a todas las programaciones", "Se escribe una vez y vale para las tres PD."),
    ("modulos", "Por módulo", "RA, criterios, UD y evaluación. IPE I es el mismo en grado medio y superior."),
    ("ciclos", "Por ciclo", "Lo que depende del título: normativa, competencia general y perfil profesional."),
    ("pd", "Por programación", "Lo propio de cada PD: contribución al título, nivel, interdisciplinariedad, dual y actividades."),
    ("grupos", "Por grupo", "La contextualización y la diversidad de cada grupo."),
]


def piece_pending(path: Path) -> int:
    return pending_fields(COMMENT.sub("", path.read_text(encoding="utf-8")))


def status_report(progs: list[Programacion]) -> str:
    from urllib.parse import quote

    lines = [
        "# Estado de las programaciones",
        "",
        "Se genera solo con cada cambio: no lo edites a mano.",
        "",
        "- **Por completar:** campos que siguen entre corchetes, como `[Peso]`.",
        "- **Revisar:** lo que no cuadra: pesos que no suman 100 %, horas de las UD",
        "  distintas de la duración, RA sin unidad, criterios sin trabajar…",
        "",
        "| Programación | PDF | Por completar | Revisar |",
        "|---|---|:---:|:---:|",
    ]
    for prog in progs:
        pdf = f"../programaciones/{quote(prog.output_name)}.pdf"
        issues = len(prog.issues) + len(prog.warnings)
        lines.append(
            f"| {prog.variables['modulo_corto']} · {prog.variables['grupo']} | [{prog.output_name}.pdf]({pdf}) "
            f"| {prog.pending or '✓'} | {f'[{issues}](#{prog.id})' if issues else '✓'} |"
        )

    users: dict[Path, list[str]] = {}
    for prog in progs:
        for path in prog.used:
            users.setdefault(path, []).append(prog.output_name.removeprefix("PD-"))
    lines += ["", "## Piezas", "", "Cada archivo, lo que le falta y en qué programaciones entra.", ""]
    for folder, title, note in PIECE_GROUPS:
        paths = sorted((p for p in users if p.relative_to(ROOT).parts[0] == folder), key=lambda p: str(p))
        if not paths:
            continue
        lines += [f"### {title}", "", note, "", "| Archivo | Por completar | Entra en |", "|---|:---:|---|"]
        for path in paths:
            rel = path.relative_to(ROOT).as_posix()
            pending = piece_pending(path)
            lines.append(f"| [{rel}](../{quote(rel)}) | {pending or '✓'} | {', '.join(sorted(users[path]))} |")
        lines.append("")

    details = [p for p in progs if p.issues or p.warnings]
    if details:
        lines += ["## Qué revisar", ""]
        for prog in details:
            lines += [f'<a name="{prog.id}"></a>', "", f"**{prog.output_name}**", ""]
            lines += [f"- {text[0].upper()}{text[1:]}." for text in prog.issues + prog.warnings] + [""]
    return "\n".join(lines).rstrip() + "\n"


def build(manifest_path: Path, only: list[str] | None = None) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    progs = [make_programacion(manifest, e) for e in manifest["programaciones"]]
    if only:
        unknown = set(only) - {p.id for p in progs}
        if unknown:
            raise ValidationError(f"Programaciones desconocidas: {', '.join(sorted(unknown))}")
        progs = [p for p in progs if p.id in only]
    outputs = {prog.output_name: assemble(manifest, prog) for prog in progs}

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    for old in BUILD_DIR.glob("*.md"):
        old.unlink()
    for name, text in outputs.items():
        (BUILD_DIR / f"{name}.md").write_text(text, encoding="utf-8")
    if not only:
        STATUS_FILE.parent.mkdir(exist_ok=True)
        STATUS_FILE.write_text(status_report(progs), encoding="utf-8")

    report = {
        "version": manifest["documento"]["version"],
        "programaciones": [
            {
                "id": p.id,
                "salida": f"{p.output_name}.pdf",
                "grupos": [g["letra"] for g in p.groups],
                "por_completar": p.pending,
                "revisar": p.issues + p.warnings,
                "piezas": sorted(path.relative_to(ROOT).as_posix() for path in p.used),
            }
            for p in progs
        ],
    }
    (ROOT / "build-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("programaciones", nargs="*", help="Generar solo estas (p. ej. ipe1-gm)")
    parser.add_argument("--manifest", type=Path, default=ROOT / "manifest.yml")
    args = parser.parse_args()
    try:
        report = build(args.manifest, args.programaciones or None)
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for item in report["programaciones"]:
        print(f"  {item['salida']:<20} por completar: {item['por_completar']:>3}   revisar: {len(item['revisar'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
