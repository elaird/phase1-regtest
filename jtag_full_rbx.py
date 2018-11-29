#!/usr/bin/env python2

import collections, subprocess, sys
import jtag


def commandOutputFull(cmd):
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    return {"stdout": stdout, "stderr": stderr, "returncode": p.returncode}


def targets(rbx):
    out = []
    if not rbx.startswith("HE"):
        return out

    out = []
    for iRm in range(1, 5):
        for iCard in range(1, 5):
            out.append("%d-%d" % (iRm, iCard))
    out += ["neigh", "calib", "pulser"]
    return out


def results(rbx, args, nIterations):
    out = collections.defaultdict(list)
    for fpga in targets(rbx):
        target = "%s-%s" % (rbx, fpga)
        cmd = " ".join(["./jtag.py", target, args])
        try:
            for i in range(nIterations):
                print(cmd)
                d = commandOutputFull(cmd)
                out[target].append(d["returncode"])
                print d["stdout"]
        except KeyboardInterrupt:
            break

    return out


def main(options, rbx):
    args = " ".join(sys.argv[1:])
    args = args.replace(rbx, "")

    res = results(rbx, args, options.nIterations).items()
    if not res:
        return

    print "\n" * 2
    print("-" * (4 + len(args)))
    print "| %s |" % args
    print("-" * 51)
    for key, codes in sorted(res):
        print "%15s: %2d success(es) out of %2d attempts" % (key, codes.count(0), len(codes))


if __name__ == "__main__":
    main(*jtag.opts(full_rbx=True))
