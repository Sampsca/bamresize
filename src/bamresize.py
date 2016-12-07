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

# ===========================================================================

versionStr = "bamresize v2.6"

uStr = \
"""Code contributions by Avenger_teambg and Sam.

bamresize [OPTIONS] filename.bam [filename2.bam...]
Resizes all frames in filename.bam, creating a new file called filenamer.bam.
The filename(s) to convert can use wildcards.

Options:
 '-p PERCENT'
 '--percentw PERCENT'
    Frame widths are resized by PERCENT percent.
    Default is 75
 '-q PERCENT'
 '--percenth PERCENT'
    Frame heights are resized by PERCENT percent.
    Default is the value for -p (if specified), otherwise it is 75
 '-x NUMBER'
 '--modxoffset NUMBER'
    Modify (either increment or decrement) x offsets by NUMBER.
    Default is 0
 '-y NUMBER'
 '--modyoffset NUMBER'
    Modify (either increment or decrement) y offsets by NUMBER.
    Default is 0
 '-s NUMBER'
 '--setxoffset NUMBER'
    Set x offsets to NUMBER.
    Default is NONE
 '-v NUMBER'
 '--setyoffset NUMBER'
    Set y offsets to NUMBER.
    Default is NONE
 '-u'
 '--unify'
    Pad frames before resize to make dimensions and offsets uniform.
    This eliminates frame 'twitching' when resized.
 '-t'
 '--trim'
    Trim transparent padding from frame after resize. (opposite of --unify)
 '-h'
 '--help'
    Print this message.

Examples:
bamresize MNO3A1.bam
 Resizes all the frames in MNO3A1.bam by 75% and creates MNO3A1r.bam

bamresize -p 50 -q 150 c:\extractedBams\*.bam
 Resizes all frame widths by 50% and all frame heights by 150% for all .bam
 files in the \extractedBams dir.

bamresize -p 100 -s -10 -y 15 ABATG1.bam
 Sets all x offsets to -10 and increments all y offsets by 15 without resizing 
 frames.
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
    printUsage (versionStr, uStr, false)

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
	s = "\nStats:\n"
	s += "# of frames: %d\n" % self.nFrames
	s += "# of cycles: %d\n" % self.nCycles
	s += "Compressed color index:    %d\n" % self.compressedColorIndex
	s += "Frame entries offset:      %d\n" % self.frameEntriesOffset
	s += "Cycle entries offset:      %d\n" % self.cycleEntriesOffset
	s += "Palette offset:            %d\n" % self.paletteOffset
	s += "Frame Lookup Table offset: %d\n" % self.frameLookupOffset
	return s
	
    def getFrameEntry (self, entryIndex):
	self.seek (self.frameEntriesOffset + \
		   (entryIndex * self.frameEntryStructLen))
	width = self.getShort()
	height = self.getShort()
	centerX = self.getShort()
	if centerX > 32767:
		centerX = centerX-65536
	centerY = self.getShort()
	if centerY > 32767:
		centerY = centerY-65536
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

    def resizeFrame (self, i, percentw, percenth, PILPalette,
                     width, height, data, centerX, centerY, modxoffset, modyoffset, setxoffset, setyoffset, unify, trim, debug):
        if width > 0 and height > 0:
            im = Image.fromstring("P", (width, height), data)
            im.putpalette(PILPalette)
            width = width * percentw / 100
            height = height * percenth / 100
            if width < 1:
                width = 1
            if height < 1:
                height = 1
            im2 = im.resize ((width, height))
            data = im2.tostring()
            centerX = centerX * percentw / 100
            centerY = centerY * percenth / 100
            if trim == 1:
                width, height, data, centerX, centerY, top, right, bottom, left = self.trimFrame(width, height, data, centerX, centerY, self.compressedColorIndex)
                self.trimDATA.append (list([i, width, left, right, height, top, bottom, centerX, centerY]))
            if setxoffset != "nan":
                centerX = setxoffset
            if setyoffset != "nan":
                centerY = setyoffset
            centerX += modxoffset
            centerY += modyoffset
        else:
            if trim ==1:
                self.trimDATA.append (list([i, width, 0, 0, height, 0, 0, centerX, centerY]))
        return width, height, data, centerX, centerY
    
    def resizeFrames (self, percentw, percenth, modxoffset, modyoffset, setxoffset, setyoffset, unify, trim, debug):
	self.trimDATA = []
	if unify == 1:
	    self.unify()
	    if debug:
	        self.dumpUnify()
	PILPalette = self.getPILPalette()
	self.getFrames()
	for i in range (self.nFrames):
	    width, height, data, centerX, centerY, isRLE = self.frames[i]
	    width, height, data, centerX, centerY = \
		   self.resizeFrame (i, percentw, percenth, PILPalette,
				     width, height, data, centerX, centerY, modxoffset, modyoffset, setxoffset, setyoffset, unify, trim, debug)
	    self.frames[i] = [width, height, data, centerX, centerY, isRLE]
	if debug:
	    if trim:
			self.dumpTrim()
	    self.dumpResizedFrames()
	
    def unify (self):
	self.unify = []
	temp = []
	MaxXCoord = 0
	MaxYCoord = 0
	self.getFrames()
	for i in range (self.nFrames):
	    width, height, data, centerX, centerY, isRLE = self.frames[i]
	    if centerX > MaxXCoord:
	        MaxXCoord = centerX
	    if centerY > MaxYCoord:
	        MaxYCoord = centerY
	MaxWidth = 0
	MaxHeight = 0
	for i in range (self.nFrames):
	    InsertLeft = 0
	    InsertTop = 0
	    width, height, data, centerX, centerY, isRLE = self.frames[i]
	    if width < 1 or height < 1:
	        temp.append (list([InsertLeft, InsertTop]))
	        continue
	    InsertLeft = MaxXCoord - centerX
	    InsertTop = MaxYCoord - centerY
	    data = self.insertRC(data, self.compressedColorIndex, InsertTop, 0, InsertLeft, 0, width, height)
	    width = width + InsertLeft
	    height = height + InsertTop
	    if width > MaxWidth:
	        MaxWidth = width
	    if height > MaxHeight:
	        MaxHeight = height
	    temp.append (list([InsertLeft, InsertTop]))
	    self.frames[i] = [width, height, data, centerX, centerY, isRLE]
	for i in range (self.nFrames):
	    InsertRight = 0
	    InsertBottom = 0
	    width, height, data, centerX, centerY, isRLE = self.frames[i]
	    if width < 1 or height < 1:
	    	InsertLeft, InsertTop = temp[i]
	    	self.unify.append (list([i, width, InsertLeft, InsertRight, height, InsertTop, InsertBottom, centerX, centerY]))
	    	continue
	    InsertRight = MaxWidth - width
	    InsertBottom = MaxHeight - height
	    data = self.insertRC(data, self.compressedColorIndex, 0, InsertBottom, 0, InsertRight, width, height)
	    width = MaxWidth
	    height = MaxHeight
	    centerX = MaxXCoord
	    centerY = MaxYCoord
	    self.frames[i] = [width, height, data, centerX, centerY, isRLE]
	    InsertLeft, InsertTop = temp[i]
	    self.unify.append (list([i, width, InsertLeft, InsertRight, height, InsertTop, InsertBottom, centerX, centerY]))
	
    def insertRC (self, data, compressedColorIndex, top, bottom, left, right, width, height):
	sbuf = cStringIO.StringIO()
	compressedChar = chr(compressedColorIndex)
	if top > 0:
		insertCount = width * top
		while insertCount > 0:
			sbuf.write(compressedChar)
			insertCount -= 1
		height += top
		sbuf.write(data)
		data = sbuf.getvalue()
		sbuf = cStringIO.StringIO()
	if bottom > 0:
		sbuf.write(data)
		insertCount = width * bottom
		while insertCount > 0:
			sbuf.write(compressedChar)
			insertCount -= 1
		height += bottom
		data = sbuf.getvalue()
		sbuf = cStringIO.StringIO()
	if left > 0:
		insertCount = left
		insertRow = 0
		insertIndex = 1
		for char in data:
			if insertIndex == insertRow * width + 1:
				while insertCount > 0:
					sbuf.write(compressedChar)
					insertCount -= 1
				insertCount = left
				insertRow += 1
			sbuf.write(char)
			insertIndex += 1
		data = sbuf.getvalue()
		sbuf = cStringIO.StringIO()
	if right > 0:
		insertCount = right
		insertRow = 1
		insertIndex = 1
		for char in data:
			sbuf.write(char)
			if insertIndex == insertRow * width:
				while insertCount > 0:
					sbuf.write(compressedChar)
					insertCount -= 1
				insertCount = right
				insertRow += 1
			insertIndex += 1
		data = sbuf.getvalue()
		sbuf = cStringIO.StringIO()
	return data

    def trimFrame (self, width, height, data, centerX, centerY, compressedColorIndex):
	compressedChar = chr(compressedColorIndex)
	PILPalette = self.getPILPalette()
	temp = 0
	# Top
	top = height
	width, height, data, centerX, centerY = self.trim(width, height, data, centerX, centerY, compressedChar)
	top -= height
	# Right
	im = Image.fromstring("P", (width, height), data)
	im.putpalette(PILPalette)
	im2 = im.transpose (2)
	data = im2.tostring()
	right = width
	height, width, data, temp, temp = self.trim(height, width, data, centerX, centerY, compressedChar)
	right -= width
	# Bottom
	im = Image.fromstring("P", (height, width), data)
	im.putpalette(PILPalette)
	im2 = im.transpose (2)
	data = im2.tostring()
	bottom = height
	width, height, data, temp, temp = self.trim(width, height, data, centerX, centerY, compressedChar)
	bottom -= height
	#Left
	im = Image.fromstring("P", (width, height), data)
	im.putpalette(PILPalette)
	im2 = im.transpose (2)
	data = im2.tostring()
	left = width
	height, width, data, centerY, centerX = self.trim(height, width, data, centerY, centerX, compressedChar)
	left -= width
	# Back to Top
	im = Image.fromstring("P", (height, width), data)
	im.putpalette(PILPalette)
	im2 = im.transpose (2)
	data = im2.tostring()
	#print len(data)
	return width, height, data, centerX, centerY, top, right, bottom, left
	
    def trim (self, width, height, data, centerX, centerY, compressedChar):
	# Trim from what is now the Top:
	sbuf = cStringIO.StringIO()
	sbufRow = cStringIO.StringIO()
	transCount = 0
	trimIndex = 0
	trimSkip = 0
	for char in data:
		if trimSkip == 1:
			sbuf.write(char)
			continue
		if char == compressedChar:
			transCount += 1
		sbufRow.write(char)
		trimIndex += 1
		if trimIndex == width:
			if transCount == width:
				height -= 1
				centerY -= 1
				sbufRow = cStringIO.StringIO()
			else:
				trimSkip = 1
				sbuf.write(sbufRow.getvalue())
			transCount = 0
			trimIndex = 0
	data = sbuf.getvalue()
	if len(data) < 1:
		sbuf = cStringIO.StringIO()
		sbuf.write(compressedChar)
		data = sbuf.getvalue()
		width = 1
		height = 1
		centerY = 0
	return width, height, data, centerX, centerY
	
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
	print "%6s %4s %11s  (%5s, %6s) , (%7s, %7s)" % ("Frame#", "RLE", "FrameOffset", "Width", "Height", "CenterX", "CenterY")
	for i in range (self.nFrames):
		width, height, centerX, centerY, frameOffset, isRLE = self.getFrameEntry(i)
		rleStr = "No"
		if isRLE:
			rleStr = "Yes"
		print "%04d %6s %11d    (%3d, %3d)    ,     (%3d, %3d)" % (i, rleStr, frameOffset, width, height, centerX, centerY)
	print ""

    def dumpResizedFrames (self):
	print "Resized Frames:"
	print "%6s %4s  (%5s, %6s) , (%7s, %7s)" % ("Frame#", "RLE", "Width", "Height", "CenterX", "CenterY")
	self.getFrames()
	for i in range (self.nFrames):
		width, height, data, centerX, centerY, isRLE = self.frames[i]
		rleStr = "No"
		if isRLE:
			rleStr = "Yes"
		print "%04d %6s    (%3d, %3d)    ,     (%3d, %3d)" % (i, rleStr, width, height, centerX, centerY)
	print ""
	
    def dumpCycles (self):
	lookupSize = self.calcFrameLookupSize()
	print "Cycles: %d (%d lookup entries)" % (self.nCycles, lookupSize)
	print "%s %15s" % ("Cycle#", "FramesInCycle")
	i = 0
	for cycle in self.cycles:
	    print "%03d      %s" % (i, cycle)
	    i += 1
	print ""
	    
    def dumpPalette (self):
	print "Palette:"
	palette = self.getPalette()
	for entry in palette:
	    print " ", entry
	print ""
	
    def dumpUnify (self):
	print "Unify:"
	print "%s, %s, %s, %s, %s, %s, %s, %s, %s" % ("Frame#", "Width", "InsLeft", "InsRight", "Height", "InsTop", "InsBottom", "CenterX", "CenterY")
	for i in range (self.nFrames):
		i, width, InsertLeft, InsertRight, height, InsertTop, InsertBottom, centerX, centerY = self.unify[i]
		print "   %03d, %5d, %7d, %8d, %6d, %6d, %9d, %7d, %7d" % (i, width, InsertLeft, InsertRight, height, InsertTop, InsertBottom, centerX, centerY)
	print ""
	
    def dumpTrim (self):
	print "Trim:"
	print "%s, %s, %s, %s, %s, %s, %s, %s, %s" % ("Frame#", "Width", "TrmLeft", "TrmRight", "Height", "TrmTop", "TrmBottom", "CenterX", "CenterY")
	for i in range (self.nFrames):
		i, width, left, right, height, top, bottom, centerX, centerY = self.trimDATA[i]
		print "   %03d, %5d, %7d, %8d, %6d, %6d, %9d, %7d, %7d" % (i, width, left, right, height, top, bottom, centerX, centerY)
	print ""

# ===========================================================================

baseDir = "C:\\Games\\BGII - SoA\\ExtractedBifs\\BAMs"

def main ():
    #filename = "MNO3A1.bam"
    #filename = os.path.join(baseDir, filename)

    percentw = 75
    percenth = 0
    modxoffset = 0
    modyoffset = 0
    setxoffset = 'nan'
    setyoffset = 'nan'
    unify = 0
    trim = 0
    debug = 0
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
				   "hp:q:x:y:s:v:utd",
				   ["help", "percentw=", "percenth=", "modxoffset", "modyoffset", "setxoffset", "setyoffset", "unify", "trim", "debug"]
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
        if o in ("-p", "--percentw"):
            percentw = int(a)
        if percenth == 0:
            percenth = int(a)
        if o in ("-q", "--percenth"):
            percenth = int(a)
        if o in ("-x", "--modxoffset"):
            modxoffset = int(a)
        if o in ("-y", "--modyoffset"):
            modyoffset = int(a)
        if o in ("-s", "--setxoffset"):
            setxoffset = int(a)
        if o in ("-v", "--setyoffset"):
            setyoffset = int(a)
        if o in ("-u", "--unify"):
            unify = 1
        if o in ("-t", "--trim"):
            trim = 1
        if o in ("-d", "--debug"):
            debug = 1
    if percenth == 0:
	percenth = 75
    #print percentw
    #print percenth


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
		if debug:
			print bFile
			bFile.dumpFrames()
			bFile.dumpCycles()
			bFile.dumpPalette()
		bFile.resizeFrames (percentw, percenth, modxoffset, modyoffset, setxoffset, setyoffset, unify, trim, debug)
		path, ext = os.path.splitext(filename)
		outputFilename = path + "r" + ext
		data = bFile.getData()
		f = open(outputFilename, "wb")
		f.write(data)
		f.close()
	

    
if __name__ == "__main__":
    startT = time.clock()
    main()
    print "Elapsed time: %.1f seconds"  % (time.clock()-startT)
