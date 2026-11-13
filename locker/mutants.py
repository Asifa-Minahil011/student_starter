"""Faulty versions (mutants) of the reference SUT.

Each mutant is a subclass of ParcelLocker with ONE injected, plausible defect.
sut.py itself is never modified.

Every NON-equivalent mutant carries a hand-written `witness` sequence that exposes
it (the reference SUT passes the same sequence), which demonstrates that the mutant
is genuinely different. Mutants marked equivalent=True cannot be distinguished from
the reference by any input in the model's input domain; `note` explains why.
"""
from dataclasses import dataclass, field

from .sut import ParcelLocker
from .types import Command, Operation, Result, State

Op = Operation


def _c(op, cid="C1", code="", expired=False):
    return Command(op, customer_id=cid, code=code, expired=expired)


# ---------------------------------------------------------------- mutants
class M01ReserveWhenOccupied(ParcelLocker):
    """RESERVE accepted while OCCUPIED (guard removed) - overwrites the parcel's owner."""
    def execute(self, command):
        if command.operation == Op.RESERVE and self.state == State.OCCUPIED:
            self.state = State.RESERVED
            self.customer_id = command.customer_id
            self.reservation_code = f"R-{command.customer_id}"
            return Result(True, "reserved")
        return super().execute(command)


class M02DepositInMaintenance(ParcelLocker):
    """DEPOSIT accepted in MAINTENANCE without any check."""
    def execute(self, command):
        if command.operation == Op.DEPOSIT and self.state == State.MAINTENANCE:
            self.state = State.OCCUPIED
            self.retrieval_code = f"P-{self.customer_id}"
            return Result(True, "deposited")
        return super().execute(command)


class M03RetrieveWithoutAuth(ParcelLocker):
    """RETRIEVE accepted with ANY code (authentication skipped)."""
    def execute(self, command):
        if command.operation == Op.RETRIEVE and self.state == State.OCCUPIED:
            self._clear()
            return Result(True, "retrieved")
        return super().execute(command)


class M04ExpireIgnoresFlag(ParcelLocker):
    """EXPIRE accepted even when the expiry condition is NOT satisfied."""
    def execute(self, command):
        if command.operation == Op.EXPIRE and self.state == State.RESERVED:
            self._clear()
            return Result(True, "expired")
        return super().execute(command)


class M05StaleRetrievalCode(ParcelLocker):
    """Clearing the locker forgets the retrieval code (stale credential)."""
    def _clear(self):
        keep = self.retrieval_code
        super()._clear()
        self.retrieval_code = keep


class M06CancelWhenOccupied(ParcelLocker):
    """CANCEL accepted while a parcel is inside (cancellation rule violated)."""
    def execute(self, command):
        if command.operation == Op.CANCEL and self.state == State.OCCUPIED:
            self._clear()
            return Result(True, "cancelled")
        return super().execute(command)


class M07RejectedDepositChangesCustomer(ParcelLocker):
    """A deposit with a wrong code is rejected but still overwrites customer_id."""
    def execute(self, command):
        if (command.operation == Op.DEPOSIT and self.state == State.RESERVED
                and command.code != self.reservation_code):
            self.customer_id = command.customer_id
        return super().execute(command)


class M08DisableWhileReserved(ParcelLocker):
    """DISABLE accepted while RESERVED (reservation silently put into maintenance)."""
    def execute(self, command):
        if command.operation == Op.DISABLE and self.state == State.RESERVED:
            self.state = State.MAINTENANCE
            return Result(True, "disabled")
        return super().execute(command)


class M09EnableWhenAvailable(ParcelLocker):
    """ENABLE accepted on a locker that is not in maintenance."""
    def execute(self, command):
        if command.operation == Op.ENABLE and self.state == State.AVAILABLE:
            return Result(True, "enabled")
        return super().execute(command)


class M10InvalidAccessWipesCode(ParcelLocker):
    """INVALID_ACCESS on an occupied locker wipes the stored retrieval code."""
    def execute(self, command):
        if command.operation == Op.INVALID_ACCESS and self.state == State.OCCUPIED:
            self.retrieval_code = None
            return Result(False, "invalid_access")
        return super().execute(command)


class M11ExpireWhenOccupied(ParcelLocker):
    """EXPIRE (expired=True) wrongly accepted while OCCUPIED, destroying the parcel record."""
    def execute(self, command):
        if (command.operation == Op.EXPIRE and self.state == State.OCCUPIED
                and command.expired):
            self._clear()
            return Result(True, "expired")
        return super().execute(command)


class M12DeepStaleReservationAfterReuse(ParcelLocker):
    """DEEP fault: from the 2nd completed retrieval onward the reservation code is not cleared.
    Needs two full RESERVE->DEPOSIT->RETRIEVE cycles in ONE sequence (>= 6 steps)."""
    def __init__(self):
        super().__init__()
        self._retrievals = 0

    def execute(self, command):
        result = super().execute(command)
        if command.operation == Op.RETRIEVE and result.accepted:
            self._retrievals += 1
            if self._retrievals >= 2:
                self.reservation_code = "R-STALE"
        return result


