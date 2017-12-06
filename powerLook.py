#!/usr/bin/env python2

import datetime, sys
import ROOT as r


def variables():
    out = ["Power", "Power0", "Power1", "fec-sfp_rx_power", "fec-sfp_tx_power"]
    for card in ["J14", "J15"]:
        for var in ["vtrx_rssi", "3V3_bkp", "1V2_voltage", "1V2_current"]:
            out.append("%s_%s" % (var, card))
    return out


def stamp_to_int(lst, fiveMins=False):
    try:
        year = int(lst[0][:4])
        month = int(lst[0][5:7])
        day = int(lst[0][8:])
        hour = int(lst[1][:2])
        min = int(lst[1][3:5])
        sec = int(lst[1][6:8])
        td = r.TDatime(year, month, day, hour, min, sec)
        x = td.Convert()
    except ValueError as e:
        print lst
        return None

    # discard unless minute is multiple of five
    if fiveMins and (min % 5):
        return None

    return x


def tuples(filename="", n=None):
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
    xStart = None
    for iLine, line in enumerate(f):
        fields = line.split()
        if not fields:
            continue

        if line[4] == "-":
            xStart = stamp_to_int(fields, fiveMins=True)
            out[xStart] = {}
        if "get" not in fields[0]:
            continue
        if len(fields) < 4:
            continue
        if 'I2C:' in fields:
            continue

        if xStart is None:
            continue

        for stem in variables():
            if stem not in fields[1]:
                continue

            if len(fields) == 4:  # reads of single RBXes
                if stem not in out[xStart]:
                    out[xStart][stem] = ['0.0'] * n

                iEnd = fields[1].find("-")
                if iEnd == -1 or not fields[1].startswith("HE"):
                    continue

                try:
                    iRbx = int(fields[1][2:iEnd])
                    out[xStart][stem][iRbx - 1] = fields[3]
                except ValueError:
                    continue
            else:
                out[xStart][stem] = fields[3:]

    f.close()
    return out


def assign(n, lst):
    out = [None] * n

    if lst is None:
        return out

    for i in range(len(lst)):
        if len(out) <= i:
            break
        try:
            out[i] = float(lst[i])
        except ValueError as e:
            if str(e).startswith("could not convert string to float"):
                continue
            print e

    return out


def sfp_filter(n, d):
    sfps = assign(n, d.get("fec-sfp_tx_power"))
    for y in filter(lambda y: y is not None, sfps):
        if y < 1.0:
            return True


