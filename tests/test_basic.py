from sphinx_pytest.plugin import CreateDoctree

from sphinx_tippy import rewrite_glossary_term_links


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


def test_rewrite_glossary_term_links_empty_base_url():
    """Test that no rewriting happens when glossary_base_url is empty."""
    content = '<p>See <a href="#term-Other">Other</a></p>'
    result = rewrite_glossary_term_links(content, "")
    assert "#term-Other" in result


def test_rewrite_glossary_term_links_with_base_url():
    """Test that glossary term links are rewritten with the base URL."""
    content = '<p>See <a href="#term-Compound-Operation">Compound Operation</a></p>'
    result = rewrite_glossary_term_links(content, "glossary.html")
    assert 'href="glossary.html#term-Compound-Operation"' in result


def test_rewrite_glossary_term_links_preserves_other_links():
    """Test that non-glossary links are preserved."""
    content = """<p>
        <a href="#term-Something">Term</a>
        <a href="#other-anchor">Other</a>
        <a href="page.html#section">External</a>
    </p>"""
    result = rewrite_glossary_term_links(content, "glossary.html")
    assert 'href="glossary.html#term-Something"' in result
    assert 'href="#other-anchor"' in result
    assert 'href="page.html#section"' in result


def test_rewrite_glossary_term_links_multiple_terms():
    """Test that multiple glossary term links are all rewritten."""
    content = """<p>
        <a href="#term-First">First</a> and
        <a href="#term-Second">Second</a>
    </p>"""
    result = rewrite_glossary_term_links(content, "glossary.html")
    assert 'href="glossary.html#term-First"' in result
    assert 'href="glossary.html#term-Second"' in result


def test_glossary_base_url_config(sphinx_doctree: CreateDoctree):
    """Test that tippy_glossary_base_url config is properly set."""
    sphinx_doctree.set_conf(
        {
            "extensions": ["sphinx_tippy"],
            "tippy_glossary_base_url": "glossary.html",
        }
    )
    sphinx_doctree.buildername = "html"
    result = sphinx_doctree(
        """
Test
----

Some content.
        """,
    )
    assert result.app.env.tippy_config.glossary_base_url == "glossary.html"
