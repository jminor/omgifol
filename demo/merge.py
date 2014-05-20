import sys

from omg import wad

if (len(sys.argv) < 3):
    print "\n    Omgifol script: merge WADs\n"
    print "    Usage:"
    print "    merge.py input1.wad input2.wad ... [-o output.wad]\n"
    print "    Default output is merged.wad"
else:
    w = wad.WAD()
    for a in sys.argv[1:]:
        if a == "-o":
            break
        print "Adding %s..." % a
        w += wad.WAD(a)
    outpath = "merged.wad"
    if "-o" in sys.argv: outpath = sys.argv[-1]
    w.to_file(outpath)
