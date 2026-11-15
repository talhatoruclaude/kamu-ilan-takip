# -*- coding: utf-8 -*-
"""Kamu ilan takip: 6 resmi kaynaktan ilanlari toplar, onlisans Isletme mezunu
(ehliyetsiz, kadin) icin uyanlari ayiklar, docs/index.html uretir.

Kaynaklar: kamuilan.sbb.gov.tr, iskur.gov.tr (Ist/Izm), yerelyonetimler.csb.gov.tr
(Ist/Izm), ilan.gov.tr (personel alimi), kariyerkapisi.gov.tr (RSS), resmigazete.gov.tr
(cesitli ilanlar, son 10 gun)."""
import re, html, io, os, json, ssl, hashlib, zipfile, http.cookiejar, urllib.request, urllib.parse, urllib.error
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

# Sayfada gosterilen kaynak listesi (sira onemli)
KAYNAKLAR = [
    ("kamuilan", "kamuilan.sbb.gov.tr", "https://kamuilan.sbb.gov.tr/"),
    ("iskur", "İŞKUR (İstanbul + İzmir)", "https://www.iskur.gov.tr/ilanlar/kamu-memur-alim-ilanlari/"),
    ("yerel", "Yerel Yönetimler (belediyeler, İstanbul + İzmir)", "https://yerelyonetimler.csb.gov.tr/duyurular"),
    ("ilangov", "ilan.gov.tr (personel alımı)", "https://www.ilan.gov.tr/"),
    ("kariyer", "Kariyer Kapısı (son 25 ilan)", "https://kariyerkapisi.gov.tr/isealim"),
    ("resmi", "Resmî Gazete (çeşitli ilanlar, son 10 gün)", "https://www.resmigazete.gov.tr/"),
]
KAYNAK_KISA = {"kamuilan": "Kamu İlan", "iskur": "İŞKUR", "yerel": "Yerel Yönetimler",
               "ilangov": "ilan.gov.tr", "kariyer": "Kariyer Kapısı", "resmi": "Resmî Gazete"}


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


def url_duzelt(u):
    """Turkce karakterli / bosluklu yollari URL'ye uygun hale getirir."""
    return urllib.parse.quote(u, safe=":/?&=%#")


def tr_upper(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


def temizle(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def tarih_dmy(s, saat=(23, 59)):
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), *saat, tzinfo=TR)
    except ValueError:
        return None


def tarih_iso(s):
    try:
        return datetime.fromisoformat(s[:19]).replace(tzinfo=TR)
    except Exception:
        return None


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


def ocr_windows(b):
    """Resim PDF'i icin Windows 11'in yerlesik Turkce OCR'i (PyMuPDF + winrt)."""
    try:
        import asyncio
        import pymupdf
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
    except Exception:
        return ""

    async def oku(png):
        s = InMemoryRandomAccessStream()
        w = DataWriter(s)
        w.write_bytes(png)
        await w.store_async()
        s.seek(0)
        bmp = await (await BitmapDecoder.create_async(s)).get_software_bitmap_async()
        motor = OcrEngine.try_create_from_language(Language("tr"))
        return (await motor.recognize_async(bmp)).text if motor else ""

    try:
        doc = pymupdf.open(stream=b, filetype="pdf")
        return "\n".join(asyncio.run(oku(p.get_pixmap(dpi=200).tobytes("png")))
                         for p in list(doc)[:8])
    except Exception as e:
        print("OCR HATA", e)
        return ""


def ocr(b):
    """Resim PDF'i icin: pdftoppm + tesseract varsa o, yoksa Windows OCR."""
    import shutil, subprocess, tempfile, glob
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return ocr_windows(b)
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


def docx_metni(b):
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        x = z.read("word/document.xml").decode("utf-8", "ignore")
    x = re.sub(r"</w:p>|</w:tc>", " \n", x)
    return html.unescape(re.sub(r"<[^>]+>", "", x))


def dosya_metni(b):
    """PDF ya da DOCX baytlarindan metin."""
    if b[:4] == b"%PDF":
        return pdf_metni(b)
    if b[:2] == b"PK":
        try:
            return docx_metni(b)
        except Exception:
            return ""
    return ""


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
        return "kontrol", "İlan metni otomatik okunamadı (resim PDF ya da ek dosya). Açıp gözle bakılmalı.", ""
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


