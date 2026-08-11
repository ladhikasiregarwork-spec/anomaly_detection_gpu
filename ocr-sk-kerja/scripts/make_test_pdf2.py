import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fitz

# Template SAMA PERSIS dengan sample_sk_baru.pdf, hanya nilai field yang beda -
# untuk menguji apakah regex yang dipelajari LLM bisa dipakai ulang tanpa LLM lagi.
TEXT = """PEMERINTAH KOTA CONTOH
DINAS KEPEGAWAIAN
SURAT KEPUTUSAN
Nomor : 555/091/SK-KEPEG/2026

TENTANG PENGANGKATAN PEGAWAI NEGERI SIPIL

Menimbang, mengingat, dan memutuskan sebagaimana ketentuan yang berlaku,
maka dengan ini ditetapkan keputusan sebagai berikut:

Nama         : Ahmad Fauzi
NIP.         : 199007202016011005
Jabatan      : Pranata Komputer Ahli Muda
Unit Kerja   : Dinas Komunikasi dan Informatika Kota Contoh
Tanggal SK   : 20 Juli 2026
TMT          : 1 Agustus 2026

Keputusan ini berlaku sejak tanggal ditetapkan dengan ketentuan apabila
di kemudian hari terdapat kekeliruan dalam penetapan ini akan diadakan
perbaikan sebagaimana mestinya sesuai dengan peraturan perundang-undangan
yang berlaku di lingkungan pemerintah kota.

Ditetapkan di Contoh
Pada tanggal 20 Juli 2026
Kepala Badan Kepegawaian Daerah
"""

doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), TEXT, fontsize=10)
out = Path(__file__).resolve().parent.parent / "data" / "uploads" / "sample_sk_template_sama.pdf"
doc.save(str(out))
doc.close()
print("Saved:", out)
