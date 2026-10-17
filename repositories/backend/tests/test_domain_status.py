from invoice_intake.domain import TRANSITIONS, ActorKind, InvoiceStatus, allowed_next, is_terminal

S = InvoiceStatus


def test_every_status_has_a_row() -> None:
    assert set(TRANSITIONS) == set(InvoiceStatus)


def test_only_the_documented_moves_exist() -> None:
    pairs = {(source, target) for source, targets in TRANSITIONS.items() for target in targets}

    assert pairs == {
        (S.UPLOADED, S.EXTRACTING),
        (S.EXTRACTING, S.NEEDS_REVIEW),
        (S.EXTRACTING, S.FAILED),
        (S.NEEDS_REVIEW, S.APPROVED),
        (S.NEEDS_REVIEW, S.REJECTED),
        (S.APPROVED, S.EXPORTED),
        (S.FAILED, S.EXTRACTING),
        (S.FAILED, S.REJECTED),
    }


def test_only_a_person_may_approve_or_reject() -> None:
    assert TRANSITIONS[S.NEEDS_REVIEW] == {S.APPROVED: ActorKind.USER, S.REJECTED: ActorKind.USER}


def test_people_decide_and_retry_the_platform_does_the_rest() -> None:
    by_person = {
        (source, target)
        for source, targets in TRANSITIONS.items()
        for target, kind in targets.items()
        if kind is ActorKind.USER
    }
    other_kinds = {kind for targets in TRANSITIONS.values() for kind in targets.values()} - {
        ActorKind.USER
    }

    assert by_person == {
        (S.NEEDS_REVIEW, S.APPROVED),
        (S.NEEDS_REVIEW, S.REJECTED),
        (S.FAILED, S.EXTRACTING),  # ask for another extraction attempt
        (S.FAILED, S.REJECTED),  # give up on the document
    }
    assert other_kinds == {ActorKind.SYSTEM}  # the AI never changes a status


def test_rejected_and_exported_are_terminal() -> None:
    assert {status for status in InvoiceStatus if is_terminal(status)} == {S.REJECTED, S.EXPORTED}


def test_allowed_next() -> None:
    assert allowed_next(S.NEEDS_REVIEW) == frozenset({S.APPROVED, S.REJECTED})
    assert allowed_next(S.EXPORTED) == frozenset()
