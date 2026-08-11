"""One-off end-to-end verification (not part of the notebooks) - replicates exactly what
DiTEmbedder and E5TextEmbedder do inside the notebooks, to confirm the pinned environment
actually produces embeddings, not just that imports succeed."""
import warnings
warnings.filterwarnings("ignore")
import logging
logging.getLogger("transformers").setLevel(logging.ERROR)

import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel, AutoTokenizer

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"torch {torch.__version__} | cuda build {torch.version.cuda} | cuda.is_available()={torch.cuda.is_available()} | DEVICE={DEVICE}\n")

# --- DiT (layout notebook) ---
print("[1/2] DiT (microsoft/dit-base) ...")
proc = AutoImageProcessor.from_pretrained("microsoft/dit-base")
dit = AutoModel.from_pretrained("microsoft/dit-base", use_safetensors=True).to(DEVICE).eval()
img = Image.fromarray((np.random.rand(300, 300, 3) * 255).astype("uint8"))
inputs = proc(images=img, return_tensors="pt").to(DEVICE)
with torch.no_grad():
    hidden = dit(**inputs).last_hidden_state
vec = hidden[0, 1:].mean(dim=0).detach().cpu().numpy().astype("float32")
print(f"      OK -> embedding shape {vec.shape}, dim={dit.config.hidden_size}\n")

# --- E5 (text notebook) ---
print("[2/2] E5 (intfloat/multilingual-e5-base) ...")
tok = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-base")
e5 = AutoModel.from_pretrained("intfloat/multilingual-e5-base", use_safetensors=True).to(DEVICE).eval()
enc = tok("passage: contoh dokumen SK Kerja pegawai", return_tensors="pt", truncation=True, max_length=512).to(DEVICE)
with torch.no_grad():
    hidden = e5(**enc).last_hidden_state
mask = enc["attention_mask"].unsqueeze(-1).to(hidden.dtype)
v = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
v = (v[0] / v[0].norm(p=2).clamp(min=1e-12)).detach().cpu().numpy().astype("float32")
print(f"      OK -> embedding shape {v.shape}, dim={e5.config.hidden_size}\n")

print(f"END-TO-END PIPELINE VERIFIED on {DEVICE.upper()}.")
