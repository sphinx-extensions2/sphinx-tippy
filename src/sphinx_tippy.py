"""Get rich tool tips in your sphinx documentation!"""
from __future__ import annotations

import json
import posixpath
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, TypedDict, cast

from bs4 import BeautifulSoup, NavigableString, Tag
from docutils import nodes
from sphinx.application import Sphinx
from sphinx.domains.math import MathDomain
from sphinx.errors import ExtensionError
from sphinx.util.logging import getLogger

try:
    # sphinx 6.1
    from sphinx.util.display import status_iterator  # type: ignore[import]
except ImportError:
    from sphinx.util import status_iterator

__version__ = "0.2.0"


def setup(app: Sphinx):
    """Setup the extension"""
    app.add_config_value("tippy_custom_tips", {}, "html", Dict[str, str])
    app.add_config_value(
        "tippy_tip_selector",
        "figure, table, img, p, aside, div.admonition, div.literal-block-wrapper",
        "html",
    )
    app.add_config_value(
        "tippy_skip_anchor_classes",
        (
            "headerlink",
            "sd-stretched-link",
        ),
        "html",
    )
    app.add_config_value("tippy_anchor_parent_selector", "", "html")
    app.add_config_value("tippy_enable_wikitips", True, "html")
    app.add_config_value("tippy_enable_mathjax", False, "html")
    app.add_config_value(
        "tippy_js",
        ("https://unpkg.com/@popperjs/core@2", "https://unpkg.com/tippy.js@6"),
        "html",
    )
    app.connect("builder-inited", validate_config)
    app.connect("html-page-context", collect_tips, priority=450)  # before mathjax
    app.connect("build-finished", write_tippy_js)
    return {"version": __version__, "parallel_read_safe": True}


LOGGER = getLogger(__name__)


@dataclass
class TippyConfig:
    custom_tips: dict[str, str]
    tip_selector: str
    skip_anchor_classes: tuple[str, ...]
    anchor_parent_selector: str
    enable_wikitips: bool
    enable_mathjax: bool
    js_files: tuple[str, ...]


def get_tippy_config(app: Sphinx) -> TippyConfig:
    """Get the tippy config"""
    return TippyConfig(
        custom_tips=app.config.tippy_custom_tips,
        tip_selector=app.config.tippy_tip_selector,
        skip_anchor_classes=app.config.tippy_skip_anchor_classes,
        anchor_parent_selector=app.config.tippy_anchor_parent_selector,
        enable_wikitips=app.config.tippy_enable_wikitips,
        enable_mathjax=app.config.tippy_enable_mathjax,
        js_files=app.config.tippy_js,
    )


def validate_config(app: Sphinx):
    """Validate the config"""
    if app.builder.name != "html":
        return
    if (
        app.config.tippy_enable_mathjax
        and app.builder.math_renderer_name != "mathjax"  # type: ignore[attr-defined]
    ):
        raise ExtensionError("tippy_enable_mathjax=True requires mathjax to be enabled")


class TippyData(TypedDict):
    pages: dict[str, TippyPageData]


class TippyPageData(TypedDict):
    element_id_map: dict[str, str]
    refs_in_page: set[tuple[None | str, None | str]]
    id_to_html: dict[str | None, str]
    custom_in_page: set[str]
    wiki_titles: set[str]


def get_tippy_data(app: Sphinx) -> TippyData:
    """Get the tippy data"""
    if not hasattr(app.env, "tippy_data"):
        app.env.tippy_data = {"pages": {}, "wiki_titles": set()}  # type: ignore
    return cast(TippyData, app.env.tippy_data)  # type: ignore


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

    page_parent = posixpath.dirname(pagename)
    tippy_config = get_tippy_config(app)
    custom_tips = tippy_config.custom_tips

    if tippy_config.enable_mathjax:
        # TODO ideally we would only run this on pages that have math in the tips
        domain = cast(MathDomain, app.env.get_domain("math"))
        domain.data["has_equations"][pagename] = True

    element_id_map = create_element_id_map(doctree)

    # load the body HTML
    body = BeautifulSoup(context["body"], "html.parser")

    # Find all href in the document, and determine if they require a tip
    anchor: Tag
    refs_in_page: set[tuple[None | str, str | None]] = set()
    custom_in_page: set[str] = set()
    wiki_titles: set[str] = set()
    for anchor in body.find_all("a", {"href": True}):

        if not isinstance(anchor["href"], str):
            continue

        if anchor["href"] in custom_tips:
            custom_in_page.add(anchor["href"])
            continue

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

        if tippy_config.enable_wikitips and path.startswith(
            "https://en.wikipedia.org/wiki/"
        ):
            wiki_titles.add(path[30:])

        # check if the reference is on another local page
        # TODO for now we assume that page names are written in posix style with ".html" prefixes
        # and that the page name relates to the docname
        elif path.endswith(".html"):
            other_pagename = posixpath.normpath(posixpath.join(page_parent, path[:-5]))
            if other_pagename in app.env.all_docs:
                refs_in_page.add((other_pagename, target))

    id_to_tip_html = create_id_to_tip_html(tippy_config, body)

    # store the data for later use
    tippy_data = get_tippy_data(app)
    tippy_data["pages"][pagename] = {  # type: ignore
        "element_id_map": element_id_map,
        "refs_in_page": refs_in_page,
        "id_to_html": id_to_tip_html,
        "custom_in_page": custom_in_page,
        "wiki_titles": wiki_titles,
    }

    # add the JS files
    js_path = Path(app.outdir, "_static", pagename).with_suffix(".tippy.js")
    for js_file in tippy_config.js_files:
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
    for node in getattr(doctree, "findall", doctree.traverse)():
        try:
            ids = node["ids"]
        except Exception:
            continue
        if not ids:
            continue
        i1 = ids[0]
        id_map[i1] = i1
        id_map.update({ix: i1 for ix in ids[1:]})
    return id_map


