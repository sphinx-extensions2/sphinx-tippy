
# Content page

This is an example of a page with lots of elements we would like to reference.

```{figure} ../fun-fish.png
:name: figure-name-file
Other Caption
```

(figure-name-dup)=
```{figure} https://via.placeholder.com/150
:name: figure-name-url
Caption
```

```{table} Table caption
:name: table-name

heading1 | heading2
-------- | --------
value1   | value2
```

```{image} ../fun-fish.png
:width: 200px
:align: center
:name: image-name
```

````{py:class} Foo
This is a class

It has a docstring
```{py:method} bar(variable: str) -> int
This is a method
```
````

```{math}
:label: math-name
\mathbf{u} \times \mathbf{v}=\left|\begin{array}{ll}u_{2} & u_{3} \\ v_{2} & v_{3}\end{array}\right| \mathbf{i}+\left|\begin{array}{ll}u_{3} & u_{1} \\ v_{3} & v_{1}\end{array}\right| \mathbf{j}+\left|\begin{array}{ll}u_{1} & u_{2} \\ v_{1} & v_{2}\end{array}\right| \mathbf{k}
```

```{code-block}
:caption: Code block caption
:name: code-name

print("Hello World")
```

:::{glossary}
term
    This is a definition of a term.
:::

:::{note}
:name: admonition-name
This is an admonition
:::

{doc}`../index`
