#!/usr/bin/env python2

import driver, printer
import datetime, optparse, os, sys, time


def hb(rbx):
    return rbx[1] == "B"


def check_rm(coords):
    try:
        rm = int(coords[1])
    except ValueError:
        sys.exit("RM must be 1, 2, 3, or 4.")

    if rm < 1 or 4 < rm:
        sys.exit("RM must be 1, 2, 3, or 4.")
    try:
        q = int(coords[2])
    except ValueError:
        sys.exit("QIEcard must be 1, 2, 3, or 4.")
    if q < 1 or 4 < q:
        sys.exit("QIEcard must be 1, 2, 3, or 4.")


def check_tb(coords, fail):
    if coords[-1] not in ["top", "bot", "iTop", "iBot"]:
        sys.exit(fail)


def check_target(target):
    coords = target.split("-")
    fail = "Expected RBX[a/b]-RM-QIEcard[-top/bot] or RBX-calib[-top/bot] or RBX-pulser or RBX[a/b]-neigh.  Found %s" % str(target)

    if not coords:
        sys.exit(fail)

    rbx = coords[0]
    if not (rbx.startswith("HB") or rbx.startswith("HE")):
        sys.exit("This script only works with HB or HE RBXes.")

    if len(coords) == 2:
        if coords[1] not in (["neigh", "pulser"] + ([] if hb(rbx) else ["calib"])):
            sys.exit(fail)
        if coords[1] == "neigh" and hb(rbx) and rbx[-1] not in "ab":
            sys.exit(fail)

    elif len(coords) == 3 and hb(rbx):
        if coords[1] != "calib":
            sys.exit(fail)
        check_tb(coords, fail)
    elif len(coords) == 3 and not hb(rbx):
        check_rm(coords)
    elif len(coords) == 4:
        if not hb(rbx):
            sys.exit(fail)
        check_rm(coords)
        check_tb(coords, fail)
    else:
        sys.exit(fail)

    if hb(rbx):
        if rbx[-1] in "ab":
            rbx = rbx[:-1]
        else:
            letter = "a" if coords[1] in ["pulser", "calib", "1", "2"] else "b"
            target = "-".join([coords[0] + letter] + coords[1:])

    target = target.replace("iTop", "top").replace("iBot", "bot")
    return target, rbx


