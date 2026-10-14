# Programaciones didácticas de IPE · IES Ciudad de Hércules

**Itinerario personal para la empleabilidad I y II · Curso 2026/2027**
Docente: Laura González Kåmerow · Departamento de Administración

Cada grupo tiene su propia programación. Los PDF se generan solos con cada cambio:

| Módulo | Grupo | PDF |
|---|---|---|
| IPE I (1709) | 1.º CFGM Gestión Administrativa A | [PD-IPE-I-1GA-A.pdf](programaciones/PD-IPE-I-1GA-A.pdf) |
| IPE I (1709) | 1.º CFGM Gestión Administrativa B | [PD-IPE-I-1GA-B.pdf](programaciones/PD-IPE-I-1GA-B.pdf) |
| IPE I (1709) | 1.º CFGS Administración y Finanzas A | [PD-IPE-I-1AF-A.pdf](programaciones/PD-IPE-I-1AF-A.pdf) |
| IPE I (1709) | 1.º CFGS Administración y Finanzas B | [PD-IPE-I-1AF-B.pdf](programaciones/PD-IPE-I-1AF-B.pdf) |
| IPE II (1710) | 2.º CFGS Administración y Finanzas | [PD-IPE-II-2AF.pdf](programaciones/PD-IPE-II-2AF.pdf) |

Lo que falta por completar y lo que no cuadra está en [docs/estado.md](docs/estado.md).

## Cómo se organiza el contenido

Todas las programaciones tienen el mismo índice (el de las PD del centro), pero
cada apartado se escribe **una sola vez, en la capa que le corresponde**:

| Carpeta | Afecta a | Ejemplos |
|---|---|---|
| `grupos/<grupo>/` | solo ese grupo | características del grupo, cualquier apartado que cambie |
| `modulos/<módulo>/<ciclo>/` | ese módulo en ese ciclo | contribución de IPE I a los objetivos de GA |
| `modulos/<módulo>/` | ese módulo en cualquier ciclo | RA, criterios, UD, evaluación |
| `ciclos/<ciclo>/` | cualquier módulo del ciclo | normativa del título, plan formativo |
| `comun/` | todas | introducción, metodología, diversidad, plan lector |

Al generar una PD, cada apartado se busca de arriba abajo y **entra el primero
que exista**. Por eso los grupos A y B parten del mismo contenido y basta con
copiar un archivo a `grupos/1ga-b/` y cambiarlo para que esa PD sea distinta.
La tabla «De dónde sale cada apartado» de [docs/estado.md](docs/estado.md)
muestra qué tiene cada grupo de propio.

Dentro de cualquier archivo:

- `<!-- incluir: fragmento -->` inserta `fragmento.md`, buscado con la misma cascada.
- `{{grupo}}`, `{{ciclo}}`, `{{modulo}}`, `{{codigo}}`, `{{horas}}`, `{{docente}}`…
  se sustituyen por los datos de `manifest.yml`.
- `<!-- ficha-modulo -->` pone la ficha del módulo (código, ciclo, grupo, horas, docente).
- `<!-- tabla-relacion-ra -->` genera la relación RA–criterios–UD a partir de la
  tabla de unidades didácticas y de la de criterios.
- Lo que va entre corchetes, `[Así]`, cuenta como pendiente y sale en gris en el PDF.

## Generar en local

```bash
python3 -m pip install -r requirements.txt   # PyYAML
python3 -m unittest discover -s tests
scripts/build-pdf.sh                          # todas (Pandoc >= 3.11 y Typst >= 0.14)
scripts/build-pdf.sh 1ga-a                    # solo un grupo
```

Los PDF quedan en `dist/`; en GitHub, la action los publica en `programaciones/`.

El motor (validación, tablas generadas, filtros de maquetación) procede del
repositorio de la PD del Departamento de Informática del IES Rafael Alberti.