def main(fileName, n=18):
    J14_rssi = []
    J14_3v3  = []
    J14_1v2i = []
    J14_1v2v = []

    J15_rssi = []
    J15_3v3  = []
    J15_1v2i = []
    J15_1v2v = []

    sr = []
    st = []
    f = []
    for i in range(n):
        J14_rssi.append(r.TGraph())
        J14_3v3.append(r.TGraph())
        J14_1v2i.append(r.TGraph())
        J14_1v2v.append(r.TGraph())
        J15_rssi.append(r.TGraph())
        J15_3v3.append(r.TGraph())
        J15_1v2i.append(r.TGraph())
        J15_1v2v.append(r.TGraph())

        sr.append(r.TGraph())
        st.append(r.TGraph())
        f.append(r.TGraph())

        J14_rssi[-1].SetTitle("<I> after J14 VTRx (mA)")
        J14_3v3[-1].SetTitle("3v3 J14 (x)")
        J14_1v2i[-1].SetTitle("1v2i J14 (x)")
        J14_1v2v[-1].SetTitle("1v2v J14 (x)")
        J15_rssi[-1].SetTitle("<I> after J15 VTRx (mA)")
        J15_3v3[-1].SetTitle("3v3 J15 (x)")
        J15_1v2i[-1].SetTitle("1v2i J15 (x)")
        J15_1v2v[-1].SetTitle("1v2v J15 (x)")

        sr[-1].SetTitle("SFP RX <P> (mW)")
        st[-1].SetTitle("SFP TX <P> reported before split (mW)")
        f[-1].SetTitle("SFP TX <P> meas. after split (mW)")

    rFact = 1.0e-3
    sFact = 1.0e3
    pFact = sFact

    for x, d in sorted(tuples(fileName, n).iteritems()):
        if x is None:
            continue

        if sfp_filter(n, d):
            continue

        if hem and (hemEnd < x):
            continue

        if (x < hemEnd) and not hem:
            continue

        J14_rssis = assign(n, d.get("vtrx_rssi_J14"))
        J14_3v3s  = assign(n, d.get("3V3_bkp_J14"))
        J14_1v2is = assign(n, d.get("1V2_current_J14"))
        J14_1v2vs = assign(n, d.get("1V2_voltage_J14"))

        J15_rssis = assign(n, d.get("vtrx_rssi_J15"))
        J15_3v3s  = assign(n, d.get("3V3_bkp_J15"))
        J15_1v2is = assign(n, d.get("1V2_current_J15"))
        J15_1v2vs = assign(n, d.get("1V2_voltage_J15"))

        sfp_rxs   = assign(n, d.get("fec-sfp_rx_power"))
        sfp_txs   = assign(n, d.get("fec-sfp_tx_power"))
        if x < 1509640201:
            powers0 = assign(n, d.get("Power"))
        else:
            powers0 = assign(n, d.get("Power0"))
        powers1 = assign(n, d.get("Power1"))

        # hack for backward compatibility with 2-fiber setup
        if J15_rssis.count(None) == (n - 2):
            J14_rssis = [None] * 6 + J14_rssis[:2] + [None] * (n - 8)
            J15_rssis = [None] * 6 + J15_rssis[:2] + [None] * (n - 8)
            sfp_rxs   = [None] * 6 + sfp_rxs[:2]   + [None] * (n - 8)
            sfp_txs   = [None] * 6 + sfp_txs[:2]   + [None] * (n - 8)

        for i in range(n):
            j14_rssi = J14_rssis[i]
            j14_3v3  = J14_3v3s[i]
            j14_1v2i = J14_1v2is[i]
            j14_1v2v = J14_1v2vs[i]

            j15_rssi = J15_rssis[i]
            j15_3v3  = J15_3v3s[i]
            j15_1v2i = J15_1v2is[i]
            j15_1v2v = J15_1v2vs[i]

            sfp_rx = sfp_rxs[i]
            sfp_tx = sfp_txs[i]
            if i < 8:  # note reversal etc.
                uhtr = powers0[8 - i - 1]
            elif powers1:
                uhtr = powers1[i - 8]
            else:
                uhtr = None

            if i < 6 and x < 1506.45e6:
                continue  # uHTR was occassionally measuring data fibers, not control fibers

            if j15_rssi is not None and 3.0e-6 < j15_rssi < 0.5e-3:
                J15_rssi[i].SetPoint(J15_rssi[i].GetN(), x, j15_rssi / rFact)
            if j15_3v3:
                J15_3v3[i].SetPoint(J15_3v3[i].GetN(), x, j15_3v3)
            if j15_1v2i:
                J15_1v2i[i].SetPoint(J15_1v2i[i].GetN(), x, j15_1v2i)
            if j15_1v2v:
                J15_1v2v[i].SetPoint(J15_1v2v[i].GetN(), x, j15_1v2v)

            if j14_rssi is not None and 0.05e-3 < j14_rssi < 0.5e-3:
                J14_rssi[i].SetPoint(J14_rssi[i].GetN(), x, j14_rssi / rFact)
            if j14_3v3:
                J14_3v3[i].SetPoint(J14_3v3[i].GetN(), x, j14_3v3)
            if j14_1v2i:
                J14_1v2i[i].SetPoint(J14_1v2i[i].GetN(), x, j14_1v2i)
            if j14_1v2v:
                J14_1v2v[i].SetPoint(J14_1v2v[i].GetN(), x, j14_1v2v)

            if sfp_rx is not None and 0.01 < (sfp_rx / sFact):
                sr[i].SetPoint(sr[i].GetN(), x, sfp_rx / sFact)

            if sfp_tx is not None:
                st[i].SetPoint(st[i].GetN(), x, sfp_tx / sFact)

            delta = 11.18e6
            if 6 <= i and (1517.598e6 - delta < x < 1517.955e6 - delta):
                continue  # different uHTR was used

            if uhtr is not None and 1.0 < uhtr < 2000.0:
                f[i].SetPoint(f[i].GetN(), x, uhtr / pFact)


    can = r.TCanvas()
    can.SetTickx()
    can.SetTicky()
    can.SetGridy()

    # h = r.TH2D("null", ";date;various;", 1, 1516.9e6, 1518e6, 1, 0.0, 0.7) # Get
    if hem:
        h = r.TH2D("null", ";date;;", 100, 1505.8e6, hemEnd, 50, 0.0, 5.0) # Convert
    else:
        h = r.TH2D("null", ";date;;", 100, hemEnd, 1513.0e6, 50, 0.0, 5.0) # Convert

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

    pdfStem = fileName.replace(".log", ".hem" if hem else ".hep")
    pdf = pdfStem + ".pdf"
    can.Print(pdf + "[")
    multi( 0,  7, h, J15_rssi, J14_rssi, st, f, can, pdf, boxYlo=0.21, boxYhi=0.29, yMax=0.7)
    multi( 8, 15, h, J15_rssi, J14_rssi, st, f, can, pdf, boxYlo=0.21, boxYhi=0.29, yMax=0.7)
    multi(16, 17, h, J15_rssi, J14_rssi, st, f, can, pdf, boxYlo=0.21, boxYhi=0.29, yMax=0.7)
    can.Print(pdf + "]")

    pdf = pdfStem + ".j14.pdf"
    can.Print(pdf + "[")
    multi( 0,  7, h, J14_rssi, J14_3v3, J14_1v2i, J14_1v2v, can, pdf, boxYlo=0.21, boxYhi=0.29, yMax=4.0, xMin=1508.24e6)
    multi( 8, 15, h, J14_rssi, J14_3v3, J14_1v2i, J14_1v2v, can, pdf, boxYlo=0.21, boxYhi=0.29, yMax=4.0, xMin=1508.24e6)
    multi(16, 17, h, J14_rssi, J14_3v3, J14_1v2i, J14_1v2v, can, pdf, boxYlo=0.21, boxYhi=0.29, yMax=4.0, xMin=1508.24e6)
    can.Print(pdf + "]")

    pdf = pdfStem + ".j15.pdf"
    can.Print(pdf + "[")
    multi( 0,  7, h, J15_rssi, J15_3v3, J15_1v2i, J15_1v2v, can, pdf, boxYlo=0.21, boxYhi=0.29, yMax=4.0, xMin=1508.24e6)
    multi( 8, 15, h, J15_rssi, J15_3v3, J15_1v2i, J15_1v2v, can, pdf, boxYlo=0.21, boxYhi=0.29, yMax=4.0, xMin=1508.24e6)
    multi(16, 17, h, J15_rssi, J15_3v3, J15_1v2i, J15_1v2v, can, pdf, boxYlo=0.21, boxYhi=0.29, yMax=4.0, xMin=1508.24e6)
    can.Print(pdf + "]")


