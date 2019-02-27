#!/usr/bin/env python

import optparse, pickle, sys
import ROOT as r


def results(filename):
    try:
        with open(filename, 'rb') as f:
            d = pickle.load(f)
        return d
    except IOError as e:
        print("Failed to open %s" % filename)
        return {}


def vi_dicts(inFile):
    voltage = {}
    current = {}
    for key, res in results(inFile).items():
        vSet, cmd = key
        if "OK" in res:
            continue
        if "LeakageCurrent" in cmd:
            current[float(vSet)] = res
        if "biasmon" in cmd:
            voltage[float(vSet)] = res
    return voltage, current


def graphs(inFile, nCh, biasMonLsb, leakLsb):
    g_voltages = []
    g_currents = []
    for iCh in range(nCh):
        g_voltages.append(r.TGraphErrors())
        g_currents.append(r.TGraphErrors())
        
    d_voltages, d_currents = vi_dicts(inFile)
    iPoint = -1
    for setting in sorted(d_voltages.keys()):
        voltages = d_voltages[setting]
        currents = d_currents[setting]
        iPoint += 1
        for iCh in range(nCh):
            g_voltages[iCh].SetPoint(iPoint, setting, voltages[iCh])
            g_voltages[iCh].SetPointError(iPoint, 0.0, biasMonLsb)
            g_currents[iCh].SetPoint(iPoint, setting, currents[iCh])
            g_currents[iCh].SetPointError(iPoint, 0.0, leakLsb)
    return g_voltages, g_currents


def fits(lst, xMin, xMax, target):
    out = []

    f = r.TF1("f", "[0] + (x<[1]?0.0:[2]*(x-[1]))", xMin, xMax)
    f.SetLineWidth(1)
    for iGraph, g in enumerate(lst):
        n = g.GetN()
        if not n:
            continue
        x = g.GetX()
        y = g.GetY()
        f.SetParameters(y[0], y[0], 0.15)
        f.SetParLimits(1, xMin, xMax)
        g.Fit(f, "q")

        prob = f.GetProb()
        if prob < 0.1:
            print("WARNING: %s graph %d has fit prob. %e" % (target, 1 + iGraph, prob))
        out.append({-1: prob})
        for iPar in range(3):
            out[-1][iPar] = (f.GetParameter(iPar), f.GetParError(iPar))
    return out


def draw_per_channel(lst, yTitle, yMax, can, outFile):
    can.Clear()
    can.DivideSquare(len(lst), 0.003, 0.001)
    
    null = r.TH2D("null", ";BVset(V);%s" % yTitle, 1, 0.0, 80.0, 1, 0.0, yMax)
    null.SetStats(False)

    x = null.GetXaxis()
    x.SetLabelSize(2.0 * x.GetLabelSize())
    x.SetTitleSize(4.0 * x.GetTitleSize())
    x.SetTitleOffset(-0.35)
    # x.CenterTitle()

    y = null.GetYaxis()
    y.SetLabelSize(2.0 * y.GetLabelSize())    
    y.SetTitleSize(4.0 * y.GetTitleSize())
    y.SetTitleOffset(-0.35)
    # y.CenterTitle()

    text = r.TText()
    text.SetTextSize(3.0 * text.GetTextSize())
    text.SetNDC()
    
    keep = []
    for iCh in range(len(lst)):
        can.cd(1 + iCh)
        r.gPad.SetTickx()
        r.gPad.SetTicky()
        null.Draw()
        keep.append(text.DrawText(0.45, 0.7, "QIECh%d" % (1 + iCh)))
        g = lst[iCh]
        g.SetMarkerStyle(20)
        g.SetMarkerSize(0.3 * g.GetMarkerSize())
        g.Draw("psame")
    can.Print(outFile)


def histogram_fit_results(d, nCh, can, outFile, target, title, unit):
    if not d:
        return

    can.Divide(0)
    can.Clear()
    can.SetTickx()
    can.SetTicky()

    if unit == "V":
        yMin = {-1: 0.0, 0: 0.0, 1: 0.0, 2:0.99}
        yMax = {-1: 1.1, 0: 0.1, 1: 0.4, 2:1.01}
    else:
        yMin = {-1: 0.0, 0:  0.0, 1:  0.0, 2:-0.15}
        yMax = {-1: 1.1, 0: 10.0, 1: 30.0, 2: 0.35}

    par_name = {-1: "fit probability", 0:"fit baseline (%s)" % unit, 1:"fit kink voltage (V)", 2:"fit slope (%s / V)" % unit}
    full_title = "%s: %s" % (target, title)

    for iPar in range(-1, 3, 1):
        h = r.TH1D("h", "%s;QIE channel number;%s" % (full_title, par_name[iPar]), nCh, 0.5, 0.5 + nCh)
        h.SetStats(False)
        for iCh in range(nCh):
            iBin = h.GetBin(1 + iCh)
            if iPar < 0:
                h.SetBinContent(iBin, d[iCh][iPar])
            else:
                c, e = d[iCh][iPar]
                h.SetBinContent(iBin, c)
                h.SetBinError(iBin, e)
        h.Draw("p")
        h.SetMarkerStyle(20)
        h.SetMarkerSize(0.5 * h.GetMarkerSize())
        h.SetMarkerColor(h.GetLineColor())
        h.GetYaxis().SetRangeUser(yMin[iPar], yMax[iPar])
        can.Print(outFile)

    null = r.TH2D("h2", "%s;%s;%s;" % (full_title, par_name[0], par_name[1]), 1, yMin[0], yMax[0], 1, yMin[1], yMax[1])
    null.SetStats(False)

    corr = r.TGraphErrors()
    corr.SetLineColor(h.GetLineColor())
    corr.SetMarkerColor(h.GetMarkerColor())
    corr.SetMarkerStyle(h.GetMarkerStyle())
    corr.SetMarkerSize(h.GetMarkerSize())

    for iCh in range(nCh):
        x, xe = d[iCh][0]
        y, ye = d[iCh][1]
        corr.SetPoint(iCh, x, y)
        corr.SetPointError(iCh, xe, ye)

    null.Draw()
    corr.Draw("psame")
    can.Print(outFile)


def opts():
    parser = optparse.OptionParser(usage="usage: %prog [options] PICKLED_FILE")

    options, args = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        sys.exit(" ")

    return options, args[0]


def main(inFile, nCh=64, bvSetMin=0.0, bvSetMax=80.0, biasMonLsb=0.01953602, hbLeakLsb=0.244, heLeakLsb=0.122):
    outFile = inFile.replace(".pickle", ".pdf")
    target = inFile.replace(".pickle", "")
    g_voltages, g_currents = graphs(inFile, nCh, biasMonLsb, hbLeakLsb if inFile.startswith("HB") else heLeakLsb)
    can = r.TCanvas()

    p_voltages = fits(g_voltages, bvSetMin, bvSetMax, target)
    p_currents = fits(g_currents, bvSetMin, bvSetMax, target)

    if not p_voltages:
        return

    can.Print(outFile + "[")
    draw_per_channel(g_voltages, "BVmeas(V)", 80.0, can, outFile)
    # histogram_fit_results(p_voltages, nCh, can, outFile, target=target, title="BV meas", unit="V")
    draw_per_channel(g_currents, "Ileak(uA)", 40.0, can, outFile)
    histogram_fit_results(p_currents, nCh, can, outFile, target=target, title="I leak", unit="uA")
    can.Print(outFile + "]")
    print("Wrote %s" % outFile)


if __name__ == "__main__":
    r.gROOT.SetBatch(True)
    r.gErrorIgnoreLevel = r.kError    
    main(opts()[1])