def opts(full_rbx=False):
    target = "RBX" if full_rbx else "FPGA_TARGET"
    parser = optparse.OptionParser(usage="\n".join(["usage: %prog [options] " + target,
                                                    "(implements https://twiki.cern.ch/twiki/bin/view/CMS/HCALngFECprotocol#Extra_steps_for_JTAG_programming)"
                                                ]))
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
                      default="jtag.log",
                      help="log file to which to append [default %default]")
    parser.add_option("--stp-igloo-HE",
                      dest="stpIglooHe",
                      metavar="a.stp",
                      default="/nfshome0/elaird/firmware/fixed_HE_RM_v3_09.stp",
                      help="[default %default]")
    parser.add_option("--stp-igloo-HE-bypass-test",
                      dest="stpIglooHeBypassTest",
                      metavar="a.stp",
                      # default="/nfshome0/elaird/firmware/fixed_HE_RM_v3_09_w_bypass_div8_max10.stp",  # always fails bypass_test
                      default="/nfshome0/elaird/firmware/fixed_HE_RM_v3_09_w_bypass_div8_max10_freq.stp",
                      # default="/nfshome0/elaird/firmware/fixed_HE_RM_v3_09_w_bypass_div8_max10_freq_shift.stp",
                      help="[default %default]")
    parser.add_option("--stp-igloo-HB",
                      dest="stpIglooHb",
                      metavar="a.stp",
                      default="/nfshome0/elaird/firmware/fixed_HB_RM_v1_03.stp",
                      help="[default %default]")
    parser.add_option("--stp-igloo-HB-bypass-test",
                      dest="stpIglooHbBypassTest",
                      metavar="a.stp",
                      # default="/nfshome0/elaird/firmware/fixed_HB_RM_v1_03_w_bypass_div8_max10.stp",  # always fails bypass_test
                      default="/nfshome0/elaird/firmware/fixed_HB_RM_v1_03_w_bypass_div8_max10_freq.stp",
                      help="[default %default]")
    parser.add_option("--stp-pulser",
                      dest="stpPulser",
                      metavar="a.stp",
                      # default="/nfshome0/elaird/firmware/HE_Pulser_ASIC_v7_FIXED_FREQ1.stp",
                      default="/nfshome0/elaird/firmware/HE_Pulser_ASIC_v7_FIXED_FREQ4.stp",
                      help="[default %default]")
    parser.add_option("--stp-J15",
                      dest="stpJ15",
                      metavar="a.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J15_half_speed_b2b_v5.2_20170928c.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J15_half_speed_both_v5.2_20170928c.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J15_half_speed_both_v5.3_20180824a.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J15_half_speed_both_20181126a_fixed.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J15_half_speed_both_DownReg_20181203c_fixed.stp",
                      default="/nfshome0/sdg/phase1-regtest/HBHE_CCC_J15_half_speed_both_20190119a_fixed.stp",
                      help="[default %default]")
    parser.add_option("--stp-J14",
                      dest="stpJ14",
                      metavar="a.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J14_MM_half_speed_b2b_v5.2_20170928c.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J14_MM_half_speed_both_v5.2_20170928c.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J14_MM_half_speed_both_v5.3_20180824a.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J14_half_speed_both_20181126a_fixed.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J14_half_speed_both_DownReg_20181203c_fixed.stp",
                      default="/nfshome0/sdg/phase1-regtest/HBHE_CCC_J14_half_speed_both_20190119a_fixed.stp",
                      help="[default %default]")
    parser.add_option("--nseconds",
                      dest="nSeconds",
                      default=5,
                      type="int",
                      help="number of seconds over which to integrate link errors [default %default]")
    parser.add_option("--ground0",
                      dest="ground0",
                      default=False,
                      action="store_true",
                      help="first, do ground0")
    parser.add_option("--device-info-only",
                      dest="deviceInfoOnly",
                      default=False,
                      action="store_true",
                      help="only do device info")
    parser.add_option("--skip-device-info",
                      dest="skipDeviceInfo",
                      default=False,
                      action="store_true",
                      help="skip DEVICE_INFO")
    parser.add_option("--skip-verify",
                      dest="skipVerify",
                      default=False,
                      action="store_true",
                      help="skip VERIFY")
    parser.add_option("--bypass-test",
                      dest="bypassTest",
                      default=False,
                      action="store_true",
                      help="do BYPASS_TEST")
    if full_rbx:
        parser.add_option("--niterations",
                          dest="nIterations",
                          metavar="N",
                          default=2,
                          type="int",
                          help="number of tries [default %default]")
    else:
        parser.add_option("--program",
                          dest="program",
                          default=False,
                          action="store_true",
                          help="do PROGRAM")

    options, args = parser.parse_args()

    if full_rbx:  # avoid programming entire RBX
        options.program = False

    if len(args) != 1:
        parser.print_help()
        sys.exit(" ")

    return options, args[0]


