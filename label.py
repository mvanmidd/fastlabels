import click
import itertools
import os
import math
import sys
import csv
import re
from collections import namedtuple, defaultdict
from PIL import Image, ImageDraw, ImageFont, ImageOps
from itertools import chain

from typing import List

Item = namedtuple("Item", ["category", "subcat", "style", "gauge", "length", "notes"])

INDIR = "csvin"
OUTDIR = "imout"

DPI = 900
MARGIN_IN = (0.1875, 0.5)
PAPERSIZE_IN = (8.5, 11) # IGNORE RIGHT MARGIN
CONTAINER_THUMBSIZE_IN = (0.5, 0.5)
SIMPLE_THUMBSIZE_IN = (0.8, 0.6)
SIMPLE_LABELSIZE_IN = (.875, .95)

# Works best for wood screw / nail labels
# THUMBSIZE_IN = (0.75, 0.2)
# LABELSIZE_IN = (1.8, 1.0)  # SIZE OF INDIVIDUAL PART LABELS
# FONT_HEAD_SIZE_IN = 0.22  # HEADER TEXT
# FONT_SUB_SIZE_IN = 0.12  # SUBTEXT

# Worked best for machine screw labels
# THUMBSIZE_IN = (0.75, 0.15)
# LABELSIZE_IN = (1.0, 0.8)  # SIZE OF INDIVIDUAL PART LABELS
# FONT_HEAD_SIZE_IN = 0.17  # HEADER TEXT
# FONT_SUB_SIZE_IN = 0.09  # SUBTEXT

CELLSIZE_IN = (2.625, .95)  # SIZE OF INDIVIDUAL PART LABELS
CELL_MARGIN_IN = (0.125, 0.05)  # SIZE OF INDIVIDUAL PART LABELS

# Worked best for cable mgmt stuff
THUMBSIZE_IN = (0.75, 0.65)
LABELSIZE_IN = (2.625, 1.0)  # SIZE OF INDIVIDUAL PART LABELS
FONT_HEAD_SIZE_IN = 0.17  # HEADER TEXT
FONT_SUB_SIZE_IN = 0.13  # SUBTEXT

CONTAINER_LABELSIZE_IN = (2, 2)  # SIZE OF CONTAINER LABELS

# Convert inch sizes to pixels
THUMBSIZE = tuple(int(s * DPI) for s in THUMBSIZE_IN)
LABELSIZE = tuple(int(s * DPI) for s in LABELSIZE_IN)
CONTAINER_LABELSIZE = tuple(int(s * DPI) for s in CONTAINER_LABELSIZE_IN)
CONTAINER_THUMBSIZE = tuple(int(s * DPI) for s in CONTAINER_THUMBSIZE_IN)
SIMPLE_THUMBSIZE = tuple(int(s * DPI) for s in SIMPLE_THUMBSIZE_IN)
SIMPLE_LABELSIZE = tuple(int(s * DPI) for s in SIMPLE_LABELSIZE_IN)
PAPERSIZE = tuple(int(s * DPI) for s in PAPERSIZE_IN)
MARGIN = (int(MARGIN_IN[0] * DPI), int(MARGIN_IN[1] * DPI))
CELLSIZE = tuple(int(s * DPI) for s in CELLSIZE_IN)
CELL_MARGIN = tuple(int(s * DPI) for s in CELL_MARGIN_IN)
FONT_HEAD = ImageFont.truetype("SourceSansPro-Semibold.ttf", int(FONT_HEAD_SIZE_IN * DPI))
FONT_SUB = ImageFont.truetype("SourceSansPro-Regular.ttf", int(FONT_SUB_SIZE_IN * DPI))

BLANK_IM = Image.open("img/misc.png").convert("RGBA")


def load_img_folder(path: str):
    """
    Returns:
        dict(str, Image): map of fname to img

    """
    fname_to_img = defaultdict(lambda: BLANK_IM)
    for imfile in sorted(os.listdir(path)):
        if "png" in imfile:
            fname = imfile.replace(".png", "")
            if fname.startswith("-"):  # allow prefix of "-N-" to specify order
                fname = "".join(fname.split("-")[2:])
            img = Image.open(os.path.join(path, imfile))
            fname_to_img[fname] = img.convert("RGBA")
    return fname_to_img


