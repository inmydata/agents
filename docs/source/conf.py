# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'agents'
copyright = '2025, DataPA Limited'
author = 'DataPA Limited'
release = '0.0.17'

import os
import sys
import enum
import inspect
sys.path.insert(0, os.path.abspath('../../src'))
# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
]

templates_path = ['_templates']
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']
html_favicon = '_static/favicon.ico'
html_logo = '_static/logo.png'
html_title = f"agents API reference ({release})" 
html_short_title = "API reference"

html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#dd3333",
        "color-brand-content": "#ffffff",
    }
}

def setup(app):
    app.add_css_file('custom.css')
    app.connect("autodoc-process-docstring", add_methods_heading)

def add_methods_heading(app, what, name, obj, options, lines):
    if what != "class":
        return

        # Skip enums
    if isinstance(obj, type) and issubclass(obj, enum.Enum):
        return
        
    methods = [
        member for member_name, member in inspect.getmembers(obj, inspect.isfunction)
        if not member_name.startswith('_')  # Ignore dunder and private methods
           and member.__qualname__.startswith(obj.__name__)  # Skip inherited methods
    ]

    if not methods:
        return  # No methods, don't add heading
    
    # Add "Methods" title before methods (if not already present)
    lines.append('')
    lines.append('Members')
    lines.append('-------')
