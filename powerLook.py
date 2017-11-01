#!/usr/bin/env python2

import datetime, sys
import ROOT as r


def variables():
    out = ["Power", "fec-sfp_rx_power", "fec-sfp_tx_power"]
    for card in ["J14", "J15"]:
        for var in ["vtrx_rssi", "3V3_bkp", "1V2_voltage", "1V2_current"]:
            out.append("%s_%s" % (var, card))
    return out


def stamp_to_int(lst):
    try:
        year = int(lst[0][:4])
        month = int(lst[0][5:7])
        day = int(lst[0][8:])
        hour = int(lst[1][:2])
        min = int(lst[1][3:5])
        sec = int(lst[1][6:8])
        td = r.TDatime(year, month, day, hour, min, sec)
        # x = td.Get()
        x = td.Convert()
    except ValueError as e:
        print lst
        x = None
    return x


def tuples(filename=""):
    # 2017-09-27 16:22:01.966990
    # get HE[7,8]-vtrx_rssi_J15_Cntrl_f_rr # 0.000126953 0.000129395
    # get HE[7,8]-fec-sfp_tx_power_f # 569.1 585.2
    # get Power # -1.0 -1.0 -1.0 -1.0 -1.0 -1.0 -1.0 -1.0 -1.0 -1.0 -1.0 -1.0

    # 2017-10-10 14:04:01.657291
    # get HE[1-8]-vtrx_rssi_J14_Cntrl_f_rr # 0.000117187 0.000129395 2.44141e-06 7.32422e-06 7.32422e-06 4.39453e-05 2.44141e-06 1.22070e-05
    # get HE[1-8]-vtrx_rssi_J15_Cntrl_f_rr # 2.44141e-06 2.44141e-06 0.000166016 0.00015625 0.00013916 0.000141602 0.000131836 8.54492e-05
    # get HE[1-8]-fec-sfp_tx_power_f # 505.5 558.4 532.5 542.5 526.5 490. 559.6 587.6
    # get HE[1-8]-fec-sfp_rx_power_f # 341.9 384.6 1011.2 847.3 853.7 474.2 443. 890.7
    # get Power # 268.7 239.1 116.5 139.5 167.0 247.4 218.7 275.5 0.0 0.0 0.0 0.0

    # 2017-11-01 11:41:01.175211
    # get HE[1-18]-vtrx_rssi_J14_Cntrl_f_rr # 0.000200195 0.000263672 0.000178223 0.000175781 0.000168457 0.000131836 0.000134277 0.000192871 0.000412598
    # get HE[1-18]-3V3_bkp_J14_Cntrl_f_rr # 3.33008 3.3252 3.28125 3.21289 3.22266 3.20312 3.25195 3.34473 3.26172 3.30078 3.22754 3.25684 3.32031 3.2080
    # get HE[1-18]-1V2_voltage_J14_Cntrl_f_rr # 1.21826 1.21826 1.23291 1.22559 1.22314 1.22314 1.23291 1.22803 1.22314 1.23535 1.21582 1.22559 1.22803 1
    # get HE[1-18]-1V2_current_J14_Cntrl_f_rr # 0.393066 0.432129 0.41748 0.439453 0.429688 0.424805 0.412598 0.432129 0.43457 0.437012 0.41748 0.400391
    # get HE[1-18]-vtrx_rssi_J15_Cntrl_f_rr # 0.000131836 0.000126953 0.000258789 0.000280762 0.000241699 0.00032959 0.000236816 0.000102539 0.000246582
    # get HE[1-18]-3V3_bkp_J15_Cntrl_f_rr # 3.33496 3.33496 3.29102 3.21777 3.24219 3.20801 3.2666 3.36426 3.27637 3.29102 3.22266 3.27637 3.33984 3.2177
    # get HE[1-18]-1V2_voltage_J15_Cntrl_f_rr # 1.2207 1.22314 1.22803 1.23291 1.22803 1.2207 1.22314 1.23047 1.22559 1.21826 1.22803 1.22559 1.22803 1.2
    # get HE[1-18]-1V2_current_J15_Cntrl_f_rr # 0.415039 0.432129 0.319824 0.339355 0.34668 0.334473 0.446777 0.427246 0.432129 0.385742 0.419922 0.42968
    # get HE[1-18]-fec-sfp_tx_power_f # 513.4 561.9 539.4 542.4 532.8 495.3 559.5 587.6 574.4 548. 559.6 516.4 577.7 563.5 560.3 573. 558.2 559.
    # get HE[1-18]-fec-sfp_rx_power_f # 376.1 354.7 473.9 421.5 414.8 510.9 451.3 415.2 469.5 399. 353.2 335.6 391.5 424.1 390.4 418.3 490.3 425.5
    # get Power # 270.8 233.3 118.0 138.8 184.0 254.7 215.9 280.1 0.0 0.0 0.0 0.0

    out = {}

    f = open(filename)
    iStart = None
    for iLine, line in enumerate(f):
        fields = line.split()
        if not fields:
            continue

        if line[4] == "-":
            iStart = iLine
            out[iStart] = [fields[0], fields[1], {}]
            # out[iStart] = [stamp_to_int(lst), None, {}]
        if "get" not in fields[0]:
            continue
        if len(fields) < 5:
            continue

        for stem in variables():
            if stem in fields[1]:
                out[iStart][2][stem] = fields[3:]

    f.close()
    return out


