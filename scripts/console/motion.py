"""Build desktop-only motion layers over the pre-rendered profile artwork."""

import re
from base64 import b64encode
from pathlib import Path
from xml.etree import ElementTree as xml

from stamp import LINK

SVG = "{http://www.w3.org/2000/svg}"
xml.register_namespace("", SVG[1:-1])

DESKTOP_MOTION = "(min-width: 601px) and (hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)"
RAW = "https://raw.githubusercontent.com/prx-my/prx-my/main/"
MOBILE_MOTION = (
    "(max-width: 600px) and (prefers-reduced-motion: no-preference), "
    "(pointer: coarse) and (prefers-reduced-motion: no-preference)"
)
MOTION_SOURCE = re.compile(
    rf'<source media="(?:{re.escape(DESKTOP_MOTION)}|{re.escape(MOBILE_MOTION)})" srcset="[^"]+">'
)
IMAGE = re.compile(r"<picture>.*?</picture>|<img\b[^>]*>", re.DOTALL)
MOTION_CLASSES = {
    "work": {"activity", "heartbeat", "packet", "port-glow"},
    "open-source": {"animated-fan"},
    "contact": {"rgb-wave"},
}
DOCUMENT_ELEMENTS = {SVG + name for name in ("defs", "style", "title", "desc")}


def keep_motion(element, classes, *, root=False):
    if classes.intersection(element.get("class", "").split()):
        return True
    for child in list(element):
        if root and child.tag in DOCUMENT_ELEMENTS:
            continue
        if not keep_motion(child, classes):
            element.remove(child)
    return len(element) > 0


def build_motion(source, still, capture_base):
    classes = {"fan-rotor"} if source.name == "activity.svg" else MOTION_CLASSES.get(source.parent.name)
    if not classes or source.stem.endswith("-mobile"):
        return None
    root = xml.fromstring(source.read_bytes())
    if not any(classes.intersection(node.get("class", "").split()) for node in root.iter()):
        return None

    # GPU rotors cover the baked still blades. The other effects need their
    # original marks removed from the background before drawing the overlay.
    gpu = classes == {"animated-fan"}
    if gpu:
        backdrop = still
    else:
        style = xml.SubElement(root, SVG + "style")
        style.text = ", ".join(f".{name}" for name in sorted(classes)) + " { display: none !important; }"
        backdrop = capture_base(xml.tostring(root))
        root.remove(style)
    keep_motion(root, classes, root=True)

    image_data = "data:image/webp;base64," + b64encode(backdrop).decode("ascii")
    if gpu:
        # The existing clip paths and hub can reference the same textured image.
        root.find(f".//{SVG}image[@id='art']").set("href", image_data)
        image = xml.Element(SVG + "use", {"href": "#art"})
    else:
        image = xml.Element(SVG + "image", {
            "width": root.attrib["width"], "height": root.attrib["height"], "href": image_data,
        })
    root.insert(0, image)
    target = source.with_suffix(".motion.svg")
    target.write_bytes(xml.tostring(root))
    return target


def strip_sources(text):
    return MOTION_SOURCE.sub("", text)


def add_sources(text, animated, mobile):
    def add(match):
        markup = match[0]
        start = markup.index("<img")
        image = LINK.search(markup, start)
        asset = Path(image[3]) if image else None
        sources = "".join(
            f'<source media="{media}" srcset="{RAW}{variants[asset].as_posix()}">'
            for media, variants in ((MOBILE_MOTION, mobile), (DESKTOP_MOTION, animated))
            if asset in variants
        )
        if not sources:
            return markup
        if start:
            # Mobile animation must precede the static phone-sized source.
            return markup[:len("<picture>")] + sources + markup[len("<picture>"):]
        return f"<picture>{sources}{markup}</picture>"

    return IMAGE.sub(add, text)
