import itertools
import os
import math
import csv
import re
from collections import namedtuple
from PIL import Image, ImageDraw, ImageFont

Item = namedtuple("Item", ["category", "subcat", "style", "gauge", "length", "notes"])

INDIR = "csvin"
OUTDIR = "imout"

DPI = 300
PAPERSIZE_IN = (8.5, 11)
MARGIN_IN = .25
THUMBSIZE_IN = (.25, .25)
LABELSIZE_IN = (1.5, .75)
FONT_HEAD_SIZE_IN = .22 # HEADER TEXT
FONT_SUB_SIZE_IN = .1  # SUBTEXT

# Convert inch sizes to pixels
THUMBSIZE = tuple(int(s*DPI) for s in THUMBSIZE_IN)
LABELSIZE = tuple(int(s*DPI) for s in LABELSIZE_IN)
PAPERSIZE = tuple(int(s*DPI) for s in PAPERSIZE_IN)
MARGIN = int(MARGIN_IN*DPI)
FONT_HEAD = ImageFont.truetype("SourceSansPro-Semibold.ttf", int(FONT_HEAD_SIZE_IN * DPI))
FONT_SUB = ImageFont.truetype("SourceSansPro-Regular.ttf", int(FONT_SUB_SIZE_IN * DPI))


def load_img_folder(path):
    """

    Args:
        path:

    Returns:
        dict(str, Image): map of fname to img

    """
    fname_to_img = {}
    for imfile in os.listdir(path):
        if "png" in imfile:
            fname = imfile.replace(".png", "")
            img = Image.open(os.path.join(path,imfile))
            fname_to_img[fname] = img.convert("RGBA")
    return fname_to_img

def load_csv(fname):
    items = []
    with open(fname) as fin:
        reader = csv.DictReader(fin)
        for row in reader:
            if row["gauge"] and row["category"] and row["subcat"]:
                items.append(Item(**row))
    return items

def load_items(path):
    if path.endswith(".csv"):
        return load_csv(path)
    else:
        return list(itertools.chain.from_iterable(load_csv(os.path.join(path, f)) for f in os.listdir(path) if f.endswith(".csv")))



CAT_IMS = load_img_folder("img/cat")
SUBCAT_IMS = load_img_folder("img/subcat")


def to_unifrac(text):
    FRAC = "\u2044"
    SUPS = dict(zip(u"0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹"))
    SUBS = dict(zip(u"0123456789", "₀₁₂₃₄₅₆₇₈₉"))
    def _tosup(s):
        return "".join(SUPS[c] for c in s)
    def _tosub(s):
        return "".join(SUBS[c] for c in s)
    m = re.search("(\d+)/(\d+)", text)
    if m:
        newmatch = _tosup(m.group(1)) + FRAC + _tosub(m.group(2))
        newtext = text.replace(m.group(0), newmatch)
        print("{} -> {}".format(text, newtext))
        return newtext
    return text



def pretty_item(item):
    return Item(**{k: to_unifrac(v) for k, v in item._asdict().items()})




def _center_text_w(font : ImageFont, text : str, canvas_width : int):
    """Return the X coordinate required to center text on canvas of a given width

    Returns:
        int

    """
    textw = font.getsize(text)[0]
    return int((canvas_width / 2) - (textw / 2))

def _center_im_w(im : Image, canvas_width : int):
    return int(canvas_width / 2 - im.size[0] / 2 )

def make_label(item: Item, fout: str):
    canvas = Image.new("RGBA", LABELSIZE, color=(255, 255, 255))
    cati = CAT_IMS.get(item.category)
    cati.thumbnail(THUMBSIZE)
    subi = SUBCAT_IMS.get("_".join([item.category, item.subcat]))
    subi.thumbnail(THUMBSIZE)

    # Draw from top down, tracking vertical offset 'y'
    y = 2
    draw = ImageDraw.Draw(canvas)
    header_text = item.gauge
    if item.length:
        header_text = header_text + ' x {}'.format(item.length)
    textw = _center_text_w(FONT_HEAD, header_text, canvas.size[0])
    draw.text((textw, y), header_text, fill=(0, 0, 0, 255), font=FONT_HEAD)
    y += FONT_HEAD.getsize(header_text)[1] + 10

    subw = _center_im_w(subi, canvas.size[0])
    canvas.paste(subi, (subw, y))
    y += subi.size[1] + 10

    summary_text = "{} {}".format(item.subcat, item.category)
    textw = _center_text_w(FONT_SUB, summary_text, canvas.size[0])
    draw.text((textw, y), summary_text, fill=(0, 0, 0, 255), font=FONT_SUB)
    y += FONT_SUB.getsize(summary_text)[1] + 10

    # canvas.paste(subi, (150, 0))
    # Add annotations
    # font = ImageFont.load_default()
    canvas.save(fout)
    return canvas


items = load_items(INDIR)
print("Loaded {} items".format(len(items)))

labels = []
for i, item in enumerate(items):
    fname = "{} {} {}.png".format(item.subcat, item.category, str(i))
    label = make_label(pretty_item(item), os.path.join(OUTDIR, fname))
    labels.append(label)

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield int(i/n), lst[i:i + n]

# Tile labels onto paper
l_per_row = math.floor((PAPERSIZE[0] - (2 * MARGIN)) / LABELSIZE[0])
l_per_col = math.floor((PAPERSIZE[1] - (2 * MARGIN)) / LABELSIZE[1])
n_pages = math.ceil(len(items) / (l_per_row * l_per_col))
print("{} labels per page, {} pages".format(l_per_row * l_per_col, n_pages))
for pageno, pagelabels in chunks(labels, l_per_col*l_per_row):
    paper = Image.new("RGBA", PAPERSIZE, color=(255, 255, 255))
    for i, label in enumerate(pagelabels):
        col = i % l_per_row
        row = math.floor(i / l_per_row)
        x, y = col * LABELSIZE[0] + MARGIN, row * LABELSIZE[1] + MARGIN
        print("row {}, col {} -> ({}., {})".format(col, row, x, y))
        paper.paste(label, (x, y))
    paper.save("all_page{}.png".format(pageno))
