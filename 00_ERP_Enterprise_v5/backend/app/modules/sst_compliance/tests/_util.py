from contextlib import contextmanager


@contextmanager
def raises(exc, code=None):
    try:
        yield
    except exc as e:  # noqa: PERF203
        if code is not None and getattr(e, "code", None) != code and code not in str(e):
            raise AssertionError(f"se esperaba código {code}, llegó {e!r}")
        return
    raise AssertionError(f"se esperaba {exc.__name__}")
