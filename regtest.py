#!/usr/bin/env python

import registers

from ngFECSendCommand import send_commands

if __name__ == "__main__":
    port = 64004
    host = hcal904daq04
    cmds = ["get HE15-1-1-i_%s" % x for x in registers.i_readables()]
    results = send_commands(port, host, cmds, script=True, raw=False, timeout=20)
