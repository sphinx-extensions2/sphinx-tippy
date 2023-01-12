"""Get rich tool tips in your sphinx documentation!"""
from __future__ import annotations

__version__ = "0.1.0"

import json
from contextlib import suppress
from pathlib import Path
from textwrap import dedent
from typing import Any, TypedDict, cast

from bs4 import BeautifulSoup, Tag
from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.logging import getLogger


def setup(app: Sphinx):
    """Setup the extension"""
    app.add_config_value(
        "tippy_js",
        ("https://unpkg.com/@popperjs/core@2", "https://unpkg.com/tippy.js@6"),
        "env",
    )
    # app.connect("doctree-read", doctree_read)
    app.connect("html-page-context", collect_tips)
    app.connect("build-finished", write_tippy_js)
    return {"version": __version__, "parallel_read_safe": True}


LOGGER = getLogger(__name__)


class TippyData(TypedDict):
    element_id_map: dict[str, str]
    refs_in_page: set[tuple[None | str, None | str]]
    id_to_html: dict[str, str]


def collect_tips(
    app: Sphinx,
    pagename: str,
    templatename: str,
    context: dict,
    doctree: nodes.document,
) -> None:
    """Add extra variables to the HTML template context."""
    if not doctree:
        # only process pages with a doctree,
        # i.e. that came from a source document
        return

    element_id_map = create_element_id_map(doctree)

    # load the body HTML
    body = BeautifulSoup(context["body"], "html.parser")

    # TODO what if referencing another document

    # Find all href in the document, and determine if they require a tip
    anchor: Tag
    refs_in_page: set[tuple[None | str, str]] = set()
    for anchor in body.find_all("a", {"href": True}):

        # split up the href into a path and a target,
        # e.g. `path/to/file.html#target` -> `path/to/file.html` and `target`
        href_parts: list[str] = anchor["href"].split("#", maxsplit=1)
        path: str
        target: str | None
        if len(href_parts) == 1:
            path = href_parts[0]
            target = None
        else:
            path, target = href_parts
            target = target or None

        # check if the reference is local to this page
        if not path:
            refs_in_page.add((None, target))

        # check if the reference is on another page

    id_to_tip_html = create_id_to_tip_html(body)

    # store the data for later use
    if not hasattr(app.env, "tippy_data"):
        app.env.tippy_data = cast(dict[str, TippyData], {})
    app.env.tippy_data[pagename] = {
        "element_id_map": element_id_map,
        "refs_in_page": refs_in_page,
        "id_to_html": id_to_tip_html,
    }

    # add the JS files
    js_path = Path(app.outdir, "_static", pagename).with_suffix(".tippy.js")
    for js_file in app.config.tippy_js:
        app.add_js_file(js_file, loading_method="defer")
    app.add_js_file(
        str(js_path.relative_to(Path(app.outdir, "_static"))), loading_method="defer"
    )


def create_element_id_map(doctree: nodes.document) -> dict[str, str]:
    """
    docutils outputs the first `id` of a element on the actual element
    then, for subsequent ids, it creates a span with the `id` (see HTMLTranslator.starttag).
    So here we create a mapping of all ids to the first id that will be on the actual element.
    """
    id_map: dict[str, str] = {}
    for node in doctree.findall():
        if "ids" not in node or not node["ids"]:
            continue
        i1 = node["ids"][0]
        id_map[i1] = i1
        id_map.update({ix: i1 for ix in node["ids"][1:]})
    return id_map


def create_id_to_tip_html(body: BeautifulSoup) -> dict[str | None, str]:
    """Create a mapping of ids to the HTML to show in the tooltip."""
    id_to_html: dict[str | None, str] = {}

    # create a tip for the actual page, by finding the first heading
    if header := body.find(["h1", "h2", "h3", "h4", "h5", "h6"]):
        id_to_html[None] = str(header)
        # try to append the first paragraph
        with suppress(AttributeError):
            para = header.find_next_sibling("p", recursive=False)
            if para:
                id_to_html[None] += str(para)

    tag: Tag
    for tag in body.find_all(id=True):
        if tag.name in {"figure", "table", "img", "dt", "p"}:
            # copy the whole HTML
            id_to_html[tag["id"]] = str(tag)
        # TODO for dt maybe get "some" of sibling dd content (first paragraph(s))
        # e.g. to get autodoc docstrings
        elif tag.name == "section":
            # find the first heading and show that
            if header := tag.find(["h1", "h2", "h3", "h4", "h5", "h6"]):
                id_to_html[tag["id"]] = str(header)
                # try to append the first paragraph
                with suppress(AttributeError):
                    para = header.find_next_sibling("p", recursive=False)
                    if para:
                        id_to_html[tag["id"]] += str(para)
        # TODO this doesn't load it with mathjax
        # elif tag.name == "div" and "math-wrapper" in (tag.get("class") or []):
        #     id_to_html[tag["id"]] = str(tag)
    return id_to_html


def write_tippy_js(app: Sphinx, exception: Any):
    """Setup the doctree."""
    if exception:
        return

    tippy_data = cast(dict[str, TippyData], getattr(app.env, "tippy_data", {}))

    for pagename, data in tippy_data.items():

        local_id_map = data["element_id_map"]
        local_id_to_html = data["id_to_html"]
        local_refs_to_html = {}
        for page, target in data["refs_in_page"]:
            if page is not None:
                continue
            if target is None:
                local_refs_to_html[""] = local_id_to_html[None]
                continue
            if target in local_id_map and local_id_map[target] in local_id_to_html:
                local_refs_to_html[target] = local_id_to_html[local_id_map[target]]

        if local_refs_to_html:
            # allow to skip for links with certain classes
            content = dedent(
                f"""\
                local_refs_to_html = {json.dumps(local_refs_to_html)}

                window.onload = function () {{
                    for (const [id, tip_html] of Object.entries(local_refs_to_html)) {{
                        const links = document.querySelectorAll(`a[href="#${{id}}"]`);
                        for (const link of links) {{
                            tippy(link, {{
                                content: tip_html,
                                allowHTML: true,
                                interactive: true,
                            }});
                        }};
                    }};
                    console.log("tippy tips loaded!");
                }};
                """
            )
        else:
            content = ""

        # create path based on pagename
        # TODO handle Windows paths?
        js_path = Path(app.outdir, "_static", pagename).with_suffix(".tippy.js")
        js_path.parent.mkdir(parents=True, exist_ok=True)
        with js_path.open("w", encoding="utf8") as handle:
            handle.write(content)
