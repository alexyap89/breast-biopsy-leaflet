#!/usr/bin/env python3
"""Second pass on the media-edition intro sentence.

k125b originally said "The pictures are illustrations, not photographs." The set is
now photoreal, so that sentence under-describes what a patient sees. What is true —
and what the AI-media disclaimer requires — is that the images were created for this
guide and do not show a real patient. Same six keys, new wording.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
K125B = {
 "en": "Tap any step below, or press play, to see what happens at each step. The pictures were created for this guide and do not show a real patient.",
 "ms": "Ketik mana-mana langkah di bawah, atau tekan main, untuk melihat apa yang berlaku pada setiap langkah. Gambar-gambar ini dihasilkan untuk panduan ini dan bukan gambar pesakit sebenar.",
 "ta": "கீழே உள்ள எந்தப் படிநிலையையும் தட்டவும் அல்லது இயக்கவும் — ஒவ்வொரு படிநிலையிலும் என்ன நடக்கிறது என்பதைப் பார்க்கலாம். இந்தப் படங்கள் இந்த வழிகாட்டிக்காக உருவாக்கப்பட்டவை; உண்மையான நோயாளியின் புகைப்படங்கள் அல்ல.",
 "zh": "点击下面的任一步骤，或按播放，查看每一步会发生什么。图片为本指南制作的示意图，并非真实患者照片。",
 "yue": "點下面任何一步，或者撳播放，睇下每一步會發生咩事。圖片係為呢份指南製作嘅示意圖，唔係真實病人嘅照片。",
 "nan": "点击下面任一步骤，或按播放，看看每一步会怎样。图片是为本指南制作的示意图，不是真实病人的照片。",
}
for code in ("en", "ms", "ta", "zh", "yue", "nan"):
    p = os.path.join(ROOT, "src", "i18n", code + ".json")
    d = json.load(open(p, encoding="utf-8"))
    d["html"]["k125b"] = K125B[code]
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(code, "k125b updated")
