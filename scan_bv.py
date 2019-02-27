#!/usr/bin/env python

import driver
import datetime, optparse, os, pickle, sys, time
from commission import sector


def check_target(target):
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

    return target, rbx


def opts():
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
                      default=60,
                      type="int",
                      help="maximum BV setting (V) [default %default]")
    parser.add_option("--step",
                      dest="bvStep",
                      default=5,
                      type="int",
                      help="step size (V) [default %default]")

    options, args = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        sys.exit(" ")

    return options, args[0]


class scanner(driver.driver):
    def __init__(self, options, target):
        self.target, self.rbx = check_target(target)

        self.options = options
        self.options.logfile = self.target + ".log"

        self.hb = self.rbx.startswith("HB")
        self.he = self.rbx.startswith("HE")

        if len(self.rbx) <= 2:
            sys.exit("The RBX must contain at least three characters.")
        else:
            self.end = self.rbx[2]

        self.assign_sector_host_port()

        self.connect()

        self.pickle(self.bv_scan())

        self.disconnect()


    def assign_sector_host_port(self):
        host = "localhost"
        port = 64000

        if self.hb:
            if self.end in "MP":
                self.sector = sector(self.rbx)
            else:  # assume 904
                self.sector = sector(self.rbx, True)
                host = "hcal904daq04"
                port = 64400 if self.sector else 64000
        elif self.he:
            if self.end in "MP":
                host = "hcalngccm02"
                self.sector = sector(self.rbx)
            else:  # assume 904
                self.sector = sector(self.rbx, True)
                host = "hcal904daq04"
        elif self.hf:
            self.sector = sector(self.rbx)
            host = "hcalngccm01"
            port = 63000

        # driver.connect assumes these are included as options
        self.options.host = host
        self.options.port = port


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
        filename = "%s.pickle" % self.target
        if os.path.exists(filename):
            backup = "%s.moved.on.%s" % (filename, datetime.datetime.today().strftime("%Y-%m-%d-%H:%M:%S"))
            os.rename(filename, backup)

        with open(filename, "w") as f:
            pickle.dump(d, f)
        print("Wrote results to %s" % filename)


if __name__ == "__main__":
    p = scanner(*opts())
