"""Smoke test: proves the fishbowl package is installed and importable."""


def test_package_imports():
    # If the src/ layout or the install is broken, this import fails first.
    import fishbowl

    # hasattr: asks "does this object have something called main?"
    assert hasattr(fishbowl, "main")
