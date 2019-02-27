#!/usr/bin/env python

import scan_bv, plot_scan
import ROOT as r

def main():
    options, _ = scan_bv.opts(multi_target=True)
    for iRbx in range(1, 14):
        for iRm in range(1, 5):
            target = "HB%d-%d" % (iRbx, iRm)
            p = scan_bv.scanner(options, [target])
            plot_scan.main("%s.pickle" % target)


if __name__ == "__main__":
    r.gROOT.SetBatch(True)
    r.gErrorIgnoreLevel = r.kError
    main()
