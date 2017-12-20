#!/usr/bin/env python2

import ngfec, printer
from powerMon import commandOutputFull
import datetime, optparse, os, sys, time


def sector(rbx, b904=False):
    if not rbx.startswith("HE"):
        sys.exit("This script only works with HE RBXes.")

    if (not b904) and (rbx[2] not in "MP"):
        sys.exit("This script only works with HEP or HEM RBXes.")

    try:
        if b904:
            s = rbx[2:]
        else:
            s = rbx[3:]
        number = int(s)
        return number
    except ValueError:
        sys.exit("RBX number '%s' cannot be converted to an integer." % s)


def opts():
    parser = optparse.OptionParser(usage="usage: %prog [options] RBX")
    parser.add_option("-H",
                      "--host",
                      dest="host",
                      default="hcalngccm02",
                      help="ngccmserver host [default %default]")
    parser.add_option("-p",
                      "--port",
                      dest="port",
                      default=64000,
                      type="int",
                      help="ngccmserver port number [default %default]")
    parser.add_option("--log-file",
                      dest="logfile",
                      default="",
                      help="log file to which to append")
    parser.add_option("--nseconds",
                      dest="nSeconds",
                      default=5,
                      type="int",
                      help="number of seconds over which to integrate link errors [default %default]")
    parser.add_option("--ccm",
                      dest="ccm",
                      default=False,
                      action="store_true",
                      help="check control link")
    parser.add_option("--j14",
                      dest="j14",
                      default=False,
                      action="store_true",
                      help="assume that J14 is connected to FEC")
    parser.add_option("--qiecards",
                      dest="qiecards",
                      default=False,
                      action="store_true",
                      help="check QIE cards")
    parser.add_option("--bv",
                      dest="bv",
                      default=False,
                      action="store_true",
                      help="check bias voltage")
    parser.add_option("--uhtr",
                      dest="uhtr",
                      default=False,
                      action="store_true",
                      help="check data links with uHTRtool.exe")
    parser.add_option("--continue",
                      dest="keepgoing",
                      default=False,
                      action="store_true",
                      help="continue even when encountering error condions")
    parser.add_option("--enable",
                      dest="enable",
                      default=False,
                      action="store_true",
                      help="enable guardians")

    options, args = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        sys.exit(" ")

    return options, args[0]


