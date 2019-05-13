#!/usr/bin/env python

import optparse, pickle, sys
import printer, scan_peltier
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


def vi_dicts(inFile, current_string="LeakageCurrent", voltage_string="biasmon", temperature_string="rtdtemperature"):
    voltage = {}
    current = {}
    temperature = {}
    for key, res in results(inFile).items():
        vSet, cmd = key
        if "OK" in res:
            continue
        if current_string in cmd:
            current[float(vSet)] = res
        if voltage_string in cmd:
            voltage[float(vSet)] = res
        if temperature_string in cmd:
            temperature[float(vSet)] = res
    return voltage, current, temperature


def graphs(inFile, nCh, options, settings, d_values, vMin, vUnc):
    g_values      = []
    factor_values = []
    min_bv_values = []

    for iCh in range(nCh):
        g_values.append(r.TGraphErrors())
        factor_values.append(-1)
        min_bv_values.append(None)

    for iSetting, setting in enumerate(settings):
        values = d_values[setting]

        for iCh in range(nCh):
            iPoint = g_values[iCh].GetN()
            g_values[iCh].SetPoint(iPoint, setting, values[iCh])
            g_values[iCh].SetPointError(iPoint, 0.0, vUnc)

            for setting2 in settings:
                denom = d_values[setting2][iCh]
                if denom:
                    factor = values[iCh] / denom
                    break

            good = vMin < values[iCh] and options.pedFactor < factor
            if min_bv_values[iCh] is None and (good or options.bvMaxMin <= setting):
                min_bv_values[iCh] = settings[iSetting]
                factor_values[iCh] = factor

    return g_values, min_bv_values, factor_values


def fit_results(f):
    out = {-3: f.GetNumberFitPoints(), -2: f.GetChisquare(), -1: f.GetProb(),}
    for iPar in range(3):
        out[iPar] = (f.GetParameter(iPar), f.GetParError(iPar))
    return out


def fits(lst, mins, options, target, p1_ini):
    out = []

    for iGraph, g in enumerate(lst):
        if not g.GetN():
            continue

        mm = (mins[iGraph], options.bvMax)
        fops = "refq0"
        f1 = r.TF1("f1", "pol2", *mm)
        f1.SetParameters(0.0, p1_ini, 0.0)
        f1.FixParameter(2, 0.0)
        g.Fit(f1, fops)

        f2 = r.TF1("f2", "pol2", *mm)
        f2.SetParameters(0.0, p1_ini, 0.0)
        g.Fit(f2, "%s+" % fops)

        out.append((fit_results(f1), fit_results(f2)))
    return out


def histogram_fit_results(lst, mins, factors,
                          options, target,
                          h_npoints, h_mins, h_factors,
                          h_pvalues, h_pvalues2,
                          h_delta_chi2, h_delta_chi2_cut_vs_ch,
                          h_offsets, h_offsets_unc,
                          h_slopes, h_slopes_unc_rel,
                          h_curvatures, h_curvatures_unc,
                          warn=True, offset2=False, slope2=False):

    for iRes, (res, res2) in enumerate(lst):
        ch = 1 + iRes
        s = "WARNING: %s MB ch %2d" % (target, ch)

        npoints = res[-3]
        h_npoints.Fill(npoints)
        if warn and npoints < options.threshold_npoints_warn:
            printer.red("%s has %d points" % (s, npoints))

        h_mins.Fill(mins[iRes])
        h_factors.Fill(factors[iRes])

        pvalue = res[-1]
        h_pvalues.Fill(pvalue)

        pvalue2 = res2[-1]
        h_pvalues2.Fill(pvalue2)

        delta_chi2 = res[-2] - res2[-2]
        h_delta_chi2.Fill(delta_chi2)
        if options.threshold_delta_chi2_warn < delta_chi2:
            h_delta_chi2_cut_vs_ch.Fill(ch)
            if warn:
                printer.dark_blue("%s has delta chi2 %e" % (s, delta_chi2))

        offset = (res2 if offset2 else res)[0][0]
        h_offsets.Fill(offset)
        h_offsets_unc.Fill((res2 if offset2 else res)[0][1])

        slope = (res2 if slope2 else res)[1][0]
        h_slopes.Fill(slope)

        h_curvatures.Fill(res2[2][0])
        h_curvatures_unc.Fill(res2[2][1])

        if options.print_fit_results and slope < 0.80:  # requirement on slope hackily filters V fits
            print("%s %2d %6.3f %6.3f" % (target.split("/")[-1], ch, offset, slope))

        if warn and not (options.threshold_slope_lo_warn < slope < options.threshold_slope_hi_warn):
            printer.purple("%s has fit slope  %g" % (s, slope))

        if slope:
            rel_unc = res[1][1] / slope
            h_slopes_unc_rel.Fill(rel_unc)
            if warn and options.threshold_slope_rel_unc_warn < rel_unc:
                printer.cyan("%s has fit rel unc %g" % (s, rel_unc))


