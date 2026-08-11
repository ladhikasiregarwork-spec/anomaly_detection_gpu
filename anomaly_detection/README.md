# anomaly_detection

Two self-contained Jupyter notebooks that flag suspicious documents by comparing each one against a
set of **known-genuine** examples — no labelled fakes required.

Both use the same *one-class* method (the PaDiM paradigm): turn each document into a fixed-length
vector with a **frozen** pretrained model, fit a Gaussian to the genuine vectors, and score new
documents by their **Mahalanobis distance** from that cloud. Nothing is trained, and the alarm
threshold comes purely from how much genuine documents vary among themselves.

| Notebook | Signal | Built for | Model |
|---|---|---|---|
| [`layout_based_anomaly_detection`](layout_based_anomaly_detection/) | how a page **looks** | documents with a stable, issuer-controlled layout — bank statements, ID cards (KTP) | Microsoft **DiT** (`microsoft/dit-base`, 768-dim) |
| [`text_based_anomaly_detection`](text_based_anomaly_detection/) | what a document **says** | documents whose layout varies by company — payment slips, work certificates | **multilingual-E5** (`intfloat/multilingual-e5-base`, 768-dim) |

## Which one do I want?

**Layout-based** scores *appearance*. Bank statements and KTPs come from a small number of issuers, so
"normal" has a consistent visual shape and a forged page stands out. It rasterizes **every page** and
scores each one, so a faked page 7 hiding behind a genuine page 1 is caught and named.

**Text-based** scores *meaning*. Payslips differ from company to company, so there is no normal layout
to learn — instead each document is OCR'd and its text embedded. It also applies a **required-field
checklist** (worker name, company, period, income…), matched by keyword **or by meaning**, so
"Received Income" satisfies `income`. A document is flagged if **either** its score exceeds the
threshold **or** a required field is missing.

## Unsupervised mode (no ground truth)

Both notebooks support `UNSUPERVISED = True`. Use it when you have **no known-genuine set** — just a
pile of documents to screen.

Put everything in `reference/<type>/`, leave `data/<type>/` empty, and Run-All. Each document is then
scored by its **leave-one-out** distance — how far it sits from the cloud formed by *all the others* —
and the most unusual `PERCENTILE`% (default 5%) are flagged automatically. Nothing is compared to
itself, and you never set a threshold by hand. You get the score distribution (strip plot + histogram)
and a most-unusual-first list plus CSV.

In the text notebook the required-field checklist **still applies** in this mode — it needs no
reference set — so a document can be flagged for a missing field even when its score is below the
threshold.

## Setup

Python 3.10+. Everything installs with `pip`; **there is no separate system software to install** —
PDF rendering (`pypdfium2`) and OCR (`rapidocr-onnxruntime`) both ship their engines inside the wheel,
so no Poppler and no Tesseract.

```bash
python -m venv .venv-gpu && source .venv-gpu/bin/activate

# GPU build FIRST (plain `pip install torch` / `pip install -r requirements.txt` alone gives a
# CPU-only build) — cu118 specifically, see "Setup GPU" below for why not cu121:
pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cu118

# then everything else both notebooks need (one shared env + one Jupyter kernel)
pip install -r requirements.txt

# register a Jupyter kernel for this venv
python -m ipykernel install --user --name anomaly-detection-gpu --display-name "Anomaly Detection (GPU-ready)"
```

