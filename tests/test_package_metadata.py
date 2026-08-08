import dogwood


def test_package_exports_version_and_author():
    assert dogwood.__version__
    assert dogwood.__author__ == "Abhishek Tiwari"
