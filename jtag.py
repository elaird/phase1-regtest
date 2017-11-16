#!/usr/bin/env python2

import ngfec, printer
import datetime, optparse, os, sys, time


def check_target(target):
    coords = target.split("-")
    fail = "Expected RBX-RM-QIEcard or RBX-calib or RBX-pulser or RBX-neigh.  Found %s" % str(target)

    if not coords:
        sys.exit(fail)

    rbx = coords[0]
    if not rbx.startswith("HE"):
        sys.exit("This script only works with HE RBXes.")

    if len(coords) == 2:
        if coords[1] not in ["neigh", "calib", "pulser"]:
            sys.exit(fail)
    elif len(coords) == 3:
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
    else:
        sys.exit(fail)

    return rbx


def opts():
    parser = optparse.OptionParser(usage="usage: %prog [options] FPGA_TARGET \n(implements https://twiki.cern.ch/twiki/bin/view/CMS/HCALngFECprotocol#Extra_steps_for_JTAG_programming)")
    parser.add_option("-H",
                      "--host",
                      dest="host",
                      default="hcal904daq04",
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
    parser.add_option("--stp-igloo",
                      dest="stpIgloo",
                      metavar="a.stp",
                      default="/nfshome0/elaird/firmware/fixed_HE_RM_v3_09.stp",
                      help="[default %default]")
    parser.add_option("--stp-pulser",
                      dest="stpPulser",
                      metavar="a.stp",
                      default="/nfshome0/elaird/firmware/HE_Pulser_Ver6_fixed_FREQ_1.stp",
                      help="[default %default]")
    parser.add_option("--stp-J15",
                      dest="stpJ15",
                      metavar="a.stp",
                      default="/nfshome0/elaird/firmware/HBHE_CCC_J15_half_speed_b2b_v5.2_20170928c.stp",
                      help="[default %default]")
    parser.add_option("--stp-J14",
                      dest="stpJ14",
                      metavar="a.stp",
                      default="/nfshome0/elaird/firmware/HBHE_CCC_J14_MM_half_speed_b2b_v5.2_20170928c.stp",
                      help="[default %default]")
    parser.add_option("--nseconds",
                      dest="nSeconds",
                      default=5,
                      type="int",
                      help="number of seconds over which to integrate link errors [default %default]")
    parser.add_option("--timeout-for-device-info",
                      dest="timeoutDeviceInfo",
                      default=30,
                      type="int",
                      help="how many seconds to spend gather device info before timing out [default %default]")
    parser.add_option("--timeout-for-verify",
                      dest="timeoutVerify",
                      default=140,
                      type="int",
                      help="how many seconds to spend verifying before timing out [default %default]")
    parser.add_option("--timeout-for-program",
                      dest="timeoutProgram",
                      default=180,
                      type="int",
                      help="how many seconds to spend programming before timing out [default %default]")
    parser.add_option("--skip-verify",
                      dest="skipVerify",
                      default=False,
                      action="store_true",
                      help="skip VERIFY")
    parser.add_option("--program",
                      dest="program",
                      default=False,
                      action="store_true",
                      help="do PROGRAM")

    options, args = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        sys.exit(" ")

    return options, args[0]


class programmer:
    def __init__(self, options, target):
        self.options = options
        self.target = target
        self.rbx = check_target(target)

        self.connect()

        self.check_version()
        self.disable()
        self.reset_fec()
        self.errors()
        self.jtag()
        self.check_version()

        self.bail()


    def connect(self):
        self.logfile = open(self.options.logfile, "a")
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
        return ngfec.command(self.server, cmd)[0]


    def check_version(self):
        if self.target.endswith("neigh"):
            cmd = "get %s_FPGA_SILSIG" % self.target.replace("neigh", "smezz")
        elif self.target.endswith("pulser"):
            cmd = "get %s-fpga" % self.target
        else:
            cmd = "get %s-i_FPGA_[MAJOR,MINOR]_VERSION_rr" % self.target

        print("Reading firmware version: %s" % self.command(cmd))


    def disable(self):
        print("Disabling Peltier control and guardian actions")
        # https://twiki.cern.ch/twiki/bin/view/CMS/HCALngFECprotocol#Extra_steps_for_JTAG_programming
        self.command("tput %s-[1-4]-g  %s-[1-4]s-sg  %s-calib-g %s-cg disable" % (self.rbx, self.rbx, self.rbx, self.rbx))
        self.command("put %s-[1-4]-peltier_control 4*0" % self.rbx)
        time.sleep(2)
        self.command("tput %s-[1-4]-[1-4]-B_[JTAG_Select_FPGA,JTAGSEL,JTAG_Select_Board,Bottom_TRST_N,Top_TRST_N,Bottom_RESET_N,Top_RESET_N,Igloo_VDD_Enable] enable" % self.rbx)
        self.command("tput %s-calib-B_[JTAG_Select_FPGA,JTAGSEL,JTAG_Select_Board,Bottom_TRST_N,Top_TRST_N,Bottom_RESET_N,Top_RESET_N,Igloo_VDD_Enable] enable" % self.rbx)


    def reset_fec(self):
        print("Resetting JTAG part of FEC")
        # ngfec.command(server, "put hefec3-cdce_sync 1")
        # ngfec.command(server, "put hefec3-cdce_sync 0")
        # ngfec.command(server, "put hefec3-gbt_bank_reset 0xff")
        # ngfec.command(server, "put hefec3-gbt_bank_reset 0x00")
        self.command("put %s-fec_jtag_part_reset 0" % self.rbx)
        self.command("put %s-fec_jtag_part_reset 1" % self.rbx)
        self.command("put %s-fec_jtag_part_reset 0" % self.rbx)


    def enable(self):
        print("Enabling Peltier control and guardian actions")
        self.command("tput %s-[1-4]-g  %s-[1-4]s-sg  %s-calib-g %s-cg enable" % (self.rbx, self.rbx, self.rbx, self.rbx))
        self.command("tput %s-lg push" % self.rbx)
        self.command("put %s-[1-4]-peltier_control 4*1" % self.rbx)


    def errors(self):
        print("Reading link error counters (integrating for %d seconds)" % self.options.nSeconds)
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
            self.bail(["pulser is not yet supported"])
        else:
            stp = self.options.stpIgloo

        self.check_stp(stp)

        self.action("DEVICE_INFO", stp, check_jtag=False)

        if not self.options.skipVerify:
            self.action("VERIFY", stp)

        if self.options.program:
            self.action("PROGRAM", stp)


    def action(self, word, stp, check_jtag=True):
        if word == "DEVICE_INFO":
            timeout = self.options.timeoutDeviceInfo
        if word == "VERIFY":
            timeout = self.options.timeoutVerify
        if word == "PROGRAM":
            timeout = self.options.timeoutProgram

        printer.cyan("%11s with %s (will time out in %3d seconds)" % (word, stp, timeout))
        lines = ngfec.command(self.server, "jtag %s %s %s" % (stp, self.target, word), timeout=timeout)
        check_exit_codes(lines)
        check_dsn(lines)
        if check_jtag:
            check_for_jtag_errors(lines)


    def bail(self, lines=None):
        if lines:
            printer.red("\n".join(lines))
        self.enable()
        self.disconnect()
        sys.exit()


def bail(lines):
        sys.exit("\n".join(lines))


def check_exit_codes(lines):
    if not lines[-2].endswith("# retcode=0"):
        bail(lines)
    if lines[-4] != 'Exit code = 0... Success':
        bail(lines)


def check_dsn(lines):
    for line in lines:
        if 'key = "DSN"' not in line:
            continue
        fields = line.split()
        value = fields[-1]
        try:
            if int(value, 16):
                return
        except ValueError:
            continue
    bail(lines)


def check_for_jtag_errors(lines):
    for line in lines:
        if "Authentication Error" in line:
            print "WAT1"
            bail(lines)
        if "Invalid/Corrupted programming file" in line:
            print "WAT2"
            bail(lines)
        if "ERROR_CODE" in line:
            fields = line.split()
            value = fields[-1]
            try:
                if int(value, 16):
                    bail(lines)
            except ValueError:
                bail(lines)


if __name__ == "__main__":
    p = programmer(*opts())
