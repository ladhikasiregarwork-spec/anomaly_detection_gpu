import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fitz

TEXT = """PEMERINTAH KOTA CONTOH
DINAS KEPEGAWAIAN
SURAT KEPUTUSAN
Nomor : 555/077/SK-KEPEG/2026

TENTANG PENGANGKATAN PEGAWAI NEGERI SIPIL

Menimbang, mengingat, dan memutuskan sebagaimana ketentuan yang berlaku,
maka dengan ini ditetapkan keputusan sebagai berikut:

Nama         : Siti Rahayu
NIP.         : 199203152015022003
Jabatan      : Analis Kepegawaian Ahli Pertama
Unit Kerja   : Badan Kepegawaian Daerah Kota Contoh
Tanggal SK   : 12 Maret 2026
TMT          : 1 April 2026

Keputusan ini berlaku sejak tanggal ditetapkan dengan ketentuan apabila
di kemudian hari terdapat kekeliruan dalam penetapan ini akan diadakan
perbaikan sebagaimana mestinya sesuai dengan peraturan perundang-undangan
yang berlaku di lingkungan pemerintah kota.

Ditetapkan di Contoh
Pada tanggal 12 Maret 2026
Kepala Badan Kepegawaian Daerah
"""

doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), TEXT, fontsize=10)
out = Path(__file__).resolve().parent.parent / "data" / "uploads" / "sample_sk_baru.pdf"
doc.save(str(out))
doc.close()
print("Saved:", out)
