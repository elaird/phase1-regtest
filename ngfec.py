#!/usr/bin/env python

import os, pexpect, re, sys


def connect(host, port, logfile=sys.stdout):
    s = "ngFEC.exe -z -c -p %d -H %s" % (port, host)
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


def command(p, cmd, timeout=5):
    out = ""

    p.sendline(cmd)
    fields = cmd.split()
    if not fields:
        return out

    if fields[0] == "jtag":
        if len(fields) < 4:
            print("COMMAND has to few fields: (%s)" % cmd)
            return out

        p.expect("(.*)%s %s %s# retcode=(.*)" % tuple(fields[1:]), timeout=timeout)
        out = p.match.group(0)
        # print p.match.group(1) #.split("\r\n")
        # print p.match.group(2).split()[0]
    else:
        try:
            p.expect("{0}\s?#((\s|E)[^\r^\n]*)".format(re.escape(cmd)), timeout=timeout)
            out = p.match.group(0)
            # print(out)
        except pexpect.TIMEOUT:
            print("TIMEOUT (%s)" % cmd)

    return out
