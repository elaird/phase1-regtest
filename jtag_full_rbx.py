#!/usr/bin/env python2

import collections, datetime, pickle, os
import jtag, printer


def targets(rbx, options):
    out = []
    lst = []
    for iRm in range(1, 5):
        for iCard in range(1, 5):
            lst.append((iRm, iCard))
    if options.reverse:
        lst.reverse()

    for iRm, iCard in lst:
            if rbx.startswith("HE"):
                out.append("%d-%d" % (iRm, iCard))
            if rbx.startswith("HB"):
                out.append("%d-%d-iTop" % (iRm, iCard))
                out.append("%d-%d-iBot" % (iRm, iCard))
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
    for fpga in targets(rbx, options):
        target = "%s-%s" % (rbx, fpga)
        options.logfile = "%s.log" % target
        try:
            out[target] += one(target, options)
        except KeyboardInterrupt:
            break

    return out


def pickled(rbx):
    return "%s.pickle" % rbx


def record(rbx, options):
    filename = pickled(rbx)
    if os.path.exists(filename):
        backup = "%s.moved.on.%s" % (filename, datetime.datetime.today().strftime("%Y-%m-%d-%H:%M:%S"))
        os.rename(filename, backup)

    with open(filename, "w") as f:
        pickle.dump(results(rbx, options), f)
    print("Wrote results to %s" % filename)


def report(rbx, options):
    filename = pickled(rbx)
    with open(filename, "r") as f:
        res = pickle.load(f)

    print("-" * 51)
    for key, codes in sorted(res.items()):
        print("%15s: %2d success(es) out of %2d attempts" % (key, codes.count(None), len(codes)))
    if options.bypassTest and any(res.values()):
        print("\nFor more information about the bypass test failures, run\n./xor.py %s" % filename)


def main():
    options, rbx = jtag.opts(full_rbx=True)
    if options.nIterations:
        record(rbx, options)
    report(rbx, options)


if __name__ == "__main__":
    main()
