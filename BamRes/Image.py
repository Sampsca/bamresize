#
# The Python Imaging Library.
# $Id$
#
# the Image class wrapper
#
# history:
# 1995-09-09 fl   Created
# 1996-03-11 fl   PIL release 0.0 (proof of concept)
# 1996-04-30 fl   PIL release 0.1b1
# 1996-05-27 fl   PIL release 0.1b2
# 1996-11-04 fl   PIL release 0.2b1
# 1996-12-08 fl   PIL release 0.2b2
# 1996-12-16 fl   PIL release 0.2b3
# 1997-01-14 fl   PIL release 0.2b4
# 1998-07-02 fl   PIL release 0.3b1
# 1998-07-17 fl   PIL release 0.3b2
# 1999-01-01 fl   PIL release 1.0b1
# 1999-02-08 fl   PIL release 1.0b2
# 1999-07-28 fl   PIL release 1.0 final
# 1999-08-15 fl   PIL release 1.0.1 (internal maintenance release)
# 2000-06-07 fl   PIL release 1.1
# 2000-10-20 fl   PIL release 1.1.1
# 2001-05-07 fl   PIL release 1.1.2
#
# Copyright (c) 1997-2001 by Secret Labs AB.
# Copyright (c) 1995-2001 by Fredrik Lundh.
#
# See the README file for information on usage and redistribution.
#

VERSION = "1.1.2"

class _imaging_not_installed:
    # module placeholder
    def __getattr__(self, id):
        raise ImportError, "The _imaging C module is not installed"

try:
    # give Tk a chance to set up the environment, in case we're
    # using an _imaging module linked against libtcl/libtk
    import FixTk
except ImportError:
    pass

try:
    # If the _imaging C module is not present, you can still use
    # the "open" function to identify files, but you cannot load
    # them.  Note that other modules should not refer to _imaging
    # directly; import Image and use the Image.core variable instead.
    import _imaging
    core = _imaging
    del _imaging
except ImportError:
    core = _imaging_not_installed()

import ImagePalette
import os, string, sys

# type stuff
from types import IntType, StringType, TupleType

def isStringType(t):
    return type(t) is StringType

def isTupleType(t):
    return type(t) is TupleType

def isImageType(t):
    return hasattr(t, "im")

def isDirectory(f):
    return isStringType(f) and os.path.isdir(f)

from operator import isNumberType, isSequenceType

#
# Debug level

DEBUG = 0

#
# Constants (also defined in _imagingmodule.c!)

NONE = 0

# transpose
FLIP_LEFT_RIGHT = 0
FLIP_TOP_BOTTOM = 1
ROTATE_90 = 2
ROTATE_180 = 3
ROTATE_270 = 4

# transforms
AFFINE = 0
EXTENT = 1
PERSPECTIVE = 2 # Not yet implemented
QUAD = 3
MESH = 4

# resampling
NONE = 0
NEAREST = 0
ANTIALIAS = 1
BILINEAR = 2
BICUBIC = 3

# dithers
NONE = 0
NEAREST = 0
ORDERED = 1 # Not yet implemented
RASTERIZE = 2 # Not yet implemented
FLOYDSTEINBERG = 3 # default

# palettes/quantizers
WEB = 0
ADAPTIVE = 1

# categories
NORMAL = 0
SEQUENCE = 1
CONTAINER = 2

# --------------------------------------------------------------------
# Registries

ID = []
OPEN = {}
MIME = {}
SAVE = {}
EXTENSION = {}

# --------------------------------------------------------------------
# Modes supported by this version

_MODEINFO = {

    # official modes
    "1": ("L", "L", ("1",)),
    "L": ("L", "L", ("L",)),
    "I": ("L", "I", ("I",)),
    "F": ("L", "F", ("F",)),
    "P": ("RGB", "L", ("P",)),
    "RGB": ("RGB", "L", ("R", "G", "B")),
    "RGBX": ("RGB", "L", ("R", "G", "B", "X")),
    "RGBA": ("RGB", "L", ("R", "G", "B", "A")),
    "CMYK": ("RGB", "L", ("C", "M", "Y", "K")),
    "YCbCr": ("RGB", "L", ("Y", "Cb", "Cr")),

    # Experimental modes include I;16, I;16B, RGBa, BGR;15,
    # and BGR;24.  Use these modes only if you know exactly
    # what you're doing...

}