def assign(out, lst):
    if lst is None:
        return
    for i in range(len(lst)):
        if len(out) <= i:
            break
        try:
            out[i] = float(lst[i])
        except ValueError as e:
            if str(e).startswith("could not convert string to float"):
                continue
            print e


def filtered(dct, n):
    out = []
    for _, lst in sorted(dct.iteritems()):
        # if not lst[2]:
        #     continue

        # ok = True
        # for x in lst[2]:
        #     if x is not None and ("I2C:" in x): # or "GEN:" in x or "timeout" in x):
        #         ok = False
        # if not ok:
        #     continue

        J14_rssis = [None] * n
        J15_rssis = [None] * n
        sfps = [None] * n
        powers = [None] * n

        assign(J14_rssis, lst[2].get("vtrx_rssi_J14"))
        assign(J15_rssis, lst[2].get("vtrx_rssi_J15"))
        assign(sfps,      lst[2].get("fec-sfp_tx_power"))
        assign(powers,    lst[2].get("Power"))

        ok = True
        for x in filter(lambda x: x is not None, sfps):
            if x < 1.0:
                ok = False
                
        if not ok:
            continue

        # if power_fib0 < 1.0 or power_fib1 < 1.0:
        #     continue

        x = stamp_to_int(lst)
        if x is None:
            continue

        out.append((x, J14_rssis, J15_rssis, sfps, powers))
    return out


