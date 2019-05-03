#!/usr/bin/env python

import driver
import datetime, optparse, os, pickle, sys, time


def opts(multi_target=False):
    parser = optparse.OptionParser(usage="usage: %prog [options] RBX-RM")
    parser.add_option("--nseconds",
                      dest="nSeconds",
                      default=1,
                      type="int",
                      help="number of seconds to wait at each setting [default %default]")
    parser.add_option("--minimum",
                      dest="bvMin",
                      default=0,
                      type="int",
                      help="minimum BV setting (V) [default %default]")
    parser.add_option("--maximum",
                      dest="bvMax",
                      default=70,
                      type="int",
                      help="maximum BV setting (V) [default %default]")
    parser.add_option("--step",
                      dest="bvStep",
                      default=1,
                      type="int",
                      help="step size (V) [default %default]")
    parser.add_option("--default-server",
                      dest="defaultServer",
                      default=False,
                      action="store_true",
                      help="connect to default server in driver.py")

    options, args = parser.parse_args()

    if len(args) != 1 and not multi_target:
        parser.print_help()
        sys.exit(" ")

    return options, args


class scanner(driver.driver):
    def __init__(self, options, args):
        self.assign_target(args[0])

        self.options = options
        self.options.logfile = self.target + ".log"

        self.assign_sector_host_port(default=self.options.defaultServer)
        self.connect()
        self.pickle(self.bv_scan())
        self.disconnect()


    def assign_target(self, target):
        coords = target.split("-")
        fail = "Expected RBX-RM.  Found %s" % str(target)

        if len(coords) != 2:
            sys.exit(fail)

        rbx, rm_s = coords

        if not (rbx.startswith("HB") or rbx.startswith("HE")):
            sys.exit("This script only works with HB or HE RBXes.")

        try:
            rm = int(rm_s)
        except ValueError:
            sys.exit("Could not convert '%s' to an int." % rm_s)

        self.target = target
        self.rbx = rbx


    def split_results(self, cmd):
        res = self.command(cmd)
        fields = res.split("#")
        
        if " " in fields[1]:
            res1 = fields[1].split()
        elif type(fields[1]) is not list:
            res1 = [fields[1]]

        if res1 == ["OK"]:
            results = res1
        elif res1[0].strip().startswith("0x"):
            results = [int(x, 16) for x in res1]
        else:
            results = [float(x) for x in res1]
        return fields[0], results


    def bv_scan(self):
        nCh = 48 if self.he else 64

        d = {}
        for v in range(self.options.bvMin, self.options.bvMax + self.options.bvStep, self.options.bvStep):
            if v == 80:
                v = 79.9

            for cmd in ["put %s-biasvoltage[1-%d]_f %d*%f" % (self.target, nCh, nCh, v),
                        "get %s-biasmon[1-%d]_f_rr" % (self.target, nCh),
                        "get %s-LeakageCurrent[1-%d]_f_rr" % (self.target, nCh),
                        ]:
                if "biasmon" in cmd:
                    time.sleep(self.options.nSeconds)
                d[(v, cmd)] = self.split_results(cmd)[1]
        return d


    def pickle(self, d):
        filename = "%s_%s.pickle" % (self.target, datetime.datetime.today().strftime("%Y_%m_%d_%Hh%M"))
        with open(filename, "w") as f:
            pickle.dump(d, f)
        print("Wrote results to %s" % filename)


if __name__ == "__main__":
    p = scanner(*opts())
