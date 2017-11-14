#!/usr/bin/env python2

import ngfec
import datetime, optparse, os, sys, time


def check_stp(stp):
    if not os.path.exists(stp):
        sys.exit("A file with name '%s' does not exist." % stp)


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


def main(options, target):
    rbx = check_target(target)
    # ngfec.survey_clients()
    ngfec.kill_clients()

    logfile = open(options.logfile, "a")
    print("Appending to %s (consider doing \"tail -f %s\" in another shell)" % (options.logfile, options.logfile))
    h = "-" * 30 + "\n"
    logfile.write(h)
    logfile.write("| %s |\n" % str(datetime.datetime.today()))
    logfile.write(h)
    server = ngfec.connect(options.host, options.port, logfile)
    work(server, target, rbx, options)
    ngfec.disconnect(server)
    logfile.close()


def work(server, target, rbx, options):
    check_version(server, target)
    disable(server, rbx)
    reset_fec(server, rbx)
    errors(server, rbx, options.nSeconds)
    jtag(server, target, options)
    enable(server, rbx)
    check_version(server, target)


def check_version(server, target):
    if target.endswith("neigh"):
        print("Reading firmware version: %s" % ngfec.command(server, "get %s_FPGA_SILSIG" % target.replace("neigh", "smezz"))[0])
    elif target.endswith("pulser"):
        print("Reading firmware version: %s" % ngfec.command(server, "get %s-fpga" % target)[0])
    else:
        print("Reading firmware version: %s" % ngfec.command(server, "get %s-i_FPGA_[MAJOR,MINOR]_VERSION_rr" % target)[0])


def errors(server, rbx, nSeconds):
    print("Reading link error counters (integrating for %d seconds)" % nSeconds)
    fec = "get %s-fec_[rx_prbs_error,rxlos,dv_down,rx_raw_error]_cnt_rr" % rbx
    ccm = "get %s-mezz_rx_[prbs,rsdec]_error_cnt_rr" % rbx
    fec1 = ngfec.command(server, fec)
    ccm1 = ngfec.command(server, ccm)

    time.sleep(nSeconds)
    fec2 = ngfec.command(server, fec)
    ccm2 = ngfec.command(server, ccm)
    if fec1 != fec2:
        bail(["Link errors detected via FEC counters:", fec1[0], fec2[0]])
    if ccm1 != ccm2:
        bail(["Link errors detected via CCM counters:", ccm1[0], ccm2[0]])


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


def action(word, server, target, stp, timeout, check_jtag=True):
    print("%11s with %s (will time out in %3d seconds)" % (word, stp, timeout))
    lines = ngfec.command(server, "jtag %s %s %s" % (stp, target, word), timeout=timeout)
    check_exit_codes(lines)
    check_dsn(lines)
    if check_jtag:
        check_for_jtag_errors(lines)


def jtag(server, target, options):
    if target.endswith("neigh"):
        mezz = ngfec.command(server, "get %s_GEO_ADDR" % target.replace("neigh", "mezz"))[0]

        try:
            mezz_geo_addr = int(mezz.split("#")[1])
        except ValueError:
            sys.exit("unexpected GEO_ADDR: %s" % mezz)

        if mezz_geo_addr == 1:
            stp = options.stpJ15  # for smezz
        elif mezz_geo_addr == 2:
            stp = options.stpJ14  # for smezz
        else:
            sys.exit("unexpected GEO_ADDR: %s" % mezz)

        print(mezz)
    elif target.endswith("pulser"):
        stp = options.stpPulser
        sys.exit("pulser not yet supported")
    else:
        stp = options.stpIgloo

    check_stp(stp)

    action("DEVICE_INFO", server, target, stp, options.timeoutDeviceInfo, check_jtag=False)

    if not options.skipVerify:
        action("VERIFY", server, target, stp, options.timeoutVerify)

    if options.program:
        action("PROGRAM", server, target, stp, options.timeoutProgram)


def disable(server, rbx):
    print("Disabling Peltier control and guardian actions")
    # https://twiki.cern.ch/twiki/bin/view/CMS/HCALngFECprotocol#Extra_steps_for_JTAG_programming
    ngfec.command(server, "tput %s-[1-4]-g  %s-[1-4]s-sg  %s-calib-g %s-cg disable" % (rbx, rbx, rbx, rbx))
    ngfec.command(server, "put %s-[1-4]-peltier_control 4*0" % rbx)
    time.sleep(2)
    ngfec.command(server, "tput %s-[1-4]-[1-4]-B_[JTAG_Select_FPGA,JTAGSEL,JTAG_Select_Board,Bottom_TRST_N,Top_TRST_N,Bottom_RESET_N,Top_RESET_N,Igloo_VDD_Enable] enable" % rbx)
    ngfec.command(server, "tput %s-calib-B_[JTAG_Select_FPGA,JTAGSEL,JTAG_Select_Board,Bottom_TRST_N,Top_TRST_N,Bottom_RESET_N,Top_RESET_N,Igloo_VDD_Enable] enable" % rbx)


def reset_fec(server, rbx):
    print("Resetting JTAG part of FEC")
    # ngfec.command(server, "put hefec3-cdce_sync 1")
    # ngfec.command(server, "put hefec3-cdce_sync 0")
    # ngfec.command(server, "put hefec3-gbt_bank_reset 0xff")
    # ngfec.command(server, "put hefec3-gbt_bank_reset 0x00")
    ngfec.command(server, "put %s-fec_jtag_part_reset 0" % rbx)
    ngfec.command(server, "put %s-fec_jtag_part_reset 1" % rbx)
    ngfec.command(server, "put %s-fec_jtag_part_reset 0" % rbx)


def enable(server, rbx):
    print("Enabling Peltier control and guardian actions")
    ngfec.command(server, "tput %s-[1-4]-g  %s-[1-4]s-sg  %s-calib-g %s-cg enable" % (rbx, rbx, rbx, rbx))
    ngfec.command(server, "tput %s-lg push" % rbx)
    ngfec.command(server, "put %s-[1-4]-peltier_control 4*1" % rbx)


if __name__ == "__main__":
    main(*opts())
