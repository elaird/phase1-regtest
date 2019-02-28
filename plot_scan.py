#!/usr/bin/env python

import optparse, pickle, sys
import ROOT as r
r.PyConfig.IgnoreCommandLineOptions = True


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


def fit1(g, f, y0, options, target, iGraph):
    dct = {}
    nIni = 4
    for iIni in range(nIni):
        ini = options.bvMin + iIni * (options.bvMax - options.bvMin) / nIni
        f.SetParameters(y0, ini, 0.15)
        f.SetParLimits(1, options.bvMin, options.bvMax)
        g.Fit(f, "q")

        prob = f.GetProb()
        dct[prob] = {}
        for iPar in range(3):
            dct[prob][iPar] = (f.GetParameter(iPar), f.GetParError(iPar))
        if options.thresholdRefit < prob:
            break

    best_prob = max(dct.keys())
    if best_prob < options.thresholdWarn:
        print("WARNING: %s graph %d has fit prob. %e" % (target, 1 + iGraph, prob))

    out = {}
    out[-1] = best_prob
    out.update(dct[best_prob])
    return out


def fits(lst, options, target, h_pValues, h_slopes, h_slopes_rel):
    out = []

    f = r.TF1("f", "[0] + (x<[1]?0.0:[2]*(x-[1]))", options.bvMin, options.bvMax)
    f.SetLineWidth(1)
    for iGraph, g in enumerate(lst):
        n = g.GetN()
        if not n:
            continue
        x = g.GetX()
        y = g.GetY()

        out.append(fit1(g, f, y[0], options, target, iGraph))
        res = out[-1]
        h_pValues.Fill(res[-1])
        slope = res[2][0]
        h_slopes.Fill(slope)
        if slope:
            h_slopes_rel.Fill(res[2][1] / slope)
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


def histogram_fit_results(d, nCh, can, outFile, target, title, unit, do_corr=False):
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

    if not do_corr:
        return

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
    parser = optparse.OptionParser(usage="usage: %prog [options] FILE1 [FILE2 ...]")
    parser.add_option("--bv-min",
                      dest="bvMin",
                      default=0.0,
                      type="float",
                      help="minimum of plot x-axis [default %default]")
    parser.add_option("--bv-max",
                      dest="bvMax",
                      default=80.0,
                      type="float",
                      help="maximum of plot x-axis [default %default]")
    parser.add_option("--lsb-factor",
                      dest="lsbFactor",
                      default=1.0,
                      type="float",
                      metavar="f",
                      help="multiple of LSB used for uncertainties [default %default]")
    parser.add_option("--summary-file",
                      dest="summaryFile",
                      default="summary.pdf",
                      metavar="s",
                      help="summary file [default %default]")
    parser.add_option("--threshold-warn",
                      dest="thresholdWarn",
                      default=0.01,
                      type="float",
                      metavar="a",
                      help="fit probability below which to warn  [default %default]")
    parser.add_option("--threshold-refit",
                      dest="thresholdRefit",
                      default=0.2,
                      metavar="b",
                      type="float",
                      help="fit probability below which to refit [default %default]")

    options, args = parser.parse_args()

    if not args:
        parser.print_help()
        sys.exit(" ")

    return options, args


def one(inFile, options, V_pValues, V_slopes, V_slopes_rel, I_pValues, I_slopes, I_slopes_rel):
    biasMonLsb = 0.01953602  # V / ADC

    final = inFile.split("/")[-1]
    if final.startswith("HB"):
        nCh = 64
        leakLsb = 0.244  # uA / ADC
    elif final.starswith("HE"):
        nCh = 48
        leakLsb = 0.122  # uA / ADC
    else:
        sys.exit("Each argument must contain either 'HB' or 'HE'.  Found '%s'" % inFile)

    outFile = inFile.replace(".pickle", ".pdf")
    target = inFile.replace(".pickle", "")
    g_voltages, g_currents = graphs(inFile, nCh, biasMonLsb*options.lsbFactor, leakLsb*options.lsbFactor)
    can = r.TCanvas()

    p_voltages = fits(g_voltages, options, target, V_pValues, V_slopes, V_slopes_rel)
    p_currents = fits(g_currents, options, target, I_pValues, I_slopes, I_slopes_rel)

    if not p_voltages:
        return

    can.Print(outFile + "[")
    draw_per_channel(g_voltages, "BVmeas(V)", 80.0, can, outFile)
    # histogram_fit_results(p_voltages, nCh, can, outFile, target=target, title="BV meas", unit="V")
    draw_per_channel(g_currents, "Ileak(uA)", 40.0, can, outFile)
    histogram_fit_results(p_currents, nCh, can, outFile, target=target, title="I leak", unit="uA")
    can.Print(outFile + "]")
    print("Wrote %s" % outFile)


def draw_summary(outFile, lst):
    can = r.TCanvas()
    can.Print(outFile + "[")
    can.SetTickx()
    can.SetTicky()
    can.SetLogy()

    for h in lst:
        h.Draw()
        h.SetMinimum(0.5)
        can.Print(outFile)

    can.Print(outFile + "]")
    print("Wrote %s" % outFile)


def main(options, args):
    V_pValues = r.TH1D("V_pValues", ";fit p-value;channels / bin", 101, 0.0, 1.01)
    I_pValues = r.TH1D("Ileak_pValues", ";fit p-value;channels / bin", 101, 0.0, 1.01)

    V_slopes  = r.TH1D("V_slopes", ";fit slope (V/V);channels / bin", 100, 0.99, 1.01)
    I_slopes  = r.TH1D("Ileak_slopes", ";fit slope (uA/V);channels / bin", 100, 0.0, 0.50)

    V_slopes_rel  = r.TH1D("V_slopes_rel", ";rel. unc. on fit slope;channels / bin", 110, 0.0, 1.1)
    I_slopes_rel  = r.TH1D("Ileak_slopes_rel", ";rel. unc. on fit slope;channels / bin", 110, 0.0, 1.1)

    h = [V_pValues, V_slopes, V_slopes_rel, I_pValues, I_slopes, I_slopes_rel]
    for arg in args:
        one(arg, options, *h)

    if 2 <= len(args):
        draw_summary(options.summaryFile, h)


if __name__ == "__main__":
    r.gROOT.SetBatch(True)
    r.gStyle.SetOptStat("ouen")
    r.gErrorIgnoreLevel = r.kError
    main(*opts())
