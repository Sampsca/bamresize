"""
$Header: c:\\document\\master/Projects/Python/baldur/bamresize.py,v 1.5 2002/05/09 03:26:57 no one Exp $

"""

"""

Requires

1).  ActiveState Python 2.1.x (because that's what the next requirement needs)
http://activestate.com/Products/ActivePython/
http://downloads.activestate.com/ActivePython/windows/2.1/ActivePython-2.1.3-214.msi

2).  Python Imaging Library
http://www.pythonware.com/products/pil/index.htm
Get 'Python Imaging Library 1.1.2 for Python 2.1.1 (Windows only) (321k EXE)'

[Eventually will probably need the 1.1.3 version once a pre-built
binary is available for download, since that has the AntiAlias filter
I should really be using.]

When I installed PIL, it automatically put itself in the c:\py21
directory???

But my version of ActiveState Python 2.1.1 was in c:\python21.

So I moved the following:

contents of py21\dlls to c:\python21\dlls 
py21\PIL to python21\PIL
py21\PIL.pth to python21\PIL.pth

Seems to work okay.

If you get a 'ImportError: No module named Image' error then PIL wasn't
installed correctly.

==========================================================================

General struction of a bam file:

  header
  frame entries
  cycle entries
  palette
  framelookup
  frames

But you can't write any frame entries until you known the size of:
  frame entries
  cycle entries
  palette
  framelookup

because each frame entry has to point to the frame's offset.

------------------------------------------------------------------------

Resizing notes:

Using bamworkshop 1.1.0.7

   0     00000846H ( 89, 100), ( 28,  80)

gets changed to (66, 75) when resize to 75%

"""

import glob
import os
import re
import cStringIO
import struct
import getopt, sys
import time
import zlib
from types import FileType

import Image

#import hexdumper

true = 1
false = 0
debugging = false

# ===========================================================================

versionStr = "Version: $Revision: 1.5 $"

uStr = \
"""python bamresize.py [OPTIONS] filename.bam [filename2.bam...]
Resizes all the frames in filename.bam, creating a new file called flenamer.bam.
The filename(s) to convert can use wildcards.

Options:
 '-p PERCENT'
 '--percent PERCENT'
    Frames are resized by PERCENT percent.
    Default is 75
 '-h'
 '--help'
    Print this message.

examples:
python bamresize.py MNO3A1.bam
 Resizes all the frames in MNO3A1.bam by 75% and creates MNO3A1r.bam
python bamresize.py -p 50 c:\extractedBams\*.bam
 Resizes all frames in all the .bam files in the \extractedBams dir by 50%.
"""

def printUsage(versionStr, usageStr, pauseF=true):
    print versionStr
    if pauseF:
	lines = usageStr.split('\n')
	counter = 0
	for line in lines:
	    print line
	    counter = counter + 1
	    if counter % 20 == 0:
		raw_input ("Press Enter key to continue...")
    else:
	print usageStr

def usage():
    printUsage (versionStr, uStr, true)

# ===========================================================================

