import dogwood
from dogwood import _version


def test_package_exports_version_and_author():
    assert dogwood.__version__
    assert dogwood.__version__ != "0.0.0+unknown"
    assert dogwood.__version__ == _version.version
    assert dogwood.__author__ == "Abhishek Tiwari"
