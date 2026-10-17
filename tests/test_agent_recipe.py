import unittest
from recipe import export_recipe


class TestBasicExport(unittest.TestCase):
    def test_single_column_single_row(self):
        payload = {
            "records": [{"name": "Alice", "age": 30}],
            "columns": [{"label": "name", "path": ["name"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["columns"], ["name"])
        self.assertEqual(result["rows"], [["Alice"]])
        self.assertEqual(result["csv"], '"name"\n"Alice"\n')


class TestCSVFormatting(unittest.TestCase):
    def test_strings_quoted_and_doubled(self):
        payload = {
            "records": [{"s": 'a"b'}],
            "columns": [{"label": "s", "path": ["s"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["csv"], '"s"\n"a""b"\n')

    def test_null_becomes_empty(self):
        payload = {
            "records": [{"x": None}],
            "columns": [{"label": "x", "path": ["x"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["csv"], '"x"\n\n')

    def test_booleans_lowercase(self):
        payload = {
            "records": [{"a": True, "b": False}],
            "columns": [
                {"label": "a", "path": ["a"]},
                {"label": "b", "path": ["b"]},
            ],
        }
        result = export_recipe(payload)
        self.assertEqual(result["csv"], '"a","b"\ntrue,false\n')

    def test_integers_decimal(self):
        payload = {
            "records": [{"n": -42}],
            "columns": [{"label": "n", "path": ["n"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["csv"], '"n"\n-42\n')

    def test_nul_escaped_as_backslash_zero(self):
        payload = {
            "records": [{"s": "a\x00b"}],
            "columns": [{"label": "s", "path": ["s"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["csv"], '"s"\n"a\\0b"\n')

    def test_lf_after_every_row(self):
        payload = {
            "records": [{"x": 1}, {"x": 2}],
            "columns": [{"label": "x", "path": ["x"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["csv"], '"x"\n1\n2\n')


class TestPathTraversal(unittest.TestCase):
    def test_nested_object_path(self):
        payload = {
            "records": [{"a": {"b": {"c": 7}}}],
            "columns": [{"label": "c", "path": ["a", "b", "c"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [[7]])

    def test_array_index_path(self):
        payload = {
            "records": [{"a": [10, 20, 30]}],
            "columns": [{"label": "a1", "path": ["a", 1]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [[20]])

    def test_missing_key_returns_null(self):
        payload = {
            "records": [{"a": 1}],
            "columns": [{"label": "missing", "path": ["nope"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [[None]])

    def test_out_of_range_index_returns_null(self):
        payload = {
            "records": [{"a": [1]}],
            "columns": [{"label": "a", "path": ["a", 5]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [[None]])

    def test_traversal_through_null_returns_null(self):
        payload = {
            "records": [{"a": None}],
            "columns": [{"label": "a", "path": ["a", "b"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [[None]])

    def test_empty_path_returns_whole_record_and_is_non_scalar(self):
        payload = {
            "records": [{"a": 1}],
            "columns": [{"label": "whole", "path": []}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "non_scalar"})


class TestNumberValidation(unittest.TestCase):
    def test_float_rejected_unsupported_number(self):
        payload = {
            "records": [{"a": 1.5}],
            "columns": [{"label": "a", "path": ["a"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "unsupported_number"})

    def test_large_integer_rejected(self):
        payload = {
            "records": [{"a": 9007199254740992}],
            "columns": [{"label": "a", "path": ["a"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "unsupported_number"})

    def test_negative_large_integer_rejected(self):
        payload = {
            "records": [{"a": -9007199254740992}],
            "columns": [{"label": "a", "path": ["a"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "unsupported_number"})

    def test_boundary_integer_ok(self):
        payload = {
            "records": [{"a": 9007199254740991}],
            "columns": [{"label": "a", "path": ["a"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [[9007199254740991]])

    def test_nested_float_rejected(self):
        payload = {
            "records": [{"a": {"b": [1.5]}}],
            "columns": [{"label": "x", "path": ["a", "b", 0]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "unsupported_number"})


class TestShapeValidation(unittest.TestCase):
    def test_missing_records(self):
        result = export_recipe({"columns": []})
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_records_not_list(self):
        result = export_recipe({"records": {}, "columns": []})
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_missing_columns(self):
        result = export_recipe({"records": []})
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_columns_not_list(self):
        result = export_recipe({"records": [], "columns": {}})
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_column_missing_label(self):
        result = export_recipe({"records": [], "columns": [{"path": ["a"]}]})
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_column_missing_path(self):
        result = export_recipe({"records": [], "columns": [{"label": "a"}]})
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_empty_label_rejected(self):
        result = export_recipe({"records": [], "columns": [{"label": "", "path": []}]})
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_label_too_long_rejected(self):
        result = export_recipe(
            {"records": [], "columns": [{"label": "x" * 129, "path": []}]}
        )
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_label_non_string_rejected(self):
        result = export_recipe({"records": [], "columns": [{"label": 5, "path": []}]})
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_path_not_list(self):
        result = export_recipe(
            {"records": [], "columns": [{"label": "a", "path": "a"}]}
        )
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_path_segment_type_invalid(self):
        result = export_recipe(
            {"records": [], "columns": [{"label": "a", "path": [True]}]}
        )
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_path_segment_float_rejected(self):
        result = export_recipe(
            {"records": [], "columns": [{"label": "a", "path": [1.5]}]}
        )
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_path_too_long(self):
        result = export_recipe(
            {"records": [], "columns": [{"label": "a", "path": [0] * 17}]}
        )
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_negative_path_index_rejected(self):
        result = export_recipe(
            {"records": [{"a": [1, 2]}], "columns": [{"label": "a", "path": ["a", -1]}]}
        )
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_float_in_unused_payload_key_rejected(self):
        payload = {"records": [], "columns": [], "meta": 1.5}
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "unsupported_number"})

    def test_multibyte_input_counts_as_bytes_not_chars(self):
        # 200000 three-byte chars = 600000 bytes; under char-count this is
        # 200000, under byte-count it is 600000 (still under 1 MiB). Use a
        # value sized to straddle the boundary.
        record = {"s": "\u4e2d" * 350000}  # 350000 chars = 1050000 bytes
        payload = {"records": [record], "columns": [{"label": "s", "path": ["s"]}]}
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "limit_exceeded"})

    def test_fallback_mode_invalid(self):
        result = export_recipe(
            {
                "records": [],
                "columns": [
                    {"label": "a", "path": ["a"], "fallback": "x", "fallback_mode": "bogus"}
                ],
            }
        )
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_more_than_32_columns(self):
        cols = [{"label": "c%d" % i, "path": ["a"]} for i in range(33)]
        result = export_recipe({"records": [], "columns": cols})
        self.assertEqual(result, {"error": "limit_exceeded"})

    def test_more_than_10000_rows(self):
        records = [{"a": 1}] * 10001
        result = export_recipe({"records": records, "columns": [{"label": "a", "path": ["a"]}]})
        self.assertEqual(result, {"error": "limit_exceeded"})

    def test_empty_columns_rejected(self):
        result = export_recipe({"records": [{}], "columns": []})
        self.assertEqual(result, {"error": "invalid_recipe"})


class TestPathType(unittest.TestCase):
    def test_string_segment_on_array(self):
        payload = {
            "records": [{"a": [1, 2]}],
            "columns": [{"label": "a", "path": ["a", "x"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "path_type"})

    def test_int_segment_on_object(self):
        payload = {
            "records": [{"a": {"b": 1}}],
            "columns": [{"label": "a", "path": ["a", 0]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "path_type"})

    def test_missing_key_is_null_not_path_type(self):
        payload = {
            "records": [{"a": {"b": 1}}],
            "columns": [{"label": "a", "path": ["a", "missing"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [[None]])


class TestNonScalar(unittest.TestCase):
    def test_object_result_rejected(self):
        payload = {
            "records": [{"a": {"b": 1}}],
            "columns": [{"label": "a", "path": ["a"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "non_scalar"})

    def test_array_result_rejected(self):
        payload = {
            "records": [{"a": [1, 2]}],
            "columns": [{"label": "a", "path": ["a"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "non_scalar"})

    def test_whole_record_via_empty_path_rejected(self):
        payload = {
            "records": [{"a": 1}],
            "columns": [{"label": "whole", "path": []}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "non_scalar"})

    def test_non_scalar_fallback_rejected(self):
        payload = {
            "records": [{}],
            "columns": [{"label": "x", "path": ["x"], "fallback": []}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "non_scalar"})


class TestScalarAggregation(unittest.TestCase):
    # Indexing a scalar (string/number/bool) with a non-empty path is an
    # incompatible traversal (path_type), matching jq's "Cannot index ...".
    def test_scalar_record_rejected_invalid_recipe(self):
        # Records must be JSON objects/arrays; a bare scalar record is malformed.
        payload = {
            "records": [5],
            "columns": [{"label": "x", "path": ["a"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_scalar_record_with_empty_path_rejected(self):
        # Even an empty path cannot turn a scalar record into a valid object.
        payload = {
            "records": [5],
            "columns": [{"label": "x", "path": []}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_bool_record_rejected_invalid_recipe(self):
        payload = {
            "records": [True],
            "columns": [{"label": "x", "path": ["a"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "invalid_recipe"})

    def test_string_scalar_indexing_is_path_type(self):
        # Record is a valid object; traversal hits a scalar mid-path -> path_type.
        payload = {
            "records": [{"a": "hello"}],
            "columns": [{"label": "a", "path": ["a", 0]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result, {"error": "path_type"})

    def test_null_record_traverses_to_null(self):
        # A null record is traversal-through-null, returning null, not invalid.
        payload = {
            "records": [None],
            "columns": [{"label": "x", "path": ["a"]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [[None]])

    def test_vector_record_with_int_path_ok(self):
        # JSON arrays are valid records; integer segments index them.
        payload = {
            "records": [[10, 20]],
            "columns": [{"label": "x", "path": [1]}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [[20]])


class TestFallback(unittest.TestCase):
    def test_jq_mode_replaces_null(self):
        payload = {
            "records": [{"a": None}],
            "columns": [{"label": "a", "path": ["a"], "fallback": "x"}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [["x"]])

    def test_jq_mode_replaces_false(self):
        payload = {
            "records": [{"a": False}],
            "columns": [{"label": "a", "path": ["a"], "fallback": "x"}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [["x"]])

    def test_jq_mode_preserves_zero(self):
        payload = {
            "records": [{"a": 0}],
            "columns": [{"label": "a", "path": ["a"], "fallback": "x"}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [[0]])

    def test_jq_mode_preserves_empty_string(self):
        payload = {
            "records": [{"a": ""}],
            "columns": [{"label": "a", "path": ["a"], "fallback": "x"}],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [[""]])

    def test_null_mode_does_not_replace_false(self):
        payload = {
            "records": [{"a": False}],
            "columns": [
                {"label": "a", "path": ["a"], "fallback": "x", "fallback_mode": "null"}
            ],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [[False]])

    def test_null_mode_replaces_null(self):
        payload = {
            "records": [{"a": None}],
            "columns": [
                {"label": "a", "path": ["a"], "fallback": "x", "fallback_mode": "null"}
            ],
        }
        result = export_recipe(payload)
        self.assertEqual(result["rows"], [["x"]])


if __name__ == "__main__":
    unittest.main()