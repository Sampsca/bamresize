# BAM Resizer
Resizes (and performs other operations on) Infinity Engine BAM V1 files.

This nifty little tool was developed to try and facilitate the porting of PST avatars to BG2. The problem was that all the Planescape avatars were larger than those in Baldur's Gate 2 by a 4:3 ratio. The author's name is unknown, but we appreciate his efforts.

## Usage
```
bamresize v2.9
Code contributions by Avenger_teambg and Sam.

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
 '-u VALUE'
 '--unify VALUE'
    Pad frames before resize to make dimensions and offsets uniform.
    This eliminates frame 'twitching' when resized.
    For VALUE, 0 is OFF, 1 is ON, and 2 is square.  Default is 1.
 '-t VALUE'
 '--trim VALUE'
    Trim transparent padding from frame after resize. (Opposite of --unify)
    For VALUE, 0 is OFF and 1 is ON.  Default is 1.
 '-e FORMAT'
 '--export FORMAT'
    Export frames in the basic format indicated by FORMAT.
    Examples include "bmp", "png", and "gif".  Default is do not export.
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
```
See <[src\usage.txt](src/usage.txt)> for extended usage and examples.
