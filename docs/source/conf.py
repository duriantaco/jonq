import datetime

project = 'jonq'
copyright = f'{datetime.datetime.now().year}, oha'
author = 'oha'
release = '0.0.2'

extensions = [
    'sphinx.ext.autodoc',    
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',    
    'sphinx.ext.intersphinx',
    # Removed sphinx_copybutton
    'sphinx_design',
    'sphinx_inline_tabs',
    'sphinxcontrib.mermaid',
    
    'myst_parser',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

myst_enable_extensions = [
    "colon_fence", 
    "deflist", 
    "smartquotes",
    "tasklist",
    "attrs_inline",
]

# Removed copybutton configuration lines

templates_path = ['_templates']
exclude_patterns = []
pygments_style = "monokai"

html_theme = 'furo'
html_title = 'jonq Documentation'

html_theme_options = {
    "sidebar_hide_name": False,
    
    "light_css_variables": {
        "color-brand-primary": "#2563EB",
        "color-brand-content": "#4F46E5",
        
        "color-background-primary": "#FFFFFF",
        "color-background-secondary": "#F9FAFB",
        
        "color-admonition-background": "#EFF6FF",
        
        "font-stack": "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif",
        "font-stack--monospace": "JetBrains Mono, SFMono-Regular, Menlo, Consolas, monospace",
    },
    
    "dark_css_variables": {
        "color-brand-primary": "#60A5FA",
        "color-brand-content": "#818CF8",
        
        "color-background-primary": "#111827",
        "color-background-secondary": "#1F2937",
        
        "color-admonition-background": "#1E3A8A",
    },
    
    "navigation_with_keys": True,
    "announcement": "📢 jonq v0.0.2 is now available! Check the installation guide for details.",
}

html_static_path = ['_static']
html_css_files = ['custom.css']

autodoc_member_order = 'bysource'
autoclass_content = 'both'
add_module_names = False

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_use_param = False
napoleon_use_rtype = False
napoleon_preprocess_types = True