#!/usr/bin/env python

import registers
import os, pexpect, re


def responses(connection="", cmds=""):
    out = []
    p = pexpect.spawn(connection)
    p.sendline("")
    p.expect(".*")

    for cmd in cmds:
        p.sendline(cmd)
        p.expect("{0}\s?#((\s|E)[^\r^\n]*)".format(re.escape(cmd)), timeout=5)
        out.append(p.match.group(0))
        print out[-1]

    p.sendline("quit")
    p.expect(pexpect.EOF)
    p.close()
    # os.system("killall ngccm >& /dev/null")
    return out


if __name__ == "__main__":
    connection = "ngFEC.exe -z -c -p 64004 -H hcal904daq04"
    cmds = ["get HE15-1-1-i_%s" % x for x in registers.i_readables()]
    results = responses(connection, cmds)
