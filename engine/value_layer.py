def value_layer(match: dict, probability: dict) -> dict:
    value = match.get("value", {})
    # EV / Kelly 保留为研究及价值字段，不允许单独决定预测方向
    return {
        "ev": value.get("ev"),
        "kelly": value.get("kelly"),
        "page_signal": value.get("signal"),
        "used_for_direction": False,
    }
