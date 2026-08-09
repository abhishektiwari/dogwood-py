# Configuration file for the Sphinx documentation builder.

import os
import sys
from datetime import datetime

# Add the source tree to the Python path.
sys.path.insert(0, os.path.abspath("../../src"))

try:
    from dogwood import __version__
except ImportError:
    __version__ = "0.0.0+unknown"

# -- Project information -----------------------------------------------------

project = "dogwood-py"
copyright = f"{datetime.now().year}, Abhishek Tiwari"
author = "Abhishek Tiwari"

version = __version__
release = __version__

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.coverage",
    "sphinx.ext.githubpages",
    "sphinx_copybutton",
]

autodoc_mock_imports = ["dogwood._dogwood_native"]

templates_path = ["_templates"]
exclude_patterns = []
source_suffix = ".rst"
master_doc = "index"

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinx_book_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]

html_theme_options = {
    "collapse_navigation": True,
    "navigation_depth": 4,
    "navbar_start": "",
    "navbar_center": "",
    "navbar_end": "",
    "navbar_persistent": "",
    "repository_url": "https://github.com/abhishektiwari/dogwood-py",
    "repository_provider": "github",
    "repository_branch": "main",
    "path_to_docs": "docs/source",
    "use_download_button": False,
    "use_fullscreen_button": True,
    "use_issues_button": True,
    "use_repository_button": True,
    "use_edit_page_button": True,
    "use_sidenotes": True,
    "icon_links_label": "Quick Links",
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/abhishektiwari/dogwood-py",
            "icon": "fa-brands fa-square-github",
            "type": "fontawesome",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/dogwood-py/",
            "icon": "fa-brands fa-python",
            "type": "fontawesome",
        },
    ],
}

html_title = f"{project} Documentation"
html_short_title = project
htmlhelp_basename = "dogwoodpydoc"

# -- Extension configuration -------------------------------------------------

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

autosummary_generate = True

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True

html_context = {
    "display_github": True,
    "github_user": "abhishektiwari",
    "github_repo": "dogwood-py",
    "github_version": "main/",
    "conf_py_path": "docs/source/",
}

github_username = "abhishektiwari"
github_repository = "dogwood-py"
pypi_name = "dogwood-py"