def draw_per_channel(lst, yTitle, can, outFile, options, xMin=0.0, yMin=0.0, yMax=10.0, fColor1=None, fColor2=None):
    can.Clear()
    can.DivideSquare(len(lst), 0.003, 0.001)

    xTitle = "PVset(V)" if options.is_voltage else "time (s)"
    null = r.TH2D("null", ";%s ;%s" % (xTitle, yTitle), 1, xMin, options.bvMax, 1, yMin, yMax)
    null.SetStats(False)

    x = null.GetXaxis()
    x.SetLabelSize(2.0 * x.GetLabelSize())
    x.SetTitleSize(3.0 * x.GetTitleSize())
    x.SetTitleOffset(-0.35)
    # x.CenterTitle()

    y = null.GetYaxis()
    y.SetLabelSize(2.0 * y.GetLabelSize())    
    y.SetTitleSize(3.0 * y.GetTitleSize())
    y.SetTitleOffset(-0.35)
    # y.CenterTitle()

    text = r.TText()
    text.SetTextSize(2.0 * text.GetTextSize())
    text.SetNDC()
    
    keep = []
    for iCh in range(len(lst)):
        mb = 1 + iCh
        can.cd(mb)
        r.gPad.SetTickx()
        r.gPad.SetTicky()
        null.Draw()
        keep.append(text.DrawText(0.28, 0.75, "RM%d" % (mb if options.rms == "[1-4]" else int(options.rms))))

        g = lst[iCh]
        if fColor2 is not None:
            f2 = g.GetFunction("f2")
            f2.SetNpx(1000)
            f2.SetLineWidth(1)
            f2.SetLineColor(fColor2)
            f2.Draw("same")

        if fColor1 is not None:
            f1 = g.GetFunction("f1")
            f1.SetNpx(1000)
            f1.SetLineWidth(1)
            f1.SetLineColor(fColor1)
            f1.Draw("same")

        g.SetMarkerStyle(20)
        g.SetMarkerSize(1.0)
        g.Draw("psame")
    can.Print(outFile)


def histogram_fit_results_vs_channel(d, nCh, can, outFile, target, title, unit):
    if not d:
        return

    can.Divide(0)
    can.Clear()
    can.SetTickx()
    can.SetTicky()

    if unit == "V":
        yMin = {-3:   0, -1: 0.0, 0: 0.0, 1: 0.90, 2:-100}
        yMax = {-3: 100, -1: 1.1, 0: 0.4, 1: 1.01, 2: 100}
    else:
        yMin = {-3:   0, -1: 0.0, 0:-20.0, 1: 0.00, 2:-0.01}
        yMax = {-3: 100, -1: 1.1, 0: 20.0, 1: 1.00, 2: 0.01}

    for iPar, par_name in [(-3, "number of fit points"),
                           (-1, "fit1 p-value"),
                           # (-2, "#chi^{2}_{0} - #chi^{2}_{c*}"),
                           ( 0, "fit1 offset (%s)" % unit),
                           ( 1, "fit1 slope (%s / V)" % unit),
                           # ( 2, "fit2 curvature (%s / V^{2})" % unit),
                           ]:

        h = r.TH1D("h", "%s: %s;RM;%s" % (target, title, par_name), nCh, 0.5, 0.5 + nCh)
        h.SetStats(False)
        h.SetMarkerStyle(20)
        h.SetMarkerSize(4.0)
        h.SetMarkerColor(h.GetLineColor())

        if iPar == 2:
            h.GetYaxis().SetTitleOffset(1.5)

        for iCh in range(nCh):
            res, res2 = d[iCh]
            iBin = h.GetBin(1 + iCh)
            if iPar == -2:
                h.SetBinContent(iBin, res[iPar] - res2[iPar])
            elif iPar < 0:
                h.SetBinContent(iBin, res[iPar])
            else:
                c, e = (res2 if iPar == 2 else res)[iPar]
                h.SetBinContent(iBin, c)
                h.SetBinError(iBin, e)

        h.Draw("pe" if 0 <= iPar else "p")
        if iPar in yMin and iPar in yMax:
            h.GetYaxis().SetRangeUser(yMin[iPar], yMax[iPar])
        can.Print(outFile)


