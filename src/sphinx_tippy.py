"""Get rich tool tips in your sphinx documentation!"""

from __future__ import annotations

import json
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Any, Sequence, TypedDict, cast
from uuid import uuid4

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from docutils import nodes
from jinja2 import Environment
from sphinx.application import Sphinx
from sphinx.domains.math import MathDomain
from sphinx.errors import ExtensionError
from sphinx.util.logging import getLogger

try:
    # sphinx 6.1
    from sphinx.util.display import status_iterator  # type: ignore[import]
except ImportError:
    from sphinx.util import status_iterator

__version__ = "0.4.3"


def setup(app: Sphinx):
    """Setup the extension"""
    app.add_config_value("tippy_props", {}, "html")
    # config for filtering tooltip creation/showing
    app.add_config_value("tippy_skip_urls", (), "html", [list, tuple])
    app.add_config_value(
        "tippy_skip_anchor_classes",
        (
            "headerlink",
            "sd-stretched-link",
        ),
        "html",
        [list, tuple],
    )
    app.add_config_value("tippy_anchor_parent_selector", "", "html")

    app.add_config_value("tippy_custom_tips", {}, "html", (dict,))
    app.add_config_value(
        "tippy_tip_selector",
        "figure, table, img, p, aside, div.admonition, div.literal-block-wrapper",
        "html",
    )
    # config for API based tooltips
    app.add_config_value("tippy_enable_wikitips", True, "html")
    app.add_config_value("tippy_enable_doitips", True, "html")
    app.add_config_value("tippy_rtd_urls", [], "html", [list, tuple])
    app.add_config_value("tippy_doi_api", "https://api.crossref.org/works/", "html")
    # see https://github.com/CrossRef/rest-api-doc/blob/master/api_format.md
    # or for https://api.datacite.org/dois/
    # see https://support.datacite.org/docs/api-get-doi
    # and http://schema.datacite.org/meta/kernel-4.4/metadata.xsd
    default_doi_template = dedent(
        """\
        {% set attrs = data.message %}
        <div>
            <h3>{{ attrs.title[0] }}</h3>
            {% if attrs.author is defined %}
            <p><b>Authors:</b> {{ attrs.author | map_join('given', 'family') | join(', ')  }}</p>
            {% endif %}
            <p><b>Publisher:</b> {{ attrs.publisher }}</p>
            <p><b>Published:</b> {{ attrs.created['date-parts'][0] | join('-') }}</p>
        </div>
        """
    )
    app.add_config_value("tippy_doi_template", default_doi_template, "html")
    app.add_config_value("tippy_enable_mathjax", False, "html")
    app.add_config_value(
        "tippy_js",
        ("https://unpkg.com/@popperjs/core@2", "https://unpkg.com/tippy.js@6"),
        "html",
        [list, tuple],
    )
    app.add_config_value("tippy_add_class", "", "html")

    app.connect("builder-inited", compile_config)
    app.connect("html-page-context", collect_tips, priority=450)  # before mathjax
    app.connect("build-finished", write_tippy_js)
    return {"version": __version__, "parallel_read_safe": True}


LOGGER = getLogger(__name__)


@dataclass
class TippyConfig:
    props: dict[str, str]
    custom_tips: dict[str, str]
    tip_selector: str
    skip_url_regexes: Sequence[re.Pattern]
    skip_anchor_classes: Sequence[str]
    anchor_parent_selector: str
    enable_wikitips: bool
    enable_mathjax: bool
    enable_doitips: bool
    tippy_rtd_urls: Sequence[str]
    doi_template: str
    doi_api: str
    js_files: tuple[str, ...]
    tippy_add_class: str


def get_tippy_config(app: Sphinx) -> TippyConfig:
    """Get the extension config"""
    return app.env.tippy_config  # type: ignore[attr-defined]