class InfinityBaseFile:
    def __init__ (self, filename, data=None, readOnly=true):
	self.filename = filename
	if data is not None:
	    if data:
		self.fileObj = cStringIO.StringIO(data)
	    else:
		self.fileObj = cStringIO.StringIO()
	else:
	    self.fileMode = "r+b"
	    if readOnly:
		self.fileMode = "rb"
	    self.fileObj = open(filename, self.fileMode)
    
    def __del__ (self):
	self.close()

    def setDataBuffer (self, data):
	self.close()
	self.fileObj = cStringIO.StringIO(data)

    def getChars (self, nChars, nullTrim=true):
	buffer = self.fileObj.read(nChars)
	if not buffer:
	    return None
	if nullTrim:
	    nullPos = buffer.find("\x00")
	    if nullPos >= 0:
		buffer = buffer[:nullPos]
	return buffer

    def putChars (self, buffer):
	self.fileObj.write(buffer)
	
    def getByte (self):
	buffer = self.fileObj.read(1)
	if not buffer:
	    return None
	byte = struct.unpack("B", buffer)[0]
	return byte

    def putByte (self, byte):
	buffer = struct.pack("B", byte)
	self.fileObj.write(buffer)
    
    def getShort (self):
	buffer = self.fileObj.read(2)
	if not buffer:
	    return None
	short = struct.unpack("<H", buffer)[0]
	return short

    def putShort (self, short):
	buffer = struct.pack("<H", short)
	self.fileObj.write(buffer)
	
    def getInt (self):
	buffer = self.fileObj.read(2)
	if not buffer:
	    return None
	value = struct.unpack("<h", buffer)[0]
	return value

    def putInt (self, value):
	buffer = struct.pack("<h", value)
	self.fileObj.write(buffer)

    def getLong (self, bigEndian=false):
	buffer = self.fileObj.read(4)
	if not buffer:
	    return None
	if bigEndian:
	    long = struct.unpack(">L", buffer)[0]
	else:
	    long = struct.unpack("<L", buffer)[0]
	return long

    def putLong (self, long):
	buffer = struct.pack("<L", long)
	self.fileObj.write(buffer)

    def seek (self, pos):
	self.fileObj.seek(pos)

    def tell (self):
	return self.fileObj.tell()

    def read (self, size=-1):
	return self.fileObj.read(size)

    def readAll (self):
	self.seek(0)
	data = self.read()
	return data

    def truncate (self, size=None):
	if size is not None:
	    self.fileObj.truncate(size)
	else:
	    self.fileObj.truncate()

    def close (self):
	if self.fileObj:
	    self.fileObj.close()
	    self.fileObj = None

    
