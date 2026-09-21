from backend.main2 import classify_module_b_risk


def test_module_b_high_risk_threshold():
    result = classify_module_b_risk({
        "value_0h": 100.0,
        "predicted_168h": 125.0,
        "drift": 25.0,
    })
    assert result == "High"


def test_module_b_review_threshold():
    result = classify_module_b_risk({
        "value_0h": 100.0,
        "predicted_168h": 112.0,
        "drift": 12.0,
    })
    assert result == "Review"


def test_module_b_normal_threshold():
    result = classify_module_b_risk({
        "value_0h": 100.0,
        "predicted_168h": 104.5,
        "drift": 4.5,
    })
    assert result == "Normal"
