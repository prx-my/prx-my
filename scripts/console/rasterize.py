"""Bake the profile README's artwork into WebP images and desktop motion layers before stamping URLs."""

import os
from pathlib import Path
from base64 import b64encode
from io import BytesIO

from PIL import Image
from playwright.sync_api import sync_playwright

from motion import add_sources, build_motion, strip_sources
from print_texture import apply_print_texture, paper_tile
from stamp import LINK, README, ROOT


def capture_svg(context, svg, *, viewport=None):
    # Load the SVG directly so reduced motion applies within its styles.
    encoded = b64encode(svg).decode("ascii")
    page = context.new_page()
    if viewport is not None:
        page.set_viewport_size(viewport)
    try:
        page.goto(f"data:image/svg+xml;base64,{encoded}", wait_until="load")
        return page.locator(":root").screenshot(omit_background=True, animations="disabled")
    finally:
        page.close()


def render_hero(context):
    hero = ROOT / "profile-assets" / "hero.motion.svg"
    screenshot = capture_svg(context, hero.read_bytes(), viewport={"width": 1774, "height": 887})
    with Image.open(BytesIO(screenshot)) as pixels:
        for suffix, size in (("", (1440, 720)), ("-mobile", (800, 400))):
            pixels.resize(size, Image.Resampling.LANCZOS).save(
                hero.with_name(f"hero{suffix}.webp"), quality=88, method=6
            )


def render_svg(context, source, texture):
    def capture(svg):
        screenshot = capture_svg(context, svg)
        with Image.open(BytesIO(screenshot)) as pixels:
            panel = source.relative_to(ROOT).as_posix()
            with BytesIO() as output:
                apply_print_texture(pixels, texture, panel).save(output, format="WEBP", quality=82, method=6)
                return output.getvalue()

    still = capture(source.read_bytes())
    source.with_suffix(".webp").write_bytes(still)
    return build_motion(source, still, capture)


def rasterize(text, context, texture):
    rendered = set()
    animated = {Path("profile-assets/hero.webp"): Path("profile-assets/hero.motion.svg")}

    def replace(match):
        url, relative_path = match[2], match[3]
        path = ROOT / relative_path
        if path.suffix not in {".svg", ".webp"}:
            return match[0]
        # Once README points at WebP, its SVG sibling still drives each refresh.
        source = path.with_suffix(".svg")
        if path.suffix == ".webp" and not source.is_file():
            return match[0]
        if source not in rendered:
            motion = render_svg(context, source, texture)
            if motion:
                animated[source.with_suffix(".webp").relative_to(ROOT)] = motion.relative_to(ROOT)
            rendered.add(source)
        return f'{match[1]}{url.removesuffix(path.suffix)}.webp"'

    still = LINK.sub(replace, strip_sources(text))
    return add_sources(still, animated)


def main():
    paper_reference = ROOT / "profile-assets" / "prxmy-risograph.webp"
    with Image.open(paper_reference) as image:
        texture = paper_tile(image)

    processor = ROOT / "profile-assets" / "stack" / "processor.webp"
    with Image.open(processor) as image:
        image.thumbnail((1440, 1440), Image.Resampling.LANCZOS)
        apply_print_texture(image, texture, processor.relative_to(ROOT).as_posix()).save(
            processor.with_name("processor-print.webp"), quality=82, method=6
        )

    readme = README.read_text(encoding="utf-8")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("PROFILE_CHROMIUM"), args=["--disable-gpu"]
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        render_hero(context)
        updated = rasterize(readme, context, texture)
        browser.close()
    README.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
