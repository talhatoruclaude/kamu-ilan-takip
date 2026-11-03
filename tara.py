# -*- coding: utf-8 -*-
"""Kamu ilan takip: kamuilan.sbb.gov.tr ilanlarini tarar, onlisans Isletme
mezunu (ehliyetsiz, kadin) icin uyanlari ayiklar, docs/index.html uretir."""
import re, html, io, os, json, ssl, hashlib, http.cookiejar, urllib.request
from datetime import datetime, timedelta, timezone

import pypdf

KOK = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(KOK, "docs")
PDFDIR = os.path.join(DOCS, "pdf")
DURUM = os.path.join(DOCS, "durum.json")
TR = timezone(timedelta(hours=3))
SIMDI = datetime.now(TR)

AYLAR = {"ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
         "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12}

# Basliginda bunlar gecen ilanlar onlisans mezununa zaten kapali
ATLA = re.compile(r"ÖĞRETİM|ARAŞTIRMA GÖREVLİSİ|MÜFETTİŞ|UZMAN|KALKINMA AJANSI|İPTAL|"
                  r"DÜZELTME|DÜLETME|HAKİM|SAVCI|MÜHENDİS|AVUKAT|DOKTOR|HEKİM|BİLİŞİM|"
                  r"ATAMA KURASI|TARIM İŞÇİSİ|ÇÖZÜMLEYİCİ")

IST = re.compile(r"[İI]STANBUL|[İi]stanbul|MARMARA ÜN|BOĞAZİÇİ|YILDIZ TEKNİK|GALATASARAY|"
                 r"MİMAR SİNAN|MEDENİYET|TÜRK-ALMAN|ŞİLE|GAZİOSMANPAŞA|KADIKÖY|ÜSKÜDAR|"
                 r"BEŞİKTAŞ|BEYOĞLU|FATİH|ESENYURT|PENDİK|KARTAL|MALTEPE|ÜMRANİYE|ATAŞEHİR|"
                 r"BAKIRKÖY|BAĞCILAR|BAHÇELİEVLER|SARIYER|BEYKOZ|ÇATALCA|SİLİVRİ|ESENLER")
IZM = re.compile(r"[İI]ZM[İI]R|[İi]zmir|DOKUZ EYLÜL|EGE ÜN|KATİP ÇELEBİ|DEMOKRASİ ÜN|"
                 r"KARŞIYAKA|BORNOVA|BUCA|KARABAĞLAR|BAYRAKLI|KONAK|ÇİĞLİ|BERGAMA|TORBALI|"
                 r"MENEMEN|ÖDEMİŞ|TİRE|ALİAĞA|URLA|ÇEŞME|SEFERİHİSAR|MENDERES|GAZİEMİR|NARLIDERE")


def acici():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    op = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        urllib.request.HTTPSHandler(context=ctx))
    op.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130 Safari/537.36"),
                     ("Referer", "https://kamuilan.sbb.gov.tr/"),
                     ("Accept-Language", "tr-TR,tr;q=0.9")]
    return op


def bitis_tarihi(baslik):
    m = re.search(r"(\d{1,2}) (\w+) - (\d{1,2}) (\w+)", baslik)
    if not m:
        return None, None
    def t(g, a):
        ay = AYLAR.get(a.lower().replace("I", "ı"), 0) or AYLAR.get(a.lower(), 0)
        if not ay:
            return None
        yil = SIMDI.year + (1 if ay < SIMDI.month - 3 else 0)
        try:
            return datetime(yil, ay, int(g), 23, 59, tzinfo=TR)
        except ValueError:
            return None
    return t(m.group(1), m.group(2)), t(m.group(3), m.group(4))


# "Önlisans" / "ön lisans" (PDF'te Ö bozuk gelebilir); "yüksek lisans", "lisans" yakalanmaz
ONLISANS = r"(?<![A-Za-zÇĞİÖŞÜçğıöşü])[ÖöO�][Nn] ?[Ll][İIi�][Ss][Aa][Nn][Ss]"


