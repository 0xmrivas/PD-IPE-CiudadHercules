"""Correcciones de Markdown al ensamblar (heredadas del repositorio del IES Rafael Alberti).

Arreglan formas de escribir que Pandoc interpretaría mal: listas con letras,
listas pegadas con sangría, títulos sin línea en blanco y <hr> en tablas.
"""

from __future__ import annotations

import re


LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)]|[a-zA-Z][.)])\s")


def indented_code_lines(markdown: str) -> list[int]:
    """Líneas que Markdown convertirá en bloque de código por ir sangradas.

    Un párrafo que empieza con 4 espacios (o un tabulador) tras una línea en
    blanco es código, salvo que continúe una lista. Pasa al pegar listas desde
    otros documentos y sale en letra monoespaciada en el PDF.
    """
    found: list[int] = []
    lines = markdown.splitlines()
    previous = ""   # última línea no vacía
    blank = True
    inside_fence = False
    for number, line in enumerate(lines, start=1):
        if line.lstrip().startswith("```"):
            inside_fence = not inside_fence
        if inside_fence or not line.strip():
            blank = blank or not line.strip()
            continue
        indented = line.startswith("    ") or line.startswith("\t")
        continues_list = LIST_ITEM.match(previous) or previous.startswith(("    ", "\t"))
        # Tras una línea en blanco o un título, lo sangrado empieza un bloque de código
        after_break = blank or re.match(r"^#{1,6}\s", previous)
        if indented and after_break and not continues_list:
            found.append(number)
        previous, blank = line, False
    return found



LETTER_ITEM = re.compile(r"^([a-zñ])([.)])\s+(.*)$")
# Bloque sangrado que en realidad es una lista (letras, viñetas) o un título
LISTISH = re.compile(r"^(?:[a-zñ][.)]|[-*+•·▪]|#{1,6})\s")
# Espacio no separable (lo mete Word al copiar) tras "##" o una viñeta:
# Markdown ya no lo reconoce como título o lista.
ODD_SPACE_MARKER = re.compile(r"^(\s*(?:#{1,6}|[-*+]))[\u00a0\u2000-\u200b]+")
ATX_HEADING = re.compile(r"^#{1,6}\s")


def normalize_markdown(markdown: str) -> str:
    """Corrige, al ensamblar, formas de escribir que Markdown interpreta mal.

    - Listas con letras (a), b), ñ)…): Markdown las renumera seguidas y no
      conoce la ñ, así que "b) o) p)" salía como "b) c) d)". Cada elemento
      pasa a ser un párrafo que empieza por la letra en negrita, tal cual se
      escribió; sus sublistas sangradas se sacan un nivel para que sigan
      siendo listas.
    - Títulos pegados a la línea anterior: sin línea en blanco delante,
      "## Objetivos" salía como texto.
    - Espacio no separable tras "##" o una viñeta: se cambia por uno normal.
    - Listas pegadas con sangría (Markdown las convertía en código): si un
      bloque sangrado solo tiene elementos de lista o títulos, se le quita la
      sangría. Si parece código de verdad, se deja (y la validación avisa).
    """
    markdown = dedent_list_blocks(markdown)
    out: list[str] = []
    inside_fence = False
    in_letter_item = False
    for line in markdown.split("\n"):
        if line.lstrip().startswith("```"):
            inside_fence = not inside_fence
        if inside_fence:
            out.append(line)
            continue
        line = ODD_SPACE_MARKER.sub(r"\1 ", line)
        letter = LETTER_ITEM.match(line)
        if letter:
            if out and out[-1].strip():
                out.append("")
            out.append(f"**{letter.group(1)}{letter.group(2)}** {letter.group(3)}")
            in_letter_item = True
            continue
        if in_letter_item and line.strip():
            if line.startswith(("    ", "\t")):
                # Sublista del elemento: se saca un nivel, detrás de una línea en blanco
                if out and out[-1].strip() and not out[-1].lstrip().startswith(("-", "*", "+")):
                    out.append("")
                out.append(line[4:] if line.startswith("    ") else line[1:])
                continue
            if out and not out[-1].strip():
                in_letter_item = False
        if ATX_HEADING.match(line) and out and out[-1].strip():
            out.append("")
        out.append(line)
    return "\n".join(out)


def indented_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Rangos [inicio, fin) de los bloques que Markdown tomará como código sangrado."""
    blocks: list[tuple[int, int]] = []
    starts = {number - 1 for number in indented_code_lines("\n".join(lines))}
    for start in sorted(starts):
        end = start
        while end < len(lines) and (lines[end].startswith(("    ", "\t")) or not lines[end].strip()):
            end += 1
        blocks.append((start, end))
    return blocks


def dedent_list_blocks(markdown: str) -> str:
    lines = markdown.split("\n")
    for start, end in indented_blocks(lines):
        content = [line.strip() for line in lines[start:end] if line.strip()]
        if not content or not all(LISTISH.match(line) for line in content):
            continue
        for i in range(start, end):
            line = lines[i][4:] if lines[i].startswith("    ") else lines[i].lstrip("\t")
            lines[i] = re.sub(r"^[•·▪]\s", "- ", line.replace("\t", " "))
    return "\n".join(lines)


def table_breaks(markdown: str) -> str:
    """Pandoc descarta lo que sigue a un <hr> dentro de una celda: se cambia por <br>."""
    return "\n".join(
        re.sub(r"<hr\s*/?>", "<br/>", line) if line.lstrip().startswith("|") else line
        for line in markdown.splitlines()
    )

