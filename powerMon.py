#!/usr/bin/env python2

import ngfec
import datetime, optparse, os, subprocess, sys, time


def commandOutput(cmd=""):
    return commandOutputFull(cmd)["stdout"].split()


def commandOutputFull(cmd=""):
    p = subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         )
    stdout, stderr = p.communicate()
    return {"stdout": stdout, "stderr": stderr, "returncode": p.returncode}


def opts():
    parser = optparse.OptionParser(usage="usage: %prog [options]")
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
                      default="/nfshome0/elaird/powerMon.log")
    parser.add_option("--rbxes",
                      dest="rbxes",
                      default="HE1,HE2,HE3,HE4,HE5,HE6,HE7,HE8,HE9,HE10,HE11,HE12,HE13,HE14,HE15,HE16,HE17,HE18")
    parser.add_option("--no-uhtr",
                      dest="noUhtr",
                      default=False,
                      action="store_true")
    return parser.parse_args()


def main(options, _):
    ngfec.kill_clients()

    # ccmLogfile = open(options.logfile + ".ccm", "a")
    # ccmLogfile.write("\n" + str(datetime.datetime.today()))

    logfile = open(options.logfile, "a")
    logfile.write("\n" + str(datetime.datetime.today()))

    server = ngfec.connect(options.host, options.port) #, ccmLogfile)
    work(server, logfile, options.rbxes.split(","), not options.noUhtr)
    ngfec.disconnect(server)

    # ccmLogfile.close()
    logfile.write("\n")
    logfile.close()


def work(server, logfile, rbxes, uhtr):
    for rbx in rbxes:
        for card in ["J14", "J15"]:
            for var in ["vtrx_rssi", "3V3_bkp", "1V2_voltage", "1V2_current", "2V5_voltage", "VIN_voltage"]:
                logfile.write("\n" + ngfec.command(server, "get %s-%s_%s_Cntrl_f_rr" % (rbx, var, card))[0])

        logfile.write("\n" + ngfec.command(server, "get %s-fec-sfp_tx_power_f" % rbx)[0])
        logfile.write("\n" + ngfec.command(server, "get %s-fec-sfp_rx_power_f" % rbx)[0])

    if uhtr:
        for iPod in range(2):
            uhtr_powers = commandOutput("uHTRtool.exe -c 63:7 -s linkStatus.uhtr | grep PPOD%d -A 1 | tail -1" % iPod)
            s = " ".join(uhtr_powers).replace(" (uW)", "%d #" % iPod)
            logfile.write("\nget " + s)


if __name__ == "__main__":
    main(*opts())
