"""Throwaway scratch file for the /simplify lesson. Safe to delete."""

from bristlenose.utils.text import count_noun


def describe_quotes(n: int) -> str:
    # REUSE bait: hand-rolled pluralisation when count_noun() already exists
    if n == 1:
        return f"{n} quote"
    else:
        return f"{n} quotes"


def is_shareable(has_pii: bool, is_anonymised: bool) -> bool:
    # SIMPLIFICATION bait: a nested if/else that is one boolean expression
    if has_pii:
        if is_anonymised:
            return True
        else:
            return False
    else:
        return True


def collect_labels(quotes: list[dict]) -> list[str]:
    # EFFICIENCY bait: rebuilds the result list from scratch every iteration
    labels: list[str] = []
    for q in quotes:
        labels = labels + [q["label"]]
    return labels


def render_header(title: str) -> str:
    # ALTITUDE bait: a one-off wrapper that earns nothing over an f-string
    def _wrap(s: str) -> str:
        return "<h1>" + s + "</h1>"

    return _wrap(title)


# count_noun import is here so the REUSE fix has something to reach for
_ = count_noun