def opts():
    parser = optparse.OptionParser(usage="usage: %prog [options] FILE1 [FILE2 ...]")
    parser.add_option("--bv-max-min",
                      dest="bvMaxMin",
                      default=0.0,
                      type="float",
                      help="maximum minimum of fit range [default %default]")
    parser.add_option("--bv-max",
                      dest="bvMax",
                      default=8.0,
                      type="float",
                      help="maximum of fit range [default %default]")
    parser.add_option("--lsb-factor-current",
                      dest="lsbFactorCurrent",
                      default=1.0,
                      type="float",
                      metavar="f",
                      help="multiple of LSB used for I uncertainties [default %default]")
    parser.add_option("--lsb-factor-temperature",
                      dest="lsbFactorTemperature",
                      default=1.0,
                      type="float",
                      metavar="f",
                      help="multiple of LSB used for I uncertainties [default %default]")
    parser.add_option("--lsb-factor-voltage",
                      dest="lsbFactorVoltage",
                      default=1.0,
                      type="float",
                      metavar="f",
                      help="multiple of LSB used for V uncertainties [default %default]")
    parser.add_option("--ped-factor",
                      dest="pedFactor",
                      default=1.5,
                      type="float",
                      metavar="f",
                      help="ignore values below f*y0 [default %default]")
    parser.add_option("--summary-file",
                      dest="summaryFile",
                      default="fit_summary.pdf",
                      metavar="s",
                      help="summary file [default %default]")
    parser.add_option("--threshold-delta-chi2-warn",
                      dest="threshold_delta_chi2_warn",
                      default=30.0,
                      type="float",
                      metavar="x",
                      help="delta chi2 above which to warn  [default %default]")
    parser.add_option("--threshold-npoints-warn",
                      dest="threshold_npoints_warn",
                      default=5,
                      type="int",
                      metavar="n",
                      help="npoints below which to warn  [default %default]")
    parser.add_option("--threshold-slope-rel-unc-warn",
                      dest="threshold_slope_rel_unc_warn",
                      default=0.06,
                      type="float",
                      metavar="x",
                      help="slope rel unc above which to warn  [default %default]")
    parser.add_option("--threshold-slope-lo-warn",
                      dest="threshold_slope_lo_warn",
                      default=0.11,
                      type="float",
                      metavar="x",
                      help="slope below which to warn  [default %default]")
    parser.add_option("--threshold-slope-hi-warn",
                      dest="threshold_slope_hi_warn",
                      default=0.19,
                      type="float",
                      metavar="x",
                      help="slope above which to warn  [default %default]")
    parser.add_option("--print-fit-results",
                      dest="print_fit_results",
                      action="store_true",
                      help="print fit results")
    parser.add_option("--rms",
                      dest="rms",
                      default="[1-4]",
                      help="RMs [default %default]")
    parser.add_option("--no-temperature",
                      dest="no_temperature",
                      default=False,
                      action="store_true",
                      help="don't analyze temperature")

    options, args = parser.parse_args()
    options.is_voltage = options.bvMax < 90  # assume larger values are vs. time rather than voltage

    if not args:
        parser.print_help()
        sys.exit(" ")

    return options, args