MODES = _MODEINFO.keys()
MODES.sort()

def getmodebase(mode):
    # corresponding "base" mode (grayscale or colour)
    return _MODEINFO[mode][0]

def getmodetype(mode):
    # storage type (per band)
    return _MODEINFO[mode][1]

def getmodebands(mode):
    # subcomponents
    return len(_MODEINFO[mode][2])

# --------------------------------------------------------------------
# Helpers

_initialized = 0

def preinit():
    "Load standard file format drivers."

    global _initialized
    if _initialized >= 1:
        return

    for m in ("Bmp", "Gif", "Jpeg", "Ppm", "Png", "Tiff"):
        try:
            __import__("%sImagePlugin" % m, globals(), locals(), [])
        except ImportError:
            pass # ignore missing driver for now

    _initialized = 1

def init():
    "Load all file format drivers."

    global _initialized
    if _initialized >= 2:
        return

    visited = {}

    directories = sys.path + [os.path.dirname(__file__)]

    # only check directories (including current, if present in the path)
    for directory in filter(isDirectory, directories):
        fullpath = os.path.abspath(directory)
        if visited.has_key(fullpath):
            continue
        for file in os.listdir(directory):
            if file[-14:] == "ImagePlugin.py":
                f, e = os.path.splitext(file)
                try:
                    sys.path.insert(0, directory)
                    try:
                        __import__(f, globals(), locals(), [])
                    finally:
                        del sys.path[0]
                except ImportError:
                    if DEBUG:
                        print "Image: failed to import",
                        print f, ":", sys.exc_value
        visited[fullpath] = None

    if OPEN or SAVE:
        _initialized = 2


# --------------------------------------------------------------------
# Codec factories (used by tostring/fromstring and ImageFile.load)

def _getdecoder(mode, decoder_name, args, extra=()):

    # tweak arguments
    if args is None:
        args = ()
    elif type(args) != TupleType:
        args = (args,)

    try:
        # get decoder
        decoder = getattr(core, decoder_name + "_decoder")
        # print decoder, (mode,) + args + extra
        return apply(decoder, (mode,) + args + extra)
    except AttributeError:
        raise IOError, "decoder %s not available" % decoder_name

def _getencoder(mode, encoder_name, args, extra=()):

    # tweak arguments
    if args is None:
        args = ()
    elif type(args) != TupleType:
        args = (args,)

    try:
        # get encoder
        encoder = getattr(core, encoder_name + "_encoder")
        # print encoder, (mode,) + args + extra
        return apply(encoder, (mode,) + args + extra)
    except AttributeError:
        raise IOError, "encoder %s not available" % encoder_name


# --------------------------------------------------------------------
# Simple expression analyzer

class _E:
    def __init__(self, data): self.data = data
    def __coerce__(self, other): return self, _E(other)
    def __add__(self, other): return _E((self.data, "__add__", other.data))
    def __mul__(self, other): return _E((self.data, "__mul__", other.data))

def _getscaleoffset(expr):
    stub = ["stub"]
    data = expr(_E(stub)).data
    try:
        (a, b, c) = data # simplified syntax
        if (a is stub and b == "__mul__" and isNumberType(c)):
            return c, 0.0
        if (a is stub and b == "__add__" and isNumberType(c)):
            return 1.0, c
    except TypeError: pass
    try:
        ((a, b, c), d, e) = data # full syntax
        if (a is stub and b == "__mul__" and isNumberType(c) and
            d == "__add__" and isNumberType(e)):
            return c, e
    except TypeError: pass
    raise ValueError, "illegal expression"


# --------------------------------------------------------------------
# Implementation wrapper

