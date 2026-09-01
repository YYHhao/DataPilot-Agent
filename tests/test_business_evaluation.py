from evaluation.run_business_eval import percentile, results_equal


def test_results_equal_ignores_aliases_but_checks_order_and_values():
    actual = {"columns": ["model_alias"], "rows": [[3.14159261], [2.0]]}
    expected = {"columns": ["gold_alias"], "rows": [[3.1415926], [2.0]]}
    assert results_equal(actual, expected)
    assert not results_equal({**actual, "rows": list(reversed(actual["rows"]))}, expected)


def test_percentile_uses_linear_interpolation():
    assert percentile([10, 20, 30], 0.5) == 20
    assert percentile([10, 20], 0.95) == 19.5
    assert percentile([], 0.95) == 0.0