def load_csv(fname: str):
    """Load a single CSV into a list of Items.

    Items must have at least a category, subcat, and gauge (size).

    """
    items = []
    with open(fname) as fin:
        reader = csv.DictReader(fin)
        for row in reader:
            if row["gauge"] and row["category"] and row["subcat"]:
                items.append(Item(**row))
            else:
                print("Ignoring row")
                print(row)
    return items


def load_items(path: str = INDIR):
    """Load all items in a path. If path is a single CSV, load it, otherwise assume path is a directory and
    load all CSVs in the directory.

    """
    if path.endswith(".csv"):
        return load_csv(path)
    else:
        return list(
            itertools.chain.from_iterable(
                load_csv(os.path.join(path, f)) for f in os.listdir(path) if f.endswith(".csv")
            )
        )


CAT_IMS = load_img_folder("img/cat")
SUBCAT_IMS = load_img_folder("img/subcat")

EXAMPLE_FRAC = "¹⁄₄"


def to_unifrac(text: str):
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


def pretty_item(item: Item):
    """Make pretty unicode fractions from object text."""
    return Item(**{k: to_unifrac(v) for k, v in item._asdict().items()})


def _center(obj: int, canvas: int):
    """Center object of a given width along a single dimension on canvas of a given width, return lower bound of
    object position.

    """
    return int((canvas - obj) / 2)


def _imname(item):
    return "_".join([item.category, item.subcat])


def _item_im(item):
    return SUBCAT_IMS[_imname(item)].copy()


def _center_text_w(font: ImageFont, text: str, canvas_width: int):
    """Return the X coordinate required to center text on canvas of a given width

    Returns:
        int

    """
    textw = font.getsize(text)[0]
    return _center(textw, canvas_width)


def _center_im_w(im: Image, canvas_width: int):
    return _center(im.size[0], canvas_width)


def _snap_y(y: int, incr: int = 1):
    """Snap to a grid with spacing incr, default is 1 == no-op."""
    return incr * math.ceil(y / incr)

def _resize(im: Image.Image, desired):
    rx, ry = desired[0] / im.size[0], desired[1] / im.size[1]
    scale = min(rx, ry)
    return im.resize((int(im.size[0] * scale), int(im.size[1] * scale)), Image.ANTIALIAS)

def make_simple_square(img: Image.Image, text, thumbsize=THUMBSIZE, labelsize=LABELSIZE, font=FONT_HEAD):
    """Label with thumbnail centered, one line of text underneath"""
    canvas = Image.new("RGBA", labelsize, color=(255, 255, 255, 0))
    thumbi = _resize(img.copy(), thumbsize)
    # thumbi = ImageOps.autocontrast(thumbi)
    thumbi_hc = ImageOps.equalize(thumbi.convert("RGB"), mask=thumbi.split()[-1]).quantize(colors=12)
    # thumbi.thumbnail(thumbsize)

    # Thumbnail on left side
    x = y = int(DPI * (1/16))
    imx = _center_im_w(thumbi, labelsize[0])
    imy = _center(thumbi.size[1], thumbsize[1])
    canvas.paste(thumbi_hc, (imx, imy), mask=thumbi)
    # canvas.paste(thumbi, (imx, imy))
    y += thumbsize[1]
    text_x = _center_text_w(font, text, canvas.size[0])

    draw = ImageDraw.Draw(canvas)
    draw.text((text_x, y), text, fill=(0,0,0,255), font=font)

    return canvas


def make_simple_landscape_label(img: Image.Image, text, thumbsize=THUMBSIZE, labelsize=LABELSIZE, font=FONT_HEAD):
    """Label with thumbnail on left, one line of text on right"""
    canvas = Image.new("RGBA", labelsize, color=(255, 255, 255, 0))
    thumbi = img.copy()
    thumbi.thumbnail(thumbsize)

    # Thumbnail on left side
    x = y = int(DPI * (1/8))
    canvas.paste(thumbi, (x, y), thumbi)

    x += thumbi.size[0]

    text_x = x + _center_text_w(font, text, canvas.size[0] - x)

    draw = ImageDraw.Draw(canvas)
    draw.text((text_x, y), text, fill=(0,0,0,255), font=FONT_HEAD)

    return canvas



