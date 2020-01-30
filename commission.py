#!/usr/bin/env python

import driver, printer
from powerMon import commandOutputFull
import datetime, optparse, os, sys, time


def opts():
    parser = optparse.OptionParser(usage="usage: %prog [options] RBX")
    parser.add_option("--log-file",
                      dest="logfile",
                      default="",
                      help="log file to which to append")
    parser.add_option("--nseconds",
                      dest="nSeconds",
                      default=5,
                      type="int",
                      help="number of seconds over which to integrate link errors [default %default]")
    parser.add_option("--temperature",
                      dest="temperature",
                      default=18.0,
                      metavar="T",
                      type="float",
                      help="expected Peltier temperature (C) [default %default]")
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
    parser.add_option("--bat28",
                      dest="bat28",
                      default=False,
                      action="store_true",
                      help="apply customizations for Bat. 28")

    options, args = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        sys.exit(" ")

    return options, args[0]


def uhtr_tool_link_status(crate, slot1, slot2, three, he):
    lines = {}
    for slot in [slot1, slot2]:
        for ppod in range(2):
            if three and he and slot == slot1 and not ppod:
                continue
            if three and (not he) and slot == slot2 and ppod:
                continue

            cmd = "uHTRtool.exe -c %d:%d -s linkStatus.uhtr | grep '^PPOD%d' -A 11" % (crate, slot, ppod)
            lines[(crate, slot, ppod)] = commandOutputFull(cmd)["stdout"]
    return lines


