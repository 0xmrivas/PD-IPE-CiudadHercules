#!/usr/bin/env bash
# Genera un PDF por programación con Pandoc + Typst:
#
#   dist/PD-IPE-I.pdf (GM y GS), dist/PD-IPE-II-GS.pdf
#
# Uso: scripts/build-pdf.sh            todas
#      scripts/build-pdf.sh ipe1       solo esa programación
#
# Requisitos: Python 3 con PyYAML, Pandoc >= 3.11 y Typst >= 0.14.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TYPST_DIR="$ROOT/typst"
BUILD="$ROOT/build"
DIST="$ROOT/dist"

command -v pandoc >/dev/null || { echo "Falta pandoc (https://pandoc.org)"; exit 1; }
command -v typst  >/dev/null || { echo "Falta typst (https://typst.app)"; exit 1; }

# 1. Validar y ensamblar: build.py escribe un Markdown por programación en build/
python3 "$ROOT/scripts/build.py" "$@"

# 2. Cada Markdown → Typst → PDF. Los .typ se quedan en build/ para depurar.
rm -rf "$DIST" "$BUILD"/*.typ
mkdir -p "$DIST"
cp "$TYPST_DIR/portada.typ" "$BUILD/"

echo "PDF generados:"
for md in "$BUILD"/PD-*.md; do
  typ="${md%.md}.typ"
  out="$DIST/$(basename "${md%.md}").pdf"
  pandoc "$md" \
    --from=markdown+footnotes+pipe_tables+raw_attribute+fenced_divs+yaml_metadata_block \
    --to=typst \
    --lua-filter="$TYPST_DIR/filtros.lua" \
    --template="$TYPST_DIR/plantilla.typ" \
    --standalone \
    -o "$typ"
  # Sin etiquetas de accesibilidad: multiplican el peso del PDF.
  typst compile --no-pdf-tags --root "$BUILD" --font-path "$TYPST_DIR/fuentes" "$typ" "$out"
  echo "  ${out#$ROOT/}"
done
