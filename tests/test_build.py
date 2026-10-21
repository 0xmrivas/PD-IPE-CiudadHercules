import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build  # noqa: E402


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build.py")], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        cls.report = json.loads((ROOT / "build-report.json").read_text(encoding="utf-8"))

    def read(self, name):
        return (ROOT / "build" / f"{name}.md").read_text(encoding="utf-8")

    def test_una_pd_por_modulo(self):
        salidas = {p["id"]: p for p in self.report["programaciones"]}
        self.assertEqual([p["salida"] for p in salidas.values()], ["PD-IPE-I.pdf", "PD-IPE-II-GS.pdf"])
        self.assertEqual(salidas["ipe1"]["grupos"], ["GM A", "GM B", "GS A", "GS B"])
        self.assertEqual(salidas["ipe2-gs"]["grupos"], ["A", "B"])

    def test_portada_y_contextualizacion_de_cada_grupo(self):
        ipe1 = self.read("PD-IPE-I")
        self.assertIn("cover-groups: Grupos GM A, GM B, GS A y GS B", ipe1)
        self.assertIn("| Dato | Grupo GM A | Grupo GM B | Grupo GS A | Grupo GS B |", ipe1)
        self.assertIn("| Turno | Mañana | Mañana |", ipe1)
        self.assertIn("El grupo GM A cuenta con 25 alumnos y alumnas", ipe1)
        self.assertIn("| Formación en empresa (FFEOE) | Del 11/03 al 23/04/2027 · 18 h de IPE I |", ipe1)
        self.assertIn("### Grupo GS B", ipe1)
        self.assertIn("Blue Zone Forum", ipe1)
        self.assertIn("cover-groups: Grupos A y B", self.read("PD-IPE-II-GS"))

    def test_ipe1_lleva_lo_de_los_dos_ciclos(self):
        ipe1, ipe2 = self.read("PD-IPE-I"), self.read("PD-IPE-II-GS")
        for texto in ("Real Decreto 1631/2009", "Real Decreto 1584/2011", "0441 Técnica contable", "0647 Gestión de la documentación"):
            self.assertIn(texto, ipe1)
        self.assertNotIn("Real Decreto 1631/2009", ipe2)
        self.assertIn("## CFGM Gestión Administrativa\n\n### Competencia general del título", ipe1)
        self.assertIn("## CFGS Administración y Finanzas\n\n### Competencia general del título", ipe1)
        # Con un solo ciclo, el fragmento entra tal cual, sin título de ciclo
        self.assertIn("# Competencias y objetivos generales", ipe2)
        self.assertNotIn("## CFGS Administración y Finanzas", ipe2)
        self.assertIn("**Equivalencia en créditos ECTS:** 5 en CFGS Administración y Finanzas", ipe1)
        self.assertIn("**Módulo profesional:** 1710", ipe2)
        self.assertIn("| González Kämerow, Laura | Redactado | 13/10/2026 | 1.0 |", ipe1)
        self.assertNotIn("13/10/2026 | 1.0", ipe2)
        piezas = {p["id"]: set(p["piezas"]) for p in self.report["programaciones"]}
        self.assertTrue({"pd/ipe1/ga/contribucion.md", "pd/ipe1/af/contribucion.md"} <= piezas["ipe1"])
        self.assertIn("ciclos/af/competencia-general.md", piezas["ipe1"] & piezas["ipe2-gs"])
        for text in (ipe1, ipe2):
            self.assertNotIn("{{", text)
            for marca in ("<!-- incluir", "<!-- por-grupo", "<!-- por-ciclo", "<!-- tabla-relacion-ra -->"):
                self.assertNotIn(marca, text)

    def test_un_solo_ciclo_de_una_pd_de_varios(self):
        """Lo que usa el proyecto de prácticas: la PD de IPE I limitada a un grupo de un ciclo."""
        manifest = build.load_manifest(ROOT / "manifest.yml")
        entry = next(e for e in manifest["programaciones"] if e["id"] == "ipe1")
        prog = build.make_programacion(manifest, {**entry, "ciclos": ["af"], "grupos": ["A"]})
        self.assertEqual(prog.variables["ciclo"], "CFGS Administración y Finanzas")
        self.assertEqual(build.resolve(prog, "contribucion"), ROOT / "pd/ipe1/af/contribucion.md")
        self.assertEqual(build.resolve(prog, "normativa-titulo"), ROOT / "ciclos/af/normativa-titulo.md")
        self.assertIn("**Equivalencia en créditos ECTS:** 5\n", build.ficha(prog) + "\n")

    def test_la_capa_pd_manda_sobre_la_comun(self):
        tmp = ROOT / "pd" / "ipe2-gs" / "plan-lector.md"
        self.assertFalse(tmp.exists())
        try:
            tmp.write_text("# Plan lector\n\nTexto exclusivo de segundo.\n", encoding="utf-8")
            build.build(ROOT / "manifest.yml")
            self.assertIn("exclusivo de segundo", self.read("PD-IPE-II-GS"))
            self.assertNotIn("exclusivo de segundo", self.read("PD-IPE-I"))
        finally:
            tmp.unlink(missing_ok=True)
            build.build(ROOT / "manifest.yml")

    def test_apartado_inexistente_es_error(self):
        manifest = (ROOT / "manifest.yml").read_text(encoding="utf-8").replace("  - plan-lector\n", "  - no-existe\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.yml"
            path.write_text(manifest, encoding="utf-8")
            with self.assertRaises(build.ValidationError):
                build.build(path, ["ipe1"])
        build.build(ROOT / "manifest.yml")


if __name__ == "__main__":
    unittest.main()