def create_id_to_tip_html(
    config: TippyConfig, body: BeautifulSoup
) -> dict[str | None, str]:
    """Create a mapping of ids to the HTML to show in the tooltip."""
    id_to_html: dict[str | None, str] = {}

    # create a tip for the actual page, by finding the first heading
    if title := body.find(["h1", "h2", "h3", "h4", "h5", "h6"]):
        id_to_html[None] = _get_header_html(title) + "<p>...</p>"

    tag: Tag

    # these are tags where we simply copy the whole HTML
    for tag in body.select(config.tip_selector):
        if "id" in tag.attrs:
            id_to_html[str(tag["id"])] = str(tag)

    # these are tags where we copy the HTML in a bespoke way
    for tag in body.find_all(id=True):

        if tag.name == "dt":
            # copy the whole HTML
            id_to_html[str(tag["id"])] = str(tag)
            # if the next tag is a dd, copy that too
            if (next_sibling := next_sibling_tag(tag)) and next_sibling.name == "dd":
                copy_dd = next_sibling.__copy__()
                # limit the children to certain numbers and types
                child_count = 0
                for child in list(copy_dd.children):
                    if not isinstance(child, Tag):
                        child.extract()
                    elif child_count > 5 or child.name != "p":
                        child.decompose()
                    else:
                        child_count += 1

                id_to_html[str(tag["id"])] += str(copy_dd)

        elif tag.name == "section" and (
            header := tag.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        ):
            id_to_html[str(tag["id"])] = _get_header_html(header) + "<p>...</p>"

        elif tag.name == "div" and "math-wrapper" in (tag.get("class") or []):
            # remove an span with eqno class, since it is not needed
            # and it can cause issues with the tooltip
            # (e.g. if the span is the last element in the div)
            tag_copy = tag.__copy__()
            for child in tag_copy.find_all("span"):
                if isinstance(child, Tag) and "eqno" in (child.get("class") or []):
                    child.decompose()
            id_to_html[str(tag["id"])] = str(tag_copy)

    return id_to_html


def next_sibling_tag(tag: Tag) -> Tag | None:
    """Get the next tag."""
    for sibling in tag.next_siblings:
        if isinstance(sibling, Tag):
            return sibling
    return None


def _get_header_html(header: Tag | NavigableString, _start: bool = True) -> str:
    """Get the HTML for a header tag, including itself and some following content."""
    if not _start or not isinstance(header, Tag):
        output = str(header)
    else:
        header_copy = header.__copy__()
        header_copy["style"] = "margin-top: 0;"
        # add a class
        if "class" in header_copy.attrs:
            header_copy["class"].append("tippy-header")  # type: ignore[union-attr]
        else:
            header_copy["class"] = ["tippy-header"]
        output = str(header_copy)
    for sibling in header.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.name == "section":
            if sub_header := sibling.find(["h1", "h2", "h3", "h4", "h5", "h6"]):
                output += _get_header_html(sub_header, False)
            break
        if sibling.name == "p":
            output += str(sibling)
            if (next_sibling := next_sibling_tag(sibling)) and next_sibling.name == "p":
                output += str(next_sibling)
            break
    return output


SCHEMA_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def rewrite_local_attrs(content: str, rel_path: str) -> str:
    """Find all attributes with local links and rewrite them."""
    if not rel_path:
        return content
    soup = BeautifulSoup(content, "html.parser")
    for tag, attr in [("a", "href"), ("img", "src")]:
        for element in soup.find_all(tag, {attr: True}):
            if SCHEMA_REGEX.match(element[attr]) or element[attr].startswith("#"):
                continue
            element[attr] = posixpath.normpath(posixpath.join(rel_path, element[attr]))
    return str(soup)


def generate_wikipedia_tooltip(title: str) -> str:
    """Generate a wikipedia tooltip, from a title."""

    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read())

    extract_html = data["extract_html"]
    if "thumbnail" in data:
        thumbnail_url = data["thumbnail"]["source"]
        style = "float:left; margin-right:10px;"
        alt = "Wikipedia thumbnail"
        extract_html = (
            f'<img src="{thumbnail_url}" alt="{alt}" style="{style}">' + extract_html
        )

    return extract_html