# ---------------------------------------------------------------- kaynaklar
# Her kaynak bir ilan listesi dondurur. Ilan: dict(kaynak, baslik, url, bas, bit,
# onbellek, metin) ; metin() -> dict(metin=str, pdf=bytes|None, bit=datetime|None)

def indir_dosya(op, url, timeout=90):
    b = op.open(url_duzelt(url), timeout=timeout).read()
    return {"metin": dosya_metni(b), "pdf": b if b[:4] == b"%PDF" else None}


def k_kamuilan(op):
    ana = op.open("https://kamuilan.sbb.gov.tr/", timeout=60).read().decode("utf-8", "replace")
    ilanlar = {}
    for m in re.finditer(r"<a[^>]+href='(ilanDetay[^']+)'[^>]*>(.*?)</a>", ana, re.S):
        t = temizle(m.group(2)).replace("(", "").replace(")", "").replace("  ", " ")
        if t and t not in ilanlar:
            ilanlar[t] = html.unescape(m.group(1))
    if len(ilanlar) < 5:
        raise RuntimeError("ilan listesi alınamadı (site engellemiş olabilir)")
    out = []
    for baslik, link in ilanlar.items():
        bas, bit = bitis_tarihi(baslik)
        url = "https://kamuilan.sbb.gov.tr/" + link
        out.append(dict(kaynak="kamuilan", baslik=baslik, url=url, bas=bas, bit=bit, onbellek=True,
                        metin=lambda u=url: indir_dosya(op, u)))
    return out


def k_iskur(op):
    out = []
    for tur in ("kamu-memur-alim-ilanlari", "kurumdisi-kamu-isci-alim-ilanlari"):
        for idd, il in (("istanbul", "İstanbul"), ("izmir", "İzmir")):
            u = f"https://www.iskur.gov.tr/ilanlar/{tur}/?idId={idd}&il={urllib.parse.quote(il)}"
            b = html.unescape(op.open(u, timeout=60).read().decode("utf-8", "replace"))
            for tarih, baslik, href in re.findall(
                    r'<tr class="clickable-row".*?<span>\s*([^<]*?)\s*</span>.*?<td>\s*(.*?)\s*</td>.*?<a href="([^"]+)"',
                    b, re.S):
                url = urllib.parse.urljoin("https://www.iskur.gov.tr/", href)
                out.append(dict(kaynak="iskur", baslik=temizle(baslik), url=url, bas=None,
                                bit=tarih_dmy(tarih), onbellek=True,
                                metin=lambda u=url: indir_dosya(op, u)))
    return out


def yerel_metin(op, url):
    d = op.open(url_duzelt(url), timeout=60).read().decode("utf-8", "replace")
    govde = re.sub(r"<script.*?</script>|<style.*?</style>|<nav.*?</nav>|<header.*?</header>|<footer.*?</footer>",
                   " ", d, flags=re.S)
    parcalar, pdf = [temizle(govde)], None
    for ek in dict.fromkeys(re.findall(r'href="(https://webdosya\.csb\.gov\.tr/v2/yerelyonetimler/[^"]+\.(?:pdf|docx))"', d, re.I)):
        try:
            r = indir_dosya(op, ek)
            parcalar.append(r["metin"])
            pdf = pdf or r["pdf"]
        except Exception as e:
            print("HATA ek", ek, e)
    return {"metin": "\n".join(parcalar), "pdf": pdf}


def k_yerel(op):
    b = op.open("https://yerelyonetimler.csb.gov.tr/duyurular", timeout=60).read().decode("utf-8", "replace")
    out, gorulen = [], set()
    for href, t in re.findall(r'<a[^>]+href="([^"]+-duyuru-\d+)"[^>]*>(.*?)</a>', b, re.S):
        if href in gorulen:
            continue
        gorulen.add(href)
        baslik = re.sub(r"^\d{1,2}\s+\S+\s+\d{4}\s+\S+\s+", "", temizle(t)).rstrip(". ")
        # belediye ilanlari yerel: sadece Istanbul / Izmir ilanlarini ac
        if not re.search(r"İSTANBUL|İZMİR", tr_upper(baslik)):
            continue
        url = urllib.parse.urljoin("https://yerelyonetimler.csb.gov.tr/", href)
        out.append(dict(kaynak="yerel", baslik=baslik, url=url, bas=None, bit=None, onbellek=True,
                        metin=lambda u=url: yerel_metin(op, u)))
    return out


