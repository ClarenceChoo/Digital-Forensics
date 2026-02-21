from digital_forensics import run


def test_run_imports() -> None:
    assert callable(run)
