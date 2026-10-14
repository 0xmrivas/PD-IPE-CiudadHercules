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

    def test_una_pd_por_grupo(self):
        salidas = [p["salida"] for p in self.report["programaciones"]]
        self.assertEqual(salidas, ["PD-IPE-I-1GA-A.pdf", "PD-IPE-I-1GA-B.pdf", "PD-IPE-I-1AF-A.pdf",
                                   "PD-IPE-I-1AF-B.pdf", "PD-IPE-II-2AF.pdf"])

    def test_datos_del_grupo_y_del_ciclo(self):
        ga_a, af_b, af2 = self.read("PD-IPE-I-1GA-A"), self.read("PD-IPE-I-1AF-B"), self.read("PD-IPE-II-2AF")
        self.assertIn("Grupo A", ga_a)
        self.assertIn("1.º CFGM Gestión Administrativa A", ga_a)
        self.assertIn("Real Decreto 1631/2009", ga_a)
        self.assertNotIn("Real Decreto 1584/2011", ga_a)
        self.assertIn("Real Decreto 1584/2011", af_b)
        self.assertIn("**Módulo profesional:** 1710", af2)
        self.assertIn("Laura González Kåmerow", af2)
        for text in (ga_a, af_b, af2):
            self.assertNotIn("{{", text)
            self.assertNotIn("<!-- incluir", text)
            self.assertNotIn("<!-- tabla-relacion-ra -->", text)

    def test_la_capa_de_grupo_manda(self):
        procedencia = {p["grupo"]: p["procedencia"] for p in self.report["programaciones"]}
        self.assertEqual(procedencia["1ga-a"]["grupo"], "grupo")
        self.assertEqual(procedencia["1ga-a"]["contribucion"], "modulo-ciclo")
        self.assertEqual(procedencia["1ga-a"]["introduccion"], "comun")
        tmp = ROOT / "grupos" / "1ga-b" / "metodologia.md"
        self.assertFalse(tmp.exists())
        try:
            tmp.write_text("# Metodología\n\nTexto exclusivo del grupo B.\n", encoding="utf-8")
            build.build(ROOT / "manifest.yml", ["1ga-a", "1ga-b"])
            self.assertIn("exclusivo del grupo B", self.read("PD-IPE-I-1GA-B"))
            self.assertNotIn("exclusivo del grupo B", self.read("PD-IPE-I-1GA-A"))
        finally:
            tmp.unlink(missing_ok=True)
            build.build(ROOT / "manifest.yml")

    def test_apartado_inexistente_es_error(self):
        manifest = (ROOT / "manifest.yml").read_text(encoding="utf-8").replace("  - plan-lector\n", "  - no-existe\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.yml"
            path.write_text(manifest, encoding="utf-8")
            with self.assertRaises(build.ValidationError):
                build.build(path, ["1ga-a"])
        build.build(ROOT / "manifest.yml")


if __name__ == "__main__":
    unittest.main()