class BamFile (InfinityBaseFile):
    """Handles Infinity Engine .bam files"""

    headerStructLen = 24
    frameEntryStructLen = 12
    cycleEntryStructLen = 4
    frameLookupStructLen = 2
    paletteStructLen = 256*4
    
    def __init__ (self, filename, data=None, readOnly=true):
	InfinityBaseFile.__init__(self, filename, data, readOnly)

	self.signature, self.version = self.checkVersion()
	self.originalSignature = self.signature

	if self.signature == "BAMC":
	    uncompressedDataLen = self.getLong()
	    compressedData = self.read(-1)
	    data = zlib.decompress(compressedData)
	    if len(data) != uncompressedDataLen:
		raise IOError, "Error decompressing %s" % filename
		return None
	    self.setDataBuffer (data)
	    self.signature, self.version = self.checkVersion()

	self.nFrames = self.getShort()
	self.nCycles = self.getByte()

	self.compressedColorIndex = self.getByte()
	self.compressedChar = chr(self.compressedColorIndex)
	self.frameEntriesOffset = self.getLong()
	self.cycleEntriesOffset = self.frameEntriesOffset + \
				  (self.nFrames * self.frameEntryStructLen)
	self.paletteOffset = self.getLong()
	self.frameLookupOffset = self.getLong()

	self.frames = None
	self.cycles = None
	self.palette = None
	
    def checkVersion (self):
	signature = self.getChars(4)
	version = self.getChars(4)
	if signature != "BAM " and signature != "BAMC":
	    raise IOError, "%s is not a BAM file" % self.filename
	if version != "V1  ":
	    raise IOError, "Can't handle BAM file version: %s" % version
	return signature, version
    
    def __str__ (self):
	s = "%s\n" % self.filename
	s += "# of frames: %d\n" % self.nFrames
	s += "# of cycles: %d\n" % self.nCycles
	s += "Compressed color index:    %d\n" % self.compressedColorIndex
	s += "Frame entries offset:      %08xH\n" % self.frameEntriesOffset
	s += "Cycle entries offset:      %08xH\n" % self.cycleEntriesOffset
	s += "Palette offset:            %08xH\n" % self.paletteOffset
	s += "Frame Lookup Table offset: %08xH\n" % self.frameLookupOffset
	return s
	
    def getFrameEntry (self, entryIndex):
	self.seek (self.frameEntriesOffset + \
		   (entryIndex * self.frameEntryStructLen))
	width = self.getShort()
	height = self.getShort()
	centerX = self.getShort()
	centerY = self.getShort()
	temp = self.getLong()
	frameOffset = temp & 0x7FFFFFFF
	isRLE =  not (temp & 0x80000000) > 0
	return width, height, centerX, centerY, frameOffset, isRLE

    def getFrame (self, entryIndex):
	width, height, centerX, centerY, frameOffset, isRLE = \
	       self.getFrameEntry(entryIndex)
	nBytes = width * height
	self.seek (frameOffset)
	if isRLE:
	    data = ""
	    lenData = 0
	    seenFlag = false

	    while lenData < nBytes:
		byte = self.getByte()
		if seenFlag:
		    data += self.compressedChar * (byte+1)
		    lenData += byte+1
		    seenFlag = false
		    continue
		if byte != self.compressedColorIndex:
		    data += chr(byte)
		    lenData += 1
		else:
		    seenFlag = true
	    if len(data) != width*height:
		raise IOError, \
		      "RLE error for frame %d: got %d, expected %d" % \
		      (entryIndex, len(data), width*height)
	else:
	    data = self.read(nBytes)

	return width, height, data, centerX, centerY, isRLE
    
    def compressFrame (self, data, compressedColorIndex):
	sbuf = cStringIO.StringIO()

	compressedChar = chr(compressedColorIndex)
	compressedCharCount = 0
	for char in data:
	    if char == compressedChar:
		compressedCharCount += 1
		if compressedCharCount > 255:
		    sbuf.write(compressedChar)
		    sbuf.write(chr(254))
		    compressedCharCount = 1
	    else:
		if compressedCharCount > 0:
		    sbuf.write(compressedChar)
		    sbuf.write(chr(compressedCharCount-1))
		    compressedCharCount = 0
		sbuf.write(char)
	if compressedCharCount > 0:
	    sbuf.write(compressedChar)
	    sbuf.write(chr(compressedCharCount-1))

	buffer = sbuf.getvalue()
	return buffer

    def getFrames (self, reRead=false):
	if self.frames and not reRead:
	    return self.frames

	self.frames = []
	for i in range(self.nFrames):
	    frame = self.getFrame(i)
	    self.frames.append (list(frame))
	return self.frames
    
    def getCycleEntry (self, entryIndex):
	self.seek (self.cycleEntriesOffset + \
		   (entryIndex * self.cycleEntryStructLen))
	nFrames = self.getShort()
	frameLookupTableIndex = self.getShort()
	return nFrames, frameLookupTableIndex

    def getCycle (self, cycleIndex):
	nFrames, frameLookupTableIndex = self.getCycleEntry (cycleIndex)

	self.seek (self.frameLookupOffset + (frameLookupTableIndex * 2))
	cycle = []
	for i in range(nFrames):
	    frameIndex = self.getShort()
	    cycle.append (frameIndex)
	return cycle

    def getCycles (self, reRead=false):
	if self.cycles and not reRead:
	    return self.cycles

	self.cycles = []
	for i in range (self.nCycles):
	    cycle = self.getCycle (i)
	    self.cycles.append (list(cycle))
	return self.cycles

    def calcFrameLookupSize(self):
	self.cycles = self.getCycles()
	lookupSize = 0
	for cycle in self.cycles:
	    start = cycle[0]
	    end = start + len(cycle)
	    if end > lookupSize:
		lookupSize = end
	return lookupSize
    
    def getPalette (self, reRead=false):
	if self.palette and not reRead:
	    return self.palette

	self.seek (self.paletteOffset)
	self.palette = []
	for i in range (256):
	    entry = self.getChars(4, nullTrim=false)
	    self.palette.append( (ord(entry[2]), ord(entry[1]), ord(entry[0]),
				  ord(entry[3])) )
	return self.palette

    def writeUncompressed (self, filename):
	self.seek(0)
	data = self.read(-1)
	f = open(filename, "wb")
	f.write(data)
	f.close()

    def load (self):
	self.frames = self.getFrames()
	self.cycles = self.getCycles()

    def getPILPalette (self):
	palette = self.getPalette()
	PILPalette = []
	for r, g, b, a in palette:
	    PILPalette.append(r)
	    PILPalette.append(g)
	    PILPalette.append(b)
	return PILPalette

    def resizeFrame (self, percent, PILPalette,
                     width, height, data, centerX, centerY):
        im = Image.fromstring("P", (width, height), data)
        im.putpalette(PILPalette)
        if width > 1 and height > 1:
            width = width * percent / 100
            height = height * percent / 100
            im2 = im.resize ((width, height))
            data = im2.tostring()
            centerX = centerX * percent / 100
            centerY = centerY * percent / 100
        return width, height, data, centerX, centerY
    
    def resizeFrames (self, percent):
	PILPalette = self.getPILPalette()
	self.getFrames()
	for i in range (self.nFrames):
	    width, height, data, centerX, centerY, isRLE = self.frames[i]
	    width, height, data, centerX, centerY = \
		   self.resizeFrame (percent, PILPalette,
				     width, height, data, centerX, centerY)
	    self.frames[i] = [width, height, data, centerX, centerY, isRLE]

    def generateFrames (self):
	sbuf = cStringIO.StringIO()

	self.frames = self.getFrames()
	framesInfo = []
	for width, height, data, centerX, centerY, isRLE in self.frames:
	    if isRLE:
		data = self.compressFrame(data, self.compressedColorIndex)
	    sbuf.write(data)
	    framesInfo.append( (width, height, len(data),
			       centerX, centerY, isRLE) )

	buffer = sbuf.getvalue()
	return framesInfo, buffer

    def generateFrameEntries (self, framesOffset, framesInfo):
	ibf = InfinityBaseFile("frameentries", "")

	for width, height, lenData, centerX, centerY, isRLE in framesInfo:
	    ibf.putShort(width)
	    ibf.putShort(height)
	    ibf.putShort(centerX)
	    ibf.putShort(centerY)
	    offset = framesOffset
	    if not isRLE:
		offset = framesOffset | 0x80000000
	    ibf.putLong(offset)
	    
	    framesOffset += lenData
	buffer = ibf.readAll()
	return buffer
	
    def generateCycleData (self):
	cycleEntryIBF = InfinityBaseFile("cycleentry", "")
	frameLookupIBF = InfinityBaseFile("framelookup", "")

	self.cycles = self.getCycles()

	frameCount = 0
	for cycle in self.cycles:
	    cycleEntryIBF.putShort(len(cycle))
	    cycleEntryIBF.putShort(frameCount)
	    frameCount += len(cycle)
	    for frameIndex in cycle:
		frameLookupIBF.putShort(frameIndex)
		
	cycleEntryBuf = cycleEntryIBF.readAll()
	frameLookupBuf = frameLookupIBF.readAll()
	return cycleEntryBuf, frameLookupBuf

    def generatePalette (self):
	paletteIBF = InfinityBaseFile("palette", "")

	if not self.palette:
	    self.palette = self.getPalette()
	    
	for r, g, b, a in self.palette:
	    paletteIBF.putByte(b)
	    paletteIBF.putByte(g)
	    paletteIBF.putByte(r)
	    paletteIBF.putByte(a)
	paletteBuf = paletteIBF.readAll()
	return paletteBuf
	    
    def generateHeader (self, paletteOffset):
	ibf = InfinityBaseFile ("header", "")

	ibf.putChars ("BAM ")
	ibf.putChars ("V1  ")
	ibf.putShort (self.nFrames)
	ibf.putByte (self.nCycles)
	ibf.putByte (self.compressedColorIndex)
	ibf.putLong (self.headerStructLen)
	ibf.putLong (paletteOffset)
	ibf.putLong (paletteOffset + self.paletteStructLen)

	buffer = ibf.readAll()
	return buffer
    
    def generateUncompressed (self):
	sbuf = cStringIO.StringIO()

	cycleEntryBuf, frameLookupBuf = self.generateCycleData ()

	paletteOffset = self.headerStructLen + \
			(self.nFrames * self.frameEntryStructLen) +\
			(self.nCycles * self.cycleEntryStructLen)
	frameLookupOffset = paletteOffset + self.paletteStructLen
	framesOffset = frameLookupOffset + len(frameLookupBuf)

	headerBuf = self.generateHeader (paletteOffset)
	paletteBuf = self.generatePalette()
	framesInfo, framesBuf = self.generateFrames()
	frameEntriesBuf = self.generateFrameEntries (framesOffset, framesInfo)

	sbuf.write(headerBuf)
	sbuf.write(frameEntriesBuf)
	sbuf.write(cycleEntryBuf)
	sbuf.write(paletteBuf)
	sbuf.write(frameLookupBuf)
	sbuf.write(framesBuf)
	
	buffer = sbuf.getvalue()
	return buffer

    def getData (self):
	ibf = InfinityBaseFile("data", "")
	data = self.generateUncompressed ()

	if self.originalSignature == "BAMC":
	    ibf.putChars ("BAMC")
	    ibf.putChars ("V1  ")
	    ibf.putLong (len(data))
	    data = zlib.compress(data)
	ibf.putChars(data)
	buffer = ibf.readAll()
	return buffer
	
    # ---------------------------------------------------------------------
    
    def dumpFrames (self):
	print "Frames:"
	for i in range (self.nFrames):
	    width, height, centerX, centerY, frameOffset, isRLE = \
		   self.getFrameEntry(i)
	    rleStr = ""
	    if isRLE:
		rleStr = "RLE"
	    print "%4d %-3s %08xH (%3d, %3d), (%3d, %3d)" % \
		  (i, rleStr, frameOffset, width, height, centerX, centerY)

    def dumpCycles (self):
	lookupSize = self.calcFrameLookupSize()
	print "Cycles: %d (%d lookup entries)" % (self.nCycles, lookupSize)
	i = 0
	for cycle in self.cycles:
	    print i, cycle
	    i += 1
	    
    def dumpPalette (self):
	print "Palette:"
	palette = self.getPalette()
	for entry in palette:
	    print " ", entry
	    

