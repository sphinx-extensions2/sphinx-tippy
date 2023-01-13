from sphinx_pytest.plugin import CreateDoctree


def test_basic(sphinx_doctree: CreateDoctree, data_regression):
    sphinx_doctree.set_conf({"extensions": ["sphinx_tippy"]})
    sphinx_doctree.buildername = "html"
    sphinx_doctree.srcdir.joinpath("hallo.png").touch()
    result = sphinx_doctree(
        """
.. _abc:

Test
----

.. figure:: hallo.png
    :name: whatever

    Caption
    """,
    )
    # remove js_path which are not deterministic
    for value in result.app.env.tippy_data["pages"].values():
        value.pop("js_path", None)
    data_regression.check(result.app.env.tippy_data)
