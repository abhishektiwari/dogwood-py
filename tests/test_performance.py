import os
import time

import pytest

from dogwood import Authorizer, Event, LoweredPolicySet, PolicySchema, native, replay_log
from tests.test_upstream_regressions import SCHEMA, SIMPLE_POLICY


def test_native_replay_performance_against_python_fallback():
    if os.environ.get("DOGWOOD_PERF_TESTS") != "1":
        pytest.skip("set DOGWOOD_PERF_TESTS=1 to run performance regression tests")
    if not native.available():
        pytest.skip("native extension is not built")

    trace = _trace(1_000)
    python_policies = LoweredPolicySet.from_str(SIMPLE_POLICY, policy_schema=PolicySchema(""))

    expected = replay_log(python_policies, trace)
    assert native.replay(SIMPLE_POLICY, SCHEMA, trace) == expected

    native_seconds = _best_of(lambda: native.replay(SIMPLE_POLICY, SCHEMA, trace))
    python_seconds = _best_of(lambda: replay_log(python_policies, trace))

    print(
        f"native replay: {native_seconds:.4f}s; "
        f"python fallback replay: {python_seconds:.4f}s; "
        f"ratio native/python: {native_seconds / python_seconds:.2f}"
    )

    max_ratio = float(os.environ.get("DOGWOOD_NATIVE_MAX_RATIO", "25"))
    assert native_seconds <= python_seconds * max_ratio


def test_persistent_native_authorizer_performance_against_python_fallback():
    if os.environ.get("DOGWOOD_PERF_TESTS") != "1":
        pytest.skip("set DOGWOOD_PERF_TESTS=1 to run performance regression tests")
    if not native.available():
        pytest.skip("native extension is not built")

    requests = _requests(1_000)
    python_policies = LoweredPolicySet.from_str(SIMPLE_POLICY, policy_schema=PolicySchema(""))

    native_decisions = _native_authorize_all(requests)
    python_decisions = _python_authorize_all(python_policies, requests)
    assert native_decisions == python_decisions

    native_seconds = _best_loop_of(
        lambda: native.NativeAuthorizer(SIMPLE_POLICY, SCHEMA),
        lambda authorizer: _native_authorize_with(authorizer, requests),
    )
    python_seconds = _best_loop_of(
        lambda: Authorizer(python_policies),
        lambda authorizer: _python_authorize_with(authorizer, requests),
    )

    print(
        f"persistent native authorizer: {native_seconds:.4f}s; "
        f"python fallback authorizer: {python_seconds:.4f}s; "
        f"ratio native/python: {native_seconds / python_seconds:.2f}"
    )

    max_ratio = float(os.environ.get("DOGWOOD_PERSISTENT_NATIVE_MAX_RATIO", "50"))
    assert native_seconds <= python_seconds * max_ratio


def _trace(count: int) -> str:
    lines = []
    for i in range(count):
        shares = 25 if i % 2 == 0 else 500
        user = f"user{i}"
        stock = "AMZN" if i % 3 == 0 else "MSFT"
        lines.append(
            f'@{i} scope(principal: Drupe::OAuthUser::"{user}", '
            'resource: Drupe::Gateway::"trading") '
            f'request_context(input: {{ shares: {shares}, stock: "{stock}" }}) '
            f'Drupe::Action::"SellShares"::request('
            f'input: {{ shares: {shares}, stock: "{stock}" }}, '
            f'callerPrincipal: Drupe::OAuthUser::"{user}", '
            'callerResource: Drupe::Gateway::"trading", '
            f'requestId: "u{i}")'
        )
    return "\n".join(lines)


def _requests(count: int) -> list[dict[str, object]]:
    return [
        {
            "user": f"user{i}",
            "shares": 25 if i % 2 == 0 else 500,
            "stock": "AMZN" if i % 3 == 0 else "MSFT",
        }
        for i in range(count)
    ]


def _native_authorize_all(requests: list[dict[str, object]]) -> list[str]:
    authorizer = native.NativeAuthorizer(SIMPLE_POLICY, SCHEMA)
    return _native_authorize_with(authorizer, requests)


def _native_authorize_with(authorizer: native.NativeAuthorizer, requests: list[dict[str, object]]) -> list[str]:
    decisions = []
    for request in requests:
        decisions.append(
            authorizer.authorize_request(
                "Drupe::Action::SellShares",
                f'Drupe::OAuthUser::"{request["user"]}"',
                'Drupe::Gateway::"trading"',
                {"shares": request["shares"], "stock": request["stock"]},
            )
        )
    return decisions


def _python_authorize_all(policies: LoweredPolicySet, requests: list[dict[str, object]]) -> list[str]:
    authorizer = Authorizer(policies)
    return _python_authorize_with(authorizer, requests)


def _python_authorize_with(authorizer: Authorizer, requests: list[dict[str, object]]) -> list[str]:
    decisions = []
    for request in requests:
        event = (
            Event.builder('Drupe::Action::"SellShares"', "request")
            .principal(f'Drupe::OAuthUser::"{request["user"]}"')
            .resource('Drupe::Gateway::"trading"')
            .field("input", "shares", request["shares"])
            .field("input", "stock", request["stock"])
            .request_context("input", "shares", request["shares"])
            .request_context("input", "stock", request["stock"])
            .build()
        )
        response = authorizer.is_authorized(event)
        decisions.append(response.decision.value if response is not None else "NoDecision")
    return decisions


def _best_of(fn, repeats: int = 3) -> float:
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def _best_loop_of(setup, run, repeats: int = 3) -> float:
    best = float("inf")
    for _ in range(repeats):
        subject = setup()
        start = time.perf_counter()
        run(subject)
        best = min(best, time.perf_counter() - start)
    return best
