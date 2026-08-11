import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image, ImageDraw, ImageFont

TEXT_LINES = [
    "PEMERINTAH KOTA CONTOH",
    "SURAT KEPUTUSAN",
    "Nomor : 900/012/SK/2026",
    "",
    "Nama       : Dewi Lestari",
    "NIP.       : 198812102012032002",
    "Jabatan    : Bendahara",
    "Unit Kerja : Dinas Keuangan Kota Contoh",
    "Tanggal SK : 3 Juni 2026",
    "TMT        : 1 Juli 2026",
]

img = Image.new("RGB", (900, 400), "white")
draw = ImageDraw.Draw(img)
y = 20
for line in TEXT_LINES:
    draw.text((30, y), line, fill="black")
    y += 30

out = Path(__file__).resolve().parent.parent / "data" / "uploads" / "sample_sk_scan.png"
img.save(out)
print("Saved:", out)
