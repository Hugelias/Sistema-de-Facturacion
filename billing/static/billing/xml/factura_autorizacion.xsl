<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html" encoding="UTF-8" indent="yes"/>

<xsl:template match="/autorizacion">
<html lang="es">
<head>
<meta charset="UTF-8"/>
<title>Factura <xsl:value-of select="comprobante/factura/infoTributaria/estab"/>-<xsl:value-of select="comprobante/factura/infoTributaria/ptoEmi"/>-<xsl:value-of select="comprobante/factura/infoTributaria/secuencial"/> — TecnoStock S.A.</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Arial,sans-serif;background:#F1F5F9;min-height:100vh;display:flex;justify-content:center;padding:28px 16px;color:#0F172A}
.doc{background:#fff;width:100%;max-width:820px;box-shadow:0 4px 32px rgba(15,23,42,.12);border-radius:4px;overflow:hidden;height:fit-content}
.hdr{background:#0B1120;padding:28px 36px;display:flex;justify-content:space-between;align-items:flex-start;gap:20px}
.brand-name{color:#fff;font-size:1.1rem;font-weight:800;letter-spacing:.3px}
.brand-sub{color:#64748B;font-size:.72rem;margin-top:2px}
.num-box{text-align:right}
.label{color:#64748B;font-size:.68rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:4px}
.num{color:#fff;font-size:1.5rem;font-weight:800;line-height:1}
.date{color:#64748B;font-size:.78rem;margin-top:6px}
.sri{background:#F0FDF4;border:1.5px solid #BBF7D0;border-radius:10px;padding:14px 18px;margin:24px 36px 0}
.sri-hdr{display:flex;align-items:center;gap:8px;font-weight:700;margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px;font-size:.72rem;color:#166534}
.dot{width:8px;height:8px;border-radius:50%;background:#22C55E;display:inline-block}
.sri-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 20px;font-size:.78rem;color:#166534}
.sri-item{overflow-wrap:break-word;word-break:break-all}
.sri-lbl{font-weight:600;color:#15803D}
.body{padding:28px 36px}
.section-title{font-size:.68rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:12px}
.cgrid{display:grid;grid-template-columns:1fr 1fr;gap:0;border:1.5px solid #E2E8F0;border-radius:10px;overflow:hidden;margin-bottom:26px}
.cfield{padding:12px 16px;border-bottom:1px solid #F1F5F9}
.cfield:nth-child(odd){border-right:1px solid #F1F5F9}
.cf-label{font-size:.68rem;font-weight:600;color:#94A3B8;text-transform:uppercase;letter-spacing:.6px;margin-bottom:3px}
.cf-val{font-size:.875rem;color:#0F172A;font-weight:500}
table.items{width:100%;border-collapse:collapse;margin-bottom:22px}
table.items thead th{background:#0B1120;color:#fff;padding:10px 14px;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.7px;text-align:left}
table.items thead th.r{text-align:right}
table.items tbody td{padding:11px 14px;border-bottom:1px solid #F1F5F9;font-size:.845rem;color:#334155}
table.items td.r{text-align:right}
.totals-wrap{display:flex;justify-content:flex-end;margin-bottom:8px}
.totals{width:280px}
.trow{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #F1F5F9;font-size:.845rem}
.trow .l{color:#64748B}
.trow .v{font-weight:600;color:#0F172A}
.grand{background:#EFF6FF;border-radius:10px;padding:12px 16px;margin-top:8px;border:1.5px solid #BFDBFE}
.grand .l{color:#1D4ED8;font-size:.9rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px}
.grand .v{color:#1D4ED8;font-size:1.15rem;font-weight:800}
.footer{border-top:2px solid #F1F5F9;padding:18px 36px;background:#FAFBFF;font-size:.72rem;color:#94A3B8;text-align:center}
</style>
</head>
<body>
<div class="doc">

    <div class="hdr">
        <div>
            <div class="brand-name"><xsl:value-of select="comprobante/factura/infoTributaria/razonSocial"/></div>
            <div class="brand-sub">RUC: <xsl:value-of select="comprobante/factura/infoTributaria/ruc"/></div>
            <div class="brand-sub"><xsl:value-of select="comprobante/factura/infoTributaria/dirMatriz"/></div>
        </div>
        <div class="num-box">
            <div class="label">Factura</div>
            <div class="num">#<xsl:value-of select="comprobante/factura/infoTributaria/estab"/>-<xsl:value-of select="comprobante/factura/infoTributaria/ptoEmi"/>-<xsl:value-of select="comprobante/factura/infoTributaria/secuencial"/></div>
            <div class="date"><xsl:value-of select="comprobante/factura/infoFactura/fechaEmision"/></div>
        </div>
    </div>

    <div class="sri">
        <div class="sri-hdr"><span class="dot"></span> Estado: <xsl:value-of select="estado"/> — <xsl:value-of select="ambiente"/></div>
        <div class="sri-grid">
            <div class="sri-item"><span class="sri-lbl">N° Autorización:</span> <xsl:value-of select="numeroAutorizacion"/></div>
            <div class="sri-item"><span class="sri-lbl">Fecha autorización:</span> <xsl:value-of select="fechaAutorizacion"/></div>
            <div class="sri-item" style="grid-column:1/-1"><span class="sri-lbl">Clave de acceso:</span> <xsl:value-of select="comprobante/factura/infoTributaria/claveAcceso"/></div>
        </div>
    </div>

    <div class="body">
        <div class="section-title">Datos del cliente</div>
        <div class="cgrid">
            <div class="cfield">
                <div class="cf-label">Nombre / Razón social</div>
                <div class="cf-val"><xsl:value-of select="comprobante/factura/infoFactura/razonSocialComprador"/></div>
            </div>
            <div class="cfield">
                <div class="cf-label">Cédula / RUC</div>
                <div class="cf-val"><xsl:value-of select="comprobante/factura/infoFactura/identificacionComprador"/></div>
            </div>
        </div>

        <div class="section-title">Detalle de productos</div>
        <table class="items">
            <thead>
                <tr>
                    <th style="width:46%">Descripción</th>
                    <th style="width:14%">Cant.</th>
                    <th class="r" style="width:20%">P. Unitario</th>
                    <th class="r" style="width:20%">Subtotal</th>
                </tr>
            </thead>
            <tbody>
                <xsl:for-each select="comprobante/factura/detalles/detalle">
                <tr>
                    <td><xsl:value-of select="descripcion"/></td>
                    <td><xsl:value-of select="cantidad"/></td>
                    <td class="r">$ <xsl:value-of select="precioUnitario"/></td>
                    <td class="r">$ <xsl:value-of select="precioTotalSinImpuesto"/></td>
                </tr>
                </xsl:for-each>
            </tbody>
        </table>

        <div class="totals-wrap">
            <div class="totals">
                <div class="trow"><span class="l">Subtotal</span><span class="v">$ <xsl:value-of select="comprobante/factura/infoFactura/totalSinImpuestos"/></span></div>
                <div class="trow"><span class="l">IVA</span><span class="v">$ <xsl:value-of select="comprobante/factura/infoFactura/totalConImpuestos/totalImpuesto/valor"/></span></div>
                <div class="trow grand"><span class="l">Total</span><span class="v">$ <xsl:value-of select="comprobante/factura/infoFactura/importeTotal"/></span></div>
            </div>
        </div>
    </div>

    <div class="footer">
        Documento tributario autorizado electrónicamente (simulación) — TecnoStock S.A.
    </div>

</div>
</body>
</html>
</xsl:template>
</xsl:stylesheet>
