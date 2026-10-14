// ============================================================
// PLANTILLA TYPST — programaciones didácticas de IPE
// IES Ciudad de Hércules
//
// Pandoc la rellena con cada build/PD-*.md (ver scripts/build-pdf.sh).
// Estructura: cada «#» es un apartado (página nueva, etiqueta y título);
// «##», «###»… son subapartados numerados 1.1, 1.1.1…
//
// Criterio de estilo, el mismo de la web del centro: marino para los
// títulos, azul solo como acento (números, filetes, etiquetas). Nada de
// bloques de color salvo en la portada.
// ============================================================

// ---------- Paleta (ciudaddehercules.es) ----------
#let azul = rgb("#0093DD")      // acento institucional
#let enlace = rgb("#006FA8")    // azul con contraste suficiente para texto
#let marino = rgb("#002954")    // títulos
#let tinta = rgb("#1F2430")     // texto
#let gris = rgb("#5E6B78")      // metadatos, cabecera, pie (gris pizarra del banner)
#let filete = rgb("#DCE3EA")    // líneas finas
#let celeste = rgb("#EAF5FC")   // fondos muy suaves (cabecera de tabla, citas)
#let fuente = ("Source Sans 3",)

// ---------- Definiciones que espera el writer typst de Pandoc ----------
#let horizontalrule = { v(0.4em); align(center, line(length: 25%, stroke: 0.6pt + filete)); v(0.4em) }
#let horizontalRule = horizontalrule
#let divider() = horizontalrule
#set terms(hanging-indent: 1.5em)

// ============================================================
// PORTADA
// ============================================================
#import "portada.typ": portada
#portada(
  titulo: [$if(cover-title)$$cover-title$$else$Programación Didáctica$endif$],
  subtitulo: $if(cover-subtitle)$[$cover-subtitle$]$else$none$endif$,
  detalle: $if(cover-detail)$[$cover-detail$]$else$none$endif$,
  grupos: $if(cover-groups)$[$cover-groups$]$else$none$endif$,
  docente: $if(teacher)$[$teacher$]$else$none$endif$,
  departamento: [$department$],
  centro: [$institution$],
  curso: [$academic-year$],
  fuente: fuente,
)

// ============================================================
// CONFIGURACIÓN GLOBAL
// ============================================================
#set text(font: fuente, size: 10.5pt, fill: tinta, lang: "es", region: "ES")
#set par(justify: true, leading: 0.68em, spacing: 1em)
#set strong(delta: 200)
#set heading(numbering: "1.1")

// Apartado vigente en la página, para la cabecera
#let apartado-actual() = {
  let aqui = query(heading.where(level: 1)).filter(h => h.location().page() == here().page())
  let previos = query(selector(heading.where(level: 1)).before(here()))
  if aqui.len() > 0 { aqui.first().body } else if previos.len() > 0 { previos.last().body }
}

#set page(
  paper: "a4",
  margin: (top: 2.7cm, bottom: 2.5cm, x: 2.4cm),
  header: context {
    set text(size: 8pt, fill: gris, tracking: 0.02em)
    grid(
      columns: (auto, 1fr),
      column-gutter: 1cm,
      upper[$header-title$],
      align(right, box(apartado-actual())),
    )
    v(-0.35em)
    line(length: 100%, stroke: 0.4pt + filete)
  },
  footer: context {
    set text(size: 8pt, fill: gris)
    grid(
      columns: (1fr, auto),
      [$institution$ · $department$ · Curso $academic-year$],
      text(fill: marino, weight: "semibold", counter(page).display()),
    )
  },
)

// ---------- Encabezados ----------
#let numero(it, color: azul) = if it.numbering != none {
  text(fill: color, counter(heading).display(it.numbering)); h(0.7em)
}

#show heading: set text(hyphenate: false, fill: marino)
#show heading: set par(justify: false, leading: 0.4em)

#show heading: it => {
  let l = it.level
  if l == 1 {
    pagebreak(weak: true)
    v(1.2cm)
    block(width: 100%, below: 1.1cm, {
      text(size: 10pt, weight: "semibold", fill: azul, tracking: 0.1em,
        upper[Apartado #counter(heading).display(it.numbering)])
      v(0.25cm)
      text(size: 24pt, weight: "bold", it.body)
      v(0.1cm)
      line(length: 1.6cm, stroke: 2pt + azul)
    })
  } else if l == 2 {
    block(above: 1.8em, below: 0.8em, sticky: true, text(size: 14pt, weight: "bold")[#numero(it)#it.body])
  } else if l == 3 {
    block(above: 1.4em, below: 0.65em, sticky: true, text(size: 11.5pt, weight: "bold")[#numero(it)#it.body])
  } else {
    block(above: 1.2em, below: 0.55em, sticky: true, text(size: 10.5pt, weight: "bold")[#numero(it, color: gris)#it.body])
  }
}

// ---------- Tablas ----------
#show figure.where(kind: table): set block(breakable: true)
#show figure.where(kind: table): set align(left)
#show figure.where(kind: table): set figure.caption(position: top)
#show figure.caption.where(kind: table): it => align(left, text(
  size: 8.5pt, weight: "bold", fill: gris, tracking: 0.04em, upper(it.body)))
#set table(
  stroke: (_, y) => (
    top: if y == 0 { 0.8pt + marino } else { 0.4pt + filete },
    bottom: 0.8pt + marino,
  ),
  inset: (x: 6pt, y: 5.5pt),
  fill: (_, y) => if y == 0 { celeste },
)
#show table: set text(size: 8.8pt)
#show table: set par(justify: false, leading: 0.5em)
#show table.cell.where(y: 0): set text(weight: "bold", size: 8.5pt, fill: marino)

// ---------- Otros elementos ----------
#set list(indent: 0.4em, body-indent: 0.6em, marker: ([•], [–], [·]).map(m => text(fill: azul, m)))
#set enum(indent: 0.4em, body-indent: 0.6em)
#show link: it => text(fill: enlace, it)
#show quote.where(block: true): it => block(
  width: 100%, inset: (left: 0.7cm, rest: 0.35cm),
  stroke: (left: 2pt + azul), fill: celeste, it.body,
)
#show raw.where(block: false): box.with(fill: luma(244), inset: (x: 2pt), outset: (y: 2pt), radius: 2pt)
#show raw: set text(size: 9pt)
#show footnote.entry: set text(size: 8.5pt)

// ============================================================
// ÍNDICE
// ============================================================
#counter(page).update(1)
#page(header: none)[
  #v(0.6cm)
  #text(size: 24pt, weight: "bold", fill: marino)[Índice]
  #v(0.1cm)
  #line(length: 1.6cm, stroke: 2pt + azul)
  #v(0.5cm)
  #set text(size: 9.5pt)
  #set par(leading: 0.5em)
  #set outline.entry(fill: box(width: 1fr, repeat(text(fill: filete)[.], gap: 0.3em)))
  #show outline.entry.where(level: 1): it => {
    v(0.7em, weak: true)
    text(weight: "bold", fill: marino, it)
  }
  #outline(title: none, depth: 2, indent: auto)
]

// ============================================================
// CUERPO (lo inyecta Pandoc)
// ============================================================
$for(header-includes)$
$header-includes$
$endfor$

$body$
