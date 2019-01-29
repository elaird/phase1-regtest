#!/usr/bin/env python2

import printer
import collections, datetime, os, pexpect, re, sys, time


class driver:
    def __init__(self, options, target):
        self.options = options
        self.rbx = target
        self.target = target

        self.connect()
        self.guardians()
        self.bail(minimal=True)


    def enable(self):
        pass


    def errors(self, store=True, letter="", fec=True, ccm=True, sleep=True, old=False):
        msg = "Reading link error counters ("
        if letter:
            msg += letter + ","
        if fec:
            msg += "fec,"
        if ccm:
            msg += "ccm,"
        if store:
            msg += "store,"
            if sleep:
                msg += "integrating for %d seconds" % self.options.nSeconds
        msg += ")"

        if hasattr(self, "target0"):
            target0 = self.target0
        else:
            target0 = self.rbx + letter

        print(msg)
        if old:
            fec_cmd = "get %s-fec_dv_down_cnt_rr" % target0
        else:
            fec_cmd = "get %s-fec_[rx_rs_err,dv_down]_cnt_rr" % target0
        ccm_cmd = "get %s-mezz_rx_[prbs,rsdec]_error_cnt_rr" % target0
        b2b_cmd = "get %s-[,s]b2b_rx_[prbs,rsdec]_error_cnt_rr" % target0

        if store:
            if fec:
                self.fec1 = self.command(fec_cmd)
            if ccm:
                self.ccm1 = self.command(ccm_cmd)
                self.b2b1 = self.command(b2b_cmd)
            if sleep:
                time.sleep(self.options.nSeconds)

        if fec:
            fec2 = self.command(fec_cmd)
        if ccm:
            ccm2 = self.command(ccm_cmd)
            b2b2 = self.command(b2b_cmd)
        minimal = not store

        if fec and "ERROR" in self.fec1:
            self.bail([""], minimal=minimal, note="fec_err")
        elif ccm and "ERROR" in self.ccm1:
            self.bail([""], minimal=minimal, note="ccm_err")
        elif ccm and "ERROR" in self.b2b1:
            self.bail([""], minimal=minimal, note="ccm_err")
        elif fec and self.fec1 != fec2:
            self.bail(["Link errors detected via FEC counters:", self.fec1, fec2], minimal=minimal, note="fec_ber")
        elif ccm and self.ccm1 != ccm2:
            self.bail(["Link errors detected via CCM counters:", self.ccm1, ccm2], minimal=minimal, note="ccm_ber")
        elif ccm and self.b2b1 != b2b2:
            lines = ["Link errors detected via CCM counters:", self.b2b1, b2b2]
            if store or (not self.target.endswith("neigh")):
                self.bail(lines, minimal=minimal, note="b2b_ber")
            else:  # don't exit due to b2b errors generated by using jtag/neigh
                printer.red("\n".join(lines))


    def ground0(self):
        if self.options.ground0:
            print("Ground stating (go_offline, ground0, waitG, push)")
            self.command("tput %s-lg go_offline" % self.rbx)
            self.command("tput %s-lg ground0" % self.rbx)
            self.command("tput %s-lg waitG" % self.rbx)
            self.command("tput %s-lg push" % self.rbx)


    def guardians(self):
        print("-" * 10)
        print("| server |")
        print("-" * 10)

        print self.command("get ccmserver_version")
        # print self.command("table")
        # print self.command("tget %s-lg fns3G" % self.rbx)


    def bail(self, lines=[], minimal=False, note="unspecified", tail=False):
        if lines:
            printer.purple("Exiting due to \"%s\"" % note)
        if tail:
            os.system("tail -20 %s" % self.logfile)

        if not minimal:
            self.enable()
            self.errors(store=False)

        self.disconnect()

        if lines:
            raise RuntimeError(note, "\n".join(lines))


    def connect(self, quiet=False):
        self.logfile = open(self.options.logfile, "a")
        if not quiet:
            printer.gray("Appending to %s (consider doing \"tail -f %s\" in another shell)" % (self.options.logfile, self.options.logfile))
        h = "-" * 30 + "\n"
        self.logfile.write(h)
        self.logfile.write("| %s |\n" % str(datetime.datetime.today()))
        self.logfile.write(h)

        os.system("killall ngccm >& /dev/null")
        self.server = pexpect.spawn("ngFEC.exe -z -c -t -p %d -H %s" % (self.options.port, self.options.host))
        self.server.logfile = self.logfile
        self.server.sendline("")
        self.server.expect(".*")


    def disconnect(self):
        self.server.sendline("quit")
        self.server.expect(pexpect.EOF)
        self.server.close()
        self.logfile.close()


    def command(self, cmd, timeout=5, bail_on_timeout=False, only_first_line=True):
        fields = cmd.split()
        if not fields:
            return None

        if fields[0] == "jtag":
            if len(fields) < 4:
                print("COMMAND has to few fields: (%s)" % cmd)
                return None

            regexp = "(.*)%s %s %s# retcode=(.*)" % tuple(fields[1:])
        else:
            regexp = "{0}\s?#((\s|E)[^\r^\n]*)".format(re.escape(cmd))

        try:
            self.server.sendline(cmd)
            self.server.expect(regexp, timeout=timeout)
            out = self.server.match.group(0).split("\r\n")
        except pexpect.TIMEOUT:
            if not bail_on_timeout:
                out = [cmd + " # ERROR: timed out after %d seconds" % timeout]
            else:
                lines = [printer.msg('The command "', p=False),
                         printer.cyan(cmd, p=False),
                         printer.msg('"\n       produced unexpected output.  Consult the log file, e.g.', p=False),
                         printer.msg('\n       "%s" gives this:' % printer.gray(tail, p=False), p=False),
                         printer.error(msg)]
                self.bail(lines, tail=True)

        if "ERROR" in out[0]:
            printer.red(out[0])
        return out[0] if only_first_line else out


def fake_options():
    out = collections.namedtuple('options', 'logfile host port nSeconds')
    out.logfile = "driver.log"
    out.host = "localhost"
    out.port = 54321
    out.nSeconds = 5
    return out


def main():
    try:
        driver(fake_options(), "target")
    except RuntimeError as e:
        printer.red(e[1])
        sys.exit(" ")


if __name__ == "__main__":
    main()
