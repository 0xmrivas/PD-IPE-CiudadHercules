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

    def test_una_pd_por_modulo_y_nivel(self):
        salidas = [p["salida"] for p in self.report["programaciones"]]
        self.assertEqual(salidas, ["PD-IPE-I-GM.pdf", "PD-IPE-I-GS.pdf", "PD-IPE-II-GS.pdf"])
        for p in self.report["programaciones"]:
            self.assertEqual(p["grupos"], ["A", "B"])

    def test_portada_y_contextualizacion_de_cada_grupo(self):
        gm = self.read("PD-IPE-I-GM")
        self.assertIn("cover-groups: Grupos A y B", gm)
        self.assertIn("| Dato | Grupo A | Grupo B |", gm)
        self.assertIn("| N.º de alumnado | 25 | 26 |", gm)
        self.assertIn("| Turno | Mañana | Mañana |", gm)
        self.assertIn("El grupo A cuenta con 25 alumnos y alumnas", gm)
        self.assertIn("El grupo B cuenta con 26 alumnos y alumnas", gm)
        self.assertIn("Blue Zone Forum", gm)
        self.assertNotIn("Blue Zone Forum", self.read("PD-IPE-I-GS"))

    def test_ipe1_comparte_modulo_y_cambia_el_ciclo(self):
        gm, gs, ipe2 = self.read("PD-IPE-I-GM"), self.read("PD-IPE-I-GS"), self.read("PD-IPE-II-GS")
        self.assertIn("Real Decreto 1631/2009", gm)
        self.assertNotIn("Real Decreto 1584/2011", gm)
        self.assertIn("Real Decreto 1584/2011", gs)
        self.assertIn("**Módulo profesional:** 1710", ipe2)
        self.assertIn("| González Kämerow, Laura | Redactado | 13/10/2026 | 1.0 |", gm)
        self.assertNotIn("13/10/2026 | 1.0", ipe2)
        piezas = {p["id"]: set(p["piezas"]) for p in self.report["programaciones"]}
        self.assertIn("modulos/ipe1/resultados.md", piezas["ipe1-gm"] & piezas["ipe1-gs"])
        self.assertIn("pd/ipe1-gm/contribucion.md", piezas["ipe1-gm"] - piezas["ipe1-gs"])
        for text in (gm, gs, ipe2):
            self.assertNotIn("{{", text)
            self.assertNotIn("<!-- incluir", text)
            self.assertNotIn("<!-- por-grupo", text)
            self.assertNotIn("<!-- tabla-relacion-ra -->", text)

    def test_la_capa_pd_manda_sobre_la_comun(self):
        tmp = ROOT / "pd" / "ipe1-gs" / "metodologia.md"
        self.assertFalse(tmp.exists())
        try:
            tmp.write_text("# Metodología\n\nTexto exclusivo del superior.\n", encoding="utf-8")
            build.build(ROOT / "manifest.yml", ["ipe1-gm", "ipe1-gs"])
            self.assertIn("exclusivo del superior", self.read("PD-IPE-I-GS"))
            self.assertNotIn("exclusivo del superior", self.read("PD-IPE-I-GM"))
        finally:
            tmp.unlink(missing_ok=True)
            build.build(ROOT / "manifest.yml")

    def test_apartado_inexistente_es_error(self):
        manifest = (ROOT / "manifest.yml").read_text(encoding="utf-8").replace("  - plan-lector\n", "  - no-existe\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.yml"
            path.write_text(manifest, encoding="utf-8")
            with self.assertRaises(build.ValidationError):
                build.build(path, ["ipe1-gm"])
        build.build(ROOT / "manifest.yml")


if __name__ == "__main__":
    unittest.main()
