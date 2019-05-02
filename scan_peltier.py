#!/usr/bin/env python

import scan_bv
import optparse, time


def opts(multi_target=False):
    parser = optparse.OptionParser(usage="usage: %prog [options] RBX-RM")
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

    options, args = parser.parse_args()

    if len(args) != 1 and not multi_target:
        parser.print_help()
        sys.exit(" ")

    return options, args


class scanner_peltier(scan_bv.scanner):
    def bv_scan(self):
        nRm = 4

        d = {}

        self.command("put %s-[1-%d]-peltier_control %d*0" % (self.rbx, nRm, nRm))

        v = self.options.bvMin
        while (v <= self.options.bvMax):
            for cmd in ["put %s-[1-%d]-SetPeltierVoltage_f %d*%f" % (self.rbx, nRm, nRm, v),
                        # "get %s-[1-%d]-PeltierVoltageMon_f_rr" % (self.rbx, nRm),
                        "get %s-[1-%d]-PeltierCurrent_f_rr" % (self.rbx, nRm),
                        "get %s-[1-%d]-PeltierVoltage_f_rr" % (self.rbx, nRm),
                        ]:
                if "SetP" in cmd:
                    time.sleep(self.options.nSeconds)
                    if v == self.options.bvMin:
                        time.sleep(10 * self.options.nSeconds)

                d[(v, cmd)] = self.split_results(cmd)[1]
            v += self.options.bvStep

        self.command("put %s-[1-%d]-SetPeltierVoltage_f %d*%f" % (self.rbx, nRm, nRm, 0.0))
        self.command("put %s-[1-%d]-peltier_control %d*1" % (self.rbx, nRm, nRm))
        return d

if __name__ == "__main__":
    p = scanner_peltier(*opts())
