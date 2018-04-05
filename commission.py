#!/usr/bin/env python2

import jtag, ngfec, printer
from powerMon import commandOutputFull
import datetime, optparse, os, sys, time


def sector(rbx, b904=False):
    if (not rbx.startswith("HB")) and (not rbx.startswith("HE")):
        sys.exit("This script only works with HB or HE RBXes.")

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
                      default="localhost",
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
    parser.add_option("--guardians",
                      dest="guardians",
                      default=False,
                      action="store_true",
                      help="check status of ngCCMserver guardians")
    parser.add_option("--fec",
                      dest="fec",
                      default=False,
                      action="store_true",
                      help="check status of FEC")
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
    parser.add_option("--device-info",
                      dest="device_info",
                      default=False,
                      action="store_true",
                      help="check JTAG device info")
    parser.add_option("--qiecards",
                      dest="qiecards",
                      default=False,
                      action="store_true",
                      help="check QIE cards")
    parser.add_option("--qiecards-full",
                      dest="qiecardsfull",
                      default=False,
                      action="store_true",
                      help="check QIE cards, more registers")
    parser.add_option("--qiecards-humid",
                      dest="qiecardshumid",
                      default=False,
                      action="store_true",
                      help="check QIE card humidity sensors")
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


def uhtr_tool_link_status(crate, slot1, he):
    lines = {}
    for slot in [slot1, slot1 + 1]:
        for ppod in range(2):
            if he and slot == slot1 and not ppod:
                continue
            if (not he) and slot == slot1 + 1 and ppod:
                continue

            cmd = "uHTRtool.exe -c %d:%d -s linkStatus.uhtr | grep '^PPOD%d' -A 11" % (crate, slot, ppod)
            lines[(crate, slot, ppod)] = commandOutputFull(cmd)["stdout"]
    return lines


