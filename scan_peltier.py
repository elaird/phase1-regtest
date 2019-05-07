#!/usr/bin/env python

import scan_bv
import optparse, sys, time


def opts():
    parser = optparse.OptionParser(usage="usage: %prog [options] RBX")
    parser.add_option("--nseconds",
                      dest="nSeconds",
                      default=2,
                      type="int",
                      help="number of seconds to wait at each setting [default %default]")
    parser.add_option("--minimum",
                      dest="bvMin",
                      default=0.0,
                      type="float",
                      help="minimum BV setting (V) [default %default]")
    parser.add_option("--maximum",
                      dest="bvMax",
                      default=7.5,
                      type="float",
                      help="maximum BV setting (V) [default %default]")
    parser.add_option("--step",
                      dest="bvStep",
                      default=0.05,
                      type="float",
                      help="step size (V) [default %default]")
    parser.add_option("--reverse",
                      dest="reverse",
                      default=False,
                      action="store_true",
                      help="scan from max down to min")
    parser.add_option("--default-server",
                      dest="defaultServer",
                      default=False,
                      action="store_true",
                      help="connect to default server in driver.py")

    options, args = parser.parse_args()
    options.time_scan = options.bvMin == options.bvMax  # add special mode

    if len(args) != 1:
        parser.print_help()
        sys.exit(" ")

    return options, args


def nRbxes(rbx):
    n = 1
    if "-" in rbx and "[" in rbx and "]" in rbx:
        limits = rbx[1 + rbx.find("["):rbx.find("]")].split("-")
        n += int(limits[1]) - int(limits[0])
    return n


class scanner_peltier(scan_bv.scanner_bv):
    def assign_target(self, rbx):
        if not (rbx.startswith("HB") or rbx.startswith("HE")):
            sys.exit("This script only works with HB or HE RBXes.")
        self.target = rbx
        self.rbx = rbx


    def settings(self):
        if not self.options.bvStep:
            return []

        if self.options.time_scan:
            return [self.options.bvMin] * int(self.options.bvStep)

        out = []
        v = self.options.bvMin
        while (v <= self.options.bvMax):
            out.append(v)
            v += self.options.bvStep
        if self.options.reverse:
            out.reverse()
        return out


    def scan(self):
        rms = "[1-4]"
        nSettings = 4 * nRbxes(self.rbx)

        d = {}

        self.command("put %s-%s-peltier_control %d*0" % (self.rbx, rms, nSettings))

        for iSetting, v in enumerate(self.settings()):
            if self.options.time_scan:
                v = iSetting * self.options.nSeconds

            for cmd in ["put %s-%s-SetPeltierVoltage_f %d*%f" % (self.rbx, rms, nSettings, v),
                        "get %s-%s-rtdtemperature_f_rr" % (self.rbx, rms),
                        "get %s-%s-PeltierCurrent_f_rr" % (self.rbx, rms),
                        "get %s-%s-PeltierVoltage_f_rr" % (self.rbx, rms),
                        ]:
                if "rtd" in cmd:
                    time.sleep(self.options.nSeconds)
                    if iSetting == 0 and not self.options.time_scan:
                        time.sleep(10 * self.options.nSeconds)

                if iSetting and self.options.time_scan and ("SetPeltier" in cmd):
                    continue

                d[(v, cmd)] = self.split_results(cmd)[1]
            v += self.options.bvStep

        self.command("put %s-%s-SetPeltierVoltage_f %d*%f" % (self.rbx, rms, nSettings, 0.0))
        self.command("put %s-%s-peltier_control %d*1" % (self.rbx, rms, nSettings))
        return d


if __name__ == "__main__":
    p = scanner_peltier(*opts())
