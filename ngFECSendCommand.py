import pexpect
from re import escape

def send_commands(port, control_hub, cmds, script=False, raw=False, time_out=10):
    # Arguments and variables
    output = []
    raw_output = ""
    if control_hub != None and port:               # Potential bug if "port=0" ... (Control_hub should be allowed to be None.)
        ## Parse commands:
        if isinstance(cmds, str):
            cmds = [cmds]
        if not script:
            pass
        else:
            cmds = [c for c in cmds if c != "quit"]         # "quit" can't be in a ngFEC script.
            cmds_str = ""
            for c in cmds:
                cmds_str += "{0}\n".format(c)
            file_script = "ngfec_script"
            with open(file_script, "w") as out:
                out.write(cmds_str)

        # Prepare the ngfec arguments:
        ngfec_cmd = 'ngFEC.exe -t -c -p {0}'.format(port)
        if not script:
            ngfec_cmd = 'ngFEC.exe -t -z -c -p {0}'.format(port)
        if control_hub != None:
            ngfec_cmd += " -H {0}".format(control_hub)

        # Send the ngfec commands:
        p = pexpect.spawn(ngfec_cmd, timeout=time_out)
        try:
            with DelayedKeyboardInterrupt():
                if not script:
                    for i, c in enumerate(cmds):
                        p.sendline(c)
                        if c != "quit":
                            t0 = time.time()
                            p.expect("{0}\s?#((\s|E)[^\r^\n]*)".format(escape(c)))
                            t1 = time.time()
                            output.append({
                                    "cmd": c,
                                    "result": p.match.group(1).strip().replace("'", ""),
                                    "times": [t0, t1],
                            })
                            raw_output += p.before + p.after
                else:
                    p.sendline("< {0}".format(file_script))
                    for i, c in enumerate(cmds):
                        # Deterimine how long to wait until the first result is expected:
                        if i == 0:
                            timeout = max([time_out, int(0.0075*len(cmds))])
                        else:
                            timeout = time_out              # pexpect default
                
                        # Send commands:
                        t0 = time.time()
                        p.expect("{0}\s?#((\s|E)[^\r^\n]*)".format(escape(c)), timeout=timeout)
                        t1 = time.time()
                        output.append({
                                "cmd": c,
                                "result": p.match.group(1).strip().replace("'", ""),
                                "times": [t0, t1],
                        })
                        raw_output += p.before + p.after
        except pexpect.TIMEOUT:
            print "PExpect Timeout! Probably ngCCM server not found!!!"
            raise
        except KeyboardInterrupt:
            print "KeyboardInterrupt detected: closing ngFEC client connection"
            raise
        finally:
            with DelayedKeyboardInterrupt():
                try:
                    p.sendline("quit")
                    p.expect(pexpect.EOF)
                except pexpect.TIMEOUT:
                    print "well, guess the client (or server??) just crashed, but the show must go on so client process is being killed"
                    if not p.terminate(True):
                        print "Client termination failed, please comense manual process cleanup!"
                    else:
                        p.read() #Take care of any unfinished business so the process can rest in peace 
                raw_output += p.before
                p.close()

        if int(options.verbosity) >= 2:
            print raw_output
        elif int(options.verbosity) == 1:
            print output

        if raw:
            return raw_output
        else:
            return output