def main(fileName, n=18):
    J14s = []
    J15s = []
    s = []
    f = []
    for i in range(n):
        J14s.append(r.TGraph())
        J15s.append(r.TGraph())
        s.append(r.TGraph())
        f.append(r.TGraph())

        J14s[-1].SetTitle("<I> after J14 VTRx (mA)")
        J15s[-1].SetTitle("<I> after J15 VTRx (mA)")

        s[-1].SetTitle("SFP TX <P> reported before split (mW)")
        f[-1].SetTitle("SFP TX <P> meas. after split (mW)")

    rFact = 1.0e-3
    sFact = 1.0e3
    pFact = sFact

    for x, J14_rssis, J15_rssis, sfps, powers in filtered(tuples(fileName), n):

        # hack for backward compatibility with 2-fiber setup
        if J15_rssis.count(None) == (n - 2):
            J14_rssis = [None] * 6 + J14_rssis[:2] + [None] * (n - 8)
            J15_rssis = [None] * 6 + J15_rssis[:2] + [None] * (n - 8)
            sfps      = [None] * 6 + sfps[:2]      + [None] * (n - 8)

        for i in range(n):
            j14 = J14_rssis[i]
            j15 = J15_rssis[i]
            sfp = sfps[i]
            if i < 8:  # note reversal etc.
                uhtr = powers[8 - i - 1]
            else:
                uhtr = None

            if i < 6 and x < 1506.45e6:
                continue  # uHTR was occassionally measuring data fibers, not control fibers

            if j15 is not None and 3.0e-6 < j15 < 0.5e-3:
                J15s[i].SetPoint(J15s[i].GetN(), x, j15 / rFact)

            if j14 is not None and 0.05e-3 < j14 < 0.5e-3:
                J14s[i].SetPoint(J14s[i].GetN(), x, j14 / rFact)

            if sfp is not None:
                s[i].SetPoint(s[i].GetN(), x, sfp / sFact)

            delta = 11.18e6
            if 6 <= i and (1517.598e6 - delta < x < 1517.955e6 - delta):
                continue  # different uHTR was used

            if uhtr is not None and 1.0 < uhtr < 2000.0:
                f[i].SetPoint(f[i].GetN(), x, uhtr / pFact)


    can = r.TCanvas()
    pdf = fileName.replace(".log", ".pdf")
    can.Print(pdf + "[")
    can.SetTickx()
    can.SetTicky()
    can.SetGridy()

    # h = r.TH2D("null", ";date;various;", 1, 1516.9e6, 1518e6, 1, 0.0, 0.7) # Get
    h = r.TH2D("null", ";date;;", 1, 1505.8e6, 1509.8e6, 1, 0.0, 0.7) # Convert
    h.SetStats(False)
    xaxis = h.GetXaxis()
    xaxis.SetTimeFormat("%m-%d")
    xaxis.SetTimeDisplay(1)
    xaxis.SetLabelSize(1.5 * xaxis.GetLabelSize())
    xaxis.SetTitleSize(1.5 * xaxis.GetTitleSize())
    # axis.SetTitleOffset(1.5)

    yaxis = h.GetYaxis()
    yaxis.SetLabelSize(1.5 * yaxis.GetLabelSize())

    # page1(h, J15s[6], J15s[7], s[6], s[7], f[6], f[7], can, pdf, boxYlo=0.21, boxYhi=0.29)
    multi(0,  7, h, J15s, J14s, s, f, can, pdf, boxYlo=0.21, boxYhi=0.29)
    multi(8, 15, h, J15s, J14s, s, f, can, pdf, boxYlo=0.21, boxYhi=0.29)
    multi(16, 17, h, J15s, J14s, s, f, can, pdf, boxYlo=0.21, boxYhi=0.29)

    can.Print(pdf + "]")


def draw(g, color):
    g.Draw("lp")
    g.SetLineStyle(7)
    g.SetLineColor(r.kGray)
    g.SetMarkerColor(color)
    if not g.GetN():
        print "%s has N=0" % g.GetTitle()


def legify(leg, g, n):
    g2 = g[n].Clone()
    g2.SetMarkerStyle(20)
    leg.AddEntry(g2, "#color[%d]{%s}" % (g2.GetMarkerColor(), g2.GetTitle()), "lp")
    return [g2]


