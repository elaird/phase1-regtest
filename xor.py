#!/usr/bin/env python2

import ROOT as r
import sys


def pairs(filename):
    out = {}
    f = open(filename)
    for iLine, line in enumerate(f):
        if not iLine:
            continue
        
        if "blockNo:" in line:
            blockLine = line

        if "bypass_reg" in line:
            regLine = line

        if "bypass_act" in line:
            blockNo = blockLine.split()[-1]
            regBits = regLine.split()[-1]
            actBits =    line.split()[-1]

            blockNo = int(blockNo)
            regBits = int(regBits, 16)
            actBits = int(actBits, 16)
            out[blockNo] = (regBits, actBits)
    f.close()
    return out


def nBits(number, maxBits):
    out = 0
    for iBit in range(maxBits):
        out += (number >> iBit) & 0x1
    return out


def fill_location(h, number, maxBits):
    for iBit in range(maxBits):
        if (number >> iBit) & 0x1:
            h.Fill(iBit)


def main(filename):
    nBitsMax = 128
    hMis = r.TH1D("nMismatch", ";# bits mismatched;# blocks", nBitsMax, 0.5, nBitsMax + 0.5)
    hDelta = r.TH1D("deltaBlocks", ";# blocks since previous mismatch;entries", 100, 0.0, 5.e3)
    hLocAll = r.TH1D("iLocAll", ";bit number;# blocks", nBitsMax, -0.5, nBitsMax - 0.5)
    hLocs = []
    for i in range(1, 1 + nBitsMax):
        hLocs.append(r.TH1D("iLoc%d" % i, "blocks with exactly %d mismatched bit%s;bit number;# mismatches" % (i, "s" if 1 < i else ""),
                            nBitsMax, -0.5, nBitsMax - 0.5))

    d = pairs(filename)
    header = "   block      delta   regBits^actBits (zero-ing LSB)"
    print header
    print "-" * 56
    blocks = sorted(d.keys())
    for iEntry, blockNo in enumerate(blocks):
        if iEntry:
            delta = blockNo - blocks[iEntry - 1]
            hDelta.Fill(delta)
        else:
            delta = None

        regBits, actBits = d[blockNo]
        xor = regBits ^ actBits
        # ignore LSB
        xor >>= 1
        xor <<= 1

        print "   ".join(["%8d" % blockNo,
                          " " * 8 if delta is None else "%8d" % delta,
                          "0x%032x" % xor,
                      ])

        nMismatch = nBits(xor, nBitsMax)
        hMis.Fill(nMismatch)
        fill_location(hLocAll, xor, nBitsMax)
        for i in range(1, 1 + nBitsMax):
            if nMismatch == i:
                fill_location(hLocs[i-1], xor, nBitsMax)

    pdf = "%s.pdf" % filename
    can = r.TCanvas()
    can.SetTickx()
    can.SetTicky()
    can.SetLogy()
    can.Print(pdf + "[")

    hDelta.Draw()
    can.Print(pdf)

    hMis.Draw()
    can.Print(pdf)

    hLocAll.Draw()
    can.Print(pdf)

    for h in hLocs:
        if not h.GetEntries():
            continue
        h.Draw()
        can.Print(pdf)

    can.Print(pdf + "]")    


if __name__ == "__main__":
    r.gROOT.SetBatch(True)
    r.gStyle.SetOptStat("ourme")
    r.gErrorIgnoreLevel = r.kWarning
    if len(sys.argv) < 2:
        sys.exit("Provide a file name as an argument.")
    main(filename=sys.argv[1])
