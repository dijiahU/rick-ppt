import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from render_inputs import source_parts_sha256,render_source_resolver


def package(stamp=(2026,1,1,0,0,0),order=False,changed=False):
    stream=io.BytesIO()
    parts={'[Content_Types].xml':b'<Types/>','ppt/presentation.xml':b'<presentation/>',
           'ppt/slides/slide1.xml':b'<slide>changed</slide>' if changed else b'<slide>same</slide>',
           'ppt/media/picture.png':b'synthetic-image-bytes'}
    with zipfile.ZipFile(stream,'w') as archive:
        for name in sorted(parts,reverse=order):
            entry=zipfile.ZipInfo(name,stamp)
            entry.compress_type=zipfile.ZIP_STORED if order else zipfile.ZIP_DEFLATED
            archive.writestr(entry,parts[name])
    return stream.getvalue()


class Tests(unittest.TestCase):
    def test_identical_parts_survive_timestamp_compression_and_order_changes(self):
        a=package();b=package((2026,2,2,0,0,0),order=True)
        self.assertNotEqual(hashlib.sha256(a).hexdigest(),hashlib.sha256(b).hexdigest())
        self.assertEqual(source_parts_sha256(a),source_parts_sha256(b))

    def test_actual_xml_and_media_changes_are_significant(self):
        self.assertNotEqual(source_parts_sha256(package()),source_parts_sha256(package(changed=True)))

    def test_duplicate_member_or_nonpresentation_cannot_supply_identity(self):
        with self.assertRaises((ValueError,zipfile.BadZipFile)):source_parts_sha256(io.BytesIO().getvalue())
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            z.writestr('[Content_Types].xml',b'1');z.writestr('ppt/presentation.xml',b'2')
            z.writestr('ppt/PRESENTATION.xml',b'3')
        with self.assertRaisesRegex(ValueError,'duplicate'):source_parts_sha256(stream.getvalue())

    def test_resolver_proves_actual_task_scoped_archive_not_asserted_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'run/artifacts/render-input';target.mkdir(parents=True)
            a=package();b=package((2026,2,2,0,0,0),True)
            (target/'a.pptx').write_bytes(a);(target/'b.pptx').write_bytes(b)
            resolve=render_source_resolver([root])
            self.assertEqual(resolve(hashlib.sha256(a).hexdigest()),resolve(hashlib.sha256(b).hexdigest()))
            self.assertIsNone(resolve('0'*64));self.assertIsNone(resolve('../outside'))

    def test_source_symlink_is_not_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'run/artifacts/render-input';target.mkdir(parents=True)
            source=root/'external.pptx';source.write_bytes(package());(target/'linked.pptx').symlink_to(source)
            self.assertIsNone(render_source_resolver([root])(hashlib.sha256(source.read_bytes()).hexdigest()))

    def test_cached_source_is_reverified_after_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'run/artifacts/render-input';target.mkdir(parents=True)
            source=target/'a.pptx';original=package();source.write_bytes(original)
            resolve=render_source_resolver([root]);sha=hashlib.sha256(original).hexdigest()
            self.assertIsNotNone(resolve(sha))
            source.write_bytes(package(changed=True))
            self.assertIsNone(resolve(sha))


if __name__=='__main__':unittest.main()