class commissioner(driver.driver):
    def __init__(self, options, target):
        self.rbx = target
        self.options = options
        if not self.options.logfile:
            self.options.logfile = self.rbx + ".log"

        self.assign_sector_host_port(default=self.options.bat28)

        fe = False
        for attr in dir(self.options):
            if attr.startswith("_"):
                continue
            if attr in ["ensure_value", "read_file", "read_module"]:
                continue
            if attr in ["logfile", "nSeconds", "keepgoing", "j14", "uhtr"]:
                continue
            if getattr(self.options, attr):
                fe = True

        if fe:
            self.connect()

        if options.guardians:
            self.guardians()

        if options.fec:
            self.fec()

        if options.ccm:
            self.ccm()

        if (self.hb or self.he) and (options.qiecards or options.qiecardsfull or options.bv):
            if self.hb:
                for letter in "ab":
                    self.check([("bkp_pwr_bad_rr", 0, None)], device="%s%s" % (self.rbx, letter))
            else:
                self.check([("bkp_pwr_bad_rr", 0, None)])

        if options.qiecards:
            if self.hb or self.he:
                self.qiecards_hbhe()
            if self.hf:
                self.qiecards_hf()

        if self.he and options.qiecardsfull:
            self.qiecards(full=True)

        if self.he and options.qiecardshumid:
            self.qiecards_humidity()

        if self.he and (options.get_delays or options.set_delays):
            self.set_delays(put=options.set_delays)

        if (self.hb or self.he) and options.bv:
            self.bv()

        if options.uhtr:
            self.uhtr()

        if fe:
            self.disconnect()


    def fec_and_sfp(self):
        out = None
        if self.end in "MP":
            if self.hf:
                filename = "/nfshome0/hcalcfg/cvs/RevHistory/CCMServer/top_hfpt5_0.txt/pro"
            elif self.he:
                filename = "/nfshome0/hcalcfg/cvs/RevHistory/CCMServer/top_hept5_0.txt/pro"
            elif self.hb:
                filename = "/nfshome0/hcalcfg/cvs/RevHistory/CCMServer/top_hbpt5_4.txt/pro"
        else:
            if self.hf:
                filename = "/nfshome0/hcalcfg/cvs/RevHistory/CCMServer/top_hf904_7.txt/pro"
            else:
                filename = "/nfshome0/hcalcfg/cvs/RevHistory/CCMServer/top_hb904_4.txt/pro"

        f = open(filename)
        for line in f:
            fields = line.split()
            if not fields:
                continue
            if fields[0] != "INCLUDE":
                continue

            fec = fields[-1].replace("_fec_=", "")
            for item in fields:
                if item.endswith(self.rbx):
                    sfp = item.replace("_=" + self.rbx, "").replace("_rbx", "")
                    try:
                        sfp = int(sfp)
                    except ValueError as e:
                        sfp = ord(sfp) - 96
                        sfp = 2 * sfp - 1
                    out = (fec, sfp)
        f.close()

        if out is None:
            sys.exit("Did not find %s in 'pro' version of %s" % (self.rbx, "/".join(["HcalCfg"] + filename.split("/")[-3:-1])))
        return out


    def fec(self):
        # hbhe_full = (3, 1, 2, 0x14032018)
        hbhe_full = (3, 1, 2, 0x20102017)
        hbhe_half = (4, 3, 9, 0x2102019)
        fw = hbhe_half
        if self.rbx in ["HEM09", "HEP10"]:
            fw = hbhe_full

        if self.hf:
            fw = (3, 1, 2, 0x16042018)

        if self.options.bat28:
            fecs = "fec1"
            sfp = 1
        else:
            fecs, sfp = self.fec_and_sfp()

        print("")
        print("-" * 7)
        print("| FEC |")
        print("-" * 7)

        self.check([("fec_ver_major_rr", fw[0], None),
                    ("fec_ver_minor_rr", fw[1], None),
                    ("fec_ver_build_rr", fw[2], None),
                    ("fec_firmware_date_rr", fw[3], None),
                    ("LHC_clk_freq_rr", 0x61d90, 10),
                    ("cdce_pll_locked", 1, None),
                    ("cdce_pll_unlocked_cnt", 1, 1),
                    ("ig_ipBus_cnt", 2, 2),
                    # SinErr_cnt_rr
                    # DbErr_cnt_rr
                    # qie_reset_cnt_rr
                    # qie_reset_early_cnt_rr
                    # qie_reset_late_cnt_rr
                    # qie_reset_ontime_cnt_rr
                   ], device=fecs)

        if self.hb:
            letters = "ab"
        else:
            letters = " "

        old = self.hf

        for i, letter in enumerate(letters):
            if letter == " ":
                letter = ""
            print("")
            print("-" * 14)
            print("| FEC site %s |" % letter)
            print("-" * 14)
            self.check([("sfp%d_status.TxFault_rr" % (sfp + i), 0, None),
                        ("sfp%d_status.RxLOS_rr" % (sfp + i), 0, None),
                        ("sfp%d_gbt_rx_ready_rr" % (sfp + i), 1, None),
                       ], device=fecs)
            self.check([("fec-sfp_rx_power_f", 420.0, 220.0),
                        ("fec-sfp_tx_power_f", 550.0, 150.0),
                       ], device="%s%s" % (self.rbx, letter))

            if not old:
                self.check([("fec_dv_down_cnt", 1, 1),
                            ("fec_min_phase", None, None), # 0x0f0, 0x30)
                            ("fec_max_phase", None, None), # 0x110, 0x30)
                        ], device="%s%s" % (self.rbx, letter))

            self.errors(ccm=False, sleep=False, letter=letter, old=old)
            if not old:
                print(self.command("put %s-test_comm 1" % (self.rbx + letter)))
                always = 0x8000
                self.check([("fecccm_test_comm_cnt", always, None),
                            ("fecccm_sys_master_cnt", None, None),  # FIXME
                            ("fecccm_sys_refclk_cnt", always, None),
                            ("fecccm_epcs_cdr_locked_cnt", always, None),
                            ("fecccm_rx_pll_locked_cnt", always, None),
                            ("fecccm_rx_header_locked_cnt", always, None),
                            # ("fecccm_rx_is_data", 1, None),
                            ("fecccm_rx_ready_cnt", always, None),
                            ("fecccm_rx_data_valid_cnt", always, None),
                           ], device="%s%s" % (self.rbx, letter))

            self.errors(store=False, ccm=False, sleep=False, letter=letter, old=old)


    def ccm(self):
        fw14 = 0x19012932
        fw15 = 0x19012922
        if self.he:
            sw15 = [1, 1, 0, 1]
            sw14 = [1, 1, 1, 1]
        elif self.hb:
            sw15 = [1, 1, 0, 0]
            sw14 = [1, 1, 1, 0]
        else:
            fw14 = None
            fw15 = None

        current = 0.35e-3
        currentE = 0.15e-3

        if self.options.j14:
            lst = [("mezz_GEO_ADDR", 1, None),
                   ("mezz_FPGA_SILSIG_rr", fw14, None),
                   ("smezz_FPGA_SILSIG_rr", fw15, None)]
        else:
            lst = [("mezz_GEO_ADDR", 2, None),
                   ("mezz_FPGA_SILSIG_rr", fw15, None),
                   ("smezz_FPGA_SILSIG_rr", fw14, None)]

        if self.hb or self.he:
            for iSw in range(4):
                lst.append(("mezz_TEST_SW%d" % iSw, (sw14 if self.options.j14 else sw15)[iSw], None))
            for iSw in range(4):
                lst.append(("smezz_TEST_SW%d" % iSw, (sw15 if self.options.j14 else sw14)[iSw], None))

        if self.hb:
            lst += [("mezz_MASTER_B_ENABLE_rr", None, None),
                    ("smezz_MASTER_B_ENABLE_rr", None, None)]
        elif self.he:
            lst += [("mezz_MASTER_J14_ENABLE_rr", None, None),
                    ("smezz_MASTER_J14_ENABLE_rr", None, None)]

        if self.hb or self.he:
            lst += [("mezz_RX_PLL_LOCK_LOST_CNT_rr", 1, 1),
                    ("b2b_RX_PLL_LOCK_LOST_CNT_rr", 1, 1),
                    ("mezz_PELTIER_DISABLE_CNTR", 5, 5),
                    ("b2b_PELTIER_DISABLE_CNTR", 5, 5),
                    ("mezz_PWR_ENABLE_CNTR", 5, 5),
                    ("b2b_PWR_ENABLE_CNTR", 5, 5)]

        if self.hb:
            prefix = "b" if self.options.j14 else "a"
        elif self.he:
            prefix = "J14_" if self.options.j14 else "J15_"

        if self.hb or self.he:
            lst.append(("vtrx_rssi_%sCntrl_f_rr" % prefix, current, currentE))

        # temp = 35.0
        # tempE = 5.0
        # lst += [("temp_J13_Clk_U10_f_rr", temp, tempE),
        #         ("temp_J13_Clk_U11_f_rr", temp, tempE),
        #         ("temp_J14_Ctrl_U18_f_rr", temp, tempE),
        #         ("temp_J14_Ctrl_U19_f_rr", temp, tempE),
        #         ("temp_J15_Ctrl_U18_f_rr", temp, tempE),
        #         ("temp_J15_Ctrl_U19_f_rr", temp, tempE),
        #         ("temp_J16_Clk_U10_f_rr", temp, tempE),
        #         ("temp_J16_Clk_U11_f_rr", temp, tempE),
        #         ("J13_Clk_1w_f", None, None),
        #         ("J14_Cntrl_1w_f", None, None),
        #         ("J15_Cntrl_1w_f", None, None),
        #         ("J16_Clk_1w_f", None, None),
        #        ]

        if self.hf:
            lst = [("mezz_FPGA_SILSIG", 0x16120501, None),
                   ("vtrx_rssi_f_rr", current, currentE),
                   ]

        if self.hb:
            for letter in "ab":
                print("")
                print("-" * 8)
                print("| CCM%s |" % letter)
                print("-" * 8)
                self.check(lst, device="%s%s" % (self.rbx, letter))
                self.errors(fec=False, letter=letter, old=not self.sector)
        else:
            print("")
            print("-" * 7)
            print("| CCM |")
            print("-" * 7)
            self.check(lst)
            self.errors(fec=False, old=(self.hf or not self.sector))


    def bv_scan(self):
        for iV in range(0, 75, 5):
            target = "HEP05-4"
            ch = 2
            print(self.command("put %s-biasvoltage%d_f %4.1f" % (target, ch, iV)))
            print(self.command("get %s-biasmon%d_f_rr" % (target, ch)))
            time.sleep(2)


    def bv(self):
        for iRm in range(1, 5):
            print("")
            print("-" * 25)
            print("| BV and Peltier (RM %d) |" % iRm)
            print("-" * 25)

            items = [("%d-PeltierVoltage_f_rr" % iRm, 2.5, 2.5),
                     ("%d-PeltierCurrent_f_rr" % iRm, 0.8, 0.8),
                     ("%d-rtdtemperature_f_rr" % iRm, self.options.temperature, 2.0),
                     # ("%d-temperature_f" % iRm, 18.0 if self.he else 5.0, 2.0),
                    ]
            self.check(items)
            self.check([("%d-humidityS_f_rr" % iRm, 3.0, 4.0)], timeout=15)

            if not self.options.set_bv:
                nCh = 48 if self.he else 64
                self.check([("%d-BVin_f_rr" % iRm, 100.0, 4.0),
                            ("%d-biasmon[1-%d]_f_rr" % (iRm, nCh), 67.0, 3.0),
                            ("%d-LeakageCurrent[1-%d]_f_rr" % (iRm, nCh), 13.0, 11.0), # https://indico.cern.ch/event/800901/
                           ])

        if self.options.set_bv:
            for value in [0.0, 67.0]:
                for iRm in range(1, 5):
                    print(self.command("put %s-%d-biasvoltage[1-48]_f 48*%3.1f" % (self.rbx, iRm, value)))
                    self.check([("%d-biasmon[1-48]_f_rr" % iRm, value, 0.3)])


    def qiecards_hf(self, **_):
        items = []

        if self.rbx == "lasermon" or self.rbx == "ZDCM":
            sites = [3, 5]
        elif self.rbx == "ZDCP":
            sites = [3, 5]
        else:
            sites = [3, 4, 5, 6, 10, 11, 12, 13, 14]

        for iQieCard in sites:
            items.append(("%d-B_FIRMVERSION_MAJOR" % iQieCard, 2, None))
            items.append(("%d-B_FIRMVERSION_MINOR" % iQieCard, 2, None))
            for igloo in ["iBot", "iTop"]:
                stem = "%d-%s" % (iQieCard, igloo)
                items.append(("%s_FPGA_MAJOR_VERSION_rr" % stem, 7, None))
                items.append(("%s_FPGA_MINOR_VERSION_rr" % stem, 1, None))

        # items.append(("pulser-fpga", 6, None))
        self.check(items)


    def qiecards_hbhe(self, full=False):
        nCh = 64 if self.hb else 48

        items = []
        for iRm in range(1, 6):
            for iQieCard in range(1, 5):
                if iRm == 5:
                    if iQieCard == 1:
                        stem = "calib"
                        stemQ = stem
                        qie = "QIE[1-%s]" % int(nCh / 4)
                    else:
                        continue
                else:
                    stem = "%d-%d" % (iRm, iQieCard)
                    stemQ = "%d" % iRm
                    qie = "QIE[1-%d]" % nCh

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

                for igloo in ["iBot", "iTop"] if self.hb else ["i"]:
                    items.append(("%s-%s_FPGA_MAJOR_VERSION_rr" % (stem, igloo), 1 if self.hb else 3, None))
                    items.append(("%s-%s_FPGA_MINOR_VERSION_rr" % (stem, igloo), 3 if self.hb else 9, None))
                    if full:
                        items.append(("%s-%s_scratch_rr"   % (stem, igloo), None, None))
                        items.append(("%s-%s_WTE_count_rr" % (stem, igloo), None, None))
                        items.append(("%s-%s_Clk_count_rr" % (stem, igloo), None, None))
                        items.append(("%s-%s_bc0_status_count_a_rr" % (stem, igloo), None, None))

                # items.append(("%s-%s_Gsel" % (stemQ, qie), None, None))
                # items.append(("%s-%s_PedestalDAC" % (stemQ, qie), None, None))
                # items.append(("%s-%s_CapID0pedestal" % (stemQ, qie), None, None))
                # items.append(("%s-%s_CapID1pedestal" % (stemQ, qie), None, None))
                # items.append(("%s-%s_CapID2pedestal" % (stemQ, qie), None, None))
                # items.append(("%s-%s_CapID3pedestal" % (stemQ, qie), None, None))

        items.append(("pulser-fpga", 7, None))
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
                print(self.command("put %s-%s-%s_PhaseDelay %d*64" % (self.rbx, stemQ, qie, nQie)))
            else:
                print(self.command("get %s-%s-%s_PhaseDelay_rr" % (self.rbx, stemQ, qie)))


    def uhtr(self, check=True):
        iEnd = "MP".find(self.end)

        if self.rbx == "lasermon":
            crate = 38
            slot1 = 7
            slot2 = 9
        elif self.usc:  # USC
            if self.hf:
                sys.exit("'--uhtr' is not yet supported for HF.")
            else:  # HBHE
              try:
                  # http://cmsdoc.cern.ch/cms/HCAL/document/CountingHouse/Crates/Crate_interfaces_2017.htm
                  crates = [30, 24, 20, 21, 25, 31, 35, 37, 34, 30]  # 30 serves sectors 18 and 1
                  crate = crates[int(self.sector / 2)]
                  slot1 = 6 * iEnd + 3 * (self.sector % 2) + 1 + int(self.he)
                  slot2 = slot1 + 1
              except IndexError:
                  printer.error("Could not find uHTR reading out %s" % self.rbx)
                  return
        elif not self.sector:  # 904
            crate = 63
            slot1 = 4 if self.hb else 5
            slot2 = slot1 + 1
        else:
            ss = self.sector - 1
            crate = 61 + int(ss / 9)
            if 9 <= ss:
                ss -= 9
            slot1 = 1 + int(4 * ss / 3)
            slot2 = slot1 + 1

        out = []
        link_status = uhtr_tool_link_status(crate, slot1, slot2, three=(self.usc or not self.sector), he=self.he)
        for (crate, slot, ppod), lines in sorted(link_status.iteritems()):
            first = slot == slot1
            link, power, bad8b10b, bc0, h1, write_delay, read_delay, fifo_occ, bprv, h2, bad_full, invalid, h3 = lines.split("\n")
            iStart, iEnd, items = self.uhtr_range_and_items(slot, ppod, fifo_occ, first)
            # iStart, iEnd, items = self.uhtr_range_and_items(slot, ppod, write_delay, first)
            out.append((self.sector, crate, slot, ppod, items[iStart:iEnd]))
            if not check:
                continue

            print("Crate %d Slot %2d" % (crate, slot))
            link_headers = link[19:]
            # https://github.com/elaird/hcalraw/blob/master/data/ref_2019.txt
            if self.hb or self.he:
                if self.usc or not self.sector:
                    s3 = slot % 3
                    if s3 == 1:
                        if ppod:
                            link_headers = " rx12(1-6) rx13(2-6) rx14(3-6) rx15(4-6) rx16(1-7) rx17(2-7) rx18(3-7) rx19(4-7) rx20(1-8) rx21(2-8) rx22(3-8) rx23(4-8)"
                        else:
                            link_headers = " rx00(1-1) rx01(2-1) rx02(3-1) rx03(4-1) rx04(1-4) rx05(2-4) rx06(3-4) rx07(4-4) rx08(1-5) rx09(2-5) rx10(3-5) rx11(4-5)"
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
                else:
                    rm0 = [2, 1, 4, 3][slot % 4]
                    rm1 = rm0 + 1
                    if 4 < rm1:
                        rm1 -= 4
                    rm2 = rm0 + 2
                    if 4 < rm2:
                        rm2 -= 4

                    if ppod:
                        link_headers = " rx12(%d-5) rx13(%d-6) rx14(%d-7) rx15(%d-8) rx16(%d-1) rx17(%d-2) rx18(%d-3) rx19(%d-4) rx20(%d-5) rx21(%d-6) rx22(%d-7) rx23(%d-8)" % tuple([rm1] * 4 + [rm2] * 8)
                    else:
                        link_headers = " rx00(%d-1) rx01(%d-2) rx02(%d-3) rx03(%d-4) rx04(%d-5) rx05(%d-6) rx06(%d-7) rx07(%d-8) rx08(%d-1) rx09(%d-2) rx10(%d-3) rx11(%d-4)" % tuple([rm0] * 8 + [rm1] * 4)

            elif self.hf:
                if ppod:
                    link_headers = " rx12      rx13      rx14      rx15      rx16      rx17      rx18      rx19      rx20      rx21      rx22      rx23     "
                else:
                    link_headers = " rx00      rx01      rx02      rx03      rx04      rx05      rx06      rx07      rx08      rx09      rx10      rx11     "

            print(link[:19] + link_headers)
            self.uhtr_compare(slot, ppod, first, power, 330.0, threshold=120.0)
            self.uhtr_compare(slot, ppod, first, bad8b10b, 0, threshold=0)
            self.uhtr_compare(slot, ppod, first, bc0, 11.2, threshold=0.1)
            printer.gray(h1)
            self.uhtr_compare(slot, ppod, first, write_delay, 300, threshold=100000, dec=True)
            self.uhtr_compare(slot, ppod, first, read_delay, 300, threshold=100000, dec=True)
            self.uhtr_compare(slot, ppod, first, fifo_occ, 12, threshold=9, dec=True)
            self.uhtr_compare(slot, ppod, first, bprv, 0x1111, threshold=0)
            printer.gray(h2)
            self.uhtr_compare(slot, ppod, first, bad_full, 0, threshold=1, doubled=True)
            self.uhtr_compare(slot, ppod, first, invalid, 0, threshold=1)
            printer.gray(h3)

        return out


    def uhtr_compare(self, slot, ppod, first, lst, expected, threshold=None, doubled=False, dec=False):
        iStart, iEnd, items = self.uhtr_range_and_items(slot, ppod, lst, first)
        n = int((len(lst) - 19) / 12)
        if doubled:
            iStart *= 2
            iEnd *= 2
            n = int(n / 2)

        msg = lst[:19]
        for i, x in enumerate(items):
            try:
                result = int(x, 10 if dec else 16)
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

        print(msg)


    def uhtr_range_and_items(self, slot, ppod, lst, first):
        items = lst[19:].split()

        if self.rbx == "lasermon":
            if slot == 9 and not ppod:
                return 0, 1, items
            else:
                return 0, 0, items

        if self.hf:
            return 0, 12, items

        if (not self.usc) and self.sector:
            if (slot % 4) == 2:
                if ppod:
                    if not first:
                        return 0, 0, items
                else:
                    if first:
                        return 8, 12, items
                    else:
                        return 0, 8, items
            if (slot % 4) == 3:
                if first:
                    if ppod:
                        return 4, 12, items
                    else:
                        return 0, 0, items
                elif ppod:
                    return 0, 4, items

            return 0, 12, items

        # USC
        if (slot % 3) == 0:
            iStart = 1
            iEnd = 12  # include ngHE CU fibers
        if (slot % 3) == 1:
            if ppod:
                iStart = 0
                iEnd = 12
            else:
                iStart = 0
                iEnd = 12
        if (slot % 3) == 2:
            if ppod:
                iStart = 0
                iEnd = 12
            else:
                iStart = 2
                iEnd = 11  # include HB CU fiber

        return iStart, iEnd, items


    def check(self, items, device=None, timeout=5):
        for item, expected, threshold in items:
            if device is None:
                res = self.command("get %s-%s" % (self.rbx, item), timeout=timeout)
            else:
                res = self.command("get %s-%s" % (device, item), timeout=timeout)
            if expected is None:
                if "ERROR" not in res:
                    print(res)
            else:
                if threshold is None:
                    self.compare(res, expected)
                else:
                    self.compare_with_threshold(res, expected, threshold)


    def compare(self, res, expected, msg=""):
        fields = res.split("#")

        try:
            result = int(fields[1], 16 if fields[1].strip().startswith("0x") else 10)
        except ValueError:
            result = None
            if "ERROR" not in res:
                fields[1] = printer.red(fields[1], p=False)
                print("#".join(fields))
            self.bail()

        if result != expected and expected is not None:
            if "ERROR" not in res:
                fields[1] = printer.red(fields[1], p=False)
                print("%s   %s" % ("#".join(fields),
                                   printer.purple("(expected %s)" % str(expected), p=False)))
            self.bail([msg] if msg else [])
        else:
            print(res)


    def compare_with_threshold(self, res, expected, threshold, msg=""):
        fields = res.split("#")

        if " " in fields[1]:
            res1 = fields[1].split()
        elif type(fields[1]) is not list:
            res1 = [fields[1]]

        try:
            if res1[0].strip().startswith("0x"):
                results = [int(x, 16) for x in res1]
            else:
                results = [float(x) for x in res1]
        except ValueError:
            results = []
            if "ERROR" not in res:
                fields[1] = printer.red(fields[1], p=False)
                print("#".join(fields))
            self.bail()

        fail = []
        for iResult, result in enumerate(results):
            if threshold < abs(result - expected):
                fail.append(iResult)
                res1[iResult] = printer.red(res1[iResult], p=False)

        if fail:
            print("%s# %s   %s" % (fields[0],
                                   " ".join(res1),
                                   printer.purple("(expected %s +- %s)" % (str(expected), str(threshold)), p=False)))
            self.bail([msg] if msg else [])
        else:
            if "ERROR" not in res:
                print(res)


    def bail(self, lines=None, minimal=False, note=""):
        if lines:
            printer.red("\n".join(lines))
        if not self.options.keepgoing:
            self.disconnect()
            sys.exit(" " if lines else "")


if __name__ == "__main__":
    p = commissioner(*opts())