def compile_config(app: Sphinx):
    """Compile and validate the config for this extension."""
    # compile the regexes
    skip_url_regexes = [re.compile(regex) for regex in app.config.tippy_skip_urls]
    # validate the props
    updates = app.config.tippy_props or {}
    if not isinstance(updates, dict):
        raise ExtensionError(f"tippy_props must be a dictionary, not a {type(updates)}")
    props = dict(
        {"placement": "auto-start", "maxWidth": 500, "interactive": False}, **updates
    )

    supported_properties = {
        "placement",
        "maxWidth",
        "interactive",
        "theme",
        "delay",
        "duration",
    }

    if set(props.keys()) - supported_properties:
        raise ExtensionError(
            "tippy_props can only contain keys '%s'" % "', '".join(supported_properties)
        )
    allowed_placements = {
        "auto",
        "auto-start",
        "auto-end",
        "top",
        "top-start",
        "top-end",
        "bottom",
        "bottom-start",
        "bottom-end",
        "right",
        "right-start",
        "right-end",
        "left",
        "left-start",
        "left-end",
    }
    if props["placement"] not in allowed_placements:
        raise ExtensionError(
            f"tippy_props['placement'] must one of {allowed_placements}"
        )
    props["placement"] = f"'{props['placement']}'"
    if not (props["maxWidth"] is None or isinstance(props["maxWidth"], int)):
        raise ExtensionError("tippy_props['maxWidth'] must be an integer or None")
    props["maxWidth"] = (
        "'none'" if props["maxWidth"] is None else str(props["maxWidth"])
    )
    if not isinstance(props["interactive"], bool):
        raise ExtensionError("tippy_props['interactive'] must be a boolean")
    props["interactive"] = "true" if props["interactive"] else "false"
    if "theme" in props:
        if not (props["theme"] is None or isinstance(props["theme"], str)):
            raise ExtensionError("tippy_props['theme'] must be None or a string")
        props["theme"] = f"'{props['theme']}'" if props["theme"] else "null"
    if "delay" in props:
        if not (props["delay"] is None or isinstance(props["delay"], list)):
            raise ExtensionError("tippy_props['delay'] must be None or a list")
        props["delay"] = props["delay"] if props["delay"] else "null"
    if "duration" in props:
        if not (props["duration"] is None or isinstance(props["duration"], list)):
            raise ExtensionError("tippy_props['duration'] must be None or a list")
        props["duration"] = props["duration"] if props["duration"] else "null"
    app.env.tippy_config = TippyConfig(  # type: ignore[attr-defined]
        props=props,
        custom_tips=app.config.tippy_custom_tips,
        skip_url_regexes=skip_url_regexes,
        tip_selector=app.config.tippy_tip_selector,
        skip_anchor_classes=app.config.tippy_skip_anchor_classes,
        anchor_parent_selector=app.config.tippy_anchor_parent_selector,
        enable_wikitips=app.config.tippy_enable_wikitips,
        enable_doitips=app.config.tippy_enable_doitips,
        enable_mathjax=app.config.tippy_enable_mathjax,
        tippy_rtd_urls=app.config.tippy_rtd_urls,
        doi_template=app.config.tippy_doi_template,
        doi_api=app.config.tippy_doi_api,
        js_files=app.config.tippy_js,
        tippy_add_class=app.config.tippy_add_class,
    )
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
    dois: set[str]
    rtd_urls: set[str]
    js_path: Path