def write_tippy_js(app: Sphinx, exception: Any):
    """For each page, filter the list of reference tooltips to only those on the page,
    and write the JS file.
    """
    if exception:
        return
    if app.builder.format != "html":
        return

    tippy_page_data = get_tippy_data(app)["pages"]

    # fetch the wikipedia tooltips, caching them for rebuilds
    wiki_cache: dict[str, str]
    wiki_cache_path = Path(app.outdir, "tippy_wiki_cache.json")
    if wiki_cache_path.exists():
        with wiki_cache_path.open("r") as file:
            wiki_cache = json.load(file)
    else:
        wiki_cache = {}
    wiki_fetch = {
        title
        for page in tippy_page_data.values()
        for title in page["wiki_titles"]
        if title not in wiki_cache
    }
    for title in status_iterator(
        wiki_fetch, "Fetching Wikipedia tips", length=len(wiki_fetch)
    ):
        try:
            wiki_cache[title] = generate_wikipedia_tooltip(title)
        except Exception as exc:
            LOGGER.warning(
                f"Could not fetch Wikipedia data for {title}: {exc} [tippy.wiki]",
                type="tippy",
                subtype="wiki",
            )
    with wiki_cache_path.open("w") as file:
        json.dump(wiki_cache, file)

    for pagename in status_iterator(
        tippy_page_data, "Writing .tippy.js files", length=len(tippy_page_data)
    ):
        write_tippy_js_page(app, pagename, wiki_cache)


def write_tippy_js_page(app: Sphinx, pagename: str, wiki_cache: dict[str, str]):

    tippy_page_data = get_tippy_data(app)["pages"]
    tippy_config = get_tippy_config(app)
    data = tippy_page_data[pagename]

    local_id_map = data["element_id_map"]
    local_id_to_html = data["id_to_html"]
    selector_to_html: dict[str, str] = {
        f'a[href="{ref}"]': tippy_config.custom_tips[ref]
        for ref in data["custom_in_page"]
    }
    for wiki_title in data["wiki_titles"]:
        if wiki_title in wiki_cache:
            selector_to_html[
                f'a[href="https://en.wikipedia.org/wiki/{wiki_title}"]'
            ] = wiki_cache[wiki_title]
            selector_to_html[
                f'a[href^="https://en.wikipedia.org/wiki/{wiki_title}#"]'
            ] = wiki_cache[wiki_title]
    for refpage, target in data["refs_in_page"]:

        if refpage is not None:
            relpage = posixpath.normpath(
                posixpath.relpath(refpage, posixpath.dirname(pagename))
            )
            relfolder = posixpath.dirname(relpage)
            if refpage not in tippy_page_data:
                pass
            elif target is None:
                selector_to_html[f'a[href="{relpage}.html"]'] = rewrite_local_attrs(
                    tippy_page_data[refpage]["id_to_html"][None], relfolder
                )
            elif (
                target
                and target in tippy_page_data[refpage]["element_id_map"]
                and tippy_page_data[refpage]["element_id_map"][target]
                in tippy_page_data[refpage]["id_to_html"]
            ):
                html_str = tippy_page_data[refpage]["id_to_html"][
                    tippy_page_data[refpage]["element_id_map"][target]
                ]
                html_str = rewrite_local_attrs(html_str, relfolder)
                selector_to_html[f'a[href="{relpage}.html#{target}"]'] = html_str
        elif target is None:
            selector_to_html['a[href="#"]'] = local_id_to_html[None]
        elif target in local_id_map and local_id_map[target] in local_id_to_html:
            selector_to_html[f'a[href="#{target}"]'] = local_id_to_html[
                local_id_map[target]
            ]

    pselector = tippy_config.anchor_parent_selector
    mathjax = (
        (
            "onShow(instance) "
            "{MathJax.typesetPromise([instance.popper]).then(() => {});},"
        )
        if tippy_config.enable_mathjax
        and app.builder.math_renderer_name == "mathjax"  # type: ignore[attr-defined]
        else ""
    )
    # TODO need to only enable when math,
    # and then need to ensure sphinx adds mathjax to the page

    content = (
        dedent(
            f"""\
        selector_to_html = {json.dumps(selector_to_html)}
        skip_classes = {json.dumps(tippy_config.skip_anchor_classes)}

        window.onload = function () {{
            for (const [select, tip_html] of Object.entries(selector_to_html)) {{
                const links = document.querySelectorAll(`{pselector} ${{select}}`);
                for (const link of links) {{
                    if (skip_classes.some(c => link.classList.contains(c))) {{
                        continue;
                    }}
                    tippy(link, {{
                        content: tip_html,
                        allowHTML: true,
                        interactive: false,
                        {mathjax}
                    }});
                }};
            }};
            console.log("tippy tips loaded!");
        }};
        """
        )
        if selector_to_html
        else ""
    )

    # create path based on pagename
    js_path = Path(app.outdir, "_static", *pagename.split("/")).with_suffix(".tippy.js")
    js_path.parent.mkdir(parents=True, exist_ok=True)
    with js_path.open("w", encoding="utf8") as handle:
        handle.write(content)
