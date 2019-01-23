#!/usr/bin/env python2

import optparse, pickle, sys


def list_of_pairs(filename):
    out = []
    with open(filename) as f:
        try:
            for key, results in sorted(pickle.load(f).items()):
                for iResult, result in enumerate(results):
                    if result is None:
                        continue
                    out.append((key, iResult, pairs(result[1])))
        except KeyError:
            return [pairs(f.read())]
    return out


def pairs(lines):
    lines = lines.split("\n")

    out = {}
    for iLine, line in enumerate(lines):
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

            xor = regBits ^ actBits
            # ignore LSB
            xor >>= 1
            xor <<= 1
            out[blockNo] = (regBits, actBits, xor)
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


def one(t, nBitsMax):
    import ROOT as r
    r.gROOT.SetBatch(True)
    r.gStyle.SetOptStat("ourme")
    r.gErrorIgnoreLevel = r.kWarning

    hMis = r.TH1D("nMismatch", ";# bits mismatched;# blocks", nBitsMax, 0.5, nBitsMax + 0.5)
    hDelta = r.TH1D("deltaBlocks", ";# blocks since previous mismatch;entries", 100, 0.0, 5.e3)
    hLocAll = r.TH1D("iLocAll", ";bit number;# blocks", nBitsMax, -0.5, nBitsMax - 0.5)
    hLocs = []
    for i in range(1, 1 + nBitsMax):
        hLocs.append(r.TH1D("iLoc%d" % i, "blocks with exactly %d mismatched bit%s;bit number;# mismatches" % (i, "s" if 1 < i else ""),
                            nBitsMax, -0.5, nBitsMax - 0.5))

    header = "   block      delta   regBits^actBits (zero-ing LSB)"
    print header
    print "-" * 56

    target, _, d = t
    blocks = sorted(d.keys())
    for iEntry, blockNo in enumerate(blocks):
        if iEntry:
            delta = blockNo - blocks[iEntry - 1]
            hDelta.Fill(delta)
        else:
            delta = None

        regBits, actBits, xor = d[blockNo]

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

    pdf = "%s.pdf" % target
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


def multi(lst, nBitsMax):
    header1 = "|                                              |        *median values*        |"
    header2 = "|  target        iter   N    block1    blockN  |     block     delta  nBitsXor |"
    topbar = "+%s+" % ("-" * (len(header1) - 2))
    bar = topbar.replace("+", "|")
    print topbar
    print header1
    print header2
    print bar

    for (key, iteration, d) in lst:
        blocks = sorted(d.keys())
        if not blocks:
            continue
        iBlockMin = min(blocks)
        iBlockMax = max(blocks)
        iBlockMed = blocks[len(blocks) / 2]

        deltas = []
        nMismatched = []
        for iEntry, blockNo in enumerate(blocks):
            if iEntry:
                deltas.append(blockNo - blocks[iEntry - 1])
            regBits, actBits, xor = d[blockNo]
            nMismatched.append(nBits(xor, nBitsMax))

        deltas.sort()
        nMismatched.sort()
        print "  ".join(["| %13s" % key,
                         " %2d" % iteration,
                         " %2d" % len(blocks),
                         "%8d" % iBlockMin,
                         "%8d" % iBlockMax,
                         "|",
                         "%8d" % iBlockMed,
                         ("%8d" % deltas[len(deltas) / 2]) if deltas else " " * 8,
                         "%5d  " % nMismatched[len(deltas) / 2],
                         "|",
                         ])
    print(topbar)


def opts():
    parser = optparse.OptionParser("usage: %prog FILE ")
    parser.add_option("--plots",
                      dest="plots",
                      default=False,
                      action="store_true",
                      help="make some plots")
    parser.add_option("--n-bits-max",
                      dest="nBitsMax",
                      default=128,
                      type="int",
                      help="number of bits to consider per block [default %default]")
    options, args = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        sys.exit(" ")

    return options, args[0]


def main(options, filename):
    lst = list_of_pairs(filename)
    if len(lst) == 1 and options.plots:
        one(lst[0], options.nBitsMax)
    else:
        multi(lst, options.nBitsMax)


if __name__ == "__main__":
    main(*opts())
