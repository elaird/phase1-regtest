#!/usr/bin/env python2

import ngfec, printer
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
                      # default=64000,
                      default=64200,
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
                      # default="/nfshome0/elaird/firmware/fixed_HE_RM_v3_09_w_bypass_div8.stp",
                      help="[default %default]")
    parser.add_option("--stp-igloo-HB",
                      dest="stpIglooHb",
                      metavar="a.stp",
                      default="/nfshome0/elaird/firmware/fixed_HB_RM_v1_03.stp",
                      # default="/nfshome0/elaird/firmware/fixed_HB_RM_v1_03_w_bypass_div8.stp",
                      help="[default %default]")
    parser.add_option("--stp-pulser",
                      dest="stpPulser",
                      metavar="a.stp",
                      default="/nfshome0/elaird/firmware/HE_Pulser_Ver6_fixed_FREQ_1.stp",
                      help="[default %default]")
    parser.add_option("--stp-J15",
                      dest="stpJ15",
                      metavar="a.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J15_half_speed_b2b_v5.2_20170928c.stp",
                      default="/nfshome0/elaird/firmware/HBHE_CCC_J15_half_speed_both_v5.2_20170928c.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J15_half_speed_both_v5.3_20180824a.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J15_half_speed_both_20181126a_fixed.stp",
                      help="[default %default]")
    parser.add_option("--stp-J14",
                      dest="stpJ14",
                      metavar="a.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J14_MM_half_speed_b2b_v5.2_20170928c.stp",
                      default="/nfshome0/elaird/firmware/HBHE_CCC_J14_MM_half_speed_both_v5.2_20170928c.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J14_MM_half_speed_both_v5.3_20180824a.stp",
                      # default="/nfshome0/elaird/firmware/HBHE_CCC_J14_half_speed_both_20181126a_fixed.stp",
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


class programmer:
    def __init__(self, options, target):
        self.options = options
        self.target, self.rbx = check_target(target)
        self.target0 = self.target.split("-")[0]

        self.connect()

        if self.options.deviceInfoOnly:
            self.options.skipVerify = True
            self.options.program = False
            self.jtag()
            self.bail(minimal=True)
        else:
            self.check_version()
            self.ground0()
            self.disable()
            self.reset_fec()
            self.errors()
            self.jtag()
            self.check_version()
            self.bail()


    def connect(self):
        self.logfile = open(self.options.logfile, "a")
        if not self.options.deviceInfoOnly:
            printer.gray("Appending to %s (consider doing \"tail -f %s\" in another shell)" % (self.options.logfile, self.options.logfile))
        h = "-" * 30 + "\n"
        self.logfile.write(h)
        self.logfile.write("| %s |\n" % str(datetime.datetime.today()))
        self.logfile.write(h)

        # ngfec.survey_clients()
        ngfec.kill_clients()
        self.server = ngfec.connect(self.options.host, self.options.port, self.logfile)


    def disconnect(self):
        ngfec.disconnect(self.server)
        self.logfile.close()


    def command(self, cmd):
        out = ngfec.command(self.server, cmd)[0]
        if "ERROR" in out:
            print(out)
        return out


    def check_version(self):
        if self.target.endswith("neigh"):
            cmd = "get %s_FPGA_SILSIG" % self.target.replace("neigh", "smezz")
        elif self.target.endswith("pulser"):
            cmd = "get %s-fpga" % self.target.replace(self.target0, self.rbx)
        else:
            if hb(self.rbx):
                s = self.target.replace(self.target0, self.rbx).replace("top", "iTop").replace("bot", "iBot")
                cmd = "get %s_FPGA_[MAJOR,MINOR]_VERSION_rr" % s
            else:
                cmd = "get %s-i_FPGA_[MAJOR,MINOR]_VERSION_rr" % self.target

        print("Reading firmware version: %s" % self.command(cmd))


    def ground0(self):
        if self.options.ground0:
            print("Ground stating")
            self.command("tput %s-lg go_offline" % self.rbx)
            self.command("tput %s-lg ground0" % self.rbx)
            self.command("tput %s-lg waitG" % self.rbx)
            self.command("tput %s-lg push" % self.rbx)


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


    def reset_fec(self):
        if not hb(self.rbx):
            print("Resetting JTAG part of FEC")
            # ngfec.command(server, "put hefec3-cdce_sync 1")
            # ngfec.command(server, "put hefec3-cdce_sync 0")
            # ngfec.command(server, "put hefec3-gbt_bank_reset 0xff")
            # ngfec.command(server, "put hefec3-gbt_bank_reset 0x00")
            self.command("put %s-fec_jtag_part_reset 0" % self.target0)
            self.command("put %s-fec_jtag_part_reset 1" % self.target0)
            self.command("put %s-fec_jtag_part_reset 0" % self.target0)


    def enable(self):
        print("Enabling Peltier control, guardian actions, and auto power-off")
        self.command("tput %s-[1-4]-g  %s-[1-4]s-sg  %s-calib-g enable" % (self.rbx, self.rbx, self.rbx))
        self.command("tput %s-cg enable" % self.target0)
        self.command("tput %s-lg push" % self.rbx)
        self.command("put %s-[1-4]-peltier_control 4*1" % self.rbx)
        self.command("put %s-lg_do_auto_pwr_off 1" % self.target0)


    def errors(self, store=True):
        msg = "Reading link error counters"
        if store:
            msg += " (integrating for %d seconds)" % self.options.nSeconds

        print(msg)
        fec = "get %s-fec_[rx_prbs_error,dv_down]_cnt_rr" % self.target0
        ccm = "get %s-mezz_rx_[prbs,rsdec]_error_cnt_rr" % self.target0
        b2b = "get %s-[,s]b2b_rx_[prbs,rsdec]_error_cnt_rr" % self.target0

        if store:
            self.fec1 = self.command(fec)
            self.ccm1 = self.command(ccm)
            self.b2b1 = self.command(b2b)
            time.sleep(self.options.nSeconds)

        fec2 = self.command(fec)
        ccm2 = self.command(ccm)
        b2b2 = self.command(b2b)

        minimal = not store

        if self.fec1 != fec2:
            self.bail(["Link errors detected via FEC counters:", self.fec1[0], fec2[0]], minimal)
        if self.ccm1 != ccm2:
            self.bail(["Link errors detected via CCM counters:", self.ccm1[0], ccm2[0]], minimal)
        if self.b2b1 != b2b2:
            self.bail(["Link errors detected via CCM counters:", self.b2b1, b2b2], minimal)


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
        else:
            stp = self.options.stpIglooHb if hb(self.rbx) else self.options.stpIglooHe

        self.check_stp(stp)

        if self.target.endswith("pulser"):
            self.action("DEVICE_INFO", stp, 30, key="FSN", check_jtag=False)
        else:
            self.action("DEVICE_INFO", stp, 30, check_jtag=False)

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
        lines = ngfec.command(self.server, "jtag %s %s %s" % (stp, self.target, word), timeout=timeout)
        self.check_exit_codes(lines)
        self.check_key(lines, key)
        if check_jtag:
            self.check_for_jtag_errors(lines)


    def bail(self, lines=[], minimal=False, note=""):
        if note:
            printer.purple(note)
        if lines:
            printer.red("\n".join(lines))

        if not minimal:
            self.enable()
            self.errors(store=False)

        self.disconnect()

        if lines:
            sys.exit(" ")  # non-zero return code
        else:
            sys.exit()


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


if __name__ == "__main__":
    p = programmer(*opts())