ILANGOV_H = {"Accept": "text/plain", "Origin": "https://www.ilan.gov.tr", "Referer": "https://www.ilan.gov.tr/",
             "X-Request-Origin": "IGT-UI", "X-Requested-With": "XMLHttpRequest"}


def ilangov_metin(op, ad_id):
    d = json.loads(op.open(urllib.request.Request(
        f"https://www.ilan.gov.tr/api/api/services/app/AdDetail/GetAdDetail?id={ad_id}",
        headers=ILANGOV_H), timeout=60).read())["result"]
    icerik = re.sub(r"<style.*?</style>", " ", d.get("content") or "", flags=re.S)
    return {"metin": temizle(icerik), "pdf": None}


def k_ilangov(op):
    api = "https://www.ilan.gov.tr/api/api/services/app/Ad/AdsByFilter"
    out, atla, toplam = [], 0, 1
    while atla < toplam and atla < 400:
        govde = json.dumps({"keys": {"txv": [8]}, "skipCount": atla, "maxResultCount": 20}).encode()
        r = json.loads(op.open(urllib.request.Request(
            api, data=govde, headers=dict(ILANGOV_H, **{"Content-Type": "application/json-patch+json"})),
            timeout=60).read())["result"]
        toplam = r.get("numFound") or 0
        ads = r.get("ads") or []
        if not ads:
            break
        for a in ads:
            f = {x.get("key"): x.get("value") for x in (a.get("adTypeFilters") or [])}
            sure = (f.get("Başvuru Süresi") or "").split("-")
            baslik = f'{a.get("advertiserName", "")} - {a.get("title", "")} ({a.get("addressCityName", "")})'
            out.append(dict(kaynak="ilangov", baslik=baslik,
                            url="https://www.ilan.gov.tr" + url_duzelt(a.get("urlStr", "")),
                            bas=tarih_dmy(sure[0], (0, 0)) if sure[0] else None,
                            bit=tarih_dmy(f.get("Son başvuru Tarihi")), onbellek=True,
                            metin=lambda i=a.get("id"): ilangov_metin(op, i)))
        atla += 20
    return out


def kariyer_metin(op, guid):
    d = json.loads(op.open(urllib.request.Request(
        "https://api.kariyerkapisi.gov.tr/api/ilan/GetIlanPreviewPublic",
        data=json.dumps({"ilanGuid": guid}).encode(),
        headers={"Content-Type": "application/json", "Origin": "https://kariyerkapisi.gov.tr",
                 "Referer": "https://kariyerkapisi.gov.tr/"}), timeout=60).read())
    d = d[0] if isinstance(d, list) else d
    metin = re.sub(r"\[/?[a-zA-Z]+(?:=[^\]]*)?\]", " ", d.get("ilanMetni") or "")
    return {"metin": temizle(metin), "pdf": None, "bit": tarih_iso(d.get("bitTarih") or "")}


def k_kariyer(op):
    b = op.open("https://kariyerkapisi.gov.tr/RSS", timeout=60).read().decode("utf-8", "replace")
    out = []
    for x in re.findall(r"<item>(.*?)</item>", b, re.S):
        link = re.search(r"<link>(.*?)</link>", x, re.S)
        t = re.search(r"<title>(.*?)</title>", x, re.S)
        if not (link and t):
            continue
        link = html.unescape(link.group(1)).strip()
        guid = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("i", [""])[0]
        baslik = temizle(re.sub(r"<!\[CDATA\[|\]\]>", "", t.group(1)))
        out.append(dict(kaynak="kariyer", baslik=baslik, url=link, bas=None, bit=None, onbellek=True,
                        metin=lambda g=guid: kariyer_metin(op, g)))
    return out


