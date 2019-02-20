#!/usr/bin/env python2

from __future__ import print_function
import pickle
from commission import commissioner, opts


def occupancies(options, arg):
    out = []
    for iRbx in range(1, 19):
        target = "%s%02d" % (arg, iRbx)
        options.logfile = "survey_links_%s.log" % target
        p = commissioner(options, target).uhtr(check=False)
        out += p
    return out


def main():
    options, arg = opts()
    options.keepgoing = True
    if arg not in ["HEP", "HEM", "HBP", "HBM"]:
        sys.exit(arg)

    filename = "%s.pickle" % arg
    f = open(filename, "w")
    pickle.dump(occupancies(options, arg), f)
    f.close()
    print("Wrote results to", filename)


if __name__ == "__main__":
    main()
