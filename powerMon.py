#!/usr/bin/env python2

import driver
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
    return parser.parse_args()[0]


class powermon(driver.driver):
    def __init__(self, options):
        self.options = options
        self.connect()
        self.work()
        self.bail(minimal=True)


    def work(self):
        for rbx in self.options.rbxes.split(","):
            for card in ["J14", "J15"]:
                for var in ["vtrx_rssi", "3V3_bkp", "1V2_voltage", "1V2_current", "2V5_voltage", "VIN_voltage"]:
                    self.command("get %s-%s_%s_Cntrl_f_rr" % (rbx, var, card))

            self.command("get %s-fec-sfp_tx_power_f" % rbx)
            self.command("get %s-fec-sfp_rx_power_f" % rbx)

        if not self.options.noUhtr:
            for iPod in range(2):
                uhtr_powers = commandOutput("uHTRtool.exe -c 63:7 -s linkStatus.uhtr | grep PPOD%d -A 1 | tail -1" % iPod)
                s = " ".join(uhtr_powers).replace(" (uW)", "%d #" % iPod)
                self.logfile.write("\nget " + s)


def main():
    try:
        powermon(opts())
    except RuntimeError as e:
        printer.red(e[1])
        sys.exit(" ")


if __name__ == "__main__":
    main()