def k_resmi(op):
    out, hata = [], 0
    for g in range(10):
        gun = SIMDI - timedelta(days=g)
        ds = gun.strftime("%Y%m%d")
        yol = f"https://www.resmigazete.gov.tr/ilanlar/eskiilanlar/{gun:%Y}/{gun:%m}/"
        for n in (4, 5, 3, 2, 6):
            try:
                raw = op.open(yol + f"{ds}-{n}.htm", timeout=60).read().decode("windows-1254", "replace")
            except urllib.error.HTTPError:
                continue
            except Exception:
                hata += 1
                if hata >= 3:
                    if out:
                        return out
                    raise RuntimeError("site yanıt vermedi")
                continue
            if not re.search(r"ÇEŞİTLİ İL", raw):
                continue
            for pdf, kurum in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', raw, re.S):
                url = urllib.parse.urljoin(yol, pdf)
                out.append(dict(kaynak="resmi", baslik=f"Resmî Gazete {gun:%d.%m.%Y} - {temizle(kurum).rstrip(':')}",
                                url=url, bas=None, bit=None, onbellek=True,
                                metin=lambda u=url: indir_dosya(op, u)))
            break
    return out


TOPLAYICI = {"kamuilan": k_kamuilan, "iskur": k_iskur, "yerel": k_yerel,
             "ilangov": k_ilangov, "kariyer": k_kariyer, "resmi": k_resmi}


# ---------------------------------------------------------------- ana akis

