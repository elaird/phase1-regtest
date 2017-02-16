#!/usr/bin/env python

import registers

from ngFECSendCommand import send_commands

#magic constants ... python needs "static & const"
port = 64004
host = "hcal904daq04"

def resetRBX(rbx):
    cmds = ["put HE%i-bkp_pwr_enable 1"%rbx,
            "put HE%i-bkp_reset 1"%rbx,
            "wait",
            "put HE%i-bkp_reset 0"%rbx
           ]
    return send_commands(port, host, cmds, script=True, raw=False, time_out=20)

if __name__ == "__main__":
    #rbxes of of interest
    rbxList = [12]
    NIterations = 5
    #Run reset on the boxes of interest
    for rbx in rbxList:
        print "=========================="
        print "Reset RBX: %3i"%(rbx)
        print "=========================="

        print resetRBX(rbx)

    #Get commands
    for rbx in rbxList:
        for i in xrange(NIterations):
            print "=========================="
            print "RBX: %3i    Iteration: %3i"%(rbx, i)
            print "=========================="
            cmds = ["get HE%i-%i-%i-B_%s" %(rbx, rm, card, x) for x in registers.B_readables() for rm in xrange(1, 5) for card in xrange(1, 5)]
            results = send_commands(port, host, cmds, script=True, raw=False, time_out=20)
            formattedResults = "\n".join(["%-40s : %s"%(x["cmd"], x["result"]) for x in results])
            print formattedResults