class Image:

    format = None
    format_description = None

    def __init__(self):
        self.im = None
        self.mode = ""
        self.size = (0, 0)
        self.palette = None
        self.info = {}
        self.category = NORMAL
        self.readonly = 0

    def _new(self, im):
        new = Image()
        new.im = im
        new.mode = im.mode
        new.size = im.size
        new.palette = self.palette
        try:
            new.info = self.info.copy()
        except AttributeError:
            # fallback (pre-1.5.2)
            new.info = {}
            for k, v in self.info:
                new.info[k] = v
        return new

    _makeself = _new # compatibility

    def _copy(self):
        self.load()
        self.im = self.im.copy()
        self.readonly = 0

    def _dump(self, file=None, format=None):
        import tempfile
        if not file:
            file = tempfile.mktemp()
        self.load()
        if not format or format == "PPM":
            self.im.save_ppm(file)
        else:
            file = file + "." + format
            self.save(file, format)
        return file

    def tostring(self, encoder_name="raw", *args):
        "Return image as a binary string"

        # may pass tuple instead of argument list
        if len(args) == 1 and isTupleType(args[0]):
            args = args[0]

        if encoder_name == "raw" and args == ():
            args = self.mode

        self.load()

        # unpack data
        e = _getencoder(self.mode, encoder_name, args)
        e.setimage(self.im)

        data = []
        while 1:
            l, s, d = e.encode(65536)
            data.append(d)
            if s:
                break
        if s < 0:
            raise RuntimeError, "encoder error %d in tostring" % s

        return string.join(data, "")

    def tobitmap(self, name="image"):
        "Return image as an XBM bitmap"

        self.load()
        if self.mode != "1":
            raise ValueError, "not a bitmap"
        data = self.tostring("xbm")
        return string.join(["#define %s_width %d\n" % (name, self.size[0]),
                "#define %s_height %d\n"% (name, self.size[1]),
                "static char %s_bits[] = {\n" % name, data, "};"], "")

    def fromstring(self, data, decoder_name="raw", *args):
        "Load data to image from binary string"

        # may pass tuple instead of argument list
        if len(args) == 1 and isTupleType(args[0]):
            args = args[0]

        # default format
        if decoder_name == "raw" and args == ():
            args = self.mode

        # unpack data
        d = _getdecoder(self.mode, decoder_name, args)
        d.setimage(self.im)
        s = d.decode(data)

        if s[0] >= 0:
            raise ValueError, "not enough image data"
        if s[1] != 0:
            raise ValueError, "cannot decode image data"

    def load(self):
        if self.im and self.palette and self.palette.rawmode:
            self.im.putpalette(self.palette.rawmode, self.palette.data)
            self.palette.mode = "RGB"
            self.palette.rawmode = None
            if self.info.has_key("transparency"):
                self.im.putpalettealpha(self.info["transparency"], 0)
                self.palette.mode = "RGBA"

    #
    # function wrappers

    def convert(self, mode=None, data=None, dither=None,
                palette=WEB, colors=256):
        "Convert to other pixel format"

        if not mode:
            # determine default mode
            if self.mode == "P":
                self.load()
                if self.palette:
                    mode = self.palette.mode
                else:
                    mode = "RGB"
            else:
                return self.copy()

        self.load()

        if data:
            # matrix conversion
            if mode not in ("L", "RGB"):
                raise ValueError, "illegal conversion"
            im = self.im.convert_matrix(mode, data)
            return self._new(im)

        if mode == "P" and palette == ADAPTIVE:
            im = self.im.quantize(colors)
            return self._new(im)

        # colourspace conversion
        if dither is None:
            dither = FLOYDSTEINBERG

        try:
            im = self.im.convert(mode, dither)
        except ValueError:
            try:
                # normalize source image and try again
                im = self.im.convert(getmodebase(self.mode))
                im = im.convert(mode, dither)
            except KeyError:
                raise ValueError, "illegal conversion"

        return self._new(im)

    def quantize(self, colors=256, method=0, kmeans=0):

        # methods:
        #    0 = median cut
        #    1 = maximum coverage

        # NOTE: this functionality will be moved to the extended
        # quantizer interface in a later versions of PIL.

        self.load()
        im = self.im.quantize(colors, method, kmeans)
        return self._new(im)

    def copy(self):
        "Copy raster data"

        self.load()
        im = self.im.copy()
        return self._new(im)

    def crop(self, box=None):
        "Crop region from image"

        self.load()
        if box is None:
            return self.copy()

        # delayed operation
        return _ImageCrop(self, box)

    def draft(self, mode, size):
        "Configure image decoder"

        pass

    def filter(self, kernel):
        "Apply environment filter to image"

        if self.mode == "P":
            raise ValueError, "cannot filter palette images"
        self.load()
        id = kernel.id
        if self.im.bands == 1:
            return self._new(self.im.filter(id))
        # fix to handle multiband images since _imaging doesn't
        ims = []
        for c in range(self.im.bands):
            ims.append(self._new(self.im.getband(c).filter(id)))
        return merge(self.mode, ims)

    def getbands(self):
        "Get band names"

        return _MODEINFO[self.mode][2]

    def getbbox(self):
        "Get bounding box of actual data (non-zero pixels) in image"

        self.load()
        return self.im.getbbox()

    def getdata(self, band = None):
        "Get image data as sequence object."

        self.load()
        if band is not None:
            return self.im.getband(band)
        return self.im # could be abused

    def getextrema(self):
        "Get min/max value"

        self.load()
        if self.im.bands > 1:
            extrema = []
            for i in range(self.im.bands):
                extrema.append(self.im.getband(i).getextrema())
            return tuple(extrema)
        return self.im.getextrema()

    def getpixel(self, xy):
        "Get pixel value"

        self.load()
        return self.im.getpixel(xy)

    def getprojection(self):
        "Get projection to x and y axes"

        self.load()
        x, y = self.im.getprojection()
        return map(ord, x), map(ord, y)

    def histogram(self, mask=None, extrema=None):
        "Take histogram of image"

        self.load()
        if mask:
            mask.load()
            return self.im.histogram((0, 0), mask.im)
        if self.mode in ("I", "F"):
            if extrema is None:
                extrema = self.getextrema()
            return self.im.histogram(extrema)
        return self.im.histogram()

    def offset(self, xoffset, yoffset=None):
        "(deprecated) Offset image in horizontal and/or vertical direction"
        import ImageChops
        return ImageChops.offset(self, xoffset, yoffset)

    def paste(self, im, box=None, mask=None):
        "Paste other image into region"

        if box is None:
            # cover all of self
            box = (0, 0) + self.size

        if len(box) == 2:
            # lower left corner given; get size from image or mask
            if isImageType(im):
                box = box + (box[0]+im.size[0], box[1]+im.size[1])
            else:
                box = box + (box[0]+mask.size[0], box[1]+mask.size[1])

        if isImageType(im):
            im.load()
            if self.mode != im.mode:
                if self.mode != "RGB" or im.mode not in ("RGBA", "RGBa"):
                    # should use an adapter for this!
                    im = im.convert(self.mode)
            im = im.im

        self.load()

        if self.readonly:
            self._copy()

        if mask:
            mask.load()
            self.im.paste(im, box, mask.im)
        else:
            self.im.paste(im, box)

    def point(self, lut, mode=None):
        "Map image through lookup table"

        if self.mode in ("I", "F"):
            # floating point; lut must be a valid expression
            scale, offset = _getscaleoffset(lut)
            self.load()
            im = self.im.point_transform(scale, offset);
        else:
            # integer image; use lut and mode
            self.load()
            if not isSequenceType(lut):
                # if it isn't a list, it should be a function
                lut = map(lut, range(256)) * self.im.bands
            im = self.im.point(lut, mode)

        return self._new(im)

    def putalpha(self, im):
        "Set alpha layer"

        if self.mode != "RGBA" or im.mode not in ("1", "L"):
            raise ValueError, "illegal image mode"

        im.load()
        self.load()

        if im.mode == "1":
            im = im.convert("L")

        self.im.putband(im.im, 3)

    def putdata(self, data, scale=1.0, offset=0.0):
        "Put data from a sequence object into an image."

        self.load() # hmm...
        self.im.putdata(data, scale, offset)

    def putpalette(self, data, rawmode="RGB"):
        "Put palette data into an image."

        if self.mode not in ("L", "P"):
            raise ValueError, "illegal image mode"
        if type(data) != StringType:
            data = string.join(map(chr, data), "")
        self.mode = "P"
        self.palette = ImagePalette.raw(rawmode, data)
        self.palette.mode = "RGB"

    def putpixel(self, xy, value):
        "Set pixel value"

        self.load()
        return self.im.putpixel(xy, value)

    def resize(self, size, resample=NEAREST):
        "Resize image"

        if resample not in (NEAREST, BILINEAR, BICUBIC, ANTIALIAS):
            raise ValueError, "unknown resampling filter"

        self.load()

        if self.mode in ("1", "P"):
            resample = NEAREST

        if resample == ANTIALIAS:
            x0, y0 = self.size
            x1, y1 = size
            try:
                if x0 * y1 < x1 * y0:
                    im = self.im.vstretch(x0, y1).hstretch(x1, y1)
                else:
                    im = self.im.hstretch(x1, y0).vstretch(x1, y1)
            except AttributeError:
                raise ValueError, "unsupported resampling filter"
        else:
            im = self.im.resize(size, resample)

        return self._new(im)

    def rotate(self, angle, resample=NEAREST):
        "Rotate image.  Angle given as degrees counter-clockwise."

        if resample not in (NEAREST, BILINEAR, BICUBIC):
            raise ValueError, "unknown resampling filter"

        self.load()

        if self.mode in ("1", "P"):
            resample = NEAREST

        return self._new(self.im.rotate(angle, resample))

    def save(self, fp, format=None, **params):
        "Save image to file or stream"

        if isStringType(fp):
            import __builtin__
            filename = fp
            fp = __builtin__.open(fp, "wb")
            close = 1
        else:
            filename = ""
            close = 0

        self.encoderinfo = params
        self.encoderconfig = ()

        self.load()

        preinit()

        ext = string.lower(os.path.splitext(filename)[1])

        try:

            if not format:
                format = EXTENSION[ext]

            SAVE[string.upper(format)](self, fp, filename)

        except KeyError, v:

            init()

            if not format:
                format = EXTENSION[ext]

            SAVE[string.upper(format)](self, fp, filename)

        if close:
            fp.close()

    def seek(self, frame):
        "Seek to given frame in sequence file"

        # overridden by file handlers
        if frame != 0:
            raise EOFError

    def show(self, title=None, command=None):
        "Display image (for debug purposes only)"

        try:
            import ImageTk
            ImageTk._show(self, title)
            # note: caller must enter mainloop!
        except:
            _showxv(self, title, command)

    def split(self):
        "Split image into bands"

        ims = []
        self.load()
        for i in range(self.im.bands):
            ims.append(self._new(self.im.getband(i)))
        return tuple(ims)

    def tell(self):
        "Return current frame number"

        return 0

    def thumbnail(self, size, resample=ANTIALIAS):
        "Create thumbnail representation (modifies image in place)"

        # preserve aspect ratio
        x, y = self.size
        if x > size[0]: y = y * size[0] / x; x = size[0]
        if y > size[1]: x = x * size[1] / y; y = size[1]
        size = x, y

        if size == self.size:
            return

        self.draft(None, size)

        self.load()

        try:
            im = self.resize(size, resample)
        except ValueError:
            if resample != ANTIALIAS:
                raise
            im = self.resize(size, NEAREST)

        self.im = im.im
        self.mode = im.mode
        self.size = size

        self.readonly = 0

    def transform(self, size, method, data, resample=NEAREST, fill=1):
        "Transform image"

        im = new(self.mode, size, None)
        if method == MESH:
            # list of quads
            for box, quad in data:
                im.__transformer(box, self, QUAD, quad, resample, fill)
        else:
            im.__transformer((0, 0)+size, self, method, data, resample, fill)

        return im

    def __transformer(self, box, image, method, data,
                      resample=NEAREST, fill=1):
        "Transform into current image"

        # FIXME: this should be turned into a lazy operation (?)

        w = box[2]-box[0]
        h = box[3]-box[1]

        if method == AFFINE:
            # change argument order to match implementation
            data = (data[2], data[0], data[1],
                    data[5], data[3], data[4])
        elif method == EXTENT:
            # convert extent to an affine transform
            x0, y0, x1, y1 = data
            xs = float(x1 - x0) / w
            ys = float(y1 - y0) / h
            method = AFFINE
            data = (x0 + xs/2, xs, 0, y0 + ys/2, 0, ys)
        elif method == QUAD:
            # quadrilateral warp.  data specifies the four corners
            # given as NW, SW, SE, and NE.
            nw = data[0:2]; sw = data[2:4]; se = data[4:6]; ne = data[6:8]
            x0, y0 = nw; As = 1.0 / w; At = 1.0 / h
            data = (x0, (ne[0]-x0)*As, (sw[0]-x0)*At,
                    (se[0]-sw[0]-ne[0]+x0)*As*At,
                    y0, (ne[1]-y0)*As, (sw[1]-y0)*At,
                    (se[1]-sw[1]-ne[1]+y0)*As*At)
        else:
            raise ValueError, "unknown transformation method"

        if resample not in (NEAREST, BILINEAR, BICUBIC):
            raise ValueError, "unknown resampling filter"

        image.load()

        self.load()

        if image.mode in ("1", "P"):
            resample = NEAREST

        self.im.transform2(box, image.im, method, data, resample, fill)

    def transpose(self, method):
        "Transpose image (flip or rotate in 90 degree steps)"

        self.load()
        im = self.im.transpose(method)
        return self._new(im)


