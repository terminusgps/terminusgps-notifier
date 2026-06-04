# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.settings.prod")
sys.path.insert(0, os.path.abspath("../../"))
django.setup()

project = "terminusgps-notifier"
copyright = "2026, Terminus GPS, LLC"
author = "Terminus GPS, LLC"
release = "3.10.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "autoclasstoc",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "django": (
        "https://docs.djangoproject.com/en/6.0/",
        "https://docs.djangoproject.com/en/6.0/objects.inv",
    ),
}

templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

autodoc_member_order = "groupwise"
html_theme = "sphinxawesome_theme"
pygments_style = "sas"
pygments_style_dark = "lightbulb"
html_static_path = ["_static"]