def one(inFile, options, h):
    vMonLsb = 0.003663  # V / ADC
    vMin = 0.0  # ADC = 0

    iLsb = 0.0006105  # A / ADC
    iMin = 0.0  # ADC = 0

    tLsb = 0.01 # FIXME
    tMin = -50.0 # FIXME

    nCh = (4 if options.rms == "[1-4]" else 1) * scan_peltier.nRbxes(inFile.split("_")[0])

    final = inFile.split("/")[-1]

    outFile = inFile.replace(".pickle", ".pdf")
    target = inFile.replace(".pickle", "")

    d_voltages, d_currents, d_temperatures = vi_dicts(inFile, current_string="PeltierCurrent_", voltage_string="PeltierVoltage_")

    settings = sorted(d_voltages.keys())
    g_voltages, min_bv_voltages, factor_voltages = graphs(inFile, nCh, options, settings,
                                                          d_voltages, vMin*1.001, vMonLsb*options.lsbFactorVoltage)

    g_currents, min_bv_currents, factor_currents = graphs(inFile, nCh, options, settings,
                                                          d_currents, iMin*1.001, iLsb*options.lsbFactorCurrent)

    if not options.no_temperature:
        g_temperatures, min_bv_temperatures, factor_temperatures = graphs(inFile, nCh, options, settings,
                                                                          d_temperatures, tMin*1.001, tLsb*options.lsbFactorTemperature)

    p_voltages = fits(g_voltages, min_bv_voltages, options, target,  1.0)
    p_currents = fits(g_currents, min_bv_currents, options, target, 0.15)
    if not options.no_temperature:
        p_temperatures = fits(g_temperatures, min_bv_temperatures, options, target, -7.0)

    if not p_voltages:
        return

    can = r.TCanvas("canvas", "canvas", 8000, 6000)
    can.Print(outFile + "[")

    draw_per_channel(g_voltages, "PVmeas(V)", can, outFile, options,
                     xMin=-0.5, yMin=0.0, yMax=(options.bvMax if options.is_voltage else 1.0),
                     fColor1=(r.kCyan if options.is_voltage else None))
    histogram_fit_results(p_voltages, min_bv_voltages, factor_voltages,
                          options, target,
                          h["V_npoints"], h["V_mins"], h["V_factors"],
                          h["V_pvalues"], h["V_pvalues2"],
                          h["V_delta_chi2"], h["V_delta_chi2_cut_vs_ch"],
                          h["V_offsets"], h["V_offsets_unc"],
                          h["V_slopes"], h["V_slopes_unc_rel"],
                          h["V_curvatures"], h["V_curvatures_unc"],
                          warn=False)
    # histogram_fit_results_vs_channel(p_voltages, nCh, can, outFile, target=target, title="PV meas", unit="V")

    draw_per_channel(g_currents, "Imeas(A) ", can, outFile, options,
                     xMin=-0.5, yMin=0.0, yMax=(7.5/2.0 if options.is_voltage else 0.025),
                     fColor1=(r.kCyan if options.is_voltage else None), fColor2=(r.kGreen if options.is_voltage else None))
    histogram_fit_results(p_currents, min_bv_currents, factor_currents,
                          options, target,
                          h["I_npoints"], h["I_mins"], h["I_factors"],
                          h["I_pvalues"], h["I_pvalues2"],
                          h["I_delta_chi2"], h["I_delta_chi2_cut_vs_ch"],
                          h["I_offsets"], h["I_offsets_unc"],
                          h["I_slopes"], h["I_slopes_unc_rel"],
                          h["I_curvatures"], h["I_curvatures_unc"],
                          offset2=True, slope2=True)
    # histogram_fit_results_vs_channel(p_currents, nCh, can, outFile, target=target, title="Imeas", unit="A")

    if not options.no_temperature:
        draw_per_channel(g_temperatures, "T(C)", can, outFile, options,
                         xMin=-0.5, yMin=-10.0, yMax=7.5*5.0, fColor2=(r.kGreen if options.is_voltage else None))
        histogram_fit_results(p_temperatures, min_bv_temperatures, factor_temperatures,
                              options, target,
                              h["T_npoints"], h["T_mins"], h["T_factors"],
                              h["T_pvalues"], h["T_pvalues2"],
                              h["T_delta_chi2"], h["T_delta_chi2_cut_vs_ch"],
                              h["T_offsets"], h["T_offsets_unc"],
                              h["T_slopes"], h["T_slopes_unc_rel"],
                              h["T_curvatures"], h["T_curvatures_unc"],
                              offset2=True, slope2=True)

    # histogram_fit_results_vs_channel(p_temperatures, nCh, can, outFile, target=target, title="T", unit="C")

    can.Print(outFile + "]")
    printer.gray("Wrote %s" % outFile)
    return True