# ===========================================================================

baseDir = "C:\\Games\\BGII - SoA\\ExtractedBifs\\BAMs"

def main ():
    #filename = "MNO3A1.bam"
    #filename = os.path.join(baseDir, filename)

    percent = 75
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
				   "hp:",
				   ["help", "percent="]
				   )
	
    except getopt.GetoptError, e:
        # print help information and exit:
	print "Illegal option error."
	print e
        sys.exit(2)

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        if o in ("-p", "--percent"):
	    percent = int(a)
	    
    if len(args) < 1:
	usage()
        sys.exit(2)
	
    filenames = []
    for filename in args:
	filenames.extend ( glob.glob(filename) )

    for filename in filenames:
	if not os.path.isfile(filename):
	    print "%s does not exist" % filename
	    sys.exit(2)

    for filename in filenames:
	print "Processing %s ..." % filename
	bFile = BamFile (filename)
	bFile.resizeFrames (percent)

	path, ext = os.path.splitext(filename)
	outputFilename = path + "r" + ext
	data = bFile.getData()
	f = open(outputFilename, "wb")
	f.write(data)
	f.close()
	
    if false:
	print bFile
	bFile.dumpFrames()
	bFile.dumpCycles()
	bFile.dumpPalette()
    
if __name__ == "__main__":
    startT = time.clock()
    main()
    print "Elapsed time: %.1f seconds"  % (time.clock()-startT)
