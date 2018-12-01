#!/usr/bin/env python2

import collections
import jtag, printer


def targets(rbx):
    out = []
    if not rbx.startswith("HE"):
        return out

    out = []
    for iRm in range(1, 5):
        for iCard in range(1, 5):
            out.append("%d-%d" % (iRm, iCard))
    # out += ["neigh", "calib", "pulser"]
    return out


def one(target, options):
    out = []
    for i in range(options.nIterations):
        try:
            jtag.programmer(options, target)
            out.append(None)
        except RuntimeError as e:
            printer.red(e[1])
            out.append(e)
    return out


def results(rbx, options):
    out = collections.defaultdict(list)
    for fpga in targets(rbx):
        target = "%s-%s" % (rbx, fpga)
        options.logfile = "%s.log" % target
        try:
            out[target] += one(target, options)
        except KeyboardInterrupt:
            break

    return out


def main():
    options, rbx = jtag.opts(full_rbx=True)
    res = results(rbx, options).items()
    if not res:
        return

    if options.bypassTest:  # FIXME
        print("\n" * 2)
        print("-" * 51)
        for key, codes in sorted(res):
            print("%15s: %2d success(es) out of %2d attempts" % (key, codes.count(None), len(codes)))
    else:
        print("\n" * 2)
        print("-" * 51)
        for key, codes in sorted(res):
            print("%15s: %2d success(es) out of %2d attempts" % (key, codes.count(None), len(codes)))


if __name__ == "__main__":
    main()
