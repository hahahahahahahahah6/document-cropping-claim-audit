# Documentation claim auditor

An offline static auditor comparing documentation promises with listed source patterns. It reads root README.md and Markdown files under any docs path component. Source is parsed with the standard library and never executed. No network, telemetry, or audit-time writes are used.

## Usage

```sh
python3 -m pip install .
document-cropping-claim-audit audit . --json
python3 -m document_cropping_claim_audit audit . --verbose
document-cropping-claim-audit audit . --fail-on medium --ignore vendor --ignore generated
document-cropping-claim-audit --version
```

The audit subcommand defaults to the current directory. Each ignore option accepts one relative path prefix. The default threshold is high; medium also fails on test-only findings. Exit codes are 0 for PASS, 2 for findings meeting the threshold, and 1 for usage or I/O errors. A PASS can contain a medium finding. JSON contains verdict, findings (rule, severity, message, locations), production_evidence, and test_evidence. Verbose text includes claims and evidence locations.

## Matching

Blank lines delimit paragraphs. Backtick and tilde fences with up to three leading spaces are excluded; inline code counts. Text is lowercased, contractions expanded, hyphens replaced with spaces, and whitespace collapsed. Exact phrases match at word boundaries, longest first with alphabetical ties. Denial spans are removed before positive matching. There is at most one finding per claim family.

Only listed calls within a single module count. Import aliases resolve; local function, method and class definitions shadow route names. Assignments, annotated assignments and context-manager bindings shadow imported names. Attribute assignments do not shadow a base import. Syntax-invalid files and symlinks provide no evidence. Files under fixtures, docs and examples are excluded; tests are tracked separately. A positive statement without source fails; a denial without source passes.

```text
documented-document-cropping-claim-false HIGH (MEDIUM when evidence is test-only)
documented-no-document-cropping-claim-false HIGH
```

## Evidence and scope

The checked operation finds positions of documents in images, returning coordinates for each. It differs from extracting fields, recognizing text, finding tables, grouping pages, or cutting an image to supplied coordinates. The precise vocabulary and accepted calls are listed below.

```text
document cropping
crop documents
crops documents
cropping documents
crop document
crops document
cropping document
document cropper
document croppers
document crop
document crops
crop document images
crops document images
cropping document images
crop document image
crops document image
cropping document image
document image cropping
crop document photos
crops document photos
cropping document photos
crop document photo
crops document photo
cropping document photo
document photo cropping
automatic document cropping
automatically crop documents
auto crop documents
document auto cropping
detect documents and crop
detects documents and crops
document detection and cropping
document boundary cropping
crop to document boundaries
crops to document boundaries
document edge cropping
crop document edges
document scan and crop
document scan and cropping
crop scanned documents
crops scanned documents
cropping scanned documents
scanned document cropping
document cropping tool
document cropping feature
document cropping support
supports document cropping
document cropping api
document cropping service
document cropping function
no document cropping
does not crop documents
does not crop document
does not support document cropping
without document cropping
no document cropper
does not crop document images
does not crop document image
no document crop
does not detect documents and crop
no automatic document cropping
does not automatically crop documents
no document image cropping
does not crop document photos
does not crop document photo
no document photo cropping
does not crop scanned documents
does not crop to document boundaries
without document cropper
no document cropping tool
no document cropping feature
does not support document cropper
document cropping not supported
no scanned document cropping

Generic call names:
crop_document, crop_documents, crop_document_image, crop_document_images, crop_document_photo, crop_document_photos, detect_and_crop_document, detect_and_crop_documents, document_cropper, document_crop, document_cropping, auto_crop_document, auto_crop_documents, automatic_document_crop, automatic_document_cropping, extract_document_crop, get_document_cropping, find_document_crop, find_document_cropping, scan_and_crop_document, scan_and_crop_documents, crop_to_document, crop_to_documents, crop_document_edges

Mindee: Client construction plus .parse(CropperV1, ...) or
.parse(product_class=CropperV1, ...) in one module. Imports and aliases
are resolved, including mindee.v1 paths. A Client alone does not count.
```

## Honest limitations

