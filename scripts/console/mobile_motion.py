"""Render small WebP animations for phones from the checked-in profile artwork."""

from base64 import b64encode
from io import BytesIO
from xml.etree import ElementTree as xml

from PIL import Image, ImageDraw

from motion import SVG, keep_motion
from stamp import ROOT

ASSETS = ROOT / "profile-assets"


def save_animation(target, frames, durations, *, loop=1):
    first, *rest = frames
    first.save(
        target, save_all=True, append_images=rest, duration=durations, loop=loop,
        quality=84, method=5, minimize_size=True,
    )
    with Image.open(target) as image:
        if not image.is_animated:
            raise ValueError(f"Expected multiple frames in {target}")


def capture_frames(context, source, times, *, scale=1):
    root = xml.fromstring(source)
    width = int(root.attrib["width"])
    height = int(root.attrib["height"])
    size = {"width": round(width * scale), "height": round(height * scale)}
    for key, value in size.items():
        root.set(key, str(value))
    encoded = b64encode(xml.tostring(root)).decode("ascii")
    page = context.new_page()
    page.set_viewport_size(size)
    try:
        page.goto(f"data:image/svg+xml;base64,{encoded}", wait_until="load")
        page.evaluate("""() => {
            window.profileAnimations = document.getAnimations();
            if (!window.profileAnimations.length) throw new Error('Missing animated SVG layers');
            for (const animation of window.profileAnimations) animation.pause();
        }""")
        frames = []
        for time in times:
            page.evaluate("""time => {
                for (const animation of window.profileAnimations) animation.currentTime = time;
            }""", time)
            with Image.open(BytesIO(page.screenshot())) as pixels:
                frames.append(pixels.convert("RGB"))
        return frames
    finally:
        page.close()


def render_hero(context):
    motion = (ASSETS / "hero-contact.motion.svg").read_bytes()
    times = list(range(0, 2700, 135)) + [2700]
    frames = capture_frames(context, motion, times, scale=400 / 887)
    durations = [after - before for before, after in zip(times, times[1:])] + [900]
    target = ASSETS / "hero-contact-mobile.motion.webp"
    save_animation(target, frames, durations)
    return target


def render_rack(context, source):
    root = xml.fromstring(source.read_bytes())
    classes = {"packet", "port-glow"}
    keep_motion(root, classes, root=True)
    for node in root:
        if node.tag == SVG + "style":
            node.text = node.text.replace("@media not all", "@media (prefers-reduced-motion: no-preference)")

    # The mobile still already contains the chassis, text and LEDs. Only the
    # cable highlight and port flash need to be drawn over it for each frame.
    still = source.with_suffix(".webp").read_bytes()
    image = xml.Element(SVG + "image", {
        "width": root.attrib["width"], "height": root.attrib["height"],
        "href": "data:image/webp;base64," + b64encode(still).decode("ascii"),
    })
    root.insert(0, image)

    # Match the same 12-second timeline across all five panels. Sample only
    # when this panel's packets are moving, and hold the still between pulses.
    times = {0, 12000}
    for node in root.iter():
        if classes.intersection(node.get("class", "").split()):
            delay = round(1000 * float(node.attrib["style"].removeprefix("--delay:").removesuffix("s")))
            times.update(delay + offset for offset in (0, 120, 260, 400, 550, 720, 880, 1000))
    times = sorted(times)
    frames = capture_frames(context, xml.tostring(root), times[:-1])
    durations = [after - before for before, after in zip(times, times[1:])]
    target = source.with_suffix(".motion.webp")
    save_animation(target, frames, durations, loop=2)
    return target


def render_loop(context, source, *, scale, period, count):
    # The desktop image guards some embedded animations by width. The mobile
    # WebP already has its own screen-size gate in the README.
    svg = xml.fromstring(source.read_bytes())
    for child in svg:
        if child.tag == SVG + "style":
            for condition in (" and (min-width: 180px)", " and (min-width: 120px)"):
                child.text = child.text.replace(condition, "")
    times = [round(period * index / count) for index in range(count)]
    # Mobile fans use one slow rotation. Match each existing animation's
    # timeline across the sampled frames, then use the chosen playback speed.
    frames = capture_frames(context, xml.tostring(svg), times, scale=scale)
    target = source.with_name(source.name.replace(".motion.svg", "-mobile.motion.webp"))
    duration = max(280, round(period / count))
    save_animation(target, frames, [duration] * count, loop=2)
    return target


def render_calendar():
    source = ASSETS / "activity-mobile.svg"
    root = xml.fromstring(source.read_bytes())
    rectangles = [
        node.find(SVG + "rect").attrib
        for node in root.iter(SVG + "g")
        if node.find(SVG + "title") is not None and node.find(SVG + "rect") is not None
    ]
    boxes = [tuple(round(float(cell[key])) for key in ("x", "y", "width", "height")) for cell in rectangles]
    with Image.open(source.with_suffix(".webp")) as image:
        still = image.convert("RGB")
    columns = sorted({x for x, _, _, _ in boxes})
    frames = [still]
    for column in columns[::2]:
        frame = still.copy()
        draw = ImageDraw.Draw(frame, "RGBA")
        for x, y, width, height in boxes:
            distance = abs(x - column)
            if distance <= 20:
                draw.rounded_rectangle(
                    (x, y, x + width - 1, y + height - 1), radius=2, width=2,
                    outline=(166, 188, 26, 245 if distance < 2 else 125),
                )
        frames.append(frame)
    frames.append(still)
    target = source.with_suffix(".motion.webp")
    save_animation(target, frames, [420] + [110] * (len(frames) - 2) + [800])
    return target


def render_mobile(context, desktop):
    variants = {}
    for still, source in desktop.items():
        match still.parts[:2], still.stem:
            case _, "hero-contact":
                asset = render_hero(context)
            case _, "activity":
                asset = render_calendar()
            case ("profile-assets", "work"), slug:
                asset = render_rack(context, ROOT / still.with_name(f"{slug}-mobile.svg"))
            case ("profile-assets", "open-source"), slug:
                period = 12000 if slug == "sugar-labs" else 8000
                asset = render_loop(context, ROOT / source, scale=.32, period=period, count=20)
            case ("profile-assets", "contact"), _:
                asset = render_loop(context, ROOT / source, scale=.48, period=6000, count=16)
            case _:
                continue
        variants[still] = asset.relative_to(ROOT)
    return variants
