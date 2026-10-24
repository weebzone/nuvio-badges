"""Build Nuvio badge packs that also work in the player.

Nuvio's player matches badge rules against a short line built from the
playing video (e.g. "1080p FHD HEVC H.265 10bit AAC 5.1"). The upstream
pack only matches when the text looks like a full filename, so most badges
never show in the player. This script removes that filename check, then
renders one pack per design.

Usage: python3 build.py   (needs Pillow, writes packs/, images/, previews/)
"""
import colorsys
import hashlib
import json
import re
import shutil
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SOURCE_URL = "https://raw.githubusercontent.com/kingsizew/badges/main/badge.json"
RAW_BASE = "https://raw.githubusercontent.com/weebzone/nuvio-badges/main"
ROOT = Path(__file__).parent
FONTS = ROOT / "fonts"
H = 72  # image height in px; Nuvio shows it at 13-18dp

# Matches only when the text has a filename, two resolutions, a newline or a hash.
FILENAME_GATE = (
    r"(?:(?=.*\.(?:mkv|mp4|avi|m2ts|webm|mov|m4v)\s+\S)"
    r"|(?=(?:.*(?:2160|1440|1080|720|576|480)[pi]?){2})"
    r"|(?=.*[\r\n])|(?=^[a-f0-9]{40,64}\s+\S))"
)

# Channel rules have their own filename gate; add a plain alternative.
# Each one only matches when no higher layout is in the text.
_UNIT = r"(?!\s*(?:kbps|mbps|gbps|kb/s|mb/s|gb/s|kb|mb|gb|mib|gib))"
_CH = {
    "7.1": r"7[-_. ]1(?:ch)?|8ch",
    "6.1": r"6[-_. ]1(?:ch)?|7ch",
    "5.1": r"5[-_. ]1(?:ch)?|6ch",
    "2.0": r"2[-_. ]0(?:ch)?|2ch",
}


def _ch(tok):
    return rf"(?<![0-9])(?:{_CH[tok]})(?![0-9]){_UNIT}"


def channel_rule(name, original):
    order = list(_CH)
    higher = order[: order.index(name)]
    simple = "^"
    if higher:
        simple += r"(?![\s\S]*(?:" + "|".join(_ch(t) for t in higher) + "))"
    simple += r"[\s\S]*" + _ch(name)
    body = original[4:] if original.startswith("(?i)") else original
    return f"(?i)(?:{body})|(?:{simple})"


def patch(filters):
    out = []
    for f in filters:
        f = dict(f)
        if f["name"] in _CH:
            f["pattern"] = channel_rule(f["name"], f["pattern"])
        else:
            f["pattern"] = f["pattern"].replace(FILENAME_GATE, "")
        out.append(f)
    return out


# ---------- designs ----------

def font(name, size, weight=None):
    f = ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)
    if weight:
        f.set_variation_by_axes([14, weight] if name == "Inter" else [weight])
    return f


def rgb(hex_):
    h = hex_.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def pastel(hex_):
    r, g, b = (c / 255 for c in rgb(hex_))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(h, 0.78, min(s, 0.75))
    return "#%02X%02X%02X" % (int(r * 255), int(g * 255), int(b * 255))


def ink_on(hex_):
    r, g, b = rgb(hex_)
    return "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#FFFFFF"


def text_layer(label, fnt, fill, pad=10, stroke=0):
    box = fnt.getbbox(label, stroke_width=stroke)
    w = box[2] - box[0] + pad * 2
    img = Image.new("RGBA", (w, H), (0, 0, 0, 0))
    y = (H - (box[3] - box[1])) // 2 - box[1]
    ImageDraw.Draw(img).text((pad - box[0], y), label, font=fnt, fill=fill,
                             stroke_width=stroke, stroke_fill=fill)
    return img