def ocr(b):
    """Resim PDF'i icin: pdftoppm + tesseract (sadece kuruluysa, GitHub sunucusunda kurulur)."""
    import shutil, subprocess, tempfile, glob
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return ""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.pdf")
        open(p, "wb").write(b)
        subprocess.run(["pdftoppm", "-r", "200", "-gray", "-png", p, os.path.join(d, "s")],
                       check=False, timeout=300)
        out = []
        for img in sorted(glob.glob(os.path.join(d, "s*.png")))[:8]:
            r = subprocess.run(["tesseract", img, "-", "-l", "tur"], capture_output=True,
                               text=True, timeout=300)
            out.append(r.stdout)
        return "\n".join(out)


def pdf_metni(b):
    r = pypdf.PdfReader(io.BytesIO(b))
    t = "\n".join((p.extract_text() or "") for p in r.pages)
    if len(t.strip()) < 300:
        t = ocr(b) or t
    return t


def sehir(baslik, metin):
    bas = baslik + " " + metin[:2500]
    if IST.search(bas):
        return "İstanbul"
    if IZM.search(bas):
        return "İzmir"
    return ""


def degerlendir(baslik, metin):
    """(kategori, gerekce, ayrinti) dondurur. kategori: uyan / kontrol / elenen / kapali"""
    s = re.sub(r"\s+", " ", metin)
    if len(s.strip()) < 300:
        return "kontrol", "PDF resim olarak taranmış, otomatik okunamadı. Açıp gözle bakılmalı.", ""
    yillar = set(re.findall(r"20(2[4-6])\s*(?:y.l.)?\s*(?:KPSS|Kamu Personel)", s))
    eski_kpss = "24" in yillar and "26" not in yillar

    p93 = [m.start() for m in re.finditer(r"P\s?93\b", s)]
    if not p93:
        # P93 yok: onlisans mezunu acikca isteniyor mu (isci / ozel alimlar)?
        for m in re.finditer(ONLISANS + r".{0,80}", s):
            parca = m.group(0)
            if re.search(r"mezun", parca, re.I) and not re.search(r"rg.n|.renci", parca, re.I):
                return "kontrol", "Önlisans mezunu geçiyor ama KPSS P93 tablosu yok. Şartları açıp bakmak lazım.", parca[:160]
        return "kapali", "", ""

    if eski_kpss:
        return "elenen", "2024 KPSS puanıyla alım yapıyor, 2026 puanı geçmiyor.", ""

    sebepler = []
    for pos in p93:
        w = s[max(0, pos - 900):pos + 40]
        # pencereyi bir onceki kadro satirinin puanindan sonrasina kirp
        onceki = list(re.finditer(r"P\s?(?:3|94|93|1|2|10|121)\b.{0,25}?[Pp]uan", w[:-40]))
        if onceki:
            w = w[onceki[-1].end():]
        bolum_ok = re.search(r"herhangi bir|t.m .{0,25}lisans|letme(?!n)|LETME(?!N)", w)
        ehliyet = re.search(r"s.r.c. belge|ehliyet", w, re.I)
        sadece_erkek = re.search(r"Erkek", w) and not re.search(r"Kad", w)
        kisa = w.strip()[-260:]
        if bolum_ok and not ehliyet and not sadece_erkek:
            return "uyan", "Önlisans (P93) kadrosu, bölüm şartı İşletme'yi ya da tüm önlisansları kapsıyor.", kisa
        if not bolum_ok:
            sebepler.append("belirli bölümler istiyor (İşletme yok)")
        if ehliyet:
            sebepler.append("B ehliyet istiyor")
        if sadece_erkek:
            sebepler.append("sadece erkek alıyor")
    sebepler = list(dict.fromkeys(sebepler))
    return "elenen", "Önlisans kadrosu var ama " + ", ".join(sebepler) + ".", ""


def osym_kontrol(op):
    try:
        h = op.open("https://www.osym.gov.tr/", timeout=30).read().decode("utf-8", "ignore")
        return bool(re.search(r"KPSS-2026/2[^<]{0,80}Tercih", h, re.I))
    except Exception:
        return None