(Folder name `.venv-gpu` on purpose, not `.venv` — see the "disk corruption" note at the end of the
GPU section below if you're wondering why.)

Then open either notebook in Jupyter and select the **"Anomaly Detection (GPU-ready)"** kernel.
`DEVICE` in the config cell of both notebooks **auto-detects CUDA** (`"cuda" if torch.cuda.is_available()
else "cpu"`) — no manual edit needed on either a GPU or a CPU-only machine.

The first run downloads model weights once and caches them (~330 MB for DiT, ~1.1 GB for E5, ~15 MB
for the RapidOCR models). To run fully offline afterwards, copy `~/.cache/huggingface` to the target
machine or point `HF_HOME` at a folder that already has the weights, then set `HF_HUB_OFFLINE=1`.

### Setup GPU — version pins and why (older/mixed hardware)

`requirements.txt` pins several packages below their latest release. Each pin exists because the
*actual* latest version breaks on real, still-common hardware (an 8th-gen Intel CPU without
AVX-512, and an old NVIDIA driver) — not out of caution. If you're on newer hardware you can likely
relax these, but they're documented here so nobody has to re-debug the same failures:

| Package | Pinned to | Why the latest breaks |
|---|---|---|
| `torch` | `==2.2.2` | `torch>=2.3` fails to even **import** on CPUs without AVX-512 (`OSError: ... DLL initialization routine failed` on Windows / illegal instruction on Linux) — its kernels assume AVX-512 is present. |
| `numpy` | `<2` | `torch==2.2.2` is compiled against the NumPy 1.x C-API. With NumPy ≥2 installed, `tensor.numpy()` doesn't just warn — it raises `RuntimeError: Numpy is not available`. |
| `opencv-python` | `<5` | `opencv-python>=5` requires NumPy ≥2, which conflicts with the pin above (needed for the OCR path — `rapidocr-onnxruntime` depends on it). |
| `onnxruntime` | `==1.17.3` | Same AVX-512 problem as `torch` above (`rapidocr-onnxruntime` pulls in the latest `onnxruntime` by default). |
| `transformers` | `>=4.40,<5` | `transformers>=5` requires `torch>=2.4` and **silently disables its PyTorch backend** if it sees 2.2.2 (`AutoModel.from_pretrained` then fails as if PyTorch weren't installed at all). |

**One more thing the notebooks now do** (see `DiTEmbedder`/`E5TextEmbedder` in each notebook's §3.2):
they call `AutoModel.from_pretrained(model_id, use_safetensors=True)`. Recent `transformers`
refuses to run legacy pickle (`torch.load`) checkpoints unless `torch>=2.6` ([CVE-2025-32434](https://nvd.nist.gov/vuln/detail/CVE-2025-32434)),
which would conflict with the `torch==2.2.2` pin above. Forcing `safetensors` sidesteps that
restriction entirely (safetensors was never affected by the CVE) — both `microsoft/dit-base` and
`intfloat/multilingual-e5-base` ship safetensors weights, so this needs no extra download.

**GPU driver.** `nvidia-smi` reports the actual driver in use; PyTorch's CUDA build needs a driver
new enough for its CUDA version (`torch.version.cuda` after install). If `torch.cuda.is_available()`
is `False` despite having an NVIDIA GPU, check `nvidia-smi`'s driver date first — an old driver
(bundled with the GPU years ago and never updated) is a common, easy-to-miss cause. Get the current
driver from [nvidia.com/Download](https://www.nvidia.com/Download/index.aspx) for your exact card,
install it **as Administrator** (a non-elevated/silent install can report success while doing
nothing), and **reboot** — a driver install doesn't take effect until the OS restarts.

**Why cu118, not cu121.** This machine (GTX 1050 Ti, driver 582.66) installs and imports the cu121
build fine right up until a GPU is actually detected — then `import torch` crashes loading
`cublas64_12.dll` with the same "DLL initialization routine failed" signature as the AVX-512 issues
above (cuBLAS's CUDA-12.x host code appears to have the same AVX-512 assumption). The cu118 build's
cuBLAS doesn't have this problem and is fully verified working here (`torch.cuda.is_available()` ==
`True`, real matmul + both models run on GPU). If cu121 works fine on your machine, that's a sign
your CPU has AVX-512 and you don't need to downgrade to cu118 at all.

**A hazard we hit worth knowing about:** running the ~900 MB driver installer *at the same time* as
a `pip install` of several GB of packages corrupted a handful of files inside the venv being built
concurrently (`OSError: [Errno 22] Invalid argument`, `"the directory is corrupted and unreadable"`
from Windows on specific files afterwards) — almost certainly because a driver install briefly
restarts the display driver / stalls the system, and that collided with pip mid-write. The broken
files couldn't be deleted or repaired in place, only worked around by building a fresh venv in a new
folder. **Don't run a GPU driver installer at the same time as a large `pip install` in the same
environment** — do the driver first, confirm it with `nvidia-smi`, *then* install packages.

## Folder layout

Each notebook auto-detects its working folder by looking for a `reference/` directory in its own
directory and the parents. Create these beside the notebook:

```
<notebook folder>/
├── the_notebook.ipynb
├── reference/<doc_type>/   ← KNOWN-GENUINE documents. These define "normal".
│                             At least 3; 12–20 is much better.
│                             (In UNSUPERVISED mode: your whole pile goes here.)
├── data/<doc_type>/        ← the documents to CHECK. Leave empty if UNSUPERVISED.
└── result/<doc_type>/      ← created for you; timestamped CSV per run.
```

Set `DOC_TYPE` in the config cell to the subfolder name (`bank_statement`, `ktp`, `payment_slip`,
`work_certificate`). Accepted files: `.pdf`, `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`. All pages of a
PDF are read.

Then choose **Run → Run All Cells**.

## Tuning

- **Sensitivity** — raise `PERCENTILE` (e.g. 99) for fewer alarms, lower it for more.
- **Resolution** (layout) — `PDF_RENDER_DPI`, default 200. Higher catches finer print, costs speed.
- **Field strictness** (text) — `semantic_threshold` in `RULES`. E5 similarities have a high baseline,
  so keep it around 0.82–0.88. Add anchor phrases so a real wording stops reading as "missing".

## Reading a result — please read this part

- **Every reference document must be genuine.** The model treats them all as the definition of
  "normal", so one bad reference widens what counts as normal.
- **A flag means "look here", not "this is fraud."** A document scoring high most often means it is a
  different layout family or document type than your references.
- **Heterogeneous pages cause false positives** (layout notebook). If a page *type* appears in `data/`
  but in no genuine reference, it can be flagged for being unusual rather than fake. Include every page
  type you expect in the reference set.
- **The threshold is not calibrated against fraud.** With only genuine examples it controls the
  false-alarm rate, nothing more. A validated cutoff needs known-fake examples.
- **Speed.** The threshold is derived by refitting the Gaussian once per sample (leave-one-out), which
  grows quadratically with the size of the set. A few hundred documents takes minutes.

## Privacy

These notebooks are designed to run **locally / on-prem**. The documents they read — statements, ID
cards, payslips — are personal data, and so is any OCR text or page image shown in a cell output.

- **Clear All Outputs before sharing or committing a notebook.** A saved `.ipynb` embeds its outputs.
  The two notebooks in this repo are committed with outputs cleared.
- **Never commit `reference/`, `data/`, or `result/`.** The `.gitignore` here excludes them; keep it
  that way.
- The results CSVs are non-identifying by design — scores, field names, and verdicts only.
