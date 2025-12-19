from unittest.mock import MagicMock

from sphinx_pytest.plugin import CreateDoctree

from sphinx_tippy import merge_tippy_data, setup


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


def test_parallel_read_safe():
    """Test that the extension reports correct parallel safety flags."""
    app = MagicMock()
    result = setup(app)
    assert result["parallel_read_safe"] is True
    assert result["parallel_write_safe"] is False


def test_merge_tippy_data_basic(sphinx_doctree: CreateDoctree):
    """Test that tippy data merging works with real Sphinx environment."""
    sphinx_doctree.set_conf({"extensions": ["sphinx_tippy"]})
    sphinx_doctree.buildername = "html"
    result = sphinx_doctree(
        """
Test Page
=========

Some content.
    """,
    )

    # Simulate data from another worker
    other_env = MagicMock()
    other_env.tippy_data = {
        "pages": {
            "other_page": {
                "element_id_map": {"other-id": "other-id"},
                "id_to_html": {"other-id": "<p>Other content</p>"},
            },
        }
    }

    # Merge the data
    merge_tippy_data(result.app, result.app.env, [], other_env)

    # Verify both pages exist after merge
    assert "index" in result.app.env.tippy_data["pages"]
    assert "other_page" in result.app.env.tippy_data["pages"]


def test_merge_tippy_data_empty_other(sphinx_doctree: CreateDoctree):
    """Test merging when other environment has no tippy data."""
    sphinx_doctree.set_conf({"extensions": ["sphinx_tippy"]})
    sphinx_doctree.buildername = "html"
    result = sphinx_doctree(
        """
Test Page
=========

Some content.
    """,
    )

    # Simulate worker with no tippy data
    other_env = MagicMock(spec=[])  # no tippy_data attribute

    original_pages = set(result.app.env.tippy_data["pages"].keys())

    # Merge should not fail and should preserve existing data
    merge_tippy_data(result.app, result.app.env, [], other_env)

    assert set(result.app.env.tippy_data["pages"].keys()) == original_pages