def multi_panel(options, hs, can, outFile, keys):
    can.cd(0)
    can.Clear()

    nPads = 4
    can.DivideSquare(nPads)

    line = r.TLine()
    line.SetLineColor(r.kMagenta)
    line.SetLineStyle(2)

    keep = []
    for iH, key in enumerate(keys):
        h = hs[key]
        can.cd(1 + (iH % nPads))
        r.gPad.SetTickx()
        r.gPad.SetTicky()

        if "vs" in h.GetName():
            h.SetBinErrorOption(r.TH1.kPoisson)
            h.Draw("e0p")
            h.SetLineWidth(2)
            # h.SetMarkerStyle(20)
            h.SetMarkerColor(h.GetLineColor())
            r.gPad.SetLogy(False)
        else:
            h.Draw("")
            h.SetLineWidth(2)
            h.SetMinimum(0.5)
            r.gPad.SetLogy("pvalue" not in h.GetName())

        # if h.GetName().startswith("I_"):
        #     xs = []
        #     if "_rel" in h.GetName():
        #         xs = [options.threshold_slope_rel_unc_warn]
        #     elif "slope" in h.GetName():
        #         xs = [options.threshold_slope_lo_warn, options.threshold_slope_hi_warn]
        #     elif "delta_chi2" in h.GetName() and "vs" not in h.GetName():
        #         xs = [options.threshold_delta_chi2_warn]

        #     for x in xs:
        #         keep.append(line.DrawLine(x, h.GetMinimum(), x, h.GetMaximum()))

        if (iH % nPads) == (nPads - 1) or iH == len(keys) - 1:
            can.Print(outFile)
    can.cd(0)
    can.Divide(1, 1)
    can.Clear()


def draw_summary(options, hs):
    outFile = options.summaryFile

    can = r.TCanvas()
    can.SetTickx()
    can.SetTicky()
    can.Print(outFile + "[")

    multi_panel(options, hs, can, outFile, ["V_pvalues", "V_offsets", "V_slopes"])
    multi_panel(options, hs, can, outFile, ["I_pvalues2", "I_offsets", "I_slopes", "I_curvatures"])
    multi_panel(options, hs, can, outFile, ["T_pvalues2", "T_offsets", "T_slopes", "T_curvatures"])

    can.Print(outFile + "]")
    print("Wrote %s" % outFile)


