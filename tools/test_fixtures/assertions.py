def assert_condition(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

def assert_raises(fn, message: str) -> None:
    try:
        fn()
    except Exception:
        return
    raise AssertionError(message)

def make_gateway_error_assertion(error_type: type[Exception]):
    def assert_gateway_error(fn, code: str | None = None) -> None:
        try:
            fn()
        except error_type as exc:
            if code is not None:
                assert_condition(exc.code == code, f"Expected {code}, got {exc.code}")
            return
        raise AssertionError("Expected GatewayError")
    return assert_gateway_error