class M13ExpireIsTrueCheck(ParcelLocker):
    """EQUIVALENT: tests `expired is not True` instead of `not expired`."""
    def execute(self, command):
        if command.operation == Op.EXPIRE and self.state == State.RESERVED:
            if command.expired is not True:
                return Result(False, "not_expired")
            self._clear()
            return Result(True, "expired")
        return super().execute(command)


class M14DepositInMaintenanceCodeChecked(ParcelLocker):
    """EQUIVALENT (unreachable): state check widened to MAINTENANCE, but the code check is kept.
    In MAINTENANCE reservation_code is None and Command.code is always a string,
    so the code can never match and the operation is still rejected."""
    def execute(self, command):
        if (command.operation == Op.DEPOSIT and self.state == State.MAINTENANCE
                and command.code == self.reservation_code):
            self.state = State.OCCUPIED
            return Result(True, "deposited")
        return super().execute(command)


# ---------------------------------------------------------------- registry
@dataclass(frozen=True)
class MutantSpec:
    mutant_id: str
    cls: type
    category: str
    description: str
    witness: list = field(default_factory=list)   # hand-written killing sequence ([] if equivalent)
    equivalent: bool = False
    note: str = ""

    @property
    def name(self):
        return self.cls.__name__


MUTANTS = [
    MutantSpec("M01", M01ReserveWhenOccupied, "missing guard", M01ReserveWhenOccupied.__doc__,
               [_c(Op.RESERVE), _c(Op.DEPOSIT, code="R-C1"), _c(Op.RESERVE, cid="C2")]),
    MutantSpec("M02", M02DepositInMaintenance, "missing guard", M02DepositInMaintenance.__doc__,
               [_c(Op.DISABLE), _c(Op.DEPOSIT, code="R-C1")]),
    MutantSpec("M03", M03RetrieveWithoutAuth, "authentication", M03RetrieveWithoutAuth.__doc__,
               [_c(Op.RESERVE), _c(Op.DEPOSIT, code="R-C1"), _c(Op.RETRIEVE, code="WRONG")]),
    MutantSpec("M04", M04ExpireIgnoresFlag, "wrong condition", M04ExpireIgnoresFlag.__doc__,
               [_c(Op.RESERVE), _c(Op.EXPIRE, expired=False)]),
    MutantSpec("M05", M05StaleRetrievalCode, "stale data", M05StaleRetrievalCode.__doc__,
               [_c(Op.RESERVE), _c(Op.DEPOSIT, code="R-C1"), _c(Op.RETRIEVE, code="P-C1")]),
    MutantSpec("M06", M06CancelWhenOccupied, "cancellation rule", M06CancelWhenOccupied.__doc__,
               [_c(Op.RESERVE), _c(Op.DEPOSIT, code="R-C1"), _c(Op.CANCEL)]),
    MutantSpec("M07", M07RejectedDepositChangesCustomer, "side effect on rejection",
               M07RejectedDepositChangesCustomer.__doc__,
               [_c(Op.RESERVE, cid="C2"), _c(Op.DEPOSIT, code="WRONG")]),
    MutantSpec("M08", M08DisableWhileReserved, "missing guard", M08DisableWhileReserved.__doc__,
               [_c(Op.RESERVE), _c(Op.DISABLE)]),
    MutantSpec("M09", M09EnableWhenAvailable, "missing guard", M09EnableWhenAvailable.__doc__,
               [_c(Op.ENABLE)]),
    MutantSpec("M10", M10InvalidAccessWipesCode, "side effect on rejection",
               M10InvalidAccessWipesCode.__doc__,
               [_c(Op.RESERVE), _c(Op.DEPOSIT, code="R-C1"), _c(Op.INVALID_ACCESS, code="BAD")]),
    MutantSpec("M11", M11ExpireWhenOccupied, "wrong state check", M11ExpireWhenOccupied.__doc__,
               [_c(Op.RESERVE), _c(Op.DEPOSIT, code="R-C1"), _c(Op.EXPIRE, expired=True)]),
    MutantSpec("M12", M12DeepStaleReservationAfterReuse, "deep / history-dependent",
               M12DeepStaleReservationAfterReuse.__doc__,
               [_c(Op.RESERVE), _c(Op.DEPOSIT, code="R-C1"), _c(Op.RETRIEVE, code="P-C1")] * 2),
    MutantSpec("M13", M13ExpireIsTrueCheck, "equivalent", M13ExpireIsTrueCheck.__doc__,
               equivalent=True,
               note="Identical for every Boolean `expired`; differs only for non-bool inputs "
                    "(e.g. 1), which are outside the model's input domain."),
    MutantSpec("M14", M14DepositInMaintenanceCodeChecked, "equivalent (unreachable)",
               M14DepositInMaintenanceCodeChecked.__doc__, equivalent=True,
               note="Needs code == reservation_code == None, impossible because Command.code "
                    "is always a str."),
]