class commissioner:
    def __init__(self, options, target):
        self.options = options
        self.rbx = target
        self.sector = sector(target, "904" in options.host)

        self.connect()

        if self.options.enable:
            self.enable()

        if options.ccm:
            self.ccm()

        if options.qiecards or options.bv:
            self.check([("bkp_pwr_bad_rr", 0, None)])

        if options.qiecards:
            self.qiecards()

        if options.bv:
            self.bv()

        if options.uhtr:
            self.uhtr()
        # if options.peltier:
        #     self.peltier()

        self.disconnect()


    def ccm(self):
        if self.options.j14:
            self.check([("mezz_GEO_ADDR", 1, None),
                        ("mezz_FPGA_SILSIG", 0x17092813, None),
                        ("smezz_FPGA_SILSIG", 0x17092803, None),
                    ])
        else:
            self.check([("mezz_GEO_ADDR", 2, None),
                        ("mezz_FPGA_SILSIG", 0x17092803, None),
                        ("smezz_FPGA_SILSIG", 0x17092813, None),
                    ])
        self.errors()


    def bv(self):
        items = []
        for iRm in range(1, 5):
            items.append(("%d-BVin_f_rr" % iRm, 100.0, 1.0))
        self.check(items)

        for value in [0.0, 67.0]:
            for iRm in range(1, 5):
                print self.command("put %s-%d-biasvoltage[1-48]_f 48*%3.1f" % (self.rbx, iRm, value))
                self.check([("%d-biasmon[1-48]_f_rr" % iRm, value, 0.3)])


    def qiecards(self):
        items = []
        for iRm in range(1, 6):
            for iQieCard in range(1, 5):
                if iRm == 5:
                    if iQieCard == 1:
                        stem = "calib"
                    else:
                        continue
                else:
                    stem = "%d-%d" % (iRm, iQieCard)

                items.append(("%s-i_FPGA_MAJOR_VERSION_rr" % stem, 3, None))
                items.append(("%s-i_FPGA_MINOR_VERSION_rr" % stem, 9, None))
                items.append(("%s-B_FIRMVERSION_MAJOR" % stem, 4, None))
                items.append(("%s-B_FIRMVERSION_MINOR" % stem, 2, None))
        items.append(("pulser-fpga", 6, None))
        self.check(items)


    def uhtr(self):
        # http://cmsdoc.cern.ch/cms/HCAL/document/CountingHouse/Crates/Crate_interfaces_2017.htm
        crates = [30, 24, 20, 21, 25, 31, 35, 37, 34, 30]  # 30 serves sectors 18 and 1
        end = ["M", "P"].index(self.rbx[2])
        if self.sector == 18:
            index = 0
        else:
            index = self.sector / 2

        try:
            crate = crates[index]
        except IndexError:
            printer.error("Could not find uHTR reading out %s" % self.rbx)
            return

        slot1 = 6 * end + 3 * (self.sector % 2) + 2

        lines = []
        for slot in [slot1, slot1 + 1]:
            print "Crate %d Slot %d" % (crate, slot)
            cmd = "uHTRtool.exe -c %d:%d -s linkStatus.uhtr | grep PPOD1 -A 11" % (crate, slot)
            lines1 = commandOutputFull(cmd)["stdout"].split("\n")
            for line in lines1:
                print line
            lines += lines1

            if slot != slot1:
                cmd = "uHTRtool.exe -c %d:%d -s linkStatus.uhtr | grep PPOD0 -A 11" % (crate, slot)
                lines2 = commandOutputFull(cmd)["stdout"].split("\n")
                for line in lines2:
                    print line
                lines += lines2

            # for line in lines:
            #     print line[19:]


    def connect(self):
        if not self.options.logfile:
            self.options.logfile = self.rbx + ".log"
        self.logfile = open(self.options.logfile, "a")
        printer.gray("Appending to %s" % self.options.logfile)
        h = "-" * 30 + "\n"
        self.logfile.write(h)
        self.logfile.write("| %s |\n" % str(datetime.datetime.today()))
        self.logfile.write(h)

        # ngfec.survey_clients()
        # ngfec.kill_clients()
        self.server = ngfec.connect(self.options.host, self.options.port, self.logfile)


    def disconnect(self):
        ngfec.disconnect(self.server)
        self.logfile.close()


    def command(self, cmd):
        return ngfec.command(self.server, cmd)[0]


    def check(self, items):
        for item, expected, threshold in items:
            res = self.command("get %s-%s" % (self.rbx, item))
            if threshold is None:
                self.compare(res, expected)
            else:
                self.compare_with_threshold(res, expected, threshold)
            print res


    def compare(self, res, expected):
        res1 = res.split("#")[1].strip()
        try:
            result = int(res1, 16 if res1.startswith("0x") else 10)
        except ValueError:
            result = None
            self.bail([res, "Could not convert '%s' to an integer." % res1])

        if result != expected:
            self.bail(["Expected %s: " % str(expected), res])


    def compare_with_threshold(self, res, expected, threshold):
        res1 = res.split("#")[1].strip()
        if " " in res1:
            res1 = res1.split()
        else:
            res1 = [res1]
        try:
            results = [float(x) for x in res1]
        except ValueError:
            results = []
            self.bail([res, "Could not convert all of these to floats:\n%s" % str(res1)])

        for result in results:
            if threshold < abs(result - expected):
                self.bail(["Expected %s +- %f: " % (str(expected), threshold), res])


    def enable(self):
        print("Enabling Peltier control and guardian actions")
        self.command("tput %s-[1-4]-g  %s-[1-4]s-sg  %s-calib-g %s-cg enable" % (self.rbx, self.rbx, self.rbx, self.rbx))
        self.command("tput %s-lg push" % self.rbx)
        self.command("put %s-[1-4]-peltier_control 4*1" % self.rbx)


    def errors(self):
        print("Reading control link error counters (integrating for %d seconds)" % self.options.nSeconds)
        fec = "get %s-fec_[rx_prbs_error,rxlos,dv_down,rx_raw_error]_cnt_rr" % self.rbx
        ccm = "get %s-mezz_rx_[prbs,rsdec]_error_cnt_rr" % self.rbx
        fec1 = self.command(fec)
        ccm1 = self.command(ccm)

        time.sleep(self.options.nSeconds)
        fec2 = self.command(fec)
        ccm2 = self.command(ccm)
        if fec1 != fec2:
            self.bail(["Link errors detected via FEC counters:", fec1[0], fec2[0]])
        if ccm1 != ccm2:
            self.bail(["Link errors detected via CCM counters:", ccm1[0], ccm2[0]])


    def bail(self, lines=None):
        if lines:
            printer.red("\n".join(lines))
        if not self.options.keepgoing:
            self.disconnect()
            sys.exit(" " if lines else "")


if __name__ == "__main__":
    p = commissioner(*opts())

    ###############################
    # still to be added
    # QIE11
    # CCM: b2b errors
    # FEC: clock status etc.
    # data links: uHTRtool 
    # Crate 38 fibers
    # peltier voltage and current
    ###############################
