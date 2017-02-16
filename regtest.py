#!/usr/bin/env python

import registers

from ngFECSendCommand import send_commands

#magic constants ... python needs "static & const"
port = 64004
host = hcal904daq04

def resetRBX(rbx):
    cmds = ["put HE%i-bkp_power_enable 1"%rbx,
            "put HE%i-bkp_reset 1"%rbx,
            "wait",
            "put HE%i-bkp_reset 0"%rbx
           ]
    return send_commands(port, host, cmds, script=True, raw=False, timeout=20)

if __name__ == "__main__":
    #rbxes of of interest
    rbxList = [12]
    NIterations = 5
    #Run reset on the boxes of interest
    for rbx in rbxList:
        print "=========================="
        print "Reset RBX: %3"%(rbx)
        print "=========================="

        print resetRBX(rbx)

    #Get commands
    for rbx in rbxList:
        for i in xrange(NIterations):
            print "=========================="
            print "RBX: %3    Iteration: %i"%(rbx, i)
            print "=========================="
            cmds = ["get HE15-1-1-i_%s" % x for x in registers.B_readables()]
            results = send_commands(port, host, cmds, script=True, raw=False, timeout=20)
            print results
