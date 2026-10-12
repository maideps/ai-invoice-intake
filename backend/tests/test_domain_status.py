from invoice_intake.domain import TRANSITIONS, ActorKind, InvoiceStatus, allowed_next, is_terminal

S = InvoiceStatus


def test_every_status_has_a_row() -> None:
    assert set(TRANSITIONS) == set(InvoiceStatus)


def test_only_the_documented_moves_exist() -> None:
    pairs = {(source, target) for source, targets in TRANSITIONS.items() for target in targets}

    assert pairs == {
        (S.UPLOADED, S.EXTRACTING),
        (S.EXTRACTING, S.NEEDS_REVIEW),
        (S.NEEDS_REVIEW, S.APPROVED),
        (S.NEEDS_REVIEW, S.REJECTED),
        (S.APPROVED, S.EXPORTED),
    }


def test_only_a_person_may_approve_or_reject() -> None:
    assert TRANSITIONS[S.NEEDS_REVIEW] == {S.APPROVED: ActorKind.USER, S.REJECTED: ActorKind.USER}


def test_the_platform_makes_every_other_move() -> None:
    kinds = {
        kind
        for source, targets in TRANSITIONS.items()
        for kind in targets.values()
        if source is not S.NEEDS_REVIEW
    }

    assert kinds == {ActorKind.SYSTEM}


def test_rejected_and_exported_are_terminal() -> None:
    assert {status for status in InvoiceStatus if is_terminal(status)} == {S.REJECTED, S.EXPORTED}


def test_allowed_next() -> None:
    assert allowed_next(S.NEEDS_REVIEW) == frozenset({S.APPROVED, S.REJECTED})
    assert allowed_next(S.EXPORTED) == frozenset()
