# Sphinx Tippy

[![GitHub Repo stars](https://img.shields.io/github/stars/chrisjsewell/sphinx-tippy?label=Like%20and%20Share%21&style=social)](https://github.com/chrisjsewell/sphinx-tippy)

Get rich hover tips in your sphinx documentation.

[**Hover on me!**](https://atomiks.github.io/tippyjs)

```{toctree}
:hidden:
folder/other
```

## Installation

Install with pip:

```bash
pip install sphinx-tippy
```

(intro/usage)=
## Usage

Add the extension to your `conf.py`:

```python
extensions = ["sphinx_tippy"]
```

Now your website will have tooltips on many of your links!

:::{list-table}

-  - [Custom tip](https://example.com)

-  - [Wikipedia tips](https://en.wikipedia.org/wiki/Tooltip)

-  - [DOI tip](https://doi.org/10.1186/gm483)

-  - [ReadTheDocs tip](https://www.sphinx-doc.org/en/master/usage/quickstart.html#intersphinx)

-  - {ref}`Figure reference with URL image <figure-name-url>`

-  - {ref}`Figure reference with local image <figure-name-file>`

-  - {ref}`Figure reference by another id <figure-name-dup>`

-  - {ref}`Image reference <image-name>`

-  - {py:class}`Python Class reference <Foo>`

-  - {ref}`Table reference <table-name>`

-  - {ref}`Heading reference <intro/usage>`

-  - {doc}`Document reference <folder/other>`

-  - {doc}`Same document reference <../index>`

-  - Math reference {eq}`math-name`

-  - {ref}`Code reference <code-name>`

-  - {ref}`Admonition reference <admonition-name>`

-  - {term}`Glossary reference <term>`

-  - Footnote reference [^1]

:::

[^1]: This is a footnote

    This is another paragraph

:::{important}
Dependent on the theme you ar using with sphinx,
you may need to add some CSS to your `conf.py` to make the tooltips show correctly.

For example, for the [Pydata Sphinx Theme](https://pydata-sphinx-theme.readthedocs.io):

`conf.py`:

```python
html_static_path = ['_static']
html_css_files = ["tippy.css"]
```

`_static/tippy.css`:

```css
.tippy-box {
    background-color:var(--pst-color-surface);
    color:var(--pst-color-text-base);
    border: 1px solid var(--pst-color-border);
}
```

:::

## How does it work?

The extension uses the [tippy.js](https://atomiks.github.io/tippyjs) library to create tooltips.

Currently, all tips are created during the build process, so there is no need for a server and, once loaded, all tips are very responsive
(although [dynamic fetching](https://atomiks.github.io/tippyjs/v6/ajax/) could be implemented later).

The internal tips are created simply by "scraping" the built HTML, which bypasses having to deal with the sphinx internals, like domains etc.

Note, there is another sphinx extension for hover tips; [sphinx-hoverxref](https://github.com/readthedocs/sphinx-hoverxref),
however, one of the annoyances with this is that documentation has to be hosted on Read the Docs for it to work, since that used the RTD embed API dynamically.

## Configuration

The extension has the following configuration options.

### Display

:::{confval} tippy_props
Overrides for the [tippy.js props](https://atomiks.github.io/tippyjs/v6/all-props/) to use, by default:

```python
tippy_props = {"placement": "auto-start", "maxWidth": 500, "interactive": False, "theme": "material", "duration": [200, 100], "delay": [200, 500]}
```

Note, only the following props are allowed to be overridden currently:

- [placement](https://atomiks.github.io/tippyjs/v6/all-props/#placement)
- [maxWidth](https://atomiks.github.io/tippyjs/v6/all-props/#maxwidth)
- [theme](https://atomiks.github.io/tippyjs/v6/all-props/#theme)
- [interactive](https://atomiks.github.io/tippyjs/v6/all-props/#interactive)
- [delay](https://atomiks.github.io/tippyjs/v6/all-props/#delay)
- [duration](https://atomiks.github.io/tippyjs/v6/all-props/#duration)

:::

:::{confval} tippy_add_class
Add a class name to all elements with tips.

For example this can be used to change the style of the cursor when hovering over a tip (see [`html_css_files`](https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-html_css_files)):

`conf.py`:

```python
html_static_path = ['_static']
html_css_files = ["tippy.css"]
tippy_add_class = "has-tippy"
```

`_static/tippy.css`:

```css
.has-tippy:hover {
    cursor: help;
}
```

:::

### Filters

These configurations enable filtering of what tips are created, and shown.

:::{confval} tippy_skip_urls
A list of URL [regexes](https://docs.python.org/3/howto/regex.html#regex-howto) to skip, for example:

```python
tippy_skip_urls = [
    "https://example.com/name_prefix.*",
]
```

:::

:::{confval} tippy_skip_pages
A list of page names or directories to skip, for example:

```python
tippy_skip_urls = [
    "custom_page",
    "directory/custom_pages/"
]
```

:::



:::{confval} tippy_tip_selector
Define what elements tips are created for, by default:

```python
tippy_tip_selector = "figure, table, img, p, aside, div.admonition, div.literal-block-wrapper"
```

:::

:::{confval} tippy_skip_anchor_classes
Skip showing tooltips for anchors with these classes, by default:

```python
tippy_skip_anchor_classes = (
    "headerlink",
    "sd-stretched-link",
)
```

:::

:::{confval} tippy_anchor_parent_selector
Only show tool tips for anchors within this select, by default `""`, examples:

```python
# For Furo theme:
tippy_anchor_parent_selector = "div.content"
# For pydata theme:
tippy_anchor_parent_selector = "article.bd-article"
```

:::

### External APIs

These configurations enable fetching tips from external APIs.

:::{confval} tippy_rtd_urls
A list of URL prefixes to use for ReadTheDocs tooltips (using the [`/api/v3/embed/` API](https://docs.readthedocs.io/en/stable/api/v3.html#embed)), for example:

```python
tippy_rtd_urls = [
    "https://www.sphinx-doc.org/en/master/",
]
```

This works for any ReadTheDocs hosted documentation.
It works well with the [intersphinx extension](https://www.sphinx-doc.org/en/master/usage/quickstart.html#intersphinx).

:::

:::{confval} tippy_enable_wikitips
Enable tooltips for wikipedia links, starting `https://en.wikipedia.org/wiki/`, by default `True`.
:::

:::{confval} tippy_enable_doitips
Enable tooltips for DOI links, starting `https://doi.org/`, by default `True`.
:::

:::{confval} tippy_doi_api
The API to use for DOI tooltips, by default `https://api.crossref.org/works/`
(another possibility is `https://api.datacite.org/dois/`)
:::

:::{confval} tippy_doi_template
The [jinja template](https://jinja.palletsprojects.com) to use for formatting DOI data to tooltips, by default:

```jinja
{% set attrs = data.message %}
<div>
    <h3>{{ attrs.title[0] }}</h3>
    {% if attrs.author is defined %}
    <p><b>Authors:</b> {{ attrs.author | map_join('given', 'family') | join(', ')  }}</p>
    {% endif %}
    <p><b>Publisher:</b> {{ attrs.publisher }}</p>
    <p><b>Published:</b> {{ attrs.created['date-parts'][0] | join('-') }}</p>
</div>
```

(See <https://github.com/CrossRef/rest-api-doc/blob/master/api_format.md>)
:::


### Miscellaneous

:::{confval} tippy_custom_tips
A dictionary, mapping URLs to HTML strings, which will be used to create custom tips.

For example, to add a tip for the URL `https://example.com`:

```python
tippy_custom_tips = {
    "https://example.com": "<p>This is a custom tip!</p>"
}
```

:::

:::{confval} tippy_enable_mathjax
Whether to enable tooltips for math equations, by default `False`.

Note, this requires the `sphinx.ext.mathjax` extension to be enabled.
At present it will cause `mathjax` to be loaded on every page, even if it is not used.
:::

:::{confval} tippy_js
The Javascript required to enable tooltips, by default:

```python
tippy_js = ("https://unpkg.com/@popperjs/core@2", "https://unpkg.com/tippy.js@6")
```

:::
