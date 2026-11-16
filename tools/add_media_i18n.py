#!/usr/bin/env python3
"""Add the media-edition i18n keys to all six locale files.

k125b — replaces the 3D 'drag to rotate' instruction on the media page (k125 stays
        untouched so index.html keeps its own correct instruction).
k71b  — the media stage badge ('Tap a step above, or press play'); the build emits
        this key but no locale had it, so every language silently showed English.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
K125B = {
 "en": "Tap any step below, or press play, to see what happens at each step. The pictures are illustrations, not photographs.",
 "ms": "Ketik mana-mana langkah di bawah, atau tekan main, untuk melihat apa yang berlaku pada setiap langkah. Gambar-gambar ini ialah ilustrasi, bukan fotograf.",
 "ta": "கீழே உள்ள எந்தப் படிநிலையையும் தட்டவும் அல்லது இயக்கவும் — ஒவ்வொரு படிநிலையிலும் என்ன நடக்கிறது என்பதைப் பார்க்கலாம். படங்கள் விளக்கப்படங்கள், புகைப்படங்கள் அல்ல.",
 "zh": "点击下面的任一步骤，或按播放，查看每一步会发生什么。图片为示意图，并非真实照片。",
 "yue": "點下面任何一步，或者撳播放，睇下每一步會發生咩事。圖片係示意圖，唔係真實照片。",
 "nan": "点击下面任一步骤，或按播放，看看每一步会怎样。图片是示意图，不是真实照片。",
}
K71B = {
 "en": "Tap a step above, or press play",
 "ms": "Ketik langkah di atas, atau tekan main",
 "ta": "மேலே ஒரு படிநிலையைத் தட்டவும் அல்லது இயக்கவும்",
 "zh": "点击上方步骤，或按播放",
 "yue": "點上面嘅步驟，或者撳播放",
 "nan": "点击上面的步骤，或按播放",
}
for code in ("en", "ms", "ta", "zh", "yue", "nan"):
    p = os.path.join(ROOT, "src", "i18n", code + ".json")
    d = json.load(open(p, encoding="utf-8"))
    d["html"]["k125b"] = K125B[code]
    d["html"]["k71b"] = K71B[code]
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(code, "k125b + k71b written")
