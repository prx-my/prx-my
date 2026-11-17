"""Bake the profile README's artwork into still WebP images before stamping URLs."""

import os
from base64 import b64encode
from io import BytesIO

from PIL import Image
from playwright.sync_api import sync_playwright

from stamp import LINK, README, ROOT


def render_svg(context, source):
    # Render the SVG document directly so reduced motion applies within its styles.
    encoded = b64encode(source.read_bytes()).decode("ascii")
    page = context.new_page()
    page.goto(f"data:image/svg+xml;base64,{encoded}", wait_until="load")
    screenshot = page.locator(":root").screenshot(omit_background=True, animations="disabled")
    page.close()
    with Image.open(BytesIO(screenshot)) as pixels:
        pixels.save(source.with_suffix(".webp"), quality=90, method=6)


def rasterize(text, context):
    rendered = set()

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
            render_svg(context, source)
            rendered.add(source)
        return f'{match[1]}{url.removesuffix(path.suffix)}.webp"'

    return LINK.sub(replace, text)


def main():
    banner = ROOT / "profile-assets" / "prxmy-risograph.webp"
    with Image.open(banner) as image:
        image.resize((800, 400), Image.Resampling.LANCZOS).save(
            banner.with_name("prxmy-risograph-mobile.webp"), quality=88, method=6
        )

    readme = README.read_text(encoding="utf-8")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("PROFILE_CHROMIUM"), args=["--disable-gpu"]
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        updated = rasterize(readme, context)
        browser.close()
    README.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