def multi(nLo, nHi, h, J15s, J14s, s, f, can, pdf, boxYlo, boxYhi):
    keep = []

    text = r.TText()
    text.SetTextSize(1.5 * text.GetTextSize())
    text.SetNDC()

    line = r.TLine()
    line.SetLineColor(r.kGray + 2)
    line0 = None
    line1 = None
    line2 = None
    line3 = None

    can.cd(0)
    r.gPad.Clear()
    can.Divide(3, 3)
    for i in range(nLo, nHi + 1):
        can.cd(1 + i - nLo)
        r.gPad.SetLeftMargin(0.06)
        r.gPad.SetRightMargin(0.0)
        r.gPad.SetTopMargin(0.03)
        r.gPad.SetBottomMargin(0.1)
        r.gPad.SetTickx()
        r.gPad.SetTicky()
        r.gPad.SetGridy()

        h.Draw()
        draw(s[i], r.kBlack)
        if i < 8:
            draw(f[i], r.kOrange + 3)
        draw(J15s[i], r.kBlue)
        draw(J14s[i], r.kPink + 7)

        rbx = 1 + i
        keep.append(text.DrawText(0.15, 0.89, "HE %d" % rbx))

        if 1 <= rbx <= 2:
            x = 1508.84e6
            line.SetLineStyle(5)
            keep.append(line.DrawLine(x, 0.03, x, 0.4))
            line3 = keep[-1]

        if rbx == 2:
            x = 1507.25e6
            line.SetLineStyle(1)
            keep.append(line.DrawLine(x, 0.03, x, 0.17))
            line1 = keep[-1]

        if 3 <= rbx:
            x = 1508.24e6
            line.SetLineStyle(2)
            keep.append(line.DrawLine(x, 0.03, x, 0.36))
            line2 = keep[-1]

        if 7 <= rbx <= 8:
            x = 1507.025e6
            line.SetLineStyle(3)
            keep.append(line.DrawLine(x, 0.03, x, 0.36))
            line0 = keep[-1]


    can.cd(9)
    leg = r.TLegend(0.0, 0.0, 1.0, 1.0)
    # leg.SetBorderSize(0)
    keep += legify(leg, s, nLo)
    if nLo <= 7:
        keep += legify(leg, f, nLo)
    keep += legify(leg, J15s, nLo)
    keep += legify(leg, J14s, nLo)
    if line0 is not None:
        leg.AddEntry(line0, "#color[%d]{%s}" % (line0.GetLineColor(), "exchange splitter"), "l")
    if line1 is not None:
        leg.AddEntry(line1, "#color[%d]{%s}" % (line1.GetLineColor(), "reassemble CCM (replacing J14 VTRx)"), "l")
    if line2 is not None:
        leg.AddEntry(line2, "#color[%d]{%s}" % (line2.GetLineColor(), "J15 TX #rightarrow J15 RX; FEC #leftrightarrow J14"), "l")
    if line3 is not None:
        leg.AddEntry(line3, "#color[%d]{%s}" % (line2.GetLineColor(), "J14 TX #rightarrow J14 RX; FEC #leftrightarrow J15"), "l")
    leg.Draw()

    can.Print(pdf)


def page1(h, r7, r8, s7, s8, f0, f1, can, pdf, boxYlo, boxYhi):
    h.Draw()

    r7.Draw("lp")
    r8.SetLineColor(r.kRed)
    r8.SetMarkerColor(r.kRed)
    r8.Draw("lp")

    s7.SetLineColor(r.kBlue)
    s7.SetMarkerColor(r.kBlue)
    s7.Draw("lp")

    s8.SetLineColor(r.kCyan)
    s8.SetMarkerColor(r.kCyan)
    s8.Draw("lp")

    f0.SetLineColor(r.kMagenta)
    f0.SetMarkerColor(r.kMagenta)
    f0.Draw("lp")

    f1.SetLineColor(r.kGreen)
    f1.SetMarkerColor(r.kGreen)
    f1.Draw("lp")

    box = r.TBox()
    box.SetFillStyle(3244)
    box.SetLineColor(r.kGray)
    box.SetFillColor(r.kGray)
    delta = 11.18e6
    # box2 = box.DrawBox(1517.593e6 - delta, boxYlo, 1517.61e6 - delta, boxYhi)
    box2 = box.DrawBox(1517.593e6 - delta, boxYlo, 1517.955e6 - delta, boxYhi)

    leg1 = r.TLegend(0.12, 0.85, 0.48, 0.99)
    leg1.AddEntry(r7, r7.GetTitle(), "lp")
    leg1.AddEntry(r8, r8.GetTitle(), "lp")
    leg1.AddEntry(s7, s7.GetTitle(), "lp")
    leg1.AddEntry(s8, s8.GetTitle(), "lp")
    leg1.Draw()

    leg2 = r.TLegend(0.52, 0.85, 0.88, 0.99)
    leg2.AddEntry(f1, f1.GetTitle(), "lp")
    leg2.AddEntry(f0, f0.GetTitle(), "lp")
    leg2.AddEntry(box2, "different uHTR", "f")
    leg2.Draw()

    can.Print(pdf)


if __name__ == "__main__":
    r.gROOT.SetBatch(True)
    r.gErrorIgnoreLevel = r.kWarning

    if len(sys.argv) < 2 or not sys.argv[1].endswith(".log"):
        sys.exit("Please provide an argument ending with .log, e.g. powerMon.log")
    main(sys.argv[1])