class programmer(driver.driver):
    def __init__(self, options, target):
        self.options = options
        if self.options.deviceInfoOnly:
            self.options.skipVerify = True
            self.options.program = False
            functions = ["jtag"]
        else:
            functions = ["check_version", "ground0", "disable", "errors", "jtag", "wait", "check_version"]

        self.target, self.rbx = check_target(target)
        self.target0 = self.target.split("-")[0]

        self.connect(quiet=self.options.deviceInfoOnly)

        for name in functions:
            getattr(self, name)()

        self.bail(minimal=self.options.deviceInfoOnly)


    def wait(self):
        if self.options.program:
            time.sleep(5)


    def check_version(self):
        if self.target.endswith("neigh"):
            cmd = "get %s_FPGA_SILSIG_rr" % self.target.replace("neigh", "smezz")
        elif self.target.endswith("pulser"):
            cmd = "get %s-fpga" % self.target.replace(self.target0, self.rbx)
        else:
            if hb(self.rbx):
                s = self.target.replace(self.target0, self.rbx).replace("top", "iTop").replace("bot", "iBot")
                cmd = "get %s_FPGA_[MAJOR,MINOR]_VERSION_rr" % s
            else:
                cmd = "get %s-i_FPGA_[MAJOR,MINOR]_VERSION_rr" % self.target

        print("Reading firmware version: %s" % self.command(cmd))


    def disable(self):
        print("Disabling Peltier control, guardian actions, and auto power-off")
        # https://twiki.cern.ch/twiki/bin/view/CMS/HCALngFECprotocol#Extra_steps_for_JTAG_programming
        self.command("tput %s-[1-4]-g  %s-[1-4]s-sg  %s-calib-g disable" % (self.rbx, self.rbx, self.rbx))
        self.command("tput %s-cg disable" % self.target0)
        self.command("put %s-[1-4]-peltier_control 4*0" % self.rbx)
        self.command("put %s-lg_do_auto_pwr_off 0" % self.target0)
        time.sleep(2)
        stuff = "B_[JTAG_Select_FPGA,JTAGSEL,JTAG_Select_Board,Bottom_TRST_N,Top_TRST_N,Bottom_RESET_N,Top_RESET_N,Igloo_VDD_Enable]"
        self.command("tput %s-[1-4]-[1-4]-%s enable" % (self.rbx, stuff))
        self.command("tput %s-calib-%s enable" % (self.rbx, stuff))
        self.command("tput %s-bkp_jtag_sel %s-sel_sec_jtag enable" % (self.target0, self.target0))


    def enable(self):
        print("Enabling Peltier control, guardian actions, and auto power-off")
        self.command("tput %s-[1-4]-g  %s-[1-4]s-sg  %s-calib-g enable" % (self.rbx, self.rbx, self.rbx))
        self.command("tput %s-cg enable" % self.target0)
        self.command("tput %s-lg push" % self.rbx)
        self.command("put %s-[1-4]-peltier_control 4*1" % self.rbx)
        self.command("put %s-lg_do_auto_pwr_off 1" % self.target0)


    def check_stp(self, stp):
        if not os.path.exists(stp):
            self.bail(["A file with name '%s' does not exist." % stp])


    def jtag(self):
        if self.target.endswith("neigh"):
            mezz = self.command( "get %s_GEO_ADDR" % self.target.replace("neigh", "mezz"))

            try:
                mezz_geo_addr = int(mezz.split("#")[1])
            except ValueError:
                self.bail(["Unexpected GEO_ADDR: %s" % mezz])

            if mezz_geo_addr == 1:
                stp = self.options.stpJ15  # for smezz
            elif mezz_geo_addr == 2:
                stp = self.options.stpJ14  # for smezz
            else:
                self.bail(["Unexpected GEO_ADDR: %s" % mezz])

            print(mezz)
        elif self.target.endswith("pulser"):
            stp = self.options.stpPulser
        elif hb(self.rbx):
            stp = self.options.stpIglooHbBypassTest if self.options.bypassTest else self.options.stpIglooHb
        else:
            stp = self.options.stpIglooHeBypassTest if self.options.bypassTest else self.options.stpIglooHe

        self.check_stp(stp)

        if not self.options.skipDeviceInfo:
            if self.target.endswith("pulser"):
                self.action("DEVICE_INFO", stp, 30, key="FSN", check_jtag=False)
            else:
                self.action("DEVICE_INFO", stp, 30)

        if not self.options.skipVerify:
            if self.target.endswith("pulser"):
                self.action("VERIFY", stp, 500, key="FSN")
            else:
                self.action("VERIFY", stp, 140)

        if self.options.bypassTest:
            if "pulser" in self.target or "neigh" in self.target:
                pass
            else:
                self.action("BYPASS_TEST", stp, 240, key="IDCODE")

        if self.options.program:
            if self.target.endswith("pulser"):
                self.action("PROGRAM", stp, 700, key="FSN")
            else:
                self.action("PROGRAM", stp, 180)


    def action(self, word, stp, timeout, key="DSN", check_jtag=True):
        printer.cyan("%11s with %s (will time out in %4d seconds)" % (word, stp, timeout))
        lines = self.command("jtag %s %s %s" % (stp, self.target, word), timeout=timeout, only_first_line=False)
        self.check_exit_codes(lines)
        self.check_key(lines, key)
        if check_jtag:
            self.check_for_jtag_errors(lines)


    def check_exit_codes(self, lines):
        if not lines[-2].endswith("# retcode=0"):
            self.bail(lines, note="retcode")
        if lines[-4] != 'Exit code = 0... Success':
            self.bail(lines, note="exitcode")


    def check_key(self, lines, key):
        for line in lines:
            if 'key = "%s"' % key not in line:
                continue
            fields = line.split()
            value = fields[-1]
            try:
                if int(value, 16):
                    return
            except ValueError:
                continue
        self.bail(lines, note="key")


    def check_for_jtag_errors(self, lines):
        for line in lines:
            if "Authentication Error" in line:
                self.bail(lines, note="auth")
            if "Invalid/Corrupted programming file" in line:
                self.bail(lines, note="invalid")
            if "ERROR_CODE" in line:
                fields = line.split()
                value = fields[-1]
                try:
                    if int(value, 16):
                        self.bail(lines)
                except ValueError:
                    self.bail(lines, note="errorcode")


def main():
    try:
        programmer(*opts())
    except RuntimeError as e:
        printer.red(e[1])
        sys.exit(" ")


if __name__ == "__main__":
    main()
