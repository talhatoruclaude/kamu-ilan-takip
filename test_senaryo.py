import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # calistir: python test_senaryo.py
import tara
D = "Genel şartlar: 657 sayılı Devlet Memurları Kanununun 48 inci maddesindeki şartları taşımak. " * 6
T = "Sıra No Kadro Unvanı Sınıfı Derece Adet Niteliği Cinsiyeti KPSS Puan Türü KPSS Taban Puanı "
S = [
 # --- güvenlik kartı
 ("uymaz", "Silahlı güvenlik kartı (Milli Saraylar biçimi)", "1.Grup: Unvanı: Koruma ve Güvenlik Görevlisi Kadro Adedi: 12 Öğrenim Grubu: Ön Lisans KPSS P93 Özel Şartları: 1- KPSS P93 puan türünde en az 60 puan almış olmak. 2- 5188 sayılı Kanunun 10 uncu maddesindeki şartlar. 3- Silahlı Güvenlik Kimlik Kartına sahip olmak veya bu belge için başvurmuş olmak. 4- 45 yaşını doldurmamış olmak. 5- Herhangi bir ön lisans bölümünden mezun olmak. 2.Grup: Unvanı: Restoratör"),
 ("uymaz", "Silahsız özel güvenlik kimlik kartı (tablo)", T + "1 Koruma ve Güvenlik Görevlisi 3 -Herhangi bir önlisans programından mezun olmak. -Geçerli özel güvenlik görevlisi kimlik kartına sahip olmak. Kadın/Erkek P93 En az 60 puan"),
 ("uymaz", "BÜYÜK HARF güvenlik sertifikası", T + "1 GÜVENLİK GÖREVLİSİ 2 -HERHANGİ BİR ÖNLİSANS PROGRAMINDAN MEZUN OLMAK. -ÖZEL GÜVENLİK SERTİFİKASINA SAHİP OLMAK. KADIN/ERKEK P93 EN AZ 60 PUAN"),
 ("uyar",  "Satır 1 güvenlik, satır 2 düz memur", T + "1 Güvenlik Görevlisi 2 -Herhangi bir önlisans programından mezun olmak. -Silahlı özel güvenlik kimlik kartı. Kadın/Erkek P93 En az 60 puan 2 Memur 3 -Herhangi bir önlisans programından mezun olmak. Kadın/Erkek P93 En az 60 puan"),
 ("uyar",  "Satır 1 düz memur, satır 2 güvenlik (karışmamalı)", T + "1 Memur 3 -Herhangi bir önlisans programından mezun olmak. Kadın/Erkek P93 En az 60 puan 2 Güvenlik Görevlisi 2 -Herhangi bir önlisans programından mezun olmak. -Silahlı özel güvenlik kimlik kartı. Kadın/Erkek P93 En az 60 puan"),
 # --- bölüm / düz / lise
 ("uyar",  "Herhangi bir önlisans (tablo)", T + "1 Memur GİH 9 2 -Herhangi bir önlisans programından mezun olmak. Kadın/Erkek P93 En az 60 puan"),
 ("uyar",  "Önlisans programlarının herhangi birinden", T + "1 Memur 1 Önlisans programlarının herhangi birinden mezun olmak. Kadın/Erkek P93 En az 65 puan"),
 ("uyar",  "Tüm bölümler (önlisans)", T + "1 Büro Personeli 2 Ön Lisans (Tüm Bölümler) Kadın/Erkek P93 En az 60 puan"),
 ("uyar",  "Düz 'Ön lisans mezunu olmak'", T + "1 Memur 1 -Ön lisans mezunu olmak. Kadın/Erkek P93 En az 60 puan"),
 ("uyar",  "Lise veya dengi", T + "1 Memur 2 -Lise veya dengi okul mezunu olmak. Kadın/Erkek P94 En az 60 puan"),
 ("uyar",  "En az lise (P94 70 biçimi)", "KOD UNVAN ADET 1 Büro Personeli 2 En az lise mezunu olmak. Kadın/Erkek P94 70 İzmir"),
 ("uyar",  "Ortaöğretim herhangi bir bölüm", T + "1 Memur 1 Ortaöğretim kurumlarının herhangi bir bölümünden mezun olmak. Kadın/Erkek P94 En az 65 puan"),
 ("uymaz", "İşletme önlisans programından", T + "1 Memur 1 -İşletme önlisans programından mezun olmak. Kadın/Erkek P93 En az 60 puan"),
 ("uymaz", "Belirli önlisans listesi", T + "1 Zabıta 9 -Mahalli İdareler, Yerel Yönetimler önlisans programlarının birinden mezun olmak. Kadın/Erkek P93 En az 60 puan"),
 ("uymaz", "Lise muhasebe alanı", T + "1 Memur 1 Ortaöğretim kurumlarının Muhasebe ve Finansman alanından mezun olmak. Kadın/Erkek P94 En az 60 puan"),
 ("uymaz", "Lisans 'tüm bölümler' + önlisans belirli", T + "1 Memur 1 Tüm bölümler lisans mezunu olmak P3 En az 70 puan 2 Teknisyen 1 Elektrik önlisans programından mezun olmak P93 En az 60 puan"),
 ("uymaz", "Sadece lisans herhangi bir bölüm", T + "1 Memur 2 Herhangi bir lisans programından mezun olmak. Kadın/Erkek P3 En az 70 puan"),
 # --- ehliyet / cinsiyet
 ("uymaz", "B sınıfı sürücü belgesi", T + "1 Memur 1 -Herhangi bir önlisans programından mezun olmak. -En az (B) sınıfı sürücü belgesine sahip olmak. Kadın/Erkek P93 En az 60 puan"),
 ("uymaz", "Ehliyet büyük harf", T + "1 MEMUR 1 HERHANGİ BİR ÖNLİSANS PROGRAMINDAN MEZUN OLMAK. B SINIFI EHLİYET SAHİBİ OLMAK. KADIN/ERKEK P93 EN AZ 60 PUAN"),
 ("uyar",  "Ehliyet tercih sebebi (elememeli)", T + "1 Memur 1 -Herhangi bir önlisans programından mezun olmak. -B sınıfı sürücü belgesi olması tercih sebebidir. Kadın/Erkek P93 En az 60 puan"),
 ("uymaz", "Sadece erkek", T + "1 Bekçi 1 -Herhangi bir önlisans programından mezun olmak. Erkek P93 En az 60 puan"),
 ("uyar",  "Sadece kadın", T + "1 Memur 1 -Herhangi bir önlisans programından mezun olmak. Kadın P93 En az 60 puan"),
 ("uyar",  "Grup biçimi + 'Erkek adayların askerlik' (elememeli)", "1.Grup: Unvanı: Memur Kadro Adedi: 3 Öğrenim: Ön Lisans KPSS P93 Özel Şartları: 1- KPSS P93 puan türünde en az 60 puan almış olmak. 2- Erkek adayların askerlik hizmetini yapmış olmaları. 3- Herhangi bir ön lisans bölümünden mezun olmak. 2.Grup: Unvanı: Tekniker"),
 # --- KPSS / metin durumu
 ("uymaz", "2024 KPSS puanı", T + "1 Memur 1 -Herhangi bir önlisans programından mezun olmak. 2024 KPSS P93 En az 60 puan"),
 ("kontrol", "Genel şart cümlesi, kadro tablosu resim", "Lisans mezunları için KPSS P3, ön lisans mezunları için KPSS P93 puan türünde en az 60 puan almış olmak. Kadrolar ekteki tabloda belirtilmiştir."),
 ("kontrol", "KPSS yok, işçi alımı lise", "Temizlik görevlisi alınacaktır. Şartlar: en az lise mezunu olmak, 18 yaşını doldurmuş olmak."),
 ("kontrol", "Metin okunamadı (kısa)", "Ek dosyaya bakınız."),
 ("uymaz", "Önlisans hiç yok (sadece lisans P3)", T + "1 Mühendis 1 İnşaat Mühendisliği lisans programından mezun olmak P3 En az 70 puan"),
]
hata = 0
for bek, ad, metin in S:
    k, g, a = tara.degerlendir("x", (D + metin) if len(metin) > 40 else metin)
    sonuc = {"uyan": "uyar", "elenen": "uymaz", "kapali": "uymaz", "kontrol": "kontrol"}[k]
    ok = sonuc == bek
    hata += not ok
    print(("✔" if ok else "✘ HATA"), f"[beklenen {bek:7} / çıkan {k:7}] {ad}" + ("" if ok else f"\n      → {g}"))
print(f"\n{len(S)-hata}/{len(S)} doğru")