WIKI_PATH = "https://en.wikipedia.org/wiki/"
DOI_PATH = "https://doi.org/"


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
    doi_names: set[str] = set()
    rtd_urls: set[str] = set()
    for anchor in body.find_all("a", {"href": True}):
        if not isinstance(anchor["href"], str):
            continue

        if anchor["href"] in custom_tips:
            custom_in_page.add(anchor["href"])
            continue

        if any(regex.match(anchor["href"]) for regex in tippy_config.skip_url_regexes):
            continue

        if tippy_config.enable_doitips and anchor["href"].startswith(DOI_PATH):
            doi_names.add(anchor["href"][len(DOI_PATH) :])
            continue

        for urls in tippy_config.tippy_rtd_urls:
            if anchor["href"].startswith(urls):
                rtd_urls.add(anchor["href"])
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
            continue

        if tippy_config.enable_wikitips and path.startswith(WIKI_PATH):
            wiki_titles.add(path[len(WIKI_PATH) :])
            continue

        # check if the reference is on another local page
        # TODO for now we assume that page names are written in posix style with ".html" prefixes
        # and that the page name relates to the docname
        if path.endswith(".html"):
            other_pagename = posixpath.normpath(posixpath.join(page_parent, path[:-5]))
            if other_pagename in app.env.all_docs:
                refs_in_page.add((other_pagename, target))

    id_to_tip_html = create_id_to_tip_html(tippy_config, body)

    # create path based on pagename
    # we also add a unique ID to the path,
    # which is in order to avoid browsers using old cached versions
    # lets also remove any old versions of the file when running rebuilds
    # TODO ideally here, we would just add a query string to the script load
    # see: https://github.com/sphinx-doc/sphinx/issues/11133
    parts = pagename.split("/")
    for old_path in Path(app.outdir, "_static", "tippy", *parts).parent.glob(
        f"{parts[0]}.*.js"
    ):
        old_path.unlink()
    js_path = Path(
        app.outdir, "_static", "tippy", *(pagename + f".{uuid4()}.js").split("/")
    )

    # store the data for later use
    tippy_data = get_tippy_data(app)
    tippy_data["pages"][pagename] = {  # type: ignore
        "element_id_map": element_id_map,
        "refs_in_page": refs_in_page,
        "id_to_html": id_to_tip_html,
        "custom_in_page": custom_in_page,
        "wiki_titles": wiki_titles,
        "dois": doi_names,
        "rtd_urls": rtd_urls,
        "js_path": js_path,
    }

    # add the JS files
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
        id_to_html[None] = _get_header_html(title)

    tag: Tag

    # these are tags where we simply copy the whole HTML
    for tag in body.select(config.tip_selector):
        if "id" in tag.attrs:
            id_to_html[str(tag["id"])] = str(tag)

    # these are tags where we copy the HTML in a bespoke way
    for tag in body.find_all(id=True):
        if tag.name == "dt":
            # copy the whole HTML
            id_to_html[str(tag["id"])] = str(strip_classes(tag.__copy__()))
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
            id_to_html[str(tag["id"])] = _get_header_html(header)

        elif tag.name == "div" and (
            all(
                class_to_check in (tag.get("class") or [])
                for class_to_check in ("math", "notranslate", "nohighlight")
            )
        ):
            # remove an span with eqno class, since it is not needed
            # and it can cause issues with the tooltip
            # (e.g. if the span is the last element in the div)
            tag_copy = tag.__copy__()
            for child in tag_copy.find_all("span"):
                if isinstance(child, Tag) and "eqno" in (child.get("class") or []):
                    child.decompose()
            id_to_html[str(tag["id"])] = str(tag_copy)

    return id_to_html


def strip_classes(tag: Tag, classes: tuple[str] = ("headerlink",)) -> Tag:
    """Strip tag with certain classes"""
    for child in tag.find_all(class_=classes):
        child.decompose()
    return tag


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
    data = requests.get(url).json()

    extract_html = data["extract_html"]
    if "thumbnail" in data:
        thumbnail_url = data["thumbnail"]["source"]
        style = "float:left; margin-right:10px;"
        alt = "Wikipedia thumbnail"
        extract_html = (
            f'<img src="{thumbnail_url}" alt="{alt}" style="{style}">' + extract_html
        )

    return extract_html


