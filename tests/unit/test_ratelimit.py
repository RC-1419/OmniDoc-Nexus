from omnidoc.core.ratelimit import RateLimiter


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def make(limit_clock=None):
    clock = limit_clock or Clock()
    return RateLimiter(clock=clock), clock


def test_allows_up_to_the_limit_then_blocks():
    rl, _ = make()
    assert [rl.hit("k", 3, 60) for _ in range(3)] == [0, 0, 0]
    assert rl.hit("k", 3, 60) == 60


def test_wait_time_counts_down_and_is_never_below_one_second():
    rl, clock = make()
    rl.hit("k", 1, 60)
    clock.now = 40
    assert rl.hit("k", 1, 60) == 20
    clock.now = 59.2
    assert rl.hit("k", 1, 60) == 1


def test_allowed_again_when_the_window_has_passed():
    rl, clock = make()
    rl.hit("k", 1, 60)
    clock.now = 60
    assert rl.hit("k", 1, 60) == 0


def test_blocked_attempts_are_not_recorded():
    rl, clock = make()
    rl.hit("k", 1, 60)
    for _ in range(5):
        rl.hit("k", 1, 60)               # all refused
    clock.now = 60
    assert rl.hit("k", 1, 60) == 0       # only the first, allowed hit counted


def test_keys_are_independent():
    rl, _ = make()
    rl.hit("alice", 1, 60)
    assert rl.hit("alice", 1, 60) > 0
    assert rl.hit("bob", 1, 60) == 0


def test_wait_time_records_nothing():
    rl, _ = make()
    for _ in range(10):
        assert rl.wait_time("k", 1, 60) == 0
    assert rl.hit("k", 1, 60) == 0


def test_record_counts_toward_wait_time():
    rl, _ = make()
    rl.record("k", 60)
    rl.record("k", 60)
    assert rl.wait_time("k", 2, 60) == 60
    assert rl.wait_time("k", 3, 60) == 0


def test_unknown_key_has_no_wait():
    rl, _ = make()
    assert rl.wait_time("never-seen", 1, 60) == 0


def test_old_keys_are_forgotten_when_there_are_too_many():
    rl, clock = make()
    rl.MAX_KEYS = 3
    for name in "abc":
        rl.record(name, 10)
    clock.now = 100
    # now 4 keys > 3, so the three expired ones are dropped
    rl.record("d", 10)
    rl.record("e", 10)
    assert set(rl._hits) == {"d", "e"}