def histos(options):
    nCh = 4  # FIXME
    out = {}
    nPoints = 200
    nChi2 = 201
    delta_chi2 = "#chi^{2}_{0} - #chi^{2}_{c*}"
    for key, (t, b) in {"V_npoints": ("V;number of fit points;RMs / bin", (nPoints, -0.5, nPoints - 0.5)),
                        "I_npoints": ("I;number of fit points;RMs / bin", (nPoints, -0.5, nPoints - 0.5)),
                        "T_npoints": ("T;number of fit points;RMs / bin", (nPoints, -0.5, nPoints - 0.5)),
                        "V_mins": ("V;fit min PV;RMs / bin", (80, 0.0, 80.0)),
                        "I_mins": ("I;fit min PV;RMs / bin", (80, 0.0, 80.0)),
                        "T_mins": ("T;fit min PV;RMs / bin", (80, 0.0, 80.0)),
                        "V_factors": ("V;fit min V / V0;RMs / bin", (100, 0.0, options.bvMax)),
                        "I_factors": ("I;fit min I / I0;RMs / bin", (100, 0.0, options.bvMax)),
                        "T_factors": ("T;fit min T / T0;RMs / bin", (100, 0.0, options.bvMax)),
                        "V_pvalues": ("V;fit p-value 1;RMs / bin", (202, 0.0, 1.01)),
                        "I_pvalues": ("I;fit p-value 1;RMs / bin", (202, 0.0, 1.01)),
                        "T_pvalues": ("T;fit p-value 1;RMs / bin", (202, 0.0, 1.01)),
                        "V_pvalues2": ("V;fit p-value 2;RMs / bin", (202, 0.0, 1.01)),
                        "I_pvalues2": ("I;fit p-value 2;RMs / bin", (202, 0.0, 1.01)),
                        "T_pvalues2": ("T;fit p-value 2;RMs / bin", (202, 0.0, 1.01)),
                        "V_chi2": ("V;fit #chi^{2}_{0};RMs / bin", (nChi2, -10.0, 100.0)),
                        "I_chi2": ("I;fit #chi^{2}_{0};RMs / bin", (nChi2, -10.0, 100.0)),
                        "T_chi2": ("T;fit #chi^{2}_{0};RMs / bin", (nChi2, -10.0, 100.0)),
                        "V_delta_chi2": ("V;%s;RMs / bin" % delta_chi2, (nChi2, -1.0, 200.0)),
                        "I_delta_chi2": ("I;%s;RMs / bin" % delta_chi2, (nChi2, -1.0, 200.0)),
                        "T_delta_chi2": ("T;%s;RMs / bin" % delta_chi2, (nChi2, -1.0, 200.0)),
                        "V_delta_chi2_cut_vs_ch": ("V (%g < %s);RM;RMs / bin" % (options.threshold_delta_chi2_warn, delta_chi2), (nCh, 0.5, 0.5 + nCh)),
                        "I_delta_chi2_cut_vs_ch": ("I (%g < %s);RM;RMs / bin" % (options.threshold_delta_chi2_warn, delta_chi2), (nCh, 0.5, 0.5 + nCh)),
                        "T_delta_chi2_cut_vs_ch": ("T (%g < %s);RM;RMs / bin" % (options.threshold_delta_chi2_warn, delta_chi2), (nCh, 0.5, 0.5 + nCh)),
                        "V_offsets": ("V;fit offset (V);RMs / bin", (200, -0.2, 0.2)),
                        "I_offsets": ("I;fit offset (A);RMs / bin", (200, -0.5, 0.5)),
                        "T_offsets": ("T;fit offset (C);RMs / bin", (200, 0.0, 50.0)),
                        "V_offsets_unc": ("V;uncertainty on fit offset (V);RMs / bin", (200, 0.0, 0.007)),
                        "I_offsets_unc": ("I;uncertainty on fit offset (A);RMs / bin", (200, 0.0, 5.0)),
                        "T_offsets_unc": ("T;uncertainty on fit offset (C);RMs / bin", (200, 0.0, 5.0)),
                        "V_slopes": ("V;fit slope (V/V);RMs / bin", (200, 0.95, 1.05)),
                        "I_slopes": ("I;fit slope (A/V);RMs / bin", (200, 0.00, 0.50)),
                        "T_slopes": ("T;fit slope (C/V);RMs / bin", (200, -10.0, 0.0)),
                        "V_slopes_unc_rel": ("V;relative uncertainty on fit slope;RMs / bin", (200, 0.0, 2.e-4)),
                        "I_slopes_unc_rel": ("I;relative uncertainty on fit slope;RMs / bin", (200, 0.0, 0.4)),
                        "T_slopes_unc_rel": ("T;relative uncertainty on fit slope;RMs / bin", (200, 0.0, 0.4)),
                        "V_curvatures": ("V;fit curvatures (V/V^{2});RMs / bin", (200, -0.2, 0.2)),
                        "I_curvatures": ("I;fit curvatures (A/V^{2});RMs / bin", (200, -0.03, 0.03)),
                        "T_curvatures": ("T;fit curvatures (C/V^{2});RMs / bin", (200, 0.0, 1.0)),
                        "V_curvatures_unc": ("V;uncertainty on fit offset (V/V^{2});RMs / bin", (200, 0.0, 0.007)),
                        "I_curvatures_unc": ("I;uncertainty on fit offset (A/V^{2});RMs / bin", (200, 0.0, 5.0)),
                        "T_curvatures_unc": ("T;uncertainty on fit offset (C/V^{2});RMs / bin", (200, 0.0, 5.0)),
    }.items():
        if len(b) == 3:
            out[key] = r.TH1D(key, t, *b)
        else:
            out[key] = r.TH2D(key, t, *b)
    return out


def main(options, args):
    h = histos(options)
    codes = []
    for arg in args:
        codes.append(one(arg, options, h))

    if any(codes):
        draw_summary(options, h)


if __name__ == "__main__":
    r.gROOT.SetBatch(True)
    r.gStyle.SetOptStat("ourme")
    r.gErrorIgnoreLevel = r.kError
    main(*opts())