def draw(gs, i, color):
    g = gs[i]
    g.Draw("lp")
    g.SetLineStyle(7)
    g.SetLineColor(r.kGray)
    g.SetMarkerColor(color)
    if not g.GetN():
        print "%s (i=%d) has N=0" % (g.GetTitle(), i)


def legify(leg, g, n):
    g2 = g[n].Clone()
    g2.SetMarkerStyle(20)
    leg.AddEntry(g2, "#color[%d]{%s}" % (g2.GetMarkerColor(), g2.GetTitle()), "lp")
    return [g2]


def multi(nLo, nHi, h, J15s, J14s, s, f, can, pdf, boxYlo, boxYhi, yMax=None, xMin=None):
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
    line4 = None
    line5 = None
    line6 = None

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
        if xMin:
            h.GetXaxis().SetRangeUser(xMin, 9.9e99)
        if yMax:
            h.GetYaxis().SetRangeUser(0.0, yMax)
        draw(s, i, r.kBlack)
        draw(f, i, r.kOrange + 3)
        draw(J15s, i, r.kBlue)
        draw(J14s, i, r.kPink + 7)

        rbx = 1 + i
        keep.append(text.DrawText(0.15, 0.89, "HE%s %d" % ("M" if hem else "P", rbx)))

        if hem and rbx == 1:
            x = 1509.71e6
            line.SetLineStyle(3)
            keep.append(line.DrawLine(x, 0.03, x, 0.36))
            line4 = keep[-1]
            line4.SetLineColor(r.kGreen)

        if hem and 1 <= rbx <= 2:
            x = 1508.84e6
            line.SetLineStyle(5)
            keep.append(line.DrawLine(x, 0.03, x, 0.36))
            line3 = keep[-1]

        if hem and rbx == 2:
            x = 1507.25e6
            line.SetLineStyle(1)
            keep.append(line.DrawLine(x, 0.03, x, 0.17))
            line1 = keep[-1]

        if hem and 3 <= rbx:
            x = 1508.24e6
            line.SetLineStyle(2)
            keep.append(line.DrawLine(x, 0.03, x, 0.36))
            line2 = keep[-1]

        if hem and 7 <= rbx <= 8:
            x = 1507.025e6
            line.SetLineStyle(3)
            keep.append(line.DrawLine(x, 0.03, x, 0.36))
            line0 = keep[-1]

        if hem and rbx == 8:
            x = 1509.6e6
            line.SetLineStyle(1)
            keep.append(line.DrawLine(x, 0.03, x, 0.36))
            line5 = keep[-1]
            line5.SetLineColor(r.kGreen)

        if not hem:
            x = 1512.56e6
            line.SetLineStyle(2)
            keep.append(line.DrawLine(x, 0.03, x, 0.36))
            line6 = keep[-1]

    can.cd(9)
    leg = r.TLegend(0.0, 0.0, 1.0, 1.0)
    # leg.SetBorderSize(0)
    keep += legify(leg, s, nLo)
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
        leg.AddEntry(line3, "#color[%d]{%s}" % (line3.GetLineColor(), "J14 TX #rightarrow J14 RX; FEC #leftrightarrow J15"), "l")
    if line4 is not None:
        leg.AddEntry(line4, "#color[%d]{%s}" % (line4.GetLineColor(), "exchange CCM"), "l")
    if line5 is not None:
        leg.AddEntry(line5, "#color[%d]{%s}" % (line5.GetLineColor(), "reassemble CCM"), "l")
    if line6 is not None:
        leg.AddEntry(line6, "#color[%d]{%s}" % (line6.GetLineColor(), "J15 TX #rightarrow J15 RX; FEC #leftrightarrow J14"), "l")
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
    hem = False
    hemEnd = 1510.5e6
    if len(sys.argv) < 2 or not sys.argv[1].endswith(".log"):
        sys.exit("Please provide an argument ending with .log, e.g. powerMon.log")
    main(sys.argv[1])