def make_label(item: Item, fout: str):
    """Make a label for an individual item."""
    canvas = Image.new("RGBA", LABELSIZE, color=(255, 255, 255))
    subi = _item_im(item)
    subi.thumbnail(THUMBSIZE)

    # Draw from top down, tracking vertical offset 'y'
    y = 2
    draw = ImageDraw.Draw(canvas)
    header_text = item.gauge
    if item.length:
        header_text = header_text + " x {}".format(item.length)
    textw = _center_text_w(FONT_HEAD, header_text, canvas.size[0])
    draw.text((textw, y), header_text, fill=(0, 0, 0, 255), font=FONT_HEAD)
    y = _snap_y(y + FONT_HEAD.getsize(EXAMPLE_FRAC)[1] + 10)

    subw = _center_im_w(subi, canvas.size[0])
    canvas.paste(subi, (subw, y))
    y = _snap_y(y + subi.size[1] + 10)

    summary_text = "{} {}".format(item.subcat, item.category)
    textw = _center_text_w(FONT_SUB, summary_text, canvas.size[0])
    draw.text((textw, y), summary_text, fill=(0, 0, 0, 255), font=FONT_SUB)
    y = _snap_y(y + FONT_SUB.getsize(summary_text)[1] + 10)

    canvas.save(fout)
    return canvas


def make_container_label(items: list, fout: str):
    """Make a label for a container of multiple items. Picture of all item categories, text of all item sizes.

    Args:
        items (list[Item]):

    Returns:

    """
    container_cats = set(i.category for i in items)
    container_subcats = set((i.category, i.subcat) for i in items)
    container_diams = set(_diam_from_gauge(i.gauge) for i in items)
    print(container_cats)
    print(container_subcats)
    print(container_diams)

    # Draw primary category images
    y = 2
    canvas = Image.new("RGBA", CONTAINER_LABELSIZE, color=(255, 255, 255))
    catis = [CAT_IMS.get(c).copy() for c in container_cats if CAT_IMS.get(c)]
    for ci in catis:
        ci.thumbnail(CONTAINER_THUMBSIZE)
    x_total = sum(ci.size[0] for ci in catis) + (len(catis) - 1) * 20
    x = _center(x_total, canvas.size[0])
    print(x, x_total, canvas.size[0])
    for ci in catis:
        canvas.paste(ci, (x, y))
        x += ci.size[0] + 20
    y = max(ci.size[1] for ci in catis) + 10

    draw = ImageDraw.Draw(canvas)
    diams_text = ",  ".join(container_diams)
    textw = _center_text_w(FONT_HEAD, diams_text, canvas.size[0])
    draw.text((textw, y), diams_text, fill=(0, 0, 0, 255), font=FONT_HEAD)

    canvas.save(fout)
    return canvas


def _diam_from_gauge(gauge: str):
    return gauge.split("-")[0]


