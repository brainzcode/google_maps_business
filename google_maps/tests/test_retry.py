"""Tests for google_maps.retry — exponential backoff decorator."""

import pytest

from google_maps.retry import retry, RetryExhausted


class TestRetry:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        async def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await succeed()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_succeeds_after_failures(self):
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "ok"

        result = await fail_then_succeed()
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_raises(self):
        @retry(max_attempts=2, base_delay=0.01)
        async def always_fail():
            raise RuntimeError("boom")

        with pytest.raises(RetryExhausted) as exc_info:
            await always_fail()

        assert exc_info.value.attempts == 2
        assert "boom" in str(exc_info.value.last_error)
        assert exc_info.value.func_name == "always_fail"

    @pytest.mark.asyncio
    async def test_retryable_filter(self):
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01, retryable=(ValueError,))
        async def fail_with_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("not retryable")

        with pytest.raises(TypeError):
            await fail_with_type_error()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        attempts_seen = []

        def track(attempt, exc):
            attempts_seen.append(attempt)

        @retry(max_attempts=3, base_delay=0.01, on_retry=track)
        async def fail_twice():
            if len(attempts_seen) < 2:
                raise ValueError("retry me")
            return "ok"

        result = await fail_twice()
        assert result == "ok"
        assert attempts_seen == [1, 2]

    @pytest.mark.asyncio
    async def test_single_attempt_no_retry(self):
        @retry(max_attempts=1, base_delay=0.01)
        async def always_fail():
            raise RuntimeError("boom")

        with pytest.raises(RetryExhausted) as exc_info:
            await always_fail()

        assert exc_info.value.attempts == 1


class TestRetryExhausted:
    def test_message(self):
        err = RetryExhausted("my_func", 3, ValueError("oops"))
        assert "my_func" in str(err)
        assert "3 attempts" in str(err)
        assert "oops" in str(err)

    def test_attributes(self):
        original = RuntimeError("original")
        err = RetryExhausted("fn", 5, original)
        assert err.func_name == "fn"
        assert err.attempts == 5
        assert err.last_error is original


class TestRetryBackoff:
    @pytest.mark.asyncio
    async def test_delay_respects_max(self, monkeypatch):
        """`max_delay` caps the exponential backoff window."""
        import importlib
        retry_mod = importlib.import_module("google_maps.retry")

        slept: list[float] = []

        async def fake_sleep(s):
            slept.append(s)

        monkeypatch.setattr(retry_mod.asyncio, "sleep", fake_sleep)

        @retry(max_attempts=5, base_delay=1.0, max_delay=2.0)
        async def always_fail():
            raise ValueError("nope")

        with pytest.raises(RetryExhausted):
            await always_fail()

        # Every sleep should respect the 2.0s cap (jitter is [0, cap))
        assert all(0 <= s <= 2.0 for s in slept)
        assert len(slept) == 4  # 5 attempts → 4 sleeps

    @pytest.mark.asyncio
    async def test_preserves_return_value(self):
        @retry(max_attempts=3, base_delay=0.01)
        async def sum_nums(a, b, c=0):
            return a + b + c

        assert await sum_nums(1, 2, c=3) == 6
