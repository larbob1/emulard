"""Review-only copy-lane ownership model; no D3D, real queue, or recovery policy."""
from dataclasses import dataclass
from enum import Enum, auto
from itertools import product
import unittest

MAX = (1 << 64) - 1


class Owner(Enum):
    LOCAL = auto()
    UNCERTAIN = auto()
    IN_FLIGHT = auto()
    REUSABLE = auto()
    NOT_SUBMITTED = auto()


@dataclass(frozen=True)
class Domain:
    queue: int
    fence: int
    epoch: int


DIRECT = Domain(1, 1, 1)
UP = Domain(2, 2, 1)
DOWN = Domain(3, 3, 1)


@dataclass(frozen=True)
class Receipt:
    domain: Domain
    completed: int
    device_ok: bool = True


def confirms(target, domain, receipt):
    return (0 < target < MAX and receipt.domain == domain
            and receipt.device_ok and target <= receipt.completed < MAX)


@dataclass
class Attempt:
    domain: Domain
    target: int
    owner: Owner = Owner.LOCAL

    def pre_execute_failure(self):
        assert self.owner is Owner.LOCAL
        self.owner = Owner.NOT_SUBMITTED

    def execute(self):
        assert self.owner is Owner.LOCAL
        self.owner = Owner.UNCERTAIN

    def signal(self, success):
        assert self.owner is Owner.UNCERTAIN
        if success:
            self.owner = Owner.IN_FLIGHT

    def observe(self, receipt):
        if self.owner is Owner.IN_FLIGHT:
            if receipt.domain == self.domain and (
                    not receipt.device_ok or receipt.completed == MAX):
                self.owner = Owner.UNCERTAIN
            elif confirms(self.target, self.domain, receipt):
                self.owner = Owner.REUSABLE


def landing_actions(sizes_and_targets, bytes_needed, receipt):
    """Candidate eligibility only; does not allocate, evict, or recover."""
    if receipt.domain != DIRECT or not receipt.device_ok or not 0 <= receipt.completed < MAX:
        return None, ()
    eligible = tuple(i for i, (_, target) in enumerate(sizes_and_targets)
                     if confirms(target, DIRECT, receipt))
    fitting = [i for i in eligible if sizes_and_targets[i][0] >= bytes_needed]
    pick = min(fitting, key=lambda i: sizes_and_targets[i][0], default=None)
    return pick, eligible


class CopyLaneOwnership(unittest.TestCase):
    def test_pre_execute_failure_is_distinct(self):
        a = Attempt(UP, 7)
        a.pre_execute_failure()
        self.assertEqual(a.owner, Owner.NOT_SUBMITTED)

    def test_failed_signal_does_not_grant_reuse(self):
        for domain in (DIRECT, UP, DOWN):
            a = Attempt(domain, 7)
            a.execute()
            a.signal(False)
            for completed in (0, 6, 7, 8, MAX):
                a.observe(Receipt(domain, completed))
                self.assertEqual(a.owner, Owner.UNCERTAIN)

    def test_same_domain_success_required(self):
        for domain, observed, completed, healthy in product(
                (DIRECT, UP, DOWN), (DIRECT, UP, DOWN, Domain(2, 2, 2)),
                (0, 6, 7, 8, MAX), (False, True)):
            a = Attempt(domain, 7)
            a.execute()
            a.signal(True)
            a.observe(Receipt(observed, completed, healthy))
            if observed == domain and (not healthy or completed == MAX):
                want = Owner.UNCERTAIN
            elif observed == domain and completed in (7, 8):
                want = Owner.REUSABLE
            else:
                want = Owner.IN_FLIGHT
            self.assertEqual(a.owner, want)

    def test_same_domain_removal_is_sticky_for_attempt(self):
        a = Attempt(DOWN, 7)
        a.execute()
        a.signal(True)
        a.observe(Receipt(DOWN, MAX))
        a.observe(Receipt(DOWN, 9))
        self.assertEqual(a.owner, Owner.UNCERTAIN)

    def test_landing_reuse_and_eviction_are_direct_domain_only(self):
        pool = [(128, 3), (64, 5), (256, 9)]
        self.assertEqual(landing_actions(pool, 32, Receipt(DIRECT, 5)), (1, (0, 1)))
        self.assertEqual(landing_actions(pool, 128, Receipt(DIRECT, 5)), (0, (0, 1)))
        self.assertEqual(landing_actions(pool, 512, Receipt(DIRECT, 5)), (None, (0, 1)))
        for bad in (Receipt(DIRECT, MAX), Receipt(DIRECT, 99, False),
                    Receipt(UP, 99), Receipt(DOWN, MAX), Receipt(Domain(1, 1, 2), 99)):
            self.assertEqual(landing_actions(pool, 32, bad), (None, ()))

    def test_reserved_values_never_confirm(self):
        for target in (0, MAX):
            self.assertFalse(confirms(target, UP, Receipt(UP, MAX - 1)))


if __name__ == "__main__":
    unittest.main()
