"""Get rich tool tips in your sphinx documentation!"""
from __future__ import annotations

__version__ = "0.1.0"

import json
from contextlib import suppress
from pathlib import Path

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
    app.connect("html-page-context", add_html_context)
    return {"version": __version__, "parallel_read_safe": True}


LOGGER = getLogger(__name__)


def add_html_context(
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

    # We want a mapping for every <local id> -> <tip HTML>
    # It should only contain ids that are actually referenced (by `a[href]`)
    # For the tip HTML:
    # - we should remove any `id` attributes
    # - all `a[href]` should be converted to `span`
    # - if the tip is a single paragraph, we want to use the paragraph text

    # docutils outputs the first id of a component on the actual component
    # then for subsequent ids, it creates a span with the id
    # (see HTMLTranslator.starttag)
    # so here we create a mapping of all ids to the first id that will be on the actual component
    id_map = {}
    for node in doctree.findall():
        if "ids" not in node or not node["ids"]:
            continue
        i1 = node["ids"][0]
        id_map[i1] = i1
        id_map.update({ix: i1 for ix in node["ids"][1:]})

    # load the body HTML
    body = BeautifulSoup(context["body"], "html.parser")

    # loop through all href
    anchor: Tag
    required_local_ids = set()
    for anchor in body.find_all("a", {"href": True}):
        # determine if the href is local or to another file in the site
        # e.g. `#target` or `path/to/file.html#target`
        href_parts = anchor["href"].split("#", maxsplit=1)
        if len(href_parts) == 1:
            path = href_parts[0]
            target = None
        else:
            path, target = href_parts

        if not path and target and target in id_map:
            required_local_ids.add(id_map[target])

        # TODO handle targets with a local path

    # Create a mapping of ids to the HTML to show in the tooltip
    id_to_html: dict[str, str] = {}
    tag: Tag
    for tag in body.find_all(id=True):
        if tag.name in {"figure", "table", "img", "dt", "p"}:
            # copy the whole HTML
            id_to_html[tag["id"]] = str(tag)
        # TODO for dt maybe get "some" of sibling dd content (first paragraph(s))
        # e.g. to get autodoc docstrings
        elif tag.name == "section":
            # find the first heading and show that
            header = tag.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            if header:
                id_to_html[tag["id"]] = str(header)
                # try to append the first paragraph
                with suppress(AttributeError):
                    para = header.find_next_sibling("p", recursive=False)
                    if para:
                        id_to_html[tag["id"]] += str(para)

    # filter id_to_html to only include ids that are actually referenced
    local_id_to_html = {k: v for k, v in id_to_html.items() if k in required_local_ids}

    if not local_id_to_html:
        # no ids to show, so nothing to do
        return

    # create the JS file
    content = f"""
ids = {json.dumps(id_map)}
data = {json.dumps(local_id_to_html)}

window.onload = function () {{
    for (const [id, data_id] of Object.entries(ids)) {{
        if (!(data_id in data)) {{
            continue;
        }};
        const links = document.querySelectorAll(`a[href="#${{id}}"]`);
        for (const link of links) {{
            tippy(link, {{
                content: data[data_id],
                allowHTML: true,
                interactive: false,
            }});
        }};
    }};
}};
"""

    # create path based on pagename
    # TODO handle Windows paths?
    js_path = Path(app.outdir, "_static", pagename).with_suffix(".tippy.js")
    js_path.parent.mkdir(parents=True, exist_ok=True)
    with js_path.open("w", encoding="utf8") as handle:
        handle.write(content)

    for js_file in app.config.tippy_js:
        app.add_js_file(js_file, loading_method="defer")
    app.add_js_file(
        str(js_path.relative_to(Path(app.outdir, "_static"))), loading_method="defer"
    )


def doctree_read(app: Sphinx, doctree: nodes.document):
    """Setup the doctree."""
    # metadata = app.env.metadata[app.env.docname]
    # if "py-config" in metadata:
    #     try:
    #         data = json.loads(metadata["py-config"])
    #         assert isinstance(data, dict), "must be a dictionary"
    #     except Exception as exc:
    #         LOGGER.warning(
    #             f"Could not parse pyscript config: {exc}", location=(app.env.docname, 0)
    #         )
    #     else:
    #         doctree["pyscript"] = True
    #         data_str = json.dumps(data, indent=2)
    #         doctree.append(
    #             nodes.raw(
    #                 "",
    #                 f'<py-config type="json">\n{data_str}\n</py-config>\n',
    #                 format="html",
    #             )
    #         )