def fetch_wikipedia_tips(app: Sphinx, data: dict[str, TippyPageData]) -> dict[str, str]:
    """fetch the wikipedia tooltips, caching them for rebuilds."""
    wiki_cache: dict[str, str]
    wiki_cache_path = Path(app.outdir, "tippy_wiki_cache.json")
    if wiki_cache_path.exists():
        with wiki_cache_path.open("r") as file:
            wiki_cache = json.load(file)
    else:
        wiki_cache = {}
    wiki_fetch = {
        title
        for page in data.values()
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
    return wiki_cache


def map_join(
    items: list[dict[str, Any]], *attributes: str, sep: str = " ", default: str = ""
) -> list[str]:
    """Jinja filter, to convert list of dicts to list of strings."""
    return [sep.join([item.get(a, default) for a in attributes]) for item in items]


def fetch_doi_tips(app: Sphinx, data: dict[str, TippyPageData]) -> dict[str, str]:
    """fetch the doi tooltips, caching them for rebuilds."""
    config = get_tippy_config(app)
    doi_cache: dict[str, str]
    doi_cache_path = Path(app.outdir, "tippy_doi_cache.json")
    if doi_cache_path.exists():
        with doi_cache_path.open("r") as file:
            doi_cache = json.load(file)
    else:
        doi_cache = {}
    doi_fetch = {
        doi for page in data.values() for doi in page["dois"] if doi not in doi_cache
    }
    for doi in status_iterator(doi_fetch, "Fetching DOI tips", length=len(doi_fetch)):
        url = f"{config.doi_api}{doi}"
        try:
            data = requests.get(url).json()
        except Exception as exc:
            LOGGER.warning(
                f"Could not fetch DOI data for {doi}: {exc} [tippy.doi]",
                type="tippy",
                subtype="doi",
            )
        try:
            env = Environment()
            env.filters["map_join"] = map_join
            template = env.from_string(config.doi_template)
            doi_cache[doi] = template.render(data=data)
        except Exception as exc:
            LOGGER.warning(
                f"Could not render DOI template for {doi}: {exc} [tippy.doi]",
                type="tippy",
                subtype="doi",
            )
    with doi_cache_path.open("w") as file:
        json.dump(doi_cache, file)
    return doi_cache


def fetch_rtd_tips(app: Sphinx, data: dict[str, TippyPageData]) -> dict[str, str]:
    """fetch the rtd tooltips, caching them for rebuilds."""
    rtd_cache: dict[str, str]
    rtd_cache_path = Path(app.outdir, "tippy_rtd_cache.json")
    if rtd_cache_path.exists():
        with rtd_cache_path.open("r") as file:
            rtd_cache = json.load(file)
    else:
        rtd_cache = {}
    rtd_fetch = {
        rtd
        for page in data.values()
        for rtd in page["rtd_urls"]
        if rtd not in rtd_cache
    }
    for rtd in status_iterator(rtd_fetch, "Fetching RTD tips", length=len(rtd_fetch)):
        # see https://docs.readthedocs.io/en/stable/api/v3.html#embed
        # TODO is this all that needs to be done, to escape the rtd url?
        url = f"https://readthedocs.org/api/v3/embed/?url={rtd.replace('#', '%23')}"
        try:
            content = requests.get(url).json()["content"]
            if content and BeautifulSoup(content, "html.parser").text:
                rtd_cache[rtd] = content
        except Exception as exc:
            LOGGER.warning(
                f"Could not fetch RTD data for {rtd}: {exc} [tippy.rtd]",
                type="tippy",
                subtype="rtd",
            )
    with rtd_cache_path.open("w") as file:
        json.dump(rtd_cache, file)
    return rtd_cache


def write_tippy_js(app: Sphinx, exception: Any):
    """For each page, filter the list of reference tooltips to only those on the page,
    and write the JS file.
    """
    if exception:
        return
    if app.builder.format != "html":
        return

    tippy_page_data = get_tippy_data(app)["pages"]

    wiki_cache = fetch_wikipedia_tips(app, tippy_page_data)
    doi_cache = fetch_doi_tips(app, tippy_page_data)
    rtd_cache = fetch_rtd_tips(app, tippy_page_data)

    for pagename in status_iterator(
        tippy_page_data, "Writing tippy data files", length=len(tippy_page_data)
    ):
        write_tippy_props_page(app, pagename, wiki_cache, doi_cache, rtd_cache)


def write_tippy_props_page(
    app: Sphinx,
    pagename: str,
    wiki_cache: dict[str, str],
    doi_cache: dict[str, str],
    rtd_cache: dict[str, str],
):
    """Write the JS file for a single page."""
    tippy_page_data = get_tippy_data(app)["pages"]
    tippy_config = get_tippy_config(app)
    data = tippy_page_data[pagename]

    local_id_map = data["element_id_map"]
    local_id_to_html = data["id_to_html"]
    selector_to_html: dict[str, str] = {}
    for wiki_title in data["wiki_titles"]:
        if wiki_title in wiki_cache:
            selector_to_html[f'a[href="{WIKI_PATH}{wiki_title}"]'] = wiki_cache[
                wiki_title
            ]
            selector_to_html[f'a[href^="{WIKI_PATH}{wiki_title}#"]'] = wiki_cache[
                wiki_title
            ]
    for doi in data["dois"]:
        if doi in doi_cache:
            selector_to_html[f'a[href="{DOI_PATH}{doi}"]'] = doi_cache[doi]
    for rtd in data["rtd_urls"]:
        if rtd in rtd_cache:
            selector_to_html[f'a[href="{rtd}"]'] = rtd_cache[rtd]
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

    # custom tips take priority over other tips
    selector_to_html.update(
        {
            f'a[href="{ref}"]': tippy_config.custom_tips[ref]
            for ref in data["custom_in_page"]
        }
    )

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

    tippy_add_class = ""
    if tippy_config.tippy_add_class:
        tippy_add_class = f"link.classList.add({tippy_config.tippy_add_class!r});"
    tippy_props = ", ".join(f"{k}: {v}" for k, v in tippy_config.props.items())
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
                    {tippy_add_class}
                    tippy(link, {{
                        content: tip_html,
                        allowHTML: true,
                        arrow: true,
                        {tippy_props},
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

    data["js_path"].parent.mkdir(parents=True, exist_ok=True)
    with data["js_path"].open("w", encoding="utf8") as handle:
        handle.write(content)
