import unittest

from recipe import export_recipe


class Contract(unittest.TestCase):
    def test_false_fallback_and_zero(self):
        output = export_recipe({"records": [{"x": False}, {"x": 0}, {}, {"x": ""}],
                                "columns": [{"label": "x", "path": ["x"], "fallback": "N"}]})
        self.assertEqual(output, {"columns": ["x"], "rows": [["N"], [0], ["N"], [""]],
                                  "csv": '"x"\n"N"\n0\n"N"\n""\n'})

    def test_null_mode_preserves_false(self):
        output = export_recipe({"records": [{"x": False}],
                                "columns": [{"label": "x", "path": ["x"], "fallback": "N", "fallback_mode": "null"}]})
        self.assertEqual(output["rows"], [[False]])

    def test_csv_escaping(self):
        output = export_recipe({"records": [{"x": 'a,"b\n東京\x00'}],
                                "columns": [{"label": "x", "path": ["x"]}]})
        self.assertEqual(output["csv"], '"x"\n"a,""b\n東京\\0"\n')

    def test_invalid_input(self):
        self.assertEqual(export_recipe({}), {"error": "invalid_recipe"})


if __name__ == "__main__":
    unittest.main()
