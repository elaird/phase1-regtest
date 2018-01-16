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
    parser.add_option("--fec",
                      dest="fec",
                      default=False,
                      action="store_true",
                      help="check status of FEC")
    parser.add_option("--guardians",
                      dest="guardians",
                      default=False,
                      action="store_true",
                      help="check status of ngCCMserver guardians")
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
    parser.add_option("--set-bv",
                      dest="set_bv",
                      default=False,
                      action="store_true",
                      help="set test values of bias voltages")
    parser.add_option("--get-delays",
                      dest="get_delays",
                      default=False,
                      action="store_true",
                      help="read values of QIE phase delays")
    parser.add_option("--set-delays",
                      dest="set_delays",
                      default=False,
                      action="store_true",
                      help="set test values of QIE phase delays")
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


def uhtr_tool_link_status(crate, slot1):
    lines = {}
    for slot in [slot1, slot1 + 1]:
        for ppod in range(2):
            if slot == slot1 and not ppod:
                continue

            cmd = "uHTRtool.exe -c %d:%d -s linkStatus.uhtr | grep '^PPOD%d' -A 11" % (crate, slot, ppod)
            lines[(crate, slot, ppod)] = commandOutputFull(cmd)["stdout"]
    return lines


class commissioner:
    def __init__(self, options, target):
        self.options = options
        self.rbx = target
        self.sector = sector(target, "904" in options.host)

        self.connect()

        if self.options.enable:
            self.enable()

        if options.guardians:
            self.guardians()

        if options.fec:
            self.fec()

        if options.ccm:
            self.ccm()

        if options.qiecards or options.bv:
            self.check([("bkp_pwr_bad_rr", 0, None)])

        if options.qiecards:
            self.qiecards()

        if options.get_delays or options.set_delays:
            self.set_delays(put=options.set_delays)

        if options.bv:
            self.bv()

        if options.uhtr:
            self.uhtr()
        # if options.peltier:
        #     self.peltier()

        self.disconnect()


    def guardians(self):
        print self.command("table\ntget %s-lg fns3G" % self.rbx)


    def fec(self):
        if self.rbx[2] != "P":
            self.bail(["fec() does not yet support HEM"])

        # http://cmsonline.cern.ch/cms-elog/1025354
        sfp = 2 + (self.sector - 1) % 6
        if 1 <= self.sector <= 6:
            fecs = "hefec1"
        elif 7 <= self.sector <= 12:
            fecs = "hefec2"
        elif 13 <= self.sector <= 18:
            fecs = "hefec3"
        else:
            fecs = "unknown"

        self.check([("fec_ver_major_rr", 3, None),
                    ("fec_ver_minor_rr", 1, None),
                    ("fec_ver_build_rr", 2, None),
                    ("fec_firmware_date_rr", 0x29112017, None),
                    ("LHC_clk_freq_rr", 0x61d90, 10),
                    ("sfp%d_status.TxFault_rr" % sfp, 0, None),
                    ("sfp%d_status.RxLOS_rr" % sfp, 0, None),
                    # SinErr_cnt_rr
                    # DbErr_cnt_rr
                    # qie_reset_cnt_rr
                    # qie_reset_early_cnt_rr
                    # qie_reset_late_cnt_rr
                    # qie_reset_ontime_cnt_rr
                ], device=fecs)

        self.check([("fec-sfp_rx_power_f", 400.0, 200.0),
                    ("fec-sfp_tx_power_f", 550.0, 150.0),
                    ])


    def ccm(self):
        fw14 = 0x17092813
        fw15 = 0x17092803
        current = 0.35e-3
        currentE = 0.15e-3
        if self.options.j14:
            lst = [("mezz_GEO_ADDR", 1, None),
                   ("mezz_FPGA_SILSIG", fw14, None),
                   ("smezz_FPGA_SILSIG", fw15, None),
                   ("vtrx_rssi_J14_Cntrl_f_rr", current, currentE),
            ]
        else:
            lst = [("mezz_GEO_ADDR", 2, None),
                   ("mezz_FPGA_SILSIG", fw15, None),
                   ("smezz_FPGA_SILSIG", fw14, None),
                   ("vtrx_rssi_J15_Cntrl_f_rr", current, currentE),
            ]

        temp = 35.0
        tempE = 5.0
        lst += [# ("temp_J13_Clk_U10_f_rr", temp, tempE),
                # ("temp_J13_Clk_U11_f_rr", temp, tempE),
                # ("temp_J14_Ctrl_U18_f_rr", temp, tempE),
                # ("temp_J14_Ctrl_U19_f_rr", temp, tempE),
                # ("temp_J15_Ctrl_U18_f_rr", temp, tempE),
                # ("temp_J15_Ctrl_U19_f_rr", temp, tempE),
                # ("temp_J16_Clk_U10_f_rr", temp, tempE),
                # ("temp_J16_Clk_U11_f_rr", temp, tempE),
                # ("J13_Clk_1w_f", None, None),
                # ("J14_Cntrl_1w_f", None, None),
                # ("J15_Cntrl_1w_f", None, None),
                # ("J16_Clk_1w_f", None, None),
            ]

        self.check(lst)
        self.errors()


    def bv(self):
        for iRm in range(1, 5):
            print self.command("get %s-%d-PeltierVoltage_f_rr" % (self.rbx, iRm))
            print self.command("get %s-%d-PeltierCurrent_f_rr" % (self.rbx, iRm))
            if not self.options.set_bv:
                print self.command("get %s-%d-biasmon[1-48]_f_rr" % (self.rbx, iRm))

            items = [("%d-BVin_f_rr" % iRm, 100.0, 4.0),
                     ("%d-LeakageCurrent[1-48]_f_rr" % iRm, 13.5, 6.5),
                     ("%d-rtdtemperature_f" % iRm, 18.0, 2.0),
                     ("%d-temperature_f" % iRm, 18.0, 2.0),
                     ("%d-humidityS_f_rr" % iRm, 10.0, 10.0),
                 ]
            self.check(items)

        if self.options.set_bv:
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
                        stemQ = stem
                        qie = "QIE[1-12]"
                    else:
                        continue
                else:
                    stem = "%d-%d" % (iRm, iQieCard)
                    stemQ = "%d" % iRm
                    qie = "QIE[1-48]"

                items.append(("%s-i_FPGA_MAJOR_VERSION_rr" % stem, 3, None))
                items.append(("%s-i_FPGA_MINOR_VERSION_rr" % stem, 9, None))
                # items.append(("%s-i_scratch_rr" % stem, None, None))
                # items.append(("%s-i_WTE_count_rr" % stem, None, None))

                items.append(("%s-B_FIRMVERSION_MAJOR" % stem, 2 if self.rbx == "HEP17" else 4, None))
                items.append(("%s-B_FIRMVERSION_MINOR" % stem, 3 if self.rbx == "HEP17" else 2, None))
                # items.append(("%s-B_FIRMVERSION_SVN" % stem, 2, None))
                # items.append(("%s-B_SCRATCH_rr" % stem, None, None))
                # items.append(("%s-B_WTECOUNTER_rr" % stem, None, None))
                # items.append(("%s-B_SHT_temp_f_rr" % stem, 25.0, 5.0))
                # items.append(("%s-B_SHT_rh_f_rr" % stem, 5.0, 5.0))

            # items.append(("%s-%s_Gsel_rr" % (stemQ, qie), None, None))
            # items.append(("%s-%s_PedestalDAC_rr" % (stemQ, qie), None, None))
            # items.append(("%s-%s_CapID0pedestal_rr" % (stemQ, qie), None, None))
            # items.append(("%s-%s_CapID1pedestal_rr" % (stemQ, qie), None, None))
            # items.append(("%s-%s_CapID2pedestal_rr" % (stemQ, qie), None, None))
            # items.append(("%s-%s_CapID3pedestal_rr" % (stemQ, qie), None, None))
        items.append(("pulser-fpga", 6, None))
        self.check(items)


    def set_delays(self, put=True):
        for iRm in range(1, 6):
            for iQieCard in range(1, 5):
                if iRm == 5:
                    if iQieCard == 1:
                        stem = "calib"
                        stemQ = stem
                        qie = "QIE[1-12]"
                        nQie = 12
                    else:
                        continue
                else:
                    stem = "%d-%d" % (iRm, iQieCard)
                    stemQ = "%d" % iRm
                    qie = "QIE[1-48]"
                    nQie = 48

            if put:
                print self.command("put %s-%s-%s_PhaseDelay %d*64" % (self.rbx, stemQ, qie, nQie))
            else:
                print self.command("get %s-%s-%s_PhaseDelay_rr" % (self.rbx, stemQ, qie))


    def uhtr(self):
        if self.rbx[2] in "MP":  # USC
            end = "MP".index(self.rbx[2])
            if self.sector == 18:
                index = 0
            else:
                index = self.sector / 2

            try:
                # http://cmsdoc.cern.ch/cms/HCAL/document/CountingHouse/Crates/Crate_interfaces_2017.htm
                crates = [30, 24, 20, 21, 25, 31, 35, 37, 34, 30]  # 30 serves sectors 18 and 1
                crate = crates[index]
                slot1 = 6 * end + 3 * (self.sector % 2) + 2
            except IndexError:
                printer.error("Could not find uHTR reading out %s" % self.rbx)
                return
        else:  # 904
            ss = self.sector - 1
            crate = 61 + ss / 9
            if 9 <= ss:
                ss -= 9
            slot1 = 1 + 4 * ss / 3

        link_status = uhtr_tool_link_status(crate, slot1)
        for (crate, slot, ppod), lines in sorted(link_status.iteritems()):
            print "Crate %d Slot %2d" % (crate, slot)
            print lines
            link, power, bad8b10b, bc0, _, write_delay, read_delay, fifo_occ, bprv, _, bad_full, invalid, _ = lines.split("\n")

            # self.uhtr_compare(slot, ppod, power, 300.0, threshold=200.0)
            self.uhtr_compare(slot, ppod, bad8b10b, 0)
            self.uhtr_compare(slot, ppod, bc0, 1.12e1, threshold=0.1e1)
            self.uhtr_compare(slot, ppod, fifo_occ, 11, threshold=8)
            self.uhtr_compare(slot, ppod, bprv, 0x1111)
            # self.uhtr_compare(slot, ppod, invalid, 0)
            # self.uhtr_compare(slot, ppod, bad_full, 0, doubled=True)


    def uhtr_compare(self, slot, ppod, lst, expected, threshold=None, doubled=False):
        items = lst[19:].split()
        if not (slot % 3):
            iStart = 1
            iEnd = 11  # FIXME: update once CU fibers are connected
        else:
            iStart = 0
            iEnd = 12

        if doubled:
            iStart *= 2
            iEnd *= 2

        if threshold is None:
            for i in range(iStart, iEnd):
                self.compare("0x" + items[i], expected, strip=False, msg="%s (link %d)" % (lst[:19], 12*ppod + (i/2 if doubled else i)))
        else:
            self.compare_with_threshold(items[iStart:iEnd], expected, threshold, strip=False, msg=lst[:19].strip())


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


    def check(self, items, device=None):
        for item, expected, threshold in items:
            if device is None:
                res = self.command("get %s-%s" % (self.rbx, item))
            else:
                res = self.command("get %s-%s" % (device, item))
            if threshold is None:
                self.compare(res, expected)
            else:
                self.compare_with_threshold(res, expected, threshold)
            print res


    def compare(self, res, expected, strip=True, msg=""):
        if strip:
            res1 = res.split("#")[1].strip()
        else:
            res1 = res

        try:
            result = int(res1, 16 if res1.startswith("0x") else 10)
        except ValueError:
            result = None
            self.bail([res, "Could not convert '%s' to an integer." % res1])

        if result != expected and expected is not None:
            lines = ["Expected %s: " % str(expected), res]
            if msg:
                lines.insert(0, msg)
            self.bail(lines)


    def compare_with_threshold(self, res, expected, threshold, strip=True, msg=""):
        if strip:
            res1 = res.split("#")[1].strip()
        else:
            res1 = res

        if " " in res1:
            res1 = res1.split()
        elif type(res1) is not list:
            res1 = [res1]

        try:
            if res1[0].startswith("0x"):
                results = [int(x, 16) for x in res1]
            else:
                results = [float(x) for x in res1]
        except ValueError:
            results = []
            self.bail([str(res), "Could not convert all of these to floats:\n%s" % str(res1)])

        for result in results:
            if threshold < abs(result - expected):
                lines = ["Expected %s +- %5.1f: " % (str(expected), threshold), str(res)]
                if msg:
                    lines.insert(0, msg)
                self.bail(lines)


    def enable(self):
        print("Enabling Peltier control and guardian actions")
        self.command("tput %s-[1-4]-g  %s-[1-4]s-sg  %s-calib-g %s-cg enable" % (self.rbx, self.rbx, self.rbx, self.rbx))
        self.command("tput %s-lg push" % self.rbx)
        self.command("put %s-[1-4]-peltier_control 4*1" % self.rbx)


    def errors(self):
        print("Reading control link error counters (integrating for %d seconds)" % self.options.nSeconds)
        fec = "get %s-fec_[rx_prbs_error,rxlos,dv_down,rx_raw_error]_cnt_rr" % self.rbx
        ccm = "get %s-mezz_rx_[prbs,rsdec]_error_cnt_rr" % self.rbx
        b2b = "get %s-[,s]b2b_rx_[prbs,rsdec]_error_cnt_rr" % self.rbx

        fec1 = self.command(fec)
        ccm1 = self.command(ccm)
        b2b1 = self.command(b2b)

        time.sleep(self.options.nSeconds)
        fec2 = self.command(fec)
        ccm2 = self.command(ccm)
        b2b2 = self.command(b2b)

        if fec1 != fec2:
            self.bail(["Link errors detected via FEC counters:", fec1[0], fec2[0]])
        if ccm1 != ccm2:
            self.bail(["Link errors detected via CCM counters:", ccm1[0], ccm2[0]])
        if b2b1 != b2b2:
            self.bail(["Link errors detected via CCM counters:", b2b1[0], b2b2[0]])


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
    # FEC link status
    # CU data links
    ###############################
