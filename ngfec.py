#!/usr/bin/env python

import os, pexpect, re, sys
import printer


def connect(host, port, logfile=sys.stdout):
    s = "ngFEC.exe -z -c -t -p %d -H %s" % (port, host)
    p = pexpect.spawn(s)
    p.logfile = logfile
    p.sendline("")
    p.expect(".*")
    return p


def disconnect(p):
    p.sendline("quit")
    p.expect(pexpect.EOF)
    p.close()


def survey_clients():
    os.system("ps -ef | grep %s | grep 'ngccm -z'" % os.environ["USER"])


def kill_clients():
    os.system("killall ngccm >& /dev/null")


def command(p, cmd, timeout=5, dontexit=False):
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
        p.sendline(cmd)
        p.expect(regexp, timeout=timeout)
        return p.match.group(0).split("\r\n")
    except pexpect.TIMEOUT:
        tail = "tail -20 %s" % p.logfile.name

        if dontexit:
            return [cmd + " # ERROR: timed out after %d seconds" % timeout]
        else:
            msg  = printer.msg('The command "', p=False)
            msg += printer.cyan(cmd, p=False)
            msg += printer.msg('"\n       produced unexpected output.  Consult the log file, e.g.', p=False)
            msg += printer.msg('\n       "%s" gives this:' % printer.gray(tail, p=False), p=False)
            printer.error(msg)
            os.system(tail)
            sys.exit()