def dusuk_oncelik():
    """Windows'ta islemi 'Dusuk' oncelige al: kullanici bilgisayardayken islemciyi ona birakir."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.SetPriorityClass(k32.GetCurrentProcess(), 0x40)  # IDLE_PRIORITY_CLASS
    except Exception:
        pass


def main():
    dusuk_oncelik()
    os.makedirs(PDFDIR, exist_ok=True)
    try:
        durum = json.load(open(DURUM, encoding="utf-8"))
    except Exception:
        durum = {"ilk_gorulme": {}}
    onbellek = durum.setdefault("onbellek", {})
    op = acici()

    ilanlar, kaynak_durum = [], {}
    for k, _, _ in KAYNAKLAR:
        try:
            liste = TOPLAYICI[k](op)
            ilanlar += liste
            kaynak_durum[k] = {"ok": True, "sayi": len(liste)}
        except Exception as e:
            print("KAYNAK HATA", k, e)
            kaynak_durum[k] = {"ok": False, "sayi": 0, "hata": str(e)[:120]}
    if not ilanlar:
        raise SystemExit("Hiçbir kaynaktan ilan alınamadı.")

    sonuc, kapali_sayi, hatali = [], 0, 0
    tum = []  # taranan her ilan + ne oldugu (sayfada "kendin kontrol et" listesi)
    tutulan_pdf = set()
    for il in ilanlar:
        baslik, k = il["baslik"], il["kaynak"]
        etiket = f"[{KAYNAK_KISA[k]}] {baslik}"
        bas, bit = il["bas"], il["bit"]
        if bit and bit < SIMDI:
            tum.append((etiket, "Süresi dolmuş"))
            continue
        if ATLA.search(tr_upper(baslik)):
            kapali_sayi += 1
            tum.append((etiket, "Önlisansa uygun değil (akademik / uzman / meslek kadrosu)"))
            continue
        anahtar = hashlib.md5(il["url"].encode("utf-8")).hexdigest()[:10] if k != "kamuilan" \
            else hashlib.md5(baslik.encode("utf-8")).hexdigest()[:10]
        pdf_b = None
        kayit = onbellek.get(anahtar) if il["onbellek"] else None
        if kayit:
            kat, gerekce, ayrinti, sh = kayit["kat"], kayit["gerekce"], kayit["ayrinti"], kayit["sehir"]
            bit = bit or (tarih_iso(kayit["bit"]) if kayit.get("bit") else None)
        else:
            try:
                r = il["metin"]()
            except Exception as e:
                hatali += 1
                print("HATA", etiket, e)
                tum.append((etiket, "İndirilemedi, sonraki taramada tekrar denenecek"))
                continue
            metin, pdf_b = r.get("metin") or "", r.get("pdf")
            bit = bit or r.get("bit")
            kat, gerekce, ayrinti = degerlendir(baslik, metin)
            sh = sehir(baslik, metin)
            if il["onbellek"]:
                onbellek[anahtar] = {"kat": kat, "gerekce": gerekce, "ayrinti": ayrinti, "sehir": sh,
                                     "bit": bit.isoformat() if bit else "", "t": SIMDI.strftime("%Y-%m-%d")}
        if bit and bit < SIMDI:
            tum.append((etiket, "Süresi dolmuş"))
            continue
        if kat == "kapali":
            kapali_sayi += 1
            tum.append((etiket, "İlan okundu: önlisans kadrosu yok"))
            continue
        tum.append((etiket, {"uyan": "✅ UYUYOR", "kontrol": "⚠️ Kontrol et",
                             "elenen": "❌ " + gerekce}[kat]))
        ilk = durum["ilk_gorulme"].setdefault(anahtar, SIMDI.strftime("%Y-%m-%d"))
        pdf_ad = ""
        if k == "kamuilan" and kat in ("uyan", "kontrol"):
            yol = os.path.join(PDFDIR, anahtar + ".pdf")
            if pdf_b:
                open(yol, "wb").write(pdf_b)
            if os.path.exists(yol):  # onbellekten geldiyse onceki taramanin PDF'i duruyor
                pdf_ad = anahtar + ".pdf"
                tutulan_pdf.add(pdf_ad)
        kurum = re.split(r" \d+ | İPTAL| ALACAK", baslik)[0].strip()
        sonuc.append({"baslik": baslik, "kurum": kurum, "kat": kat, "gerekce": gerekce,
                      "ayrinti": ayrinti, "sehir": sh, "pdf": pdf_ad, "kaynak": k, "link": il["url"],
                      "bitis": bit.strftime("%d.%m.%Y") if bit else "",
                      "kalan": (bit - SIMDI).days if bit else 999,
                      "basladi": (bas <= SIMDI) if bas else True,
                      "yeni": ilk >= (SIMDI - timedelta(days=3)).strftime("%Y-%m-%d")})
    for f in os.listdir(PDFDIR):
        if f.endswith(".pdf") and f not in tutulan_pdf:
            os.remove(os.path.join(PDFDIR, f))

    # 45 gunden eski onbellek kayitlarini at
    sinir = (SIMDI - timedelta(days=45)).strftime("%Y-%m-%d")
    for a in [a for a, v in onbellek.items() if v.get("t", "") < sinir]:
        del onbellek[a]

    durum["son_tarama"] = SIMDI.strftime("%d.%m.%Y %H:%M")
    durum["osym_tercih"] = osym_kontrol(op)
    durum["kaynaklar"] = kaynak_durum
    durum.setdefault("gecmis", []).append({"zaman": durum["son_tarama"], "toplam": len(ilanlar),
        "uyan": sum(x["kat"] == "uyan" for x in sonuc)})
    durum["gecmis"] = durum["gecmis"][-15:]
    json.dump(durum, open(DURUM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sayfa_yaz(sonuc, kapali_sayi, hatali, len(ilanlar), durum, tum)
    kd = " ".join(f"{k}={'OK' if v['ok'] else 'HATA'}:{v['sayi']}" for k, v in kaynak_durum.items())
    print(f"{len(ilanlar)} ilan, uyan={sum(x['kat']=='uyan' for x in sonuc)}, "
          f"kontrol={sum(x['kat']=='kontrol' for x in sonuc)}, elenen={sum(x['kat']=='elenen' for x in sonuc)}, "
          f"kapali={kapali_sayi}, hatali={hatali} | {kd}")


def kart(x):
    e = html.escape
    rozet = f'<span class="rozet kaynak">{e(KAYNAK_KISA.get(x.get("kaynak", "kamuilan"), ""))}</span>'
    if x["sehir"]:
        rozet += f'<span class="rozet sehir">{e(x["sehir"])}</span>'
    if x["yeni"]:
        rozet += '<span class="rozet yeni">YENİ</span>'
    if not x["basladi"]:
        rozet += '<span class="rozet bekle">Başvuru henüz açılmadı</span>'
    tarih = f'Son başvuru: <b>{e(x["bitis"])}</b>' if x["bitis"] else "Son başvuru tarihi: ilanın içinde"
    if x["bitis"] and x["kalan"] <= 3:
        tarih += ' <span class="acil">(son günler!)</span>'
    if x["pdf"]:
        dugme = f'<a class="dugme" href="pdf/{e(x["pdf"])}">İlanı aç (PDF)</a>'
    elif x.get("link"):
        dugme = f'<a class="dugme" href="{e(x["link"])}" target="_blank" rel="noopener">İlanı kaynağında aç</a>'
    else:
        dugme = ""
    ayr = f'<details><summary>İlandaki ilgili kısım</summary><p class="alinti">{e(x["ayrinti"])}</p></details>' if x["ayrinti"] else ""
    return (f'<div class="kart {x["kat"]}"><div class="rozetler">{rozet}</div>'
            f'<h3>{e(x["baslik"])}</h3><p>{e(x["gerekce"])}</p><p class="tarih">{tarih}</p>{dugme}{ayr}</div>')


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
    kd = durum.get("kaynaklar", {})
    kaynak_satir = ""
    for k, ad, url in KAYNAKLAR:
        v = kd.get(k, {})
        if v.get("ok"):
            d = f'✅ {v.get("sayi", 0)} ilan alındı'
        elif v:
            d = '⚠️ Bu taramada ulaşılamadı, sonraki taramada tekrar denenecek'
        else:
            d = "—"
        kaynak_satir += f'<li><a href="{e(url)}" target="_blank" rel="noopener">{e(ad)}</a><br><span class="neden">{d}</span></li>'
    satirlar = "".join(f'<li><b>{e(b)}</b><br><span class="neden">{e(n)}</span></li>' for b, n in tum)
    gecmis = "".join(f'<li>{e(g["zaman"])}: {g["toplam"]} ilan tarandı, {g["uyan"]} uyan</li>'
                     for g in reversed(durum.get("gecmis", [])))
    kanit = f'''<h2>🔍 Kendin kontrol et</h2>
<div class="kart bilgi"><p>Bu sayfa ilanları aşağıdaki <b>{len(KAYNAKLAR)} resmî siteden</b> toplar.
Her siteyi açıp karşılaştırabilirsin. Aynı ilan iki sitede yayımlandıysa listede iki kez görünebilir.</p>
<ul class="liste">{kaynak_satir}</ul>
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
.kaynak{{background:#2b313d;color:#dfe5ee;font-weight:600}}
.acil{{color:var(--kirmizi);font-weight:700}}
.dugme{{display:block;text-align:center;background:var(--mavi);color:#04172b;font-weight:700;text-decoration:none;padding:14px;border-radius:10px;margin-top:10px;font-size:19px}}
.sayi{{background:#2b313d;border-radius:20px;padding:2px 12px;font-size:18px}}
.bos{{color:var(--soluk);background:var(--kart);padding:16px;border-radius:14px}}
details{{margin-top:8px}} summary{{color:var(--mavi);font-size:17px}}
.alinti{{color:var(--soluk);font-size:16px}}
.not{{color:var(--soluk);font-size:16px}}
.liste{{padding-left:22px;font-size:16px}} .liste li{{margin:8px 0}} .neden{{color:var(--soluk)}}
.liste a{{color:var(--mavi)}}
.yenile{{display:block;width:100%;background:#2b313d;color:#fff;border:0;border-radius:10px;padding:14px;font-size:19px;margin:12px 0}}
</style></head><body>
<h1>Kamu İlan Takip</h1>
<p class="ust">Önlisans İşletme · KPSS P93 · ehliyet şartı yok · İstanbul / İzmir öncelikli<br>
Son tarama: <b>{html.escape(durum.get("son_tarama",""))}</b> · günde 3 kez otomatik güncellenir · {len(KAYNAKLAR)} kaynak</p>
<button class="yenile" onclick="location.reload()">Sayfayı yenile</button>
{tercih}
{bolum("✅ Sana uyan ilanlar", uyan, "Şu an uyan ilan yok. Yeni ilan çıkınca burada görünecek.")}
{bolum("⚠️ Kontrol et", kontrol, "Kontrol edilecek ilan yok.")}
{bolum("❌ Önlisans kadrosu var ama uymuyor", elenen, "Yok.")}
{kanit}
<p class="not">Toplam {toplam} ilan tarandı. {kapali_sayi} ilan önlisans mezununa kapalı (lisans, lise ya da akademik kadro).
Başvuru öncesi ilanın kendisini mutlaka oku; otomatik eleme hata yapabilir.</p>{hata}
</body></html>"""
    open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8").write(sayfa)


if __name__ == "__main__":
    main()