Static patterns are not semantic proof. Dead code counts. Unresolved alias chains are missed. Exact wording and the denial vocabulary limit coverage. The following detailed limitations explain false positives and omitted operations; quoted wording is fenced to avoid making a claim about the auditor itself.

```text
- The bare phrases "document cropping" / "crop document" / "crop
  documents" are deliberately DOCUMENTCROPPING phrases: in
  document-tool docs they almost always name document cropping.
  But "document cropping" can also name a manual corner-drag crop
  UI that lets a user drag corners around a document photo with no
  detection at all: a doc that means manual cropping, not
  detection-based cropping, is a false positive; the tool flags
  the claim, only the code decides.
- "document cropper" / "document crop" are deliberately phrases:
  "document cropper" can also name a UI widget or a library
  function that crops to coordinates the caller supplies, with no
  document detection. The tool flags the claim; only the code
  decides.
- "detect documents and crop" / "document detection and cropping"
  are deliberately phrases: "document detection" alone can mean
  merely classifying whether an image contains a document, with
  no positions returned and no crop performed. The tool flags the
  claim; only the code decides.
- "crop document photos" / "document photo cropping" are
  deliberately phrases: a doc can say "crop document photos"
  about a tool that only crops photos to a fixed aspect ratio for
  upload, with no document detection. The tool flags the claim;
  only the code decides.
- "document scanning and cropping" claims are deliberately NOT in
  the phrase lists as a single phrase: scanning a document (OCR /
  capture) plus cropping it is two operations, and the lists cover
  the cropping half ("document scan and crop", "document scan and
  cropping"). A doc that claims scanning only is missed. Say so in
  the README.
- "document boundary detection" / "detect document boundaries" /
  "document edge detection" claims are deliberately NOT in the
  phrase lists: detecting a document boundary without cropping is
  detection, not cropping, and the lists require a crop verb or
  noun. A doc that claims boundary detection only is missed. 
- "receipt cropping" / "crop receipts" claims are deliberately NOT
  in the phrase lists: cropping receipts is the multi-receipts
  family's neighbour, and the lists require the word "document".
  A doc that claims receipt cropping only is missed. Say so in the
  README.
- "image cropping" / "crop images" claims are deliberately NOT in
  the phrase lists: cropping an image to supplied coordinates is
  the image-cropping family's domain (R168), not document
  cropping, and the lists require the word "document". A doc that
  claims image cropping only is missed. 
- "page cropping" / "crop pages" claims are deliberately NOT in
  the phrase lists: cropping a PDF page is a different operation
  from detecting documents in a photo. 
- CropperV1 returns cropping positions (List[PositionField]), not
  a cropped image: the downstream crop is performed by the
  caller's own code. The tool detects the CropperV1 call, not
  whether the caller actually crops with the returned positions.
  
- CropperV1 is NOT a 4.x-only fingerprint: the mindee 5.4.0 wheel
  still contains it at mindee/v1/product/cropper/. Say so in the
  README.
- The CropperExtra / `cropping` extra attached to other mindee
  products' predictions is NOT detected: it is position metadata
  attached to every mindee prediction, not a CropperV1 call. 
- Mindee `parse` with ANY product other than CropperV1 is NOT
  detected: in particular MultiReceiptsDetectorV1 (detecting
  receipts is not detecting documents generally) and
  InvoiceSplitterV1 (page grouping is not cropping). Say so in the
  README.
- Mindee `parse` passing CropperV2 or TypeCropperV1 is NOT
  detected: neither exists in the 4.22.0 or 5.4.0 wheels. Say so in
  the README.
- Pillow `Image.crop` / `ImageOps.crop`, OpenCV array slicing,
  and scikit-image `crop` calls are NOT detected: cropping to
  supplied coordinates is the image-cropping family's domain (R168)
  — no document detection. 
- cv2.findContours / cv2.boundingRect / YOLO / generic object
  detection calls are NOT detected: finding shapes is not finding
  documents. 
- Azure `begin_analyze_document` with ANY model id is NOT
  detected: there is no crop model in the v4.0 GA catalog
  (prebuilt-layout is layout analysis, prebuilt-read is OCR).
  
- Veryfi calls of ANY kind are NOT detected: veryfi has no crop
  method (5.1.0 wheel inspected 2026-11-15 — zero "crop" hits in
  any file name or any .py file). 
- Google Document AI `process_document` /
  `batch_process_documents` with ANY processor is NOT detected:
  Document AI has no document-crop processor. 
- Eden AI universal-ai calls with ANY model id are NOT detected:
  Eden AI documents no document-crop parser model. Say so in the
  README.
- Textract calls of ANY kind are NOT detected: Textract has no
  crop operation, and Textract Queries carries free-text
  natural-language questions with no fixed static fingerprint
  naming document cropping. 
- LlamaParse calls are NOT detected: its parsing API is
  generative with no fixed static fingerprint naming document
  cropping. 
- Nanonets / Docsumo / ABBYY Vantage / Rossum / Klippa / Parseur /
  Extend calls are NOT detected: opaque model / skill / queue /
  template / workflow IDs, or a generic upload endpoint with the
  document type configured outside the call — no fixed fingerprint.
  
- A hand-rolled extraction from OCR text (`re.search` /
  `re.findall` on extracted text plus manual field assembly, no
  listed call) is NOT detected: the tool requires a listed call.
  
- A hand-rolled document detector built on cv2.findContours or
  YOLO plus a Pillow crop is NOT detected: the tool requires a
  listed call (mindee CropperV1 or a document-crop-named call).
  
- The mindee CLI and any other external document cropping tool
  invoked through subprocess are NOT detected: subprocess calls
  invoking an external CLI are NOT evidence by design. Say so in
  the README.
- Mindee is a cloud API: the tool detects the client call in
  source, not whether credentials are configured or the call
  succeeds. 
- Invoice extraction claims ("extract invoices", "invoice
  extraction"), receipt extraction claims ("extract receipts",
  "receipt extraction"), ID document extraction claims ("extract
  passports", "passport extraction"), bank check extraction claims
  ("extract bank checks", "check extraction"), bank statement
  extraction claims ("extract bank statements", "statement
  extraction"), tax form extraction claims ("extract tax forms",
  "extract w2 forms", "1099 extraction"), pay stub extraction
  claims ("extract pay stubs", "payslip extraction"), health
  insurance card extraction claims ("extract health insurance
  cards", "health insurance card extraction"), business card
  extraction claims ("extract business cards", "business card
  extraction"), credit card extraction claims ("extract credit
  cards", "credit card extraction"), contract extraction claims
  ("extract contracts", "contract extraction"), mortgage
  extraction claims ("extract mortgages", "mortgage extraction"),
  resume extraction claims ("extract resumes", "resume
  extraction"), bill of lading extraction claims ("extract
  bills of lading", "bill of lading extraction"), delivery
  note extraction claims ("extract delivery notes", "delivery
  note extraction"), carte grise extraction claims ("extract
  carte grises", "carte grise extraction"), energy bill
  extraction claims ("extract energy bills", "energy bill
  extraction"), marriage certificate extraction claims ("extract
  marriage certificates", "marriage certificate extraction"),
  bank account details extraction claims ("extract bank account
  details", "bank account details extraction"), nutrition facts
  label extraction claims ("extract nutrition facts labels",
  "nutrition facts label extraction"), material certificate
  extraction claims ("extract material certificates", "material
  certificate extraction"), US mail extraction claims ("extract
  us mail", "us mail extraction"), invoice splitter claims
  ("split invoices", "invoice splitting"), multi-receipts
  detection claims ("detect multiple receipts", "multi receipt
  detection"), French health card extraction claims ("extract
  carte vitales", "french health card extraction"), Indian
  passport extraction claims ("extract indian passports", "indian
  passport extraction"), driver license extraction claims
  ("extract driver licenses", "driver license extraction"), and
  vaccination card extraction claims ("extract vaccination cards",
  "vaccination card extraction") are NOT in the phrase lists:
  this family covers document cropping only. 
- As with every family: static pattern matching, not semantic
  judgement; dead code counts; alias chains the tracer cannot follow
  are missed; exact phrases only, not semantics; denial handling
  depends on the denial phrase list; each route must sit in a single
  module.

```
