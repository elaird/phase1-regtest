#!/usr/bin/env python

import optparse, pickle, sys
import printer
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


def graphs(inFile, nCh, biasMonUnc, leakUnc, biasMin, leakMin, options):
    g_voltages = []
    g_currents = []
    for iCh in range(nCh):
        g_voltages.append(r.TGraphErrors())
        g_currents.append(r.TGraphErrors())
        
    d_voltages, d_currents = vi_dicts(inFile)
    for setting in sorted(d_voltages.keys()):
        voltages = d_voltages[setting]
        currents = d_currents[setting]
        for iCh in range(nCh):
            if biasMin < voltages[iCh] and options.bvMin <= setting <= options.bvMax:
                iPoint = g_voltages[iCh].GetN()
                g_voltages[iCh].SetPoint(iPoint, setting, voltages[iCh])
                g_voltages[iCh].SetPointError(iPoint, 0.0, biasMonUnc)
            if leakMin < currents[iCh] and options.bvMin <= setting <= options.bvMax:
                iPoint = g_currents[iCh].GetN()
                g_currents[iCh].SetPoint(iPoint, setting, currents[iCh])
                g_currents[iCh].SetPointError(iPoint, 0.0, leakUnc)

    return g_voltages, g_currents


def fits2(lst, options, target, p1_ini,
          h_pvalues, h_pvalues_vs_ch,
          h_offsets, h_offsets_unc,
          h_slopes, h_slopes_unc_rel,
          warn=True):
    out = []

    f = r.TF1("f", "[0] + [1]*x", options.bvMin, options.bvMax)
    for iGraph, g in enumerate(lst):
        if not g.GetN():
            continue

        f.SetParameters(0.0, p1_ini)
        g.Fit(f, "q0")

        res = {-1: f.GetProb()}
        for iPar in range(f.GetNumberFreeParameters()):
            res[iPar] = (f.GetParameter(iPar), f.GetParError(iPar))
        out.append(res)

        ch = 1 + iGraph
        pvalue = res[-1]
        h_pvalues.Fill(pvalue)
        h_pvalues_vs_ch.Fill(ch, pvalue)
        if warn and pvalue < options.threshold_pvalue_warn:
            printer.red("WARNING: %s graph %d has fit prob. %e" % (target, ch, pvalue))

        h_offsets.Fill(res[0][0])
        h_offsets_unc.Fill(res[0][1])

        slope = res[1][0]
        h_slopes.Fill(slope)
        if warn and not (options.threshold_slope_lo_warn < slope < options.threshold_slope_hi_warn):
            printer.purple("WARNING: fit slope %g" % slope)

        if slope:
            rel_unc = res[1][1] / slope
            h_slopes_unc_rel.Fill(rel_unc)
            if warn and options.threshold_rel_unc_warn < rel_unc:
                printer.cyan("WARNING: fit rel unc %g" % rel_unc)
    return out


def draw_per_channel(lst, yTitle, yMax, can, outFile, fColor=r.kRed):
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
        f = g.GetFunction("f")
        f.SetNpx(1000)
        f.SetLineWidth(1)
        f.SetLineColor(fColor)
        f.Draw("same")

        g.SetMarkerStyle(20)
        g.SetMarkerSize(0.3 * g.GetMarkerSize())
        g.Draw("ex0psame")
    can.Print(outFile)


def histogram_fit_results(d, nCh, can, outFile, target, title, unit, do_corr=False):
    if not d:
        return

    can.Divide(0)
    can.Clear()
    can.SetTickx()
    can.SetTicky()

    if unit == "V":
        yMin = {-1: 0.0, 0: 0.0, 1: 0.99}
        yMax = {-1: 1.1, 0: 0.4, 1: 1.01}
    else:
        yMin = {-1: 0.0, 0:-20.0, 1: 0.00}
        yMax = {-1: 1.1, 0: 20.0, 1: 0.50}

    par_name = {-1: "fit probability", 0:"fit offset (%s)" % unit, 1:"fit slope (%s / V)" % unit}
    full_title = "%s: %s" % (target, title)

    for iPar in range(-1, 2, 1):
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
                      default=0.5,
                      type="float",
                      metavar="f",
                      help="multiple of LSB used for uncertainties [default %default]")
    parser.add_option("--summary-file",
                      dest="summaryFile",
                      default="summary.pdf",
                      metavar="s",
                      help="summary file [default %default]")
    parser.add_option("--threshold-rel-unc-warn",
                      dest="threshold_rel_unc_warn",
                      default=0.05,
                      type="float",
                      metavar="x",
                      help="rel unc above which to warn  [default %default]")
    parser.add_option("--threshold-slope-lo-warn",
                      dest="threshold_slope_lo_warn",
                      default=0.11,
                      type="float",
                      metavar="x",
                      help="slope below which to warn  [default %default]")
    parser.add_option("--threshold-slope-hi-warn",
                      dest="threshold_slope_hi_warn",
                      default=0.2,
                      type="float",
                      metavar="x",
                      help="slope above which to warn  [default %default]")
    parser.add_option("--threshold-pvalue-warn",
                      dest="threshold_pvalue_warn",
                      default=0.005,
                      type="float",
                      metavar="x",
                      help="fit probability below which to warn  [default %default]")

    options, args = parser.parse_args()

    if not args:
        parser.print_help()
        sys.exit(" ")

    return options, args


