# Sphinx PyScript

Get rich tool tips in your sphinx documentation!

Using <https://atomiks.github.io/tippyjs>

```{toctree}
folder/other
```

## Installation

Install with pip:

```bash
pip install sphinx-tippy
```

(usage/xx)=
## Usage

Add the extension to your `conf.py`:

```python
extensions = [
    "sphinx_tippy",
]
```

[custom tip](https://example.com)

(xxx)=
```{figure} https://via.placeholder.com/150
:name: hallo
Caption
```

```{table} Table caption
:name: table

 a  |  b
--- | ---
c   | d
```

```{image} fun-fish.png
:width: 1000px
:name: fun-fish
```

````{py:class} Foo
This is a class

It has a docstring
```{py:method} bar(variable: str) -> int
This is a method
```
````

```{math}
:label: eq1
a = 1
```

{ref}`hallo`

{ref}`xxx`

{ref}`yep <fun-fish>`

{py:class}`Foo`

{ref}`table`

{ref}`other`

{ref}`usage/xx`

{doc}`folder/other`

{doc}`../index`

{eq}`eq1`

{confval}`name`

## Configuration

The extension has the following configuration options:

```{confval} name
something
```