def main():
    os.makedirs(PDFDIR, exist_ok=True)
    try:
        durum = json.load(open(DURUM, encoding="utf-8"))
    except Exception:
        durum = {"ilk_gorulme": {}}
    op = acici()
    ana = op.open("https://kamuilan.sbb.gov.tr/", timeout=60).read().decode("utf-8", "replace")
    ilanlar = {}
    for m in re.finditer(r"<a[^>]+href='(ilanDetay[^']+)'[^>]*>(.*?)</a>", ana, re.S):
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        t = t.replace("(", "").replace(")", "").replace("  ", " ")
        if t and t not in ilanlar:
            ilanlar[t] = html.unescape(m.group(1))
    if len(ilanlar) < 5:
        raise SystemExit("Ana sayfadan ilan listesi alınamadı (site engellemiş olabilir).")

    sonuc, kapali_sayi, hatali = [], 0, 0
    tum = []  # taranan her ilan + ne oldugu (sayfada "kendin kontrol et" listesi)
    tutulan_pdf = set()
    for baslik, link in ilanlar.items():
        bas, bit = bitis_tarihi(baslik)
        if bit and bit < SIMDI:
            tum.append((baslik, "Süresi dolmuş"))
            continue
        if ATLA.search(baslik):
            kapali_sayi += 1
            tum.append((baslik, "Önlisansa uygun değil (akademik / uzman / meslek kadrosu)"))
            continue
        try:
            b = op.open("https://kamuilan.sbb.gov.tr/" + link, timeout=90).read()
            metin = pdf_metni(b) if b[:4] == b"%PDF" else ""
        except Exception as e:
            hatali += 1
            print("HATA", baslik, e)
            tum.append((baslik, "İndirilemedi, sonraki taramada tekrar denenecek"))
            continue
        kat, gerekce, ayrinti = degerlendir(baslik, metin)
        if kat == "kapali":
            kapali_sayi += 1
            tum.append((baslik, "İlan okundu: önlisans kadrosu yok"))
            continue
        tum.append((baslik, {"uyan": "✅ UYUYOR", "kontrol": "⚠️ Kontrol et",
                             "elenen": "❌ " + gerekce}[kat]))
        anahtar = hashlib.md5(baslik.encode("utf-8")).hexdigest()[:10]
        ilk = durum["ilk_gorulme"].setdefault(anahtar, SIMDI.strftime("%Y-%m-%d"))
        pdf_ad = ""
        if kat in ("uyan", "kontrol") and b[:4] == b"%PDF":
            pdf_ad = anahtar + ".pdf"
            open(os.path.join(PDFDIR, pdf_ad), "wb").write(b)
            tutulan_pdf.add(pdf_ad)
        kurum = re.split(r" \d+ | İPTAL| ALACAK", baslik)[0].strip()
        sonuc.append({"baslik": baslik, "kurum": kurum, "kat": kat, "gerekce": gerekce,
                      "ayrinti": ayrinti, "sehir": sehir(baslik, metin), "pdf": pdf_ad,
                      "bitis": bit.strftime("%d.%m.%Y") if bit else "",
                      "kalan": (bit - SIMDI).days if bit else 999,
                      "basladi": (bas <= SIMDI) if bas else True,
                      "yeni": ilk >= (SIMDI - timedelta(days=3)).strftime("%Y-%m-%d")})
    for f in os.listdir(PDFDIR):
        if f.endswith(".pdf") and f not in tutulan_pdf:
            os.remove(os.path.join(PDFDIR, f))

    durum["son_tarama"] = SIMDI.strftime("%d.%m.%Y %H:%M")
    durum["osym_tercih"] = osym_kontrol(op)
    durum.setdefault("gecmis", []).append({"zaman": durum["son_tarama"], "toplam": len(ilanlar),
        "uyan": sum(x["kat"] == "uyan" for x in sonuc)})
    durum["gecmis"] = durum["gecmis"][-15:]
    json.dump(durum, open(DURUM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sayfa_yaz(sonuc, kapali_sayi, hatali, len(ilanlar), durum, tum)
    print(f"{len(ilanlar)} ilan, uyan={sum(x['kat']=='uyan' for x in sonuc)}, "
          f"kontrol={sum(x['kat']=='kontrol' for x in sonuc)}, elenen={sum(x['kat']=='elenen' for x in sonuc)}, "
          f"kapali={kapali_sayi}, hatali={hatali}")


def kart(x):
    e = html.escape
    rozet = ""
    if x["sehir"]:
        rozet += f'<span class="rozet sehir">{e(x["sehir"])}</span>'
    if x["yeni"]:
        rozet += '<span class="rozet yeni">YENİ</span>'
    if not x["basladi"]:
        rozet += '<span class="rozet bekle">Başvuru henüz açılmadı</span>'
    tarih = f'Son başvuru: <b>{e(x["bitis"])}</b>' if x["bitis"] else ""
    if x["bitis"] and x["kalan"] <= 3:
        tarih += ' <span class="acil">(son günler!)</span>'
    pdf = f'<a class="dugme" href="pdf/{e(x["pdf"])}">İlanı aç (PDF)</a>' if x["pdf"] else ""
    ayr = f'<details><summary>İlandaki ilgili kısım</summary><p class="alinti">{e(x["ayrinti"])}</p></details>' if x["ayrinti"] else ""
    return (f'<div class="kart {x["kat"]}"><div class="rozetler">{rozet}</div>'
            f'<h3>{e(x["baslik"])}</h3><p>{e(x["gerekce"])}</p><p class="tarih">{tarih}</p>{pdf}{ayr}</div>')


def sayfa_yaz(sonuc, kapali_sayi, hatali, toplam, durum, tum=()):
    sira = lambda x: (0 if x["sehir"] else 1, x["kalan"])
    uyan = sorted([x for x in sonuc if x["kat"] == "uyan"], key=sira)
    kontrol = sorted([x for x in sonuc if x["kat"] == "kontrol"], key=sira)
    elenen = sorted([x for x in sonuc if x["kat"] == "elenen"], key=sira)

    if durum.get("osym_tercih"):
        tercih = ('<div class="kart uyan"><h3>KPSS-2026/2 tercih kılavuzu yayımlanmış görünüyor!</h3>'
                  '<p>ÖSYM sitesinde tercih duyurusu var. Talha\'ya haber ver, kılavuzdan İstanbul/İzmir kadroları çıkaralım.</p>'
                  '<a class="dugme" href="https://www.osym.gov.tr/">ÖSYM sitesine git</a></div>')
    else:
        tercih = ('<div class="kart bilgi"><h3>Aralık: KPSS-2026/2 merkezi atama</h3>'
                  '<p>Haberlere göre tercihler 17-24 Aralık 2026 arasında (ÖSYM henüz resmî duyuru yapmadı). '
                  'Kılavuz yayımlanınca bu kutu yeşile döner.</p></div>')

    def bolum(baslik, liste, bos):
        icerik = "".join(kart(x) for x in liste) if liste else f'<p class="bos">{bos}</p>'
        return f'<h2>{baslik} <span class="sayi">{len(liste)}</span></h2>{icerik}'

    e = html.escape
    satirlar = "".join(f'<li><b>{e(b)}</b><br><span class="neden">{e(n)}</span></li>' for b, n in tum)
    gecmis = "".join(f'<li>{e(g["zaman"])}: {g["toplam"]} ilan tarandı, {g["uyan"]} uyan</li>'
                     for g in reversed(durum.get("gecmis", [])))
    kanit = f'''<h2>🔍 Kendin kontrol et</h2>
<div class="kart bilgi"><p>Bu sayfa ilanları devletin resmî ilan sitesi <b>kamuilan.sbb.gov.tr</b>'den alır.
Aşağıda taranan <b>{toplam}</b> ilanın hepsi ve her birine ne karar verildiği yazıyor.
Siteyi açıp listeyi karşılaştırabilirsin.</p>
<a class="dugme" href="https://kamuilan.sbb.gov.tr/" target="_blank" rel="noopener">Resmî ilan sitesini aç</a>
<details><summary>Taranan tüm ilanlar ({len(tum)})</summary><ol class="liste">{satirlar}</ol></details>
<details><summary>Tarama geçmişi</summary><ul class="liste">{gecmis}</ul></details></div>'''
    hata = f'<p class="not">{hatali} ilan bu taramada indirilemedi, bir sonraki taramada tekrar denenecek.</p>' if hatali else ""
    sayfa = f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Kamu İlan Takip</title>
<style>
:root{{--zemin:#0f1115;--kart:#1b1f27;--yazi:#f4f6fa;--soluk:#c3c9d4;--yesil:#2fbf71;--sari:#f2b633;--kirmizi:#ef5b5b;--mavi:#4da3ff}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--zemin);color:var(--yazi);font:19px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;padding:16px;max-width:760px;margin:auto}}
h1{{font-size:28px;margin:8px 0 4px}}
h2{{font-size:23px;margin:28px 0 12px;border-bottom:2px solid #2b313d;padding-bottom:6px}}
h3{{font-size:20px;margin:6px 0 8px;line-height:1.35}}
.ust{{color:var(--soluk);font-size:17px}}
.kart{{background:var(--kart);border-radius:14px;padding:16px;margin:12px 0;border-left:7px solid #555}}
.kart.uyan{{border-left-color:var(--yesil)}} .kart.kontrol{{border-left-color:var(--sari)}}
.kart.elenen{{border-left-color:var(--kirmizi);opacity:.92}} .kart.bilgi{{border-left-color:var(--mavi)}}
.kart p{{margin:6px 0}}
.rozet{{display:inline-block;font-size:15px;font-weight:700;padding:3px 10px;border-radius:20px;margin:0 6px 4px 0}}
.sehir{{background:var(--mavi);color:#04172b}} .yeni{{background:var(--yesil);color:#04170c}} .bekle{{background:#3a4150;color:#fff}}
.acil{{color:var(--kirmizi);font-weight:700}}
.dugme{{display:block;text-align:center;background:var(--mavi);color:#04172b;font-weight:700;text-decoration:none;padding:14px;border-radius:10px;margin-top:10px;font-size:19px}}
.sayi{{background:#2b313d;border-radius:20px;padding:2px 12px;font-size:18px}}
.bos{{color:var(--soluk);background:var(--kart);padding:16px;border-radius:14px}}
details{{margin-top:8px}} summary{{color:var(--mavi);font-size:17px}}
.alinti{{color:var(--soluk);font-size:16px}}
.not{{color:var(--soluk);font-size:16px}}
.liste{{padding-left:22px;font-size:16px}} .liste li{{margin:8px 0}} .neden{{color:var(--soluk)}}
.yenile{{display:block;width:100%;background:#2b313d;color:#fff;border:0;border-radius:10px;padding:14px;font-size:19px;margin:12px 0}}
</style></head><body>
<h1>Kamu İlan Takip</h1>
<p class="ust">Önlisans İşletme · KPSS P93 · ehliyet şartı yok · İstanbul / İzmir öncelikli<br>
Son tarama: <b>{html.escape(durum.get("son_tarama",""))}</b> · günde 3 kez otomatik güncellenir</p>
<button class="yenile" onclick="location.reload()">Sayfayı yenile</button>
{tercih}
{bolum("✅ Sana uyan ilanlar", uyan, "Şu an uyan ilan yok. Yeni ilan çıkınca burada görünecek.")}
{bolum("⚠️ Kontrol et", kontrol, "Kontrol edilecek ilan yok.")}
{bolum("❌ Önlisans kadrosu var ama uymuyor", elenen, "Yok.")}
{kanit}
<p class="not">Toplam {toplam} ilan tarandı. {kapali_sayi} ilan önlisans mezununa kapalı (lisans, lise ya da akademik kadro).
Kaynak: kamuilan.sbb.gov.tr. Başvuru öncesi ilanın kendisini mutlaka oku; otomatik eleme hata yapabilir.</p>{hata}
</body></html>"""
    open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8").write(sayfa)


if __name__ == "__main__":
    main()
