#!/usr/bin/env python3
"""Valida y ensambla las programaciones didácticas individuales de IPE.

Cada programación del manifiesto da un Markdown en build/<grupo>.md, que
build-pdf.sh convierte en PDF. Los apartados se resuelven por capas (ver
manifest.yml): grupo → módulo en el ciclo → módulo → ciclo → común.
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
SCHEMA_VERSION = 1

INCLUDE = re.compile(r"^[ \t]*<!--\s*incluir:\s*([a-z0-9][a-z0-9-]*)\s*-->[ \t]*$", re.MULTILINE)
VARIABLE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
FICHA = "<!-- ficha-modulo -->"
ORDINAL = {1: "1.º", 2: "2.º"}

# Abreviatura de cada capa para la tabla de procedencia de docs/estado.md
LAYER_LABELS = {
    "grupo": ("G", "propio del grupo"),
    "modulo-ciclo": ("MC", "del módulo en este ciclo"),
    "modulo": ("M", "del módulo"),
    "ciclo": ("C", "del ciclo"),
    "comun": ("·", "común"),
}


class ValidationError(Exception):
    pass


@dataclass
class Programacion:
    entry: dict[str, Any]
    module: dict[str, Any]
    cycle: dict[str, Any]
    variables: dict[str, str]
    layers: list[tuple[str, Path]]
    origin: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    pending: int = 0
    issues: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.entry["grupo"]

    @property
    def output_name(self) -> str:
        return f"PD-{self.module['corto'].replace(' ', '-')}-{self.id.upper()}"


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
    ids = [p.get("grupo") for p in data["programaciones"]]
    if len(set(ids)) != len(ids) or not all(isinstance(i, str) and re.fullmatch(r"[a-z0-9-]+", i) for i in ids):
        raise ValidationError("Cada programación necesita un «grupo» único en minúsculas (p. ej. 1ga-a)")
    return data


def group_label(entry: dict[str, Any], cycle: dict[str, Any]) -> str:
    label = f"{ORDINAL.get(entry['curso'], str(entry['curso']) + '.º')} {cycle['corto']}"
    return f"{label} {entry['letra']}" if entry.get("letra") else label


def make_programacion(manifest: dict[str, Any], entry: dict[str, Any]) -> Programacion:
    for key in ("grupo", "modulo", "ciclo", "curso", "horas"):
        if entry.get(key) in (None, ""):
            raise ValidationError(f"La programación {entry.get('grupo', '?')} no tiene «{key}»")
    module = manifest["modulos"].get(entry["modulo"])
    cycle = manifest["ciclos"].get(entry["ciclo"])
    if not module or not cycle:
        raise ValidationError(f"{entry['grupo']}: módulo o ciclo no declarado en manifest.yml")
    doc = manifest["documento"]
    weekly = entry.get("horas_semana")
    variables = {
        "centro": doc["centro"],
        "localidad": doc.get("localidad", ""),
        "codigo_centro": str(doc.get("codigo_centro", "")),
        "departamento": doc["departamento"],
        "docente": doc["docente"],
        "curso_academico": doc["curso_academico"],
        "modulo": module["titulo"],
        "modulo_corto": module["corto"],
        "codigo": str(module["codigo"]),
        "horas": str(entry["horas"]),
        "horas_semana": str(weekly) if weekly else "[Horas semanales]",
        "ciclo": cycle["corto"],
        "titulo_ciclo": cycle["titulo"],
        "grado": cycle["grado"],
        "curso": ORDINAL.get(entry["curso"], f"{entry['curso']}.º"),
        "letra": entry.get("letra", ""),
        "grupo": group_label(entry, cycle),
    }
    layers = [
        ("grupo", ROOT / "grupos" / entry["grupo"]),
        ("modulo-ciclo", ROOT / "modulos" / entry["modulo"] / entry["ciclo"]),
        ("modulo", ROOT / "modulos" / entry["modulo"]),
        ("ciclo", ROOT / "ciclos" / entry["ciclo"]),
        ("comun", ROOT / "comun"),
    ]
    return Programacion(entry, module, cycle, variables, layers)


def resolve(prog: Programacion, name: str) -> tuple[str, Path] | None:
    """Primera capa que tiene <name>.md."""
    for layer, folder in prog.layers:
        candidate = folder / f"{name}.md"
        if candidate.is_file():
            return layer, candidate
    return None


def expand(prog: Programacion, text: str, chain: tuple[str, ...]) -> str:
    def include(match: re.Match) -> str:
        name = match.group(1)
        if name in chain:
            raise ValidationError(f"{prog.id}: inclusión circular {' → '.join(chain + (name,))}")
        found = resolve(prog, name)
        if not found:
            prog.warnings.append(f"no existe el fragmento «{name}» en ninguna capa")
            return f"[Fragmento «{name}» por redactar]"
        prog.origin.setdefault(name, found[0])
        return expand(prog, found[1].read_text(encoding="utf-8").strip(), chain + (name,))

    return INCLUDE.sub(include, text)


def substitute(prog: Programacion, text: str) -> str:
    def value(match: re.Match) -> str:
        key = match.group(1)
        if key not in prog.variables:
            prog.warnings.append(f"variable desconocida {{{{{key}}}}}")
            return match.group(0)
        return prog.variables[key]

    return VARIABLE.sub(value, text)


def ficha(prog: Programacion) -> str:
    v = prog.variables
    weekly = f" ({v['horas_semana']} horas semanales)" if prog.entry.get("horas_semana") else " ([Horas semanales])"
    group = f"{v['curso']} curso, grupo {v['letra']}" if v["letra"] else f"{v['curso']} curso"
    return "\n".join([
        f"- **Módulo profesional:** {v['codigo']}. {v['modulo']}",
        f"- **Ciclo formativo:** {v['titulo_ciclo']} ({v['grado'].lower()})",
        f"- **Curso y grupo:** {group}",
        f"- **Duración:** {v['horas']} horas{weekly}",
        f"- **Docente:** {v['docente']}",
        f"- **Departamento:** {v['departamento']}",
        f"- **Curso académico:** {v['curso_academico']}",
    ])


def section_text(prog: Programacion, name: str) -> str:
    found = resolve(prog, name)
    if not found:
        raise ValidationError(
            f"{prog.id}: no existe el apartado «{name}» (búscalo como {name}.md en grupos/, modulos/, ciclos/ o comun/)"
        )
    layer, path = found
    prog.origin[name] = layer
    text = path.read_text(encoding="utf-8").strip()
    headings = re.findall(r"^# +(.+)$", text, flags=re.MULTILINE)
    if len(headings) != 1 or not text.startswith("# "):
        raise ValidationError(f"{path.relative_to(ROOT)}: debe empezar por un único título «# …»")
    if re.match(r"^\d+[.) ]", headings[0]):
        raise ValidationError(f"{path.relative_to(ROOT)}: el título no lleva numeración (la pone la maquetación)")
    text = expand(prog, text, (name,))
    return substitute(prog, text).replace(FICHA, ficha(prog))


def front_matter(manifest: dict[str, Any], prog: Programacion) -> dict[str, Any]:
    doc, v = manifest["documento"], prog.variables
    detail = f"Módulo {v['codigo']} · {v['curso']} {v['ciclo']}" + (f" · Grupo {v['letra']}" if v["letra"] else "")
    return {
        "title": f"Programación Didáctica · {v['modulo']} · {v['grupo']}",
        "lang": "es",
        "cover-title": "Programación Didáctica",
        "cover-subtitle": v["modulo"],
        "cover-detail": detail,
        "teacher": doc["docente"],
        "department": doc["departamento"],
        "institution": doc["centro"],
        "city": doc.get("localidad", ""),
        "academic-year": doc["curso_academico"],
        "version": str(doc["version"]),
        "header-title": f"{v['modulo_corto']} · {v['curso']} {v['ciclo']}" + (f" · Grupo {v['letra']}" if v["letra"] else ""),
        "module-level": 0,
    }


def assemble(manifest: dict[str, Any], prog: Programacion) -> str:
    parts = [section_text(prog, name) for name in manifest["apartados"]]
    source = "\n\n".join(parts)
    # Las marcas de las tablas generadas se comprueban antes de sustituirlas
    prog.issues = structure_issues(source) + check_module(source)
    body = render_planning(source)
    prog.pending = pending_fields(body)
    code = indented_code_lines(body)
    if code:
        prog.warnings.append(f"texto sangrado con 4 espacios (saldrá como código) en {len(code)} líneas")
    meta = yaml.safe_dump(front_matter(manifest, prog), allow_unicode=True, sort_keys=False).strip()
    return table_breaks(normalize_markdown(f"---\n{meta}\n---\n\n{body}")).rstrip() + "\n"


def status_report(manifest: dict[str, Any], progs: list[Programacion]) -> str:
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
    names = list(manifest["apartados"]) + sorted({n for p in progs for n in p.origin} - set(manifest["apartados"]))
    lines += [
        "",
        "## De dónde sale cada apartado",
        "",
        "Lo que diferencia una programación de otra. "
        + ", ".join(f"**{abbr}** {text}" for abbr, text in LAYER_LABELS.values()) + ".",
        "Los fragmentos incluidos con `<!-- incluir: … -->` van al final.",
        "",
        "| Apartado | " + " | ".join(p.id.upper() for p in progs) + " |",
        "|---|" + ":---:|" * len(progs),
    ]
    for name in names:
        row = [LAYER_LABELS[p.origin[name]][0] if name in p.origin else "—" for p in progs]
        lines.append(f"| {name} | " + " | ".join(row) + " |")
    details = [p for p in progs if p.issues or p.warnings]
    if details:
        lines += ["", "## Qué revisar", ""]
        for prog in details:
            lines += [f'<a name="{prog.id}"></a>', "", f"**{prog.variables['modulo_corto']} · {prog.variables['grupo']}**", ""]
            lines += [f"- {text[0].upper()}{text[1:]}." for text in prog.issues + prog.warnings] + [""]
    return "\n".join(lines).rstrip() + "\n"


def build(manifest_path: Path, only: list[str] | None = None) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    progs = [make_programacion(manifest, e) for e in manifest["programaciones"]]
    if only:
        unknown = set(only) - {p.id for p in progs}
        if unknown:
            raise ValidationError(f"Grupos desconocidos: {', '.join(sorted(unknown))}")
        progs = [p for p in progs if p.id in only]
    outputs = {prog.output_name: assemble(manifest, prog) for prog in progs}

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    for old in BUILD_DIR.glob("*.md"):
        old.unlink()
    for name, text in outputs.items():
        (BUILD_DIR / f"{name}.md").write_text(text, encoding="utf-8")
    if not only:
        STATUS_FILE.parent.mkdir(exist_ok=True)
        STATUS_FILE.write_text(status_report(manifest, progs), encoding="utf-8")

    report = {
        "version": manifest["documento"]["version"],
        "programaciones": [
            {
                "grupo": p.id,
                "salida": f"{p.output_name}.pdf",
                "por_completar": p.pending,
                "revisar": p.issues + p.warnings,
                "procedencia": p.origin,
            }
            for p in progs
        ],
    }
    (ROOT / "build-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grupos", nargs="*", help="Generar solo estos grupos (p. ej. 1ga-a)")
    parser.add_argument("--manifest", type=Path, default=ROOT / "manifest.yml")
    args = parser.parse_args()
    try:
        report = build(args.manifest, args.grupos or None)
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for item in report["programaciones"]:
        print(f"  {item['salida']:<24} por completar: {item['por_completar']:>3}   revisar: {len(item['revisar'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
