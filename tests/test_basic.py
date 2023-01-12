from sphinx_pytest.plugin import CreateDoctree


def test_basic(sphinx_doctree: CreateDoctree):
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
    """
    )
    assert (
        [li.rstrip() for li in result.pformat().strip().splitlines()]
        == """
<document source="<src>/index.rst">
    <section ids="test" names="test">
        <title>
            Test
    """.strip().splitlines()
    )