# --------------------------------------------------------------------
# Delayed operations

class _ImageCrop(Image):

    def __init__(self, im, box):

        Image.__init__(self)

        self.mode = im.mode
        self.size = box[2]-box[0], box[3]-box[1]

        self.__crop = box

        self.im = im.im

    def load(self):

        # lazy evaluation!
        if self.__crop:
            self.im = self.im.crop(self.__crop)
            self.__crop = None

        # FIXME: future versions should optimize crop/paste
        # sequences!

# --------------------------------------------------------------------
# Factories

#
# Debugging

def _wedge():
    "Create greyscale wedge (for debugging only)"

    return Image()._new(core.wedge("L"))

#
# Create/open images.

def new(mode, size, color=0):
    "Create a new image"

    if color is None:
        # don't initialize
        return Image()._new(core.new(mode, size))

    return Image()._new(core.fill(mode, size, color))


def fromstring(mode, size, data, decoder_name="raw", *args):
    "Load image from string"

    # may pass tuple instead of argument list
    if len(args) == 1 and isTupleType(args[0]):
        args = args[0]

    if decoder_name == "raw" and args == ():
        args = mode

    im = new(mode, size)
    im.fromstring(data, decoder_name, args)
    return im

def open(fp, mode="r"):
    "Open an image file, without loading the raster data"

    if mode != "r":
        raise ValueError, "bad mode"

    if isStringType(fp):
        import __builtin__
        filename = fp
        fp = __builtin__.open(fp, "rb")
    else:
        filename = ""

    prefix = fp.read(16)

    preinit()

    for i in ID:
        try:
            factory, accept = OPEN[i]
            if not accept or accept(prefix):
                fp.seek(0)
                return factory(fp, filename)
        except (SyntaxError, IndexError, TypeError):
            pass

    init()

    for i in ID:
        try:
            factory, accept = OPEN[i]
            if not accept or accept(prefix):
                fp.seek(0)
                return factory(fp, filename)
        except (SyntaxError, IndexError, TypeError):
            pass

    raise IOError, "cannot identify image file"