def gradient_text(label, fnt, top, bottom, pad=10):
    mask = text_layer(label, fnt, "#FFFFFF", pad).getchannel("A")
    grad = Image.new("RGBA", mask.size)
    t, b = rgb(top), rgb(bottom)
    for y in range(H):
        k = y / (H - 1)
        ImageDraw.Draw(grad).line([(0, y), (mask.width, y)],
                                  fill=tuple(int(t[i] + (b[i] - t[i]) * k) for i in range(3)))
    grad.putalpha(mask)
    return grad


def glow_text(label, fnt, color, pad=14):
    core = "#%02X%02X%02X" % tuple((c + 2 * 255) // 3 for c in rgb(color))  # accent mixed with white
    sharp = text_layer(label, fnt, core, pad)
    out = text_layer(label, fnt, color, pad, stroke=1).filter(ImageFilter.GaussianBlur(3))
    out.alpha_composite(sharp, ((out.width - sharp.width) // 2, 0))
    return out


def pill(label, fnt, bg, fg, pad=16):
    txt = text_layer(label, fnt, fg, pad)
    img = Image.new("RGBA", txt.size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle([0, 0, txt.width - 1, H - 1], radius=14, fill=bg)
    return Image.alpha_composite(img, txt)


# Each design returns (image, chip fields). Chip fields style the box Nuvio draws.
DESIGNS = {
    "mono": dict(
        title="Mono", blurb="White bold text in a thin grey outline.",
        draw=lambda l, a: text_layer(l, font("Inter", 44, 850), "#FFFFFF"),
        chip=lambda a: dict(tagStyle="bordered", tagColor="", borderColor="#FFFFFF59", textColor="#FFFFFF")),
    "neon": dict(
        title="Neon", blurb="Glowing text in each badge's colour.",
        draw=lambda l, a: glow_text(l.replace("·", "/"), font("Orbitron", 38, 700), a),  # Orbitron has no "·"
        chip=lambda a: dict(tagStyle="bordered", tagColor="", borderColor=a, textColor=a)),
    "solid": dict(
        title="Solid", blurb="Filled colour pills.",
        draw=lambda l, a: pill(l, font("ArchivoBlack", 40), a, ink_on(a)),
        chip=lambda a: dict(tagStyle="bordered", tagColor="", borderColor="", textColor=ink_on(a))),
    "gold": dict(
        title="Gold", blurb="Gold gradient on black, cinema style.",
        draw=lambda l, a: gradient_text(l, font("BebasNeue", 60), "#FFF1B8", "#C9962B"),
        chip=lambda a: dict(tagStyle="filled", tagColor="#0B0B0B", borderColor="#D4AF37", textColor="#D4AF37")),
    "glass": dict(
        title="Glass", blurb="Frosted see-through chips.",
        draw=lambda l, a: text_layer(l, font("SpaceGrotesk", 44, 700), "#FFFFFF"),
        chip=lambda a: dict(tagStyle="filled", tagColor="#FFFFFF1F", borderColor="#FFFFFF40", textColor="#FFFFFF")),
    "minimal": dict(
        title="Minimal", blurb="Just the text, no box.",
        draw=lambda l, a: text_layer(l, font("Inter", 42, 600), "#E6E6E6", pad=4),
        chip=lambda a: dict(tagStyle="bordered", tagColor="", borderColor="", textColor="#E6E6E6")),
    "pastel": dict(
        title="Pastel", blurb="Soft colours, rounded mono font.",
        draw=lambda l, a: text_layer(l, font("RubikMonoOne", 36), pastel(a)),
        chip=lambda a: dict(tagStyle="bordered", tagColor="", borderColor=pastel(a) + "99", textColor=pastel(a))),
    "retro": dict(
        title="Retro", blurb="8-bit pixel font on black.",
        draw=lambda l, a: text_layer(l, font("PressStart2P", 30), a),
        chip=lambda a: dict(tagStyle="filled", tagColor="#000000", borderColor=a, textColor=a)),
    "condensed": dict(
        title="Condensed", blurb="Tall narrow type, fits more badges in a row.",
        draw=lambda l, a: text_layer(l, font("Oswald", 52, 700), "#FFFFFF", pad=8),
        chip=lambda a: dict(tagStyle="filled", tagColor=a + "33", borderColor=a, textColor="#FFFFFF")),
}


def label(name):
    return re.sub(r" \d+$", "", name)  # "BLU-RAY 3" -> "BLU-RAY"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("+", "plus")).strip("-")


def build_design(key, spec, filters, groups):
    img_dir = ROOT / "images" / key
    img_dir.mkdir(parents=True)
    out, urls = [], {}
    for f in filters:
        text = label(f["name"])
        if text not in urls:
            img = spec["draw"](text, f["borderColor"])
            path = img_dir / f"{slug(text)}.png"
            img.save(path, optimize=True)
            rev = hashlib.sha1(path.read_bytes()).hexdigest()[:10]
            urls[text] = f"{RAW_BASE}/images/{key}/{path.name}?rev={rev}"
        out.append({**f, "imageURL": urls[text], **spec["chip"](f["borderColor"])})
    return {"groups": groups, "filters": out}


# ---------- previews ----------

PREVIEW_NAMES = ["4K", "1080p", "DV · HDR10", "HDR10+", "10bit", "HEVC", "ATMOS DIGITAL+",
                 "DD+", "AAC", "5.1", "7.1", "BluRay", "WEB-DL", "NETFLIX"]


def chip_preview(pack, root):
    by_name = {f["name"]: f for f in pack["filters"]}
    chips = []
    for n in PREVIEW_NAMES:
        f = by_name[n]
        url = f["imageURL"].split("?")[0]
        local = root / url.removeprefix(RAW_BASE + "/") if url.startswith(RAW_BASE) else None
        if not local or not local.exists():
            continue
        img = Image.open(local).convert("RGBA")
        w = int(img.width * 36 / H)
        img = img.resize((w, 36), Image.LANCZOS)
        chip = Image.new("RGBA", (w + 12, 48), (0, 0, 0, 0))
        d = ImageDraw.Draw(chip)
        fill = f["tagColor"] if f["tagStyle"] == "filled" and f["tagColor"] else None
        border = f["borderColor"] or None
        if fill or border:
            d.rounded_rectangle([0, 0, chip.width - 1, 47], radius=8,
                                fill=_rgba(fill) if fill else None,
                                outline=_rgba(border) if border else None, width=2)
        chip.alpha_composite(img, (6, 6))
        chips.append(chip)
    width = sum(c.width for c in chips) + 10 * (len(chips) - 1) + 48
    sheet = Image.new("RGBA", (width, 96), (17, 17, 17, 255))
    x = 24
    for c in chips:
        sheet.alpha_composite(c, (x, 24))
        x += c.width + 10
    return sheet


def _rgba(hex_):
    h = hex_.lstrip("#")
    a = int(h[6:8], 16) if len(h) == 8 else 255
    return (*rgb(h[:6]), a)


def main():
    src = json.loads(urllib.request.urlopen(SOURCE_URL, timeout=30).read())
    filters = patch(src["filters"])
    for d in ("packs", "images", "previews"):
        shutil.rmtree(ROOT / d, ignore_errors=True)
        (ROOT / d).mkdir()

    # classic: upstream images, patched rules only
    (ROOT / "packs/classic.json").write_text(json.dumps({"groups": src["groups"], "filters": filters}, indent=2))
    for key, spec in DESIGNS.items():
        pack = build_design(key, spec, filters, src["groups"])
        (ROOT / f"packs/{key}.json").write_text(json.dumps(pack, indent=2))
        chip_preview(pack, ROOT).convert("RGB").save(ROOT / f"previews/{key}.png", optimize=True)
    print("built:", ", ".join(["classic", *DESIGNS]))


if __name__ == "__main__":
    main()
