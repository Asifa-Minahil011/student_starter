import unittest
from locker.model import LockerModel, ACCEPTED, REJECTED_PRECONDITION, REJECTED_GUARD
from locker.types import Command, Operation, State, Snapshot

EMPTY = lambda s: Snapshot(s, None, None, None)


def model_in(state, cid="C1"):
    """Drive a fresh model into the requested state using public operations."""
    m = LockerModel()
    if state == State.RESERVED:
        m.step(Command(Operation.RESERVE, customer_id=cid))
    elif state == State.OCCUPIED:
        m.step(Command(Operation.RESERVE, customer_id=cid))
        m.step(Command(Operation.DEPOSIT, code="R-" + cid))
    elif state == State.MAINTENANCE:
        m.step(Command(Operation.DISABLE))
    return m


class TestModelRules(unittest.TestCase):
    def test_initial_state(self):
        self.assertEqual(LockerModel().snapshot(), EMPTY(State.AVAILABLE))

    def test_rule1_2_reserve(self):
        m = LockerModel()
        r = m.step(Command(Operation.RESERVE, customer_id="C7"))
        self.assertTrue(r.accepted)
        self.assertEqual(m.snapshot(), Snapshot(State.RESERVED, "C7", "R-C7", None))

    def test_rule1_reserve_rejected_elsewhere(self):
        for s in (State.RESERVED, State.OCCUPIED, State.MAINTENANCE):
            m = model_in(s); before = m.snapshot()
            self.assertFalse(m.step(Command(Operation.RESERVE, customer_id="C2")).accepted)
            self.assertEqual(m.snapshot(), before)

    def test_rule3_cancel(self):
        m = model_in(State.RESERVED)
        self.assertTrue(m.step(Command(Operation.CANCEL)).accepted)
        self.assertEqual(m.snapshot(), EMPTY(State.AVAILABLE))

    def test_rule3_cancel_rejected_elsewhere(self):
        for s in (State.AVAILABLE, State.OCCUPIED, State.MAINTENANCE):
            m = model_in(s); before = m.snapshot()
            self.assertFalse(m.step(Command(Operation.CANCEL)).accepted)
            self.assertEqual(m.snapshot(), before)

    def test_rule4_5_deposit(self):
        m = model_in(State.RESERVED)
        self.assertTrue(m.step(Command(Operation.DEPOSIT, code="R-C1")).accepted)
        self.assertEqual(m.snapshot(), Snapshot(State.OCCUPIED, "C1", "R-C1", "P-C1"))

    def test_rule4_deposit_wrong_codes(self):
        for bad in ("", "WRONG", "P-C1", "R-C2"):
            m = model_in(State.RESERVED); before = m.snapshot()
            self.assertFalse(m.step(Command(Operation.DEPOSIT, code=bad)).accepted)
            self.assertEqual(m.snapshot(), before)

    def test_rule4_deposit_rejected_in_other_states(self):
        for s in (State.AVAILABLE, State.OCCUPIED, State.MAINTENANCE):
            m = model_in(s); before = m.snapshot()
            self.assertFalse(m.step(Command(Operation.DEPOSIT, code="R-C1")).accepted)
            self.assertEqual(m.snapshot(), before)

    def test_rule6_7_retrieve(self):
        m = model_in(State.OCCUPIED)
        self.assertTrue(m.step(Command(Operation.RETRIEVE, code="P-C1")).accepted)
        self.assertEqual(m.snapshot(), EMPTY(State.AVAILABLE))

    def test_rule6_retrieve_wrong_code_or_state(self):
        for bad in ("", "WRONG", "R-C1"):
            m = model_in(State.OCCUPIED); before = m.snapshot()
            self.assertFalse(m.step(Command(Operation.RETRIEVE, code=bad)).accepted)
            self.assertEqual(m.snapshot(), before)
        for s in (State.AVAILABLE, State.RESERVED, State.MAINTENANCE):
            m = model_in(s); before = m.snapshot()
            self.assertFalse(m.step(Command(Operation.RETRIEVE, code="P-C1")).accepted)
            self.assertEqual(m.snapshot(), before)

    def test_retrieved_parcel_cannot_be_retrieved_again(self):
        m = model_in(State.OCCUPIED)
        m.step(Command(Operation.RETRIEVE, code="P-C1"))
        self.assertFalse(m.step(Command(Operation.RETRIEVE, code="P-C1")).accepted)

    def test_rule8_expire(self):
        m = model_in(State.RESERVED)
        self.assertTrue(m.step(Command(Operation.EXPIRE, expired=True)).accepted)
        self.assertEqual(m.snapshot(), EMPTY(State.AVAILABLE))

    def test_rule8_expire_not_expired(self):
        m = model_in(State.RESERVED); before = m.snapshot()
        self.assertFalse(m.step(Command(Operation.EXPIRE, expired=False)).accepted)
        self.assertEqual(m.snapshot(), before)

    def test_rule8_expire_wrong_state_even_if_flag_true(self):
        for s in (State.AVAILABLE, State.OCCUPIED, State.MAINTENANCE):
            m = model_in(s); before = m.snapshot()
            self.assertFalse(m.step(Command(Operation.EXPIRE, expired=True)).accepted)
            self.assertEqual(m.snapshot(), before)

    def test_rule9_disable(self):
        m = LockerModel()
        self.assertTrue(m.step(Command(Operation.DISABLE)).accepted)
        self.assertEqual(m.snapshot(), EMPTY(State.MAINTENANCE))

    def test_rule9_disable_rejected_elsewhere(self):
        for s in (State.RESERVED, State.OCCUPIED, State.MAINTENANCE):
            m = model_in(s); before = m.snapshot()
            self.assertFalse(m.step(Command(Operation.DISABLE)).accepted)
            self.assertEqual(m.snapshot(), before)

    def test_rule10_enable(self):
        m = model_in(State.MAINTENANCE)
        self.assertTrue(m.step(Command(Operation.ENABLE)).accepted)
        self.assertEqual(m.snapshot(), EMPTY(State.AVAILABLE))

    def test_rule10_enable_rejected_elsewhere(self):
        for s in (State.AVAILABLE, State.RESERVED, State.OCCUPIED):
            m = model_in(s); before = m.snapshot()
            self.assertFalse(m.step(Command(Operation.ENABLE)).accepted)
            self.assertEqual(m.snapshot(), before)

    def test_rule11_invalid_access_never_changes_anything(self):
        for s in State:
            m = model_in(s); before = m.snapshot()
            r = m.step(Command(Operation.INVALID_ACCESS, code="X"))
            self.assertFalse(r.accepted)
            self.assertEqual(m.snapshot(), before)


class TestTransitionClassification(unittest.TestCase):
    def test_transition_count_is_35(self):
        """Enumerate every (state, op, outcome) the model can produce."""
        seen = set()
        for s in State:
            for op in Operation:
                for code_kind in ("good", "bad"):
                    for expired in (True, False):
                        m = model_in(s)
                        good = {Operation.DEPOSIT: "R-C1", Operation.RETRIEVE: "P-C1"}.get(op, "")
                        code = good if code_kind == "good" else "BAD"
                        seen.add(m.classify(Command(op, code=code, expired=expired)))
        self.assertEqual(len(seen), 35)
        self.assertEqual(sum(1 for t in seen if t[2] == ACCEPTED), 7)
        self.assertEqual(sum(1 for t in seen if t[2] == REJECTED_GUARD), 3)
        self.assertEqual(sum(1 for t in seen if t[2] == REJECTED_PRECONDITION), 25)

    def test_classify_does_not_mutate(self):
        m = model_in(State.RESERVED); before = m.snapshot()
        m.classify(Command(Operation.CANCEL))
        self.assertEqual(m.snapshot(), before)


if __name__ == "__main__":
    unittest.main()