#
# Image processing.

def blend(im1, im2, alpha):
    "Interpolate between images."

    if alpha <= 0.0:
        return im1
    elif alpha >= 1.0:
        return im2
    im1.load()
    im2.load()
    return im1._new(core.blend(im1.im, im2.im, alpha))

def composite(image1, image2, mask):
    "Create composite image by blending images using a transparency mask"

    image = image2.copy()
    image.paste(image1, None, mask)
    return image

def eval(image, *args):
    "Evaluate image expression"

    return image.point(args[0])

def merge(mode, bands):
    "Merge a set of single band images into a new multiband image."

    if getmodebands(mode) != len(bands) or "*" in mode:
        raise ValueError, "wrong number of bands"
    for im in bands[1:]:
        if im.mode != getmodetype(mode):
            raise ValueError, "mode mismatch"
        if im.size != bands[0].size:
            raise ValueError, "size mismatch"
    im = core.new(mode, bands[0].size)
    for i in range(getmodebands(mode)):
        bands[i].load()
        im.putband(bands[i].im, i)
    return bands[0]._new(im)

# --------------------------------------------------------------------
# Plugin registry

def register_open(id, factory, accept=None):
    id = string.upper(id)
    ID.append(id)
    OPEN[id] = factory, accept

def register_mime(id, mimetype):
    MIME[string.upper(id)] = mimetype

def register_save(id, driver):
    SAVE[string.upper(id)] = driver

def register_extension(id, extension):
    EXTENSION[string.lower(extension)] = string.upper(id)


# --------------------------------------------------------------------
# Unix display support

def _showxv(self, title=None, command=None):

    if os.name == "nt":
        format = "BMP"
        if not command:
            command = "start"
    else:
        format = None
        if not command:
            command = "xv"
            if title:
                command = command + " -name \"%s\"" % title

    base = getmodebase(self.mode)
    if base != self.mode and self.mode != "1":
        file = self.convert(base)._dump(format=format)
    else:
        file = self._dump(format=format)

    if os.name == "nt":
        os.system("%s %s" % (command, file))
        # FIXME: leaves temporary files around...
    else:
        os.system("(%s %s; rm -f %s)&" % (command, file, file))
