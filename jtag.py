#!/usr/bin/env python2

import ngfec
import datetime, optparse, os, sys, time


def check_stp(stp):
    if not os.path.exists(stp):
        sys.exit("A file with name '%s' does not exist." % stp)


def check_target(target):
    coords = target.split("-")
    if not coords:
        sys.exit("Expected RBX-RM-QIEcard or RBX-calib.  Found %s" % coords)

    rbx = coords[0]
    if not rbx.startswith("HE"):
        sys.exit("This script only works with HE RBXes.")

    if len(coords) == 2:
        if coords[1] != "calib":
            sys.exit("Expected RBX-RM-QIEcard or RBX-calib")
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
        sys.exit("Expected RBX-RM-QIEcard or RBX-calib.  Found %s" % coords)

    return rbx


def opts():
    parser = optparse.OptionParser(usage="usage: %prog [options] FPGA_TARGET \n(implements https://twiki.cern.ch/twiki/bin/view/CMS/HCALngFECprotocol#Extra_steps_for_JTAG_programming)")
    parser.add_option("-H",
                      "--host",
                      dest="host",
                      default="hcal904daq04",
                      help="ngccmserver host")
    parser.add_option("-p",
                      "--port",
                      dest="port",
                      default=64000,
                      type="int",
                      help="ngccmserver port number")
    parser.add_option("--log-file",
                      dest="logfile",
                      default="jtag.log",
                      help="log file to which to append")
    parser.add_option("--stp-for-verify",
                      dest="stpForVerify",
                      default="/nfshome0/tgrassi/fw/HE/fixed_HE_RM_v3_03.stp",
                      help=".stp file")
    parser.add_option("--stp-for-program",
                      dest="stpForProgram",
                      default="/nfshome0/tgrassi/fw/HE/fixed_HE_RM_v3_03.stp",
                      help=".stp file")
    parser.add_option("--nseconds",
                      dest="nSeconds",
                      default=10,
                      type="int",
                      help="number of seconds over which to integrate link errors")
    parser.add_option("--timeout-for-device-info",
                      dest="timeoutDeviceInfo",
                      default=15,
                      type="int",
                      help="how many seconds to spend gather device info before timing out")
    parser.add_option("--timeout-for-verify",
                      dest="timeoutVerify",
                      default=140,
                      type="int",
                      help="how many seconds to spend verifying before timing out")
    parser.add_option("--timeout-for-program",
                      dest="timeoutProgram",
                      default=140,
                      type="int",
                      help="how many seconds to spend programming before timing out")

    options, args = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        sys.exit(" ")

    return options, args[0]


def main(options, target):
    rbx = check_target(target)
    for stp in [options.stpForVerify, options.stpForProgram]:
        check_stp(stp)
    # ngfec.survey_clients()
    ngfec.kill_clients()

    logfile = open(options.logfile, "a")
    print("Appending to %s (consider doing ' tail -f %s ' in another shell)" % (options.logfile, options.logfile))
    h = "-" * 30 + "\n"
    logfile.write(h)
    logfile.write("| %s |\n" % str(datetime.datetime.today()))
    logfile.write(h)
    server = ngfec.connect(options.host, options.port, logfile)
    work(server, target, rbx, options)
    ngfec.disconnect(server)
    logfile.close()


def work(server, target, rbx, options):
    disable(server, rbx)
    reset_fec(server, rbx)
    errors(server, rbx, options.nSeconds)
    jtag(server, target, options)
    enable(server, rbx)


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
        sys.exit("Link errors detected via FEC counters.")
    if ccm1 != ccm2:
        sys.exit("Link errors detected via CCM counters.")


def jtag(server, target, options):
    print("Reading DEVICE_INFO (timeout %d seconds)" % options.timeoutDeviceInfo)
    ngfec.command(server, "jtag %s %s DEVICE_INFO" % (options.stpForVerify, target), timeout=options.timeoutDeviceInfo)

    print("VERIFYing against %s (timeout %d seconds)" % (options.stpForVerify, options.timeoutVerify))
    ngfec.command(server, "jtag %s %s VERIFY" % (options.stpForVerify, target), timeout=options.timeoutVerify)

    # print("PROGRAMming with %s" % stpForProgram)


def disable(server, rbx):
    print("Disabling Peltier control")
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
    print("Enabling Peltier control")
    ngfec.command(server, "tput %s-[1-4]-g  %s-[1-4]s-sg  %s-calib-g %s-cg enable" % (rbx, rbx, rbx, rbx))
    ngfec.command(server, "tput %s-lg push" % rbx)
    ngfec.command(server, "put %s-[1-4]-peltier_control 4*1" % rbx)


if __name__ == "__main__":
    main(*opts())
