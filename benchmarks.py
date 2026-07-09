import time
import statistics

import backon

try:
    import tenacity
except ImportError:
    tenacity = None


def bench_success(impl, name, n=10000):
    def fn():
        return 42

    wrapped = impl(fn)
    times = []
    for _ in range(n):
        t0 = time.perf_counter_ns()
        wrapped()
        t1 = time.perf_counter_ns()
        times.append(t1 - t0)
    avg = statistics.mean(times) / 1000
    med = statistics.median(times) / 1000
    print(f"  {name:20s}  avg={avg:7.2f}µs  median={med:7.2f}µs")
    return avg


def bench_retry(impl, name, tries=3, n=500):
    call_count = [0]

    def fn():
        call_count[0] += 1
        if call_count[0] < tries:
            raise ValueError("retry")
        return 42

    call_count[0] = 0
    wrapped = impl(fn)
    times = []
    for _ in range(n):
        call_count[0] = 0
        t0 = time.perf_counter_ns()
        wrapped()
        t1 = time.perf_counter_ns()
        times.append(t1 - t0)
    avg = statistics.mean(times) / 1000
    med = statistics.median(times) / 1000
    print(f"  {name:20s}  avg={avg:7.2f}µs  median={med:7.2f}µs")
    return avg


def bench_decorator_creation(impl, name, n=2000):
    # how long to apply the decorator
    def fn():
        return 42

    times = []
    for _ in range(n):
        t0 = time.perf_counter_ns()
        impl(fn)
        t1 = time.perf_counter_ns()
        times.append(t1 - t0)
    avg = statistics.mean(times) / 1000
    print(f"  {name:20s}  decorator creation avg={avg:7.2f}µs")


# --- Backon 4.1.0 ---
print("=== Backon 4.1.0 (current, fast path) ===")
backon_success = bench_success(
    lambda f: backon.on_exception(backon.constant, ValueError, max_tries=1, jitter=None, interval=0)(f),
    "success (fast path)",
)
backon_retry = bench_retry(
    lambda f: backon.on_exception(backon.constant, ValueError, max_tries=3, jitter=None, interval=0)(f),
    "retry 3x",
    tries=3,
)
bench_decorator_creation(
    lambda f: backon.on_exception(backon.constant, ValueError, max_tries=1, jitter=None, interval=0)(f),
    "backon",
)

# --- Tenacity ---
if tenacity:
    print("\n=== Tenacity ===")
    t_success = bench_success(
        lambda f: tenacity.retry(
            stop=tenacity.stop_after_attempt(1),
            wait=tenacity.wait_none(),
            retry=tenacity.retry_if_exception_type(ValueError),
        )(f),
        "success",
    )
    t_retry = bench_retry(
        lambda f: tenacity.retry(
stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_none(),
        retry=tenacity.retry_if_exception_type(ValueError),
    )(f),
    "retry 3x",
    tries=3,
    )
    bench_decorator_creation(
        lambda f: tenacity.retry(
            stop=tenacity.stop_after_attempt(1),
            wait=tenacity.wait_none(),
            retry=tenacity.retry_if_exception_type(ValueError),
        )(f),
        "tenacity",
    )

    print(f"\n=== Speedup (backon vs tenacity) ===")
    if backon_success and t_success:
        print(f"  Success path: {t_success/backon_success:.1f}x faster")
    if backon_retry and t_retry:
        print(f"  Retry 3x:     {t_retry/backon_retry:.1f}x faster")
