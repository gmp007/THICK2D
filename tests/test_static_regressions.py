from pathlib import Path
import ast
import configparser
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StaticRegressionTests(unittest.TestCase):
    def test_console_script_uses_thick2d_distribution_name(self):
        source = (ROOT / "src" / "thick2d").read_text(encoding="utf-8")
        tree = ast.parse(source)
        constants = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}

        self.assertIn("thick2d", constants)
        self.assertNotIn("SMATool", constants)

    def test_console_script_imports_project_helper(self):
        source = (ROOT / "src" / "thick2d").read_text(encoding="utf-8")

        self.assertIn("from thick2d_read_write import", source)
        self.assertNotIn("from read_write import", source)

    def test_input_templates_reference_thick2d(self):
        template_paths = ROOT.glob("ThicknessDatabase/*Database/*/thick2dtool.in")
        for path in template_paths:
            with self.subTest(path=path):
                source = path.read_text(encoding="utf-8")
                self.assertIn("THICK2D package input control", source)
                self.assertNotIn("SMATool package input control", source)

    def test_setup_installs_helper_modules(self):
        parser = configparser.ConfigParser()
        parser.read(ROOT / "setup.cfg")
        py_modules = parser.get("options", "py_modules")

        self.assertIn("read_write", py_modules)
        self.assertIn("thick2d_read_write", py_modules)


if __name__ == "__main__":
    unittest.main()
