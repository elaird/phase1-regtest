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

    return parser.parse_args()


def main(options, _):
    ngfec.kill_clients()

    # ccmLogfile = open(options.logfile + ".ccm", "a")
    # ccmLogfile.write("\n" + str(datetime.datetime.today()))

    logfile = open(options.logfile, "a")
    logfile.write("\n" + str(datetime.datetime.today()))

    server = ngfec.connect(options.host, options.port) #, ccmLogfile)
    work(server, logfile)
    ngfec.disconnect(server)

    # ccmLogfile.close()
    logfile.write("\n")
    logfile.close()


def work(server, logfile):
    logfile.write("\n" + ngfec.command(server, "get HE[7,8]-vtrx_rssi_J15_Cntrl_f_rr")[0])
    logfile.write("\n" + ngfec.command(server, "get HE[7,8]-fec-sfp_tx_power_f")[0])
    uhtr_powers = commandOutput("uHTRtool.exe -c 63:1 -s linkStatus.uhtr | grep PPOD0 -A 1 | tail -1")
    s = " ".join(uhtr_powers).replace("(uW)", "#")
    logfile.write("\nget " + s)


if __name__ == "__main__":
    main(*opts())