class commissioner:
    def __init__(self, options, target):
        self.options = options
        self.rbx = target
        self.he = self.rbx.startswith("HE")
        self.sector = sector(target, "904" in options.host)

        fe = False
        for attr in dir(self.options):
            if attr.startswith("_"):
                continue
            if attr in ["ensure_value", "read_file", "read_module"]:
                continue
            if attr in ["host", "port", "logfile", "nSeconds", "keepgoing", "j14", "uhtr"]:
                continue
            if getattr(self.options, attr):
                fe = True

        if fe:
            self.connect()

        if self.options.enable:
            self.enable()

        if options.guardians:
            self.guardians()

        if options.device_info:
            self.device_info()

        if options.fec:
            self.fec()

        if options.ccm:
            self.ccm()

        if options.qiecards or options.qiecardsfull or options.bv:
            self.check([("bkp_pwr_bad_rr", 0, None)])

        if options.qiecards:
            self.qiecards()

        if options.qiecardsfull:
            self.qiecards(full=True)

        if options.qiecardshumid:
            self.qiecards_humidity()

        if options.get_delays or options.set_delays:
            self.set_delays(put=options.set_delays)

        if options.bv:
            self.bv()

        if options.uhtr:
            self.uhtr()

        if fe:
            self.disconnect()


    def guardians(self):
        print self.command("table\ntget %s-lg fns3G" % self.rbx)


    def device_info(self):
        opts2, _ = jtag.opts()
        opts2.host = self.options.host
        opts2.port = self.options.port
        opts2.logfile = self.options.logfile

        targets = ["%s-neigh" % self.rbx, "%s-pulser" % self.rbx]
        for iRm in range(1, 6):
            for iQieCard in range(1, 5):
                if iRm == 5:
                    if iQieCard == 1:
                        stem = "calib"
                    else:
                        continue
                else:
                    stem = "%d-%d" % (iRm, iQieCard)

                targets.append("%s-%s" % (self.rbx, stem))

        for target in targets:
            print target
            p = jtag.programmer(opts2, target)


    def fec(self):
        # http://cmsonline.cern.ch/cms-elog/1030680
        offset = 0 if self.rbx[2] == "M" else 3

        sfp = 2 + (self.sector - 1) % 6
        if 1 <= self.sector <= 6:
            fecs = "hefec%d" % (1 + offset)
        elif 7 <= self.sector <= 12:
            fecs = "hefec%d" % (2 + offset)
        elif 13 <= self.sector <= 18:
            fecs = "hefec%d" % (3 + offset)
        else:
            fecs = "unknown"

        print self.command("get ccmserver_version")

        self.check([("fec_ver_major_rr", 3, None),
                    ("fec_ver_minor_rr", 1, None),
                    ("fec_ver_build_rr", 2, None),
                    ("fec_firmware_date_rr", 0x14032018, None),
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


    def bv_scan(self):
        for iV in range(0, 75, 5):
            target = "HEP05-4"
            ch = 2
            print self.command("put %s-biasvoltage%d_f %4.1f" % (target, ch, iV))
            print self.command("get %s-biasmon%d_f_rr" % (target, ch))
            time.sleep(2)


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


    def qiecards(self, full=False):
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
                if full:
                    items.append(("%s-i_scratch_rr" % stem, None, None))
                    items.append(("%s-i_WTE_count_rr" % stem, None, None))
                    items.append(("%s-i_Clk_count_rr" % stem, None, None))
                    items.append(("%s-i_bc0_status_count_a_rr" % stem, None, None))

                items.append(("%s-B_FIRMVERSION_MAJOR" % stem, 4, None))
                items.append(("%s-B_FIRMVERSION_MINOR" % stem, 2, None))
                if full:
                    items.append(("%s-B_WTECOUNTER_rr" % stem, None, None))
                    items.append(("%s-B_bc0_status_count" % stem, None, None))
                    # items.append(("%s-B_FIRMVERSION_SVN" % stem, 2, None))
                    items.append(("%s-B_SCRATCH_rr" % stem, None, None))
                    items.append(("%s-B_SHT_temp_f_rr" % stem, 27.0, 7.0))
                    items.append(("%s-UniqueID_rr" % stem, None, None))
                    #items.append(("%s-B_SHT_rh_f_rr" % stem, 15.0, 10.0))

            # items.append(("%s-%s_Gsel_rr" % (stemQ, qie), None, None))
            # items.append(("%s-%s_PedestalDAC_rr" % (stemQ, qie), None, None))
            # items.append(("%s-%s_CapID0pedestal_rr" % (stemQ, qie), None, None))
            # items.append(("%s-%s_CapID1pedestal_rr" % (stemQ, qie), None, None))
            # items.append(("%s-%s_CapID2pedestal_rr" % (stemQ, qie), None, None))
            # items.append(("%s-%s_CapID3pedestal_rr" % (stemQ, qie), None, None))
        items.append(("pulser-fpga", 6, None))
        self.check(items)


    def qiecards_humidity(self):
        items = []
        for iRm in range(1, 6):
            for iQieCard in range(1, 5):
                if iRm == 5:
                    if iQieCard == 1:
                        stem = "calib"
                        stemQ = stem
                    else:
                        continue
                else:
                    stem = "%d-%d" % (iRm, iQieCard)
                    stemQ = "%d" % iRm

                items.append(("%s-B_SHT_rh_f_rr" % stem, 15.0, 10.0))

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


    def uhtr(self, check=True):
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
                slot1 = 6 * end + 3 * (self.sector % 2) + 1 + int(self.he)
            except IndexError:
                printer.error("Could not find uHTR reading out %s" % self.rbx)
                return
        else:  # 904
            ss = self.sector - 1
            crate = 61 + ss / 9
            if 9 <= ss:
                ss -= 9
            slot1 = 1 + 4 * ss / 3

        out = []
        link_status = uhtr_tool_link_status(crate, slot1, he=self.he)
        for (crate, slot, ppod), lines in sorted(link_status.iteritems()):
            link, power, bad8b10b, bc0, h1, write_delay, read_delay, fifo_occ, bprv, h2, bad_full, invalid, h3 = lines.split("\n")
            iStart, iEnd, items = self.uhtr_range_and_items(slot, ppod, fifo_occ)
            out.append((self.sector, crate, slot, ppod, items[iStart:iEnd]))
            if not check:
                continue

            print "Crate %d Slot %2d" % (crate, slot)
            link_headers = link[19:]
            # https://github.com/elaird/hcalraw/blob/master/data/ref_2018.txt
            s3 = slot % 3
            if s3 == 1:
                if ppod:
                    link_headers = " rx12(1-6) rx13(2-6) rx14(3-6) rx15(4-6) rx16(1-7) rx17(2-7) rx18(3-7) rx19(4-7) rx20      rx21      rx22      rx23     "
                else:
                    link_headers = " rx00      rx01      rx02      rx03      rx04(1-4) rx05(2-4) rx06(3-4) rx07(4-4) rx08(1-5) rx09(2-5) rx10(3-5) rx11(4-5)"
            elif s3 == 2:
                if ppod:
                    link_headers = " rx12(1-2) rx13(1-4) rx14(1-6) rx15(2-4) rx16(2-5) rx17(2-7) rx18(3-2) rx19(3-4) rx20(3-6) rx21(4-4) rx22(4-5) rx23(4-7)"
                else:
                    link_headers = " rx00      rx01      rx02(1-2) rx03(1-3) rx04(2-2) rx05(2-3) rx06(3-2) rx07(3-3) rx08(4-2) rx09(4-3) rx10(5-1) rx11     "
            elif not s3:
                if ppod:
                    link_headers = " rx12      rx13(3-1) rx14(3-3) rx15(3-5) rx16(3-7) rx17(3-8) rx18(4-1) rx19(4-2) rx20(4-3) rx21(4-6) rx22(4-8) rx23(5-1)"
                else:
                    link_headers = " rx00      rx01(1-1) rx02(1-3) rx03(1-5) rx04(1-7) rx05(1-8) rx06(2-1) rx07(2-2) rx08(2-3) rx09(2-6) rx10(2-8) rx11(5-2)"

            print link[:19] + link_headers
            self.uhtr_compare(slot, ppod, power, 300.0, threshold=200.0)
            self.uhtr_compare(slot, ppod, bad8b10b, 0, threshold=0)
            self.uhtr_compare(slot, ppod, bc0, 1.12e1, threshold=0.1e1)
            printer.gray(h1)
            self.uhtr_compare(slot, ppod, write_delay, 300, threshold=10000)
            self.uhtr_compare(slot, ppod, read_delay, 300, threshold=10000)
            self.uhtr_compare(slot, ppod, fifo_occ, 12, threshold=9)
            self.uhtr_compare(slot, ppod, bprv, 0x1111, threshold=0)
            printer.gray(h2)
            self.uhtr_compare(slot, ppod, bad_full, 0, threshold=1, doubled=True)
            self.uhtr_compare(slot, ppod, invalid, 0, threshold=1)
            printer.gray(h3)

        return out


    def uhtr_compare(self, slot, ppod, lst, expected, threshold=None, doubled=False):
        iStart, iEnd, items = self.uhtr_range_and_items(slot, ppod, lst)
        n = (len(lst) - 19) / 12
        if doubled:
            iStart *= 2
            iEnd *= 2
            n /= 2

        msg = lst[:19]
        for i, x in enumerate(items):
            try:
                result = int(x, 16)
            except ValueError:
                try:
                    result = float(x)
                except ValueError:
                    result = None

            if doubled:
                space = " " * (n - len(x) - 1)
            else:
                space = " " * (n - len(x) - 1)

            if i < iStart or iEnd <= i or result is None:
                msg += space + printer.gray(x, p=False) + " "
            elif threshold is not None and threshold < abs(result - expected):
                msg += space + printer.red(x, p=False) + " "
            else:
                msg += space + printer.green(x, p=False) + " "

        print msg


    def uhtr_range_and_items(self, slot, ppod, lst):
        items = lst[19:].split()

        if (slot % 3) == 0:
            iStart = 1
            iEnd = 12  # include ngHE CU fibers
        if (slot % 3) == 1:
            if ppod:
                iStart = 0
                iEnd = 8
            else:
                iStart = 4
                iEnd = 12
        if (slot % 3) == 2:
            if ppod:
                iStart = 0
                iEnd = 12
            else:
                iStart = 2
                iEnd = 11  # include HB CU fiber

        return iStart, iEnd, items


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
            if expected is not None:
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
                lines = ["Expected %s +- %s: " % (str(expected), str(threshold)), str(res)]
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
