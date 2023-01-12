# Sphinx PyScript

Get rich tool tips in your sphinx documentation!

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

[hi](https://via.placeholder.com/150)

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
```{py:method} bar(variable: str) -> int
This is a method
```
````

{ref}`hallo`

{ref}`xxx`

{ref}`yep <fun-fish>`

{py:meth}`Foo.bar`

{ref}`table`

{ref}`other`

{ref}`usage/xx`

## Configuration

The extension has the following configuration options:

xxx
: something
