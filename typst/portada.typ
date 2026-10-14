// ============================================================
// PORTADA de las programaciones · IES Ciudad de Hércules
//
// Toma los elementos del banner del centro: fondo marino, franjas
// horizontales en azul y gris pizarra y la silueta del castillo sobre
// las líneas de agua. Todo vectorial, sin imágenes.
// ============================================================

#let azul = rgb("#0093DD")
#let marino = rgb("#002954")
#let pizarra = rgb("#5E6B78")
#let celeste = rgb("#9FD4F2")

// Silueta del castillo (coordenadas en una caja de 100 × 40)
#let castillo(ancho, color) = {
  let u = ancho / 100
  let puntos = (
    (0, 40), (0, 31), (7, 31), (7, 28), (19, 28), (19, 25), (33, 25), (33, 22),
    (50, 22), (50, 18), (59, 18), (59, 7), (62, 7), (62, 4), (64.5, 1.5), (67, 4),
    (67, 7), (71, 7), (71, 18), (79, 18), (79, 26), (89, 26), (89, 32), (100, 32), (100, 40),
  )
  box(width: ancho, height: 40 * u, polygon(fill: color, ..puntos.map(((x, y)) => (x * u, y * u))))
}

// Líneas de agua bajo la silueta, cada vez más cortas
#let agua(ancho, color) = stack(
  spacing: ancho * 0.022,
  ..(1, 0.82, 0.62, 0.4).map(f => align(center, rect(width: ancho * f, height: ancho * 0.012, fill: color))),
)

#let portada(
  titulo: [Programación Didáctica],
  subtitulo: none,           // el módulo
  detalle: none,             // código y ciclo
  grupos: none,              // «Grupos A y B»
  docente: none,
  departamento: [],
  centro: [],
  curso: [],
  fuente: ("Source Sans 3",),
) = page(
  margin: 0cm,
  header: none,
  footer: none,
  fill: marino,
  background: {
    // Franjas del banner: arriba gris y azul, abajo azul y gris
    place(top + left, dy: 1.1cm, rect(width: 72%, height: 0.32cm, fill: pizarra))
    place(top + left, dy: 1.75cm, rect(width: 88%, height: 0.32cm, fill: azul))
    place(bottom + right, dy: -1.75cm, rect(width: 62%, height: 0.32cm, fill: azul))
    place(bottom + right, dy: -1.1cm, rect(width: 76%, height: 0.32cm, fill: pizarra))
    // Castillo y agua, a la derecha, en tonos que no compiten con el texto
    place(bottom + right, dx: -1.6cm, dy: -4.6cm, stack(
      spacing: 0.35cm,
      castillo(9cm, azul.transparentize(55%)),
      agua(9cm, celeste.transparentize(70%)),
    ))
  },
)[
  #set text(font: fuente, fill: white, lang: "es")
  #let suave = white.transparentize(28%)
  #let etiqueta(body) = text(size: 10pt, weight: "semibold", tracking: 0.14em, fill: celeste, upper(body))

  #pad(left: 2.3cm, right: 3.2cm, top: 3.6cm, bottom: 3.4cm, block(height: 100%)[
    #etiqueta(centro)
    #v(1.1cm)
    #block({
      set par(leading: 0.5em)
      text(size: 44pt, weight: "bold", titulo)
    })
    #v(0.7cm)
    #line(length: 2.4cm, stroke: 3.5pt + azul)
    #v(0.7cm)
    #if subtitulo != none {
      block({
        set par(leading: 0.45em)
        text(size: 26pt, weight: "bold", subtitulo)
      })
    }
    #if detalle != none {
      v(0.35cm)
      text(size: 13.5pt, fill: suave, detalle)
    }
    #if grupos != none {
      v(0.5cm)
      box(fill: azul, inset: (x: 0.35cm, y: 0.2cm), radius: 2pt,
        text(size: 12pt, weight: "bold", tracking: 0.08em, upper(grupos)))
    }
    #v(1fr)
    #if docente != none {
      etiqueta[Docente]
      v(0.1cm)
      text(size: 16pt, weight: "semibold", docente)
      v(0.6cm)
    }
    #etiqueta[Curso académico]
    #v(0.1cm)
    #text(size: 22pt, weight: "bold", curso)
    #v(0.25cm)
    #text(size: 11pt, fill: suave, departamento)
  ])
]
