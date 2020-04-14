import itertools
import os
import math
import sys
import csv
import re
from collections import namedtuple, defaultdict
from PIL import Image, ImageDraw, ImageFont

Item = namedtuple("Item", ["category", "subcat", "style", "gauge", "length", "notes"])

INDIR = "csvin"
OUTDIR = "imout"

DPI = 300
PAPERSIZE_IN = (8.5, 11)
MARGIN_IN = 0.25
CONTAINER_THUMBSIZE_IN = (0.5, 0.5)

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

# Worked best for cable mgmt stuff
THUMBSIZE_IN = (0.75, 0.45)
LABELSIZE_IN = (1.6, 1.3)  # SIZE OF INDIVIDUAL PART LABELS
FONT_HEAD_SIZE_IN = 0.17  # HEADER TEXT
FONT_SUB_SIZE_IN = 0.13  # SUBTEXT

CONTAINER_LABELSIZE_IN = (2, 2)  # SIZE OF CONTAINER LABELS

# Convert inch sizes to pixels
THUMBSIZE = tuple(int(s * DPI) for s in THUMBSIZE_IN)
LABELSIZE = tuple(int(s * DPI) for s in LABELSIZE_IN)
CONTAINER_LABELSIZE = tuple(int(s * DPI) for s in CONTAINER_LABELSIZE_IN)
CONTAINER_THUMBSIZE = tuple(int(s * DPI) for s in CONTAINER_THUMBSIZE_IN)
PAPERSIZE = tuple(int(s * DPI) for s in PAPERSIZE_IN)
MARGIN = int(MARGIN_IN * DPI)
FONT_HEAD = ImageFont.truetype("SourceSansPro-Semibold.ttf", int(FONT_HEAD_SIZE_IN * DPI))
FONT_SUB = ImageFont.truetype("SourceSansPro-Regular.ttf", int(FONT_SUB_SIZE_IN * DPI))

BLANK_IM = Image.open("img/misc.png").convert("RGBA")

def load_img_folder(path: str):
    """
    Returns:
        dict(str, Image): map of fname to img

    """
    fname_to_img = defaultdict(lambda: BLANK_IM)
    for imfile in os.listdir(path):
        if "png" in imfile:
            fname = imfile.replace(".png", "")
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


def load_items(path: str=INDIR):
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

    # canvas.paste(subi, (150, 0))
    # Add annotations
    # font = ImageFont.load_default()
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

    # Draw subcat images
    # x = 0
    # subis = [SUBCAT_IMS.get("_".join(c)) for c in container_subcats if SUBCAT_IMS.get("_".join(c))]
    # for ci in subis:
    #     ci.thumbnail(THUMBSIZE)
    #     canvas.paste(ci, (x, y))
    #     x += ci.size[0]

    draw = ImageDraw.Draw(canvas)
    diams_text = ",  ".join(container_diams)
    textw = _center_text_w(FONT_HEAD, diams_text, canvas.size[0])
    draw.text((textw, y), diams_text, fill=(0, 0, 0, 255), font=FONT_HEAD)

    canvas.save(fout)
    return canvas


def _diam_from_gauge(gauge: str):
    return gauge.split("-")[0]


items = load_items(sys.argv[1] if len(sys.argv) > 1 else INDIR)
print("Loaded {} items".format(len(items)))

labels = []
for i, item in enumerate(items):
    fname = "{} {} {}.png".format(item.subcat, item.category, str(i))
    label = make_label(pretty_item(item), os.path.join(OUTDIR, fname))
    labels.append(label)


def chunks(lst: list, n: int):
    """Enumerate successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield int(i / n), lst[i : i + n]


def summarize_inventory(items: list):
    """Print a bunch of stats.

    This really would've been better with a dataframe, but hey, using dict as group_by is "pythonic".

    Args:
        items (list[Item])

    Returns:

    """
    categories = set([i.category for i in items])
    cat_dict = {cat: [i for i in items if i.category == cat] for cat in list(categories)}
    print("{} categories".format(len(cat_dict)))
    for cat, catitems in cat_dict.items():
        subcat_dict = {
            subcat: [i for i in items if i.subcat == subcat]
            for subcat in list(set([ii.subcat for ii in catitems]))
        }
        summary = ", ".join(["{} {}".format(k, len(v)) for k, v in subcat_dict.items()])
        print("  {}: {}".format(cat, summary))
    screws = [i for i in items if "screw" in i.category]
    nuts = [i for i in items if "nut" in i.category]
    nut_threads = set(i.gauge for i in nuts)
    screws_without_nuts = [scr for scr in screws if scr.gauge not in nut_threads]
    if screws_without_nuts:
        print(
            "The following screws have no nuts: {}".format(
                ", ".join(set([s.gauge for s in screws_without_nuts]))
            )
        )
    # Uncomment to use for your purposes
    # threadeds = screws + nuts
    # thread_sizes = set([i.gauge for i in threadeds])
    # threadeds_diameters = [gauge.split("-")[0] for gauge in thread_sizes]
    # washers = [i for i in items if "washer" in i.category]
    # washer_diameters = set([w.gauge for w in washers])


# example_container = [i for i in items if i.gauge in ("M3", "M4")]
# container_img = make_container_label(example_container, "container_label.png")

# summarize_inventory(items)

# Tile labels onto paper
def tile(ims, target_size, imsize, out_label, rethumb=False):
    l_per_row = math.floor((target_size[0] - (2 * MARGIN)) / imsize[0])
    l_per_col = math.floor((target_size[1] - (2 * MARGIN)) / imsize[1])
    n_pages = math.ceil(len(items) / (l_per_row * l_per_col))
    print(
        "{} labels per page ({} per row X {} per column), {} pages".format(
            l_per_row * l_per_col, l_per_row, l_per_col, n_pages
        )
    )
    for pageno, pagelabels in chunks(ims, int(l_per_col * l_per_row)):
        paper = Image.new("RGBA", target_size, color=(255, 255, 255))
        for i, label in enumerate(pagelabels):
            col = i % l_per_row
            row = math.floor(i / l_per_row)
            x, y = col * imsize[0] + MARGIN, row * imsize[1] + MARGIN
            # print("col {}, row {} -> ({}., {})".format(col, row, x, y))
            label_copy = label.copy()
            if rethumb:
                thumbsize = imsize[0] - 10, imsize[1] - 10
                label_copy.thumbnail(thumbsize)
            paper.paste(label_copy, (x, y))
        paper.save("{}_page{}.png".format(out_label, pageno))

tile(labels, PAPERSIZE, LABELSIZE, "all")

### If we're labeling a single CSV, assume it's for one container and generate a container label too
if len(sys.argv) == 2:
    container_subcats = set(_imname(i) for i in items)
    container_ims = [SUBCAT_IMS[c] for c in container_subcats]
    tile(container_ims, PAPERSIZE, CONTAINER_THUMBSIZE, "container", rethumb=True)
