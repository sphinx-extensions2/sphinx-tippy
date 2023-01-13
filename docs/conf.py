from datetime import date
from pathlib import Path

from sphinx_tippy import __version__

# -- Project information -----------------------------------------------------

project = "Sphinx Tippy"
version = __version__
copyright = f"{date.today().year}, Chris Sewell"
author = "Chris Sewell"

# -- General configuration ---------------------------------------------------

extensions = [
    "myst_parser",
    "sphinx_tippy",
]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
myst_enable_extensions = ["deflist", "colon_fence"]

# -- HTML output -------------------------------------------------

html_theme = "furo"
html_logo = "tippy-logo.svg"
html_theme_options = {
    "source_repository": "https://github.com/chrisjsewell/sphinx_tippy/",
    "source_branch": "main",
    "source_directory": "docs/",
}

tippy_enable_mathjax = True
tippy_anchor_parent_selector = "div.content"
tippy_logo_svg = Path("tippy-logo.svg").read_text("utf8")
tippy_custom_tips = {
    "https://example.com": "<p>This is a custom tip for <a>example.com</a></p>",
    "https://atomiks.github.io/tippyjs": (
        f"{tippy_logo_svg}<p>Using Tippy.js, the complete tooltip, popover, dropdown, "
        "and menu solution for the web, powered by Popper.</p>"
    ),
}


def setup(app):
    app.add_object_type(
        "confval",  # directivename
        "confval",  # rolename
        "pair: %s; configuration value",  # indextemplate
    )
