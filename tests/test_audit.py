"""Fixed vocabulary oracle and behavioral regression suite."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from document_cropping_claim_audit import phrases
from document_cropping_claim_audit.audit import audit, claims, normalize, source_evidence
from document_cropping_claim_audit.__main__ import main

EXPECTED_YES = ('document cropping', 'crop documents', 'crops documents', 'cropping documents', 'crop document', 'crops document', 'cropping document', 'document cropper', 'document croppers', 'document crop', 'document crops', 'crop document images', 'crops document images', 'cropping document images', 'crop document image', 'crops document image', 'cropping document image', 'document image cropping', 'crop document photos', 'crops document photos', 'cropping document photos', 'crop document photo', 'crops document photo', 'cropping document photo', 'document photo cropping', 'automatic document cropping', 'automatically crop documents', 'auto crop documents', 'document auto cropping', 'detect documents and crop', 'detects documents and crops', 'document detection and cropping', 'document boundary cropping', 'crop to document boundaries', 'crops to document boundaries', 'document edge cropping', 'crop document edges', 'document scan and crop', 'document scan and cropping', 'crop scanned documents', 'crops scanned documents', 'cropping scanned documents', 'scanned document cropping', 'document cropping tool', 'document cropping feature', 'document cropping support', 'supports document cropping', 'document cropping api', 'document cropping service', 'document cropping function')
EXPECTED_NO = ('no document cropping', 'does not crop documents', 'does not crop document', 'does not support document cropping', 'without document cropping', 'no document cropper', 'does not crop document images', 'does not crop document image', 'no document crop', 'does not detect documents and crop', 'no automatic document cropping', 'does not automatically crop documents', 'no document image cropping', 'does not crop document photos', 'does not crop document photo', 'no document photo cropping', 'does not crop scanned documents', 'does not crop to document boundaries', 'without document cropper', 'no document cropping tool', 'no document cropping feature', 'does not support document cropper', 'document cropping not supported', 'no scanned document cropping')
EXPECTED_GENERIC = ('crop_document', 'crop_documents', 'crop_document_image', 'crop_document_images', 'crop_document_photo', 'crop_document_photos', 'detect_and_crop_document', 'detect_and_crop_documents', 'document_cropper', 'document_crop', 'document_cropping', 'auto_crop_document', 'auto_crop_documents', 'automatic_document_crop', 'automatic_document_cropping', 'extract_document_crop', 'get_document_cropping', 'find_document_crop', 'find_document_cropping', 'scan_and_crop_document', 'scan_and_crop_documents', 'crop_to_document', 'crop_to_documents', 'crop_document_edges')

PAIR = 'from mindee import Client, product\nc = Client()\nc.parse(product.CropperV1, source)\n'


class AuditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('AUDIT_TEST_TMPDIR'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                status = main(list(args))
            except SystemExit as exc:
                status = exc.code
        return status, output.getvalue(), errors.getvalue()

    def test_phrase_oracle_parses_implementation(self):
        tree = ast.parse(Path(phrases.__file__).read_text())
        actual = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)}
        for name, expected, count in [('DOCUMENTCROPPING', EXPECTED_YES, 50),
                                      ('NODOCUMENTCROPPING', EXPECTED_NO, 24),
                                      ('GENERIC_NAMES', EXPECTED_GENERIC, 24)]:
            self.assertEqual(tuple(map(normalize, actual[name])), tuple(map(normalize, expected)))
            self.assertEqual(len(actual[name]), count)
            self.assertEqual(len(set(actual[name])), count)

    def test_all_positive_phrases(self):
        for phrase in EXPECTED_YES:
            with self.subTest(phrase=phrase):
                self.assertTrue(claims(phrase)[0])
                self.assertFalse(claims(phrase)[1])

    def test_all_denials_remove_positive_spans(self):
        for phrase in EXPECTED_NO:
            with self.subTest(phrase=phrase):
                self.assertFalse(claims(phrase)[0])
                self.assertEqual(len(claims(phrase)[1]), 1)

    def test_normalization_and_boundaries(self):
        self.assertEqual(normalize("DOESN'T crop-documents"), 'does not crop documents')
        self.assertEqual(normalize("can’t won't isn't"), 'can not will not is not')
        self.assertTrue(claims('DOCUMENT-\nCROPPING')[0])
        self.assertFalse(claims('predocument croppingish')[0])
        self.assertFalse(claims("doesn't crop-documents")[0])

    def test_longest_and_mixed_paragraphs(self):
        yes, no = claims('no document cropping tool; supports document cropping')
        self.assertEqual([p for _, p in no], ['no document cropping tool'])
        self.assertEqual([p for _, p in yes], ['supports document cropping'])
        self.assertFalse(claims('document\n\ncropping')[0])

    def test_fences_and_inline(self):
        for marker in ('```', '~~~', '   ````'):
            with self.subTest(marker=marker):
                self.assertFalse(claims(marker+'text\ndocument cropping\n'+marker.strip())[0])
        self.assertTrue(claims('`document cropping`')[0])
        self.assertTrue(claims('    ```\ndocument cropping\n    ```')[0])
        self.assertFalse(claims('````\n```\ndocument cropping\n````')[0])
        self.assertFalse(claims('~~~\ndocument cropping')[0])

    def test_claim_only_exact_high(self):
        self.write('README.md', 'document cropping')
        result = audit(self.root)
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual(result['findings'][0]['rule'], 'documented-document-cropping-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertEqual(self.run_cli('audit', str(self.root))[0], 2)

    def test_mindee_claim_pass(self):
        self.write('README.md', 'document cropping')
        self.write('main.py', PAIR)
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_denial_contradiction(self):
        self.write('README.md', 'does not crop documents')
        self.write('main.py', PAIR)
        result = audit(self.root)
        self.assertEqual(result['findings'][0]['rule'], 'documented-no-document-cropping-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertEqual(self.run_cli('audit', str(self.root))[0], 2)

    def test_no_claim_pass(self):
        self.write('README.md', 'Text recognition only.')
        self.write('main.py', PAIR)
        self.assertEqual(audit(self.root)['findings'], [])

    def test_no_source_denial_pass(self):
        self.write('README.md', 'no document cropping')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_test_only_thresholds(self):
        self.write('README.md', 'crop documents')
        self.write('tests/helper.py', PAIR)
        result = audit(self.root)
        self.assertEqual(result['findings'][0]['severity'], 'MEDIUM')
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(self.run_cli('audit', str(self.root))[0], 0)
        self.assertEqual(self.run_cli('audit', str(self.root), '--fail-on', 'medium')[0], 2)

    def test_source_path_exclusions(self):
        for name in ('tests/helper.py', 'test_main.py', 'main_test.py', 'pkg/tests/helper.py'):
            with self.subTest(name=name):
                path = self.write(name, PAIR)
                result = audit(self.root)
                self.assertFalse(result['production_evidence'])
                self.assertTrue(result['test_evidence'])
                path.unlink()
        for name in ('fixtures/main.py', 'docs/main.py', 'pkg/examples/main.py', 'fixtures/tests/test_x.py'):
            with self.subTest(name=name):
                path = self.write(name, PAIR)
                result = audit(self.root)
                self.assertFalse(result['production_evidence'])
                self.assertFalse(result['test_evidence'])
                path.unlink()

    def test_document_selection(self):
        self.write('nested/README.md', 'document cropping')
        self.write('notes.md', 'document cropping')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')
        self.write('nested/docs/guide.md', 'document cropping')
        self.assertEqual(audit(self.root)['verdict'], 'FAIL')

    def test_symlinks(self):
        evidence = self.write('fixtures/source.py', PAIR)
        (self.root/'main.py').symlink_to(evidence)
        (self.root/'linked').symlink_to(evidence.parent, target_is_directory=True)
        self.write('fixtures/claims.txt', 'document cropping')
        (self.root/'README.md').symlink_to(self.root/'fixtures/claims.txt')
        self.assertFalse(audit(self.root)['production_evidence'])
        self.assertFalse(audit(self.root)['claims'])

    def test_split_modules(self):
        self.write('README.md', 'document cropping')
        self.write('a.py', 'import mindee\nc=mindee.Client()')
        self.write('b.py', 'from mindee import product\nx.parse(product.CropperV1, source)')
        self.assertEqual(audit(self.root)['verdict'], 'FAIL')

    def test_ignore_repeatable_single_value(self):
        self.write('README.md', 'document cropping')
        self.write('vendor/main.py', PAIR)
        self.write('generated/main.py', PAIR)
        self.assertEqual(self.run_cli('audit', str(self.root), '--ignore', 'vendor', '--ignore', 'generated')[0], 2)
        self.assertEqual(self.run_cli('audit', str(self.root), '--ignore', 'vendor', 'generated')[0], 1)
        self.assertEqual(audit(self.root, ['README'])['verdict'], 'PASS')

    def test_json_verbose_and_version(self):
        self.write('README.md', 'document cropping')
        code, output, _ = self.run_cli('audit', str(self.root), '--json')
        self.assertEqual(code, 2)
        data = json.loads(output)
        self.assertEqual(data['verdict'], 'FAIL')
        self.assertIn('message', data['findings'][0])
        self.assertIn('README.md:1', self.run_cli('audit', str(self.root), '--verbose')[1])
        self.assertEqual(self.run_cli('--version')[:2], (0, '0.1.0\n'))

    def test_usage_errors(self):
        for args in ((), ('oops',), ('audit', '--fail-on', 'HIGH'), ('audit', str(self.root/'missing'))):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args)[0], 1)

    def test_io_error(self):
        self.write('README.md', 'document cropping')
        with patch.object(Path, 'read_text', side_effect=PermissionError('unreadable')):
            self.assertEqual(self.run_cli('audit', str(self.root))[0], 1)

    def test_entry_module(self):
        run = subprocess.run([sys.executable, '-m', 'document_cropping_claim_audit', '--version'], capture_output=True, text=True)
        self.assertEqual((run.returncode, run.stdout), (0, '0.1.0\n'))

    def test_readme_self_audit(self):
        readme = Path(__file__).resolve().parents[1]/'README.md'
        if not readme.exists():
            self.skipTest('README is not installed in wheel')
        self.assertEqual(claims(readme.read_text()), ([], []))
        self.assertEqual(audit(readme.parent)['verdict'], 'PASS')

    def test_generic_all_attribute_import_alias_forms(self):
        for name in EXPECTED_GENERIC:
            for source in (f'x.{name}()', f'from sdk import {name}\n{name}()',
                           f'from sdk import {name} as alias\nalias()',
                           f'import sdk as s\ns.{name}()'):
                with self.subTest(source=source):
                    self.assertTrue(source_evidence(source))
            self.assertFalse(source_evidence(name+'()'))

    def test_mindee_import_forms(self):
        sources = [PAIR,
            'import mindee\nx=mindee.Client()\nx.parse(mindee.product.CropperV1, source)',
            'import mindee as m\nx=m.Client()\nx.parse(product_class=m.product.CropperV1)',
            'from mindee import Client as C\nfrom mindee.product import CropperV1 as P\nC()\nx.parse(P, source)',
            'from mindee.product.cropper import CropperV1\nfrom mindee import Client\nClient()\nx.parse(product_class=CropperV1)',
            'import mindee.product as p\nfrom mindee import Client\nClient()\nx.parse(p.CropperV1, source)',
            'from mindee.product import cropper as p\nfrom mindee import Client\nClient()\nx.parse(p.CropperV1, source)',
            'import mindee.product.cropper\nmindee.Client()\nx.parse(mindee.product.cropper.CropperV1)',
            'from mindee.v1 import Client, product\nClient()\nx.parse(product_class=product.CropperV1)',
            'import mindee.v1 as m\nm.Client()\nx.parse(m.product.CropperV1)',
            'from mindee.v1.product.cropper import CropperV1 as P\nfrom mindee.v1 import Client as C\nC()\nx.parse(P)',
        ]
        for source in sources:
            with self.subTest(source=source):
                self.assertTrue(source_evidence(source))

    def test_unrelated_imports_cannot_fabricate_mindee_pair(self):
        for source in (
            'from other import Client, product\nClient()\nx.parse(product.CropperV1)',
            'from mindee import unrelated\nunrelated.Client()\nx.parse(unrelated.CropperV1)',
            'from mindee import Client, unrelated\nClient()\nx.parse(unrelated.CropperV1)',
            'from mindee import product\nproduct.Client()\nx.parse(product.CropperV1)',
            'from .mindee import Client, product\nClient()\nx.parse(product.CropperV1)',
        ):
            with self.subTest(source=source):
                self.assertFalse(source_evidence(source))

    def test_mindee_other_products(self):
        products = ('InvoiceV4 ReceiptV5 PassportV1 FinancialDocumentV1 BankCheckV1 BankAccountDetailsV2 PayslipV2 PayslipV3 HealthcareCardV1 BusinessCardV1 CustomV1 GeneratedV1 BillOfLadingV1 ResumeV1 DeliveryNoteV1 DriverLicenseV1 IdCardV1 InternationalIdV2 CarteGriseV1 EnergyBillV1 MultiReceiptsDetectorV1 InvoiceSplitterV1 CropperV2 TypeCropperV1').split()
        for product in products:
            with self.subTest(product=product):
                self.assertFalse(source_evidence(PAIR.replace('CropperV1', product)))
                self.assertFalse(source_evidence(PAIR.replace('CropperV1', product)+'\nx.prediction.extras.cropping\n'))

    def test_import_bindings_and_local_shadows(self):
        negatives = [
            'from sdk import crop_document\ndef crop_document(): pass\ncrop_document()',
            'from sdk import crop_document as f\ndef f(): pass\nf()',
            'class X:\n def crop_document(self): pass\nx.crop_document()',
            'class crop_document: pass\nx.crop_document()',
            'from sdk import crop_document as f\nf=other\nf()',
            'from sdk import crop_document as f\nf: object=other\nf()',
            'from sdk import crop_document as f\nwith manager() as f:\n f()',
            'from sdk import crop_document as f\nasync def go():\n async with manager() as f:\n  f()',
            'from sdk import crop_document as f\nf, other = pair\nf()',
            PAIR+'\nClient=other', PAIR+'\nproduct: object=other',
            PAIR+'\ndef CropperV1(): pass', PAIR+'\ndef Client(): pass',
            PAIR+'\nclass Local:\n def parse(self, product): pass',
            'import mindee as m\nwith manager() as m:\n m.Client()\n x.parse(m.product.CropperV1)',
        ]
        for source in negatives:
            with self.subTest(source=source):
                self.assertFalse(source_evidence(source))
        self.assertTrue(source_evidence(PAIR+'\nproduct.some_attribute=other'))

    def test_non_call_and_invalid_source(self):
        for source in ('import mindee', 'import azure.ai.documentintelligence', 'import veryfi',
                       'from google.cloud import documentai', 'from mindee import Client\nClient()',
                       'from mindee.product import CropperV1\nx.parse(CropperV1)',
                       '# x.crop_document()\ns="document cropping"', 'x.crop_document',
                       'x.crop_document(', 'CropperV1()'):
            with self.subTest(source=source):
                self.assertFalse(source_evidence(source))

    def test_excluded_vendors_and_operations(self):
        sources = [
            'from mindee.fields import CropperExtra\nCropperExtra()',
            'from PIL import Image\nImage.open(path).crop(box)', 'from PIL import ImageOps\nImageOps.crop(image, 5)',
            'img[y:y+h, x:x+w]', 'from skimage.util import crop\ncrop(image, width)',
            'cv2.findContours(img, mode, method)', 'cv2.boundingRect(contour)', 'YOLO(model)(image)',
            'LlamaParse().load_data(path)', 'nanonets.ocr(model_id=model_id)', 'docsumo.upload(path)',
            'abbyy.process(skill_id)', 'rossum.upload(queue)', 'klippa.parse(template)', 'parseur.upload(template)', 'extend.run(workflow)',
            'mindee.ClientV2().enqueue_and_get_inference(model_id=model_id)',
            'pdfplumber.open(path).pages[0].extract_text()', 'fitz.open(path)[0].extract_text()',
            'pytesseract.image_to_string(image)', 'pandas.read_csv(path)', 'pandas.read_excel(path)',
            'camelot.read_pdf(path)', 'tabula.read_pdf(path)', 'tabula.convert_into(path)',
            'pdfplumber.open(path).pages[0].extract_table()', 'fitz.open(path)[0].find_tables()',
            're.search(pattern, ocr_text)', 're.findall(pattern, ocr_text)', 'text.split(":")',
            'subprocess.run(["mindee", "parse", "CropperV1", path])',
            'requests.post(endpoint, data=payload)',
        ]
        sources += [f'azure.begin_analyze_document("{model}", body)' for model in
                    ('prebuilt-layout', 'prebuilt-read', 'prebuilt-invoice', 'prebuilt-receipt', 'prebuilt-idDocument', 'anything')]
        sources += [f'azure.begin_analyze_document_from_url("{model}", location)' for model in ('prebuilt-layout', 'anything')]
        veryfi_names = ('Client process_any_document process_any_document_url process_document process_document_url process_w2_document process_w9_document process_w8_document process_check process_check_url process_check_with_remittance process_check_with_remittance_url process_bank_statement_document process_bank_statement_document_url process_bussines_card_document process_bussines_card_document_url classify_document get_business_cards get_business_card delete_business_card process_crop_document process_crop_document_url').split()
        sources += [f'veryfi.{name}(data)' for name in veryfi_names]
        sources += ['documentai.process_document(request)', 'documentai.batch_process_documents(request)']
        sources += [f'textract.{name}(Queries={{"Queries": [{{"Text": "crop documents"}}]}})' for name in
                    ('analyze_document', 'analyze_expense', 'analyze_id', 'start_document_analysis', 'start_document_text_detection', 'get_expense_analysis')]
        sources += [f'eden.universal_ai(model="{model}", data=payload)' for model in ('ocr/invoice_parser/affinda', 'ocr/resume_parser/affinda', 'anything')]
        for source in sources:
            with self.subTest(source=source):
                self.assertFalse(source_evidence(source))


if __name__ == '__main__':
    unittest.main()
