"""Build isolated backtest datasets."""


def build_dataset(records, labels):
    from research.result_label.matcher import match_results
    return match_results(records, labels)
