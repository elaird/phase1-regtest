#!/usr/bin/env python

import scan_bv

def main():
    options, _ = scan_bv.opts(multi_target=True)
    for iRbx in range(1, 14):
        for iRm in range(1, 5):
            target = "HB%d-%d" % (iRbx, iRm)
            p = scan_bv.scanner(options, [target])


if __name__ == "__main__":
    main()
