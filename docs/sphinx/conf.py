import os
import sys
sys.path.insert(0, os.path.abspath('../..'))

project = 'SAYbrand'
copyright = '2026, SAYbrand Team'
author = 'SAYbrand Team'
release = 'v0.3.1'

extensions = [
    'myst_parser',
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.todo',
]

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_css_files = ['custom.css']

html_theme_options = {
    'logo_only': False,
    'display_version': True,
    'prev_next_buttons_location': 'bottom',
    'style_external_links': True,
    'collapse_navigation': False,
    'sticky_navigation': True,
    'navigation_depth': 4,
}

html_title = 'SAYbrand 기술 문서'
html_short_title = 'SAYbrand'

myst_enable_extensions = [
    'colon_fence',
    'deflist',
]

todo_include_todos = True