def chunks(lst: list, n: int):
    """Enumerate successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield int(i / n), lst[i : i + n]


def template_tile(ims, cell_size, cell_margin = CELL_MARGIN, target_size=PAPERSIZE, underlay=None, skip_cells=0):
    """Tile to a template, grouping ims horizontally into `cell_size` chunks."""
    imsize = ims[0].size
    print("Image dimensions: {}x{} px, {:.2}x{:.2} in".format(imsize[0], imsize[1], imsize[0]/DPI, imsize[1]/DPI))
    cell_margin_x, cell_margin_y = cell_margin
    ims_per_cell = math.floor(cell_size[0] / ims[0].size[0])
    cell_per_row = math.floor((target_size[0] + cell_margin_x - (2 * MARGIN[0])) / (cell_size[0] + cell_margin_x))
    cell_per_col = math.floor((target_size[1] + cell_margin_y - (2 * MARGIN[1])) / (cell_size[1] + cell_margin_y))
    print(
        "{} labels per page ({} per row X {} per column X {} labels per cell)".format(
            cell_per_row * cell_per_col * ims_per_cell, cell_per_row, cell_per_col, ims_per_cell
        )
    )
    if underlay:
        paper = underlay.copy()
        paper.thumbnail(target_size)
    else:
        paper = Image.new("RGBA", target_size, color=(255, 255, 255))
    for cellno, cell_ims in chunks(ims, ims_per_cell):
        cellno += skip_cells
        cell_im = Image.new("RGBA", cell_size, color=(255, 255, 255, 0))
        for imno, im in enumerate(cell_ims):
            im_x_center = (imsize[0] / 2) + (imno) * ((cell_size[0]-imsize[0]) / (ims_per_cell - 1))
            im_x = int(im_x_center - .5 * imsize[0])
            cell_im.paste(im, (im_x, 0), im)
        col = cellno % cell_per_row
        row = math.floor(cellno / cell_per_row)
        cellx = MARGIN[0] + (cell_size[0] + cell_margin[0]) * col
        celly = MARGIN[1] + (cell_size[1] + cell_margin[1]) * row
        # Mark cell corners
        for px in ((0, 0), (cell_size[0]-1, 0), (cell_size[0]-1, cell_size[1]-1), (0, cell_size[1]-1)):
            cell_im.putpixel(px, (0, 0, 0, 255))
        paper.paste(cell_im, (cellx, celly), cell_im)
    return paper



# Tile labels onto paper
def tile(ims, target_size, imsize, out_label, rethumb=False, underlay=None):
    l_per_row = math.floor((target_size[0] - (2 * MARGIN[0])) / imsize[0])
    l_per_col = math.floor((target_size[1] - (2 * MARGIN[1])) / imsize[1])
    n_pages = math.ceil(len(ims) / (l_per_row * l_per_col))
    print(
        "{} labels per page ({} per row X {} per column), {} pages".format(
            l_per_row * l_per_col, l_per_row, l_per_col, n_pages
        )
    )
    for pageno, pagelabels in chunks(ims, int(l_per_col * l_per_row)):
        if underlay:
            paper = underlay.copy()
            paper.thumbnail(target_size)
        else:
            paper = Image.new("RGBA", target_size, color=(255, 255, 255))
        for i, label in enumerate(pagelabels):
            col = i % l_per_row
            row = math.floor(i / l_per_row)
            x, y = col * imsize[0] + MARGIN[0], row * imsize[1] + MARGIN[1]
            # print("col {}, row {} -> ({}., {})".format(col, row, x, y))
            label_copy = label.copy()
            if rethumb:
                thumbsize = imsize[0] - 10, imsize[1] - 10
                label_copy.thumbnail(thumbsize)
            paper.paste(label_copy, (x, y), label_copy)
        paper.save("{}_page{}.png".format(out_label, pageno))


@click.command()
@click.option("-s", "--simple", is_flag=True, default=False)
@click.option("-t", "--template", is_flag=True, default=False)
@click.option("-k", "--skip-cells", type=int, default=0)
@click.option("-f", "--outfile", default="out.png")
@click.argument("inpath", required=True)
def main(simple, template, skip_cells, outfile, inpath):
    labels = []
    if not simple:
        items = load_items(inpath[0])
        print("Loaded {} items".format(len(items)))

        for i, item in enumerate(items):
            fname = "{} {} {}.png".format(item.subcat, item.category, str(i))
            label = make_label(pretty_item(item), os.path.join(OUTDIR, fname))
            labels.append(label)

    else:
        # Simple mode: just load a dir of images, use name as text
        simple_ims = {}
        print(inpath)
        for indir in [inpath]: # minor change to support nargs=-1 on inpath
            simple_ims.update(load_img_folder(indir))
        for fname, im in simple_ims.items():
            labels.append(make_simple_square(im, fname, thumbsize=SIMPLE_THUMBSIZE, labelsize=SIMPLE_LABELSIZE, font=FONT_SUB))

    underlay = Image.open("label_sheet_template.png").convert("RGBA") if template else None

    if not simple:
        tile(labels, PAPERSIZE, LABELSIZE, "all", underlay=underlay)
    else:
        im = template_tile(labels, cell_size=CELLSIZE, cell_margin=CELL_MARGIN, underlay=underlay, skip_cells=skip_cells)
        im.save(outfile)

    ### If we're labeling a single CSV, assume it's for one container and generate a container label too
    if inpath[0].endswith("csv"):
        container_subcats = set(_imname(i) for i in items)
        container_ims = [SUBCAT_IMS[c] for c in container_subcats]
        tile(container_ims, PAPERSIZE, CONTAINER_THUMBSIZE, "container", rethumb=True)


if __name__ == "__main__":
    main()
