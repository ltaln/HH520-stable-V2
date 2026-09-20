"""Build isolated research datasets."""


def build_dataset(prematch, labels=None):
    return {
        "prematch_count": len(prematch),
        "label_count": len(labels or []),
        "prematch": prematch,
        "labels": labels or [],
        "stable_write": False,
    }