def one(inFile, options,
        V_pvalues, V_offsets, V_slopes, V_pvalues_vs_ch, V_offsets_unc, V_slopes_unc_rel,
        I_pvalues, I_offsets, I_slopes, I_pvalues_vs_ch, I_offsets_unc, I_slopes_unc_rel):
    biasMonLsb = 0.01953602  # V / ADC

    final = inFile.split("/")[-1]
    if final.startswith("HB"):
        nCh = 64
        leakLsb = 0.244      # uA / ADC
        biasMin = 0.0586081  # ADC = 0
        leakMin = 1.708      # ADC = 0
    elif final.starswith("HE"):
        nCh = 48
        leakLsb = 0.122  # uA / ADC
    else:
        sys.exit("Each argument must contain either 'HB' or 'HE'.  Found '%s'" % inFile)

    outFile = inFile.replace(".pickle", ".pdf")
    target = inFile.replace(".pickle", "")
    g_voltages, g_currents = graphs(inFile, nCh,
                                    biasMonLsb*options.lsbFactor, leakLsb*options.lsbFactor,
                                    biasMin*1.001, leakMin*1.001, options)

    can = r.TCanvas()

    p_voltages = fits2(g_voltages, options, target,  1.0,
                       V_pvalues, V_pvalues_vs_ch,
                       V_offsets, V_offsets_unc,
                       V_slopes, V_slopes_unc_rel,
                       warn=False)

    p_currents = fits2(g_currents, options, target, 0.15,
                       I_pvalues, I_pvalues_vs_ch,
                       I_offsets, I_offsets_unc,
                       I_slopes, I_slopes_unc_rel)

    if not p_voltages:
        return

    can.Print(outFile + "[")
    draw_per_channel(g_voltages, "BVmeas(V)", 80.0, can, outFile, fColor=r.kCyan)
    # histogram_fit_results(p_voltages, nCh, can, outFile, target=target, title="BV meas", unit="V")
    draw_per_channel(g_currents, "Ileak(uA)", 40.0, can, outFile)
    histogram_fit_results(p_currents, nCh, can, outFile, target=target, title="I leak", unit="uA")
    can.Print(outFile + "]")
    printer.gray("Wrote %s" % outFile)


def draw_summary(options, lst):
    outFile = options.summaryFile

    can = r.TCanvas()
    can.Print(outFile + "[")
    nPads = len(lst) // 2
    can.DivideSquare(nPads)

    line = r.TLine()
    line.SetLineColor(r.kMagenta)
    line.SetLineStyle(2)

    keep = []
    for iH, h in enumerate(lst):
        can.cd(1 + (iH % nPads))
        r.gPad.SetTickx()
        r.gPad.SetTicky()
        r.gPad.SetLogy("pvalue" not in h.GetName())

        if "vs" in h.GetName():
            continue

        h.Draw("colz" if "vs" in h.GetName() else "")
        h.SetLineWidth(2)
        h.SetMinimum(0.5)

        if h.GetName().startswith("Ileak"):
            xs = []
            if "_rel" in h.GetName():
                xs = [options.threshold_rel_unc_warn]
            elif h.GetName().endswith("p_values"):
                xs = [options.threshold_pvalue_warn]
            elif "slope" in h.GetName():
                xs = [options.threshold_slope_lo_warn, options.threshold_slope_hi_warn]

            for x in xs:
                keep.append(line.DrawLine(x, h.GetMinimum(), x, h.GetMaximum()))

        if (iH % nPads) == (nPads - 1) or iH == len(lst) - 1:
            can.Print(outFile)

    can.Print(outFile + "]")
    print("Wrote %s" % outFile)


def main(options, args):
    V_pvalues = r.TH1D("V_pvalues", ";fit p-value;channels / bin", 202, 0.0, 1.01)
    I_pvalues = r.TH1D("Ileak_pvalues", ";fit p-value;channels / bin", 202, 0.0, 1.01)

    nCh = 64  # FIXME
    V_pvalues_vs_ch = r.TH2D("V_pvalues_vs_qie", ";QIE channel number;fit p-value;channels / bin",
                              nCh, 0.5, 0.5 + nCh, 11, 0.0, 1.1)
    I_pvalues_vs_ch = r.TH2D("Ileak_pvalues_vs_qie", ";QIE channel number;fit p-value;channels / bin",
                              nCh, 0.5, 0.5 + nCh, 11, 0.0, 1.1)

    V_offsets = r.TH1D("V_offsets", ";fit offset (V);channels / bin", 200, -0.2, 0.2)
    I_offsets = r.TH1D("Ileak_offsets", ";fit offset (uA);channels / bin", 200, -50.0, 50.0)

    V_offsets_unc = r.TH1D("V_offsets_unc", ";uncertainty on fit offset (V);channels / bin", 200, 0.0, 0.02)
    I_offsets_unc = r.TH1D("Ileak_offsets_unc", ";uncertainty on fit offset (uA);channels / bin", 200, 0.0, 1.0)

    V_slopes = r.TH1D("V_slopes", ";fit slope (V/V);channels / bin", 200, 0.99, 1.01)
    I_slopes = r.TH1D("Ileak_slopes", ";fit slope (uA/V);channels / bin", 200, 0.0, 0.50)

    V_slopes_unc_rel = r.TH1D("V_slopes_unc_rel", ";relative uncertainty on fit slope;channels / bin", 200, 0.0, 2.e-4)
    I_slopes_unc_rel = r.TH1D("Ileak_slopes_unc_rel", ";relative uncertainty on fit slope;channels / bin", 200, 0.0, 0.4)

    h = [V_pvalues, V_offsets, V_slopes, V_pvalues_vs_ch, V_offsets_unc, V_slopes_unc_rel,
         I_pvalues, I_offsets, I_slopes, I_pvalues_vs_ch, I_offsets_unc, I_slopes_unc_rel]
    for arg in args:
        one(arg, options, *h)

    draw_summary(options, h)


if __name__ == "__main__":
    r.gROOT.SetBatch(True)
    r.gStyle.SetOptStat("ourme")
    r.gErrorIgnoreLevel = r.kError
    main(*opts())
