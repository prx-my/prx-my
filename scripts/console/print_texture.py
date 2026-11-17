"""Apply the hero illustration's paper grain to the profile artwork."""

import hashlib

from PIL import Image, ImageChops, ImageFilter, ImageOps


def paper_tile(hero):
    # The upper-left margin is a clean patch of the hero's original paper.
    paper = hero.convert("RGB").crop((6, 6, 642, 168))
    strip = Image.new("RGB", (paper.width * 2, paper.height))
    strip.paste(paper)
    strip.paste(ImageOps.mirror(paper), (paper.width, 0))
    tile = Image.new("RGB", (strip.width, strip.height * 2))
    tile.paste(strip)
    tile.paste(ImageOps.flip(strip), (0, strip.height))
    return tile


def apply_print_texture(image, tile, panel):
    rgb = image.convert("RGB")
    # Keep the grain consistent across the profile without repeating the same
    # flecks at the start of every card. A stable offset keeps refreshes identical.
    offset = int.from_bytes(hashlib.blake2s(panel.encode(), digest_size=2).digest())
    left, top = offset % tile.width, offset % tile.height
    paper = Image.new("RGB", rgb.size)
    for y in range(-top, rgb.height, tile.height):
        for x in range(-left, rgb.width, tile.width):
            paper.paste(tile, (x, y))

    green = paper.getchannel("G")
    fibers = ImageChops.subtract(green.filter(ImageFilter.GaussianBlur(1.3)), green)

    result = []
    for (r, g, b), (paper_r, paper_g, paper_b), fleck in zip(
        rgb.get_flattened_data(), paper.get_flattened_data(), fibers.get_flattened_data(), strict=True
    ):
        if r >= 222 and 3 <= r - g <= 48 and 10 <= g - b <= 68 and b >= 126:
            # Carry the color and fibers of the original paper into the cream
            # and gold areas while preserving their shading and printed marks.
            result.append((
                r + paper_r - 249,
                g + paper_g - 229,
                b + paper_b - 204,
            ))
        elif b - r >= 45 and b - g >= 30:
            # Reduce ink coverage along the darker fibers. Keep the face of
            # the small labels dark enough to read at mobile sizes.
            coverage = min(0.27, max(0, fleck - 1) * 0.018)
            result.append((
                round(r + (paper_r - r) * coverage),
                round(g + (paper_g - g) * coverage),
                round(b + (paper_b - b) * coverage),
            ))
        else:
            result.append((r, g, b))

    rgb.putdata(result)
    if "A" in image.getbands():
        rgb.putalpha(image.getchannel("A"))
    return rgb
