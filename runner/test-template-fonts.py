"""Offline: library template fonts map to approved fonts with weight kept; fallback rows stay."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from template_fonts import classify, map_pptx

SLIDE = ('<p:sld xmlns:a="a" xmlns:p="p"><a:r><a:rPr lang="zh-CN" sz="11200"><a:latin typeface="思源黑体 CN Heavy"/>'
         '<a:ea typeface="思源黑体 CN Heavy"/></a:rPr><a:t>本周</a:t></a:r>'
         '<a:r><a:rPr lang="en" b="0"><a:latin typeface="Lato Black"/></a:rPr><a:t>X</a:t></a:r>'
         '<a:r><a:rPr lang="en"/><a:t>plain</a:t></a:r>'
         '<a:r><a:rPr lang="zh-CN"><a:ea typeface="汉鼎简行书"/></a:rPr><a:t>书</a:t></a:r></p:sld>')
THEME = ('<a:theme xmlns:a="a"><a:majorFont><a:latin typeface="Montserrat"/><a:ea typeface=""/>'
         '<a:font script="Thai" typeface="Angsana New"/></a:majorFont></a:theme>')


class TemplateFontTests(unittest.TestCase):
    def test_classify_keeps_role_and_weight(self):
        self.assertEqual(classify('思源黑体 CN Heavy'), ('Microsoft YaHei', 'heavy'))
        self.assertEqual(classify('思源黑体 CN Light'), ('Microsoft YaHei Light', 'light'))
        self.assertEqual(classify('思源宋体 CN Bold'), ('SimSun', 'bold'))
        self.assertEqual(classify('全字庫說文解字')[0], 'KaiTi')
        self.assertEqual(classify('Bebas Neue'), ('Arial', 'heavy'))
        for keep in ('Arial', '微软雅黑', 'Wingdings', '+mn-ea', 'Calibri Light'):
            self.assertIsNone(classify(keep))

    def test_map_rewrites_text_fonts_bolds_heavy_and_keeps_script_fallbacks(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 't.pptx'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('ppt/slides/slide1.xml', SLIDE); z.writestr('ppt/theme/theme1.xml', THEME)
                z.writestr('[Content_Types].xml', '<Types/>')
            result = map_pptx(path)
            with zipfile.ZipFile(path) as z:
                slide = z.read('ppt/slides/slide1.xml').decode(); theme = z.read('ppt/theme/theme1.xml').decode()
                self.assertEqual(z.read('[Content_Types].xml').decode(), '<Types/>')
        self.assertNotIn('思源', slide); self.assertIn('typeface="Microsoft YaHei"', slide)
        self.assertIn('sz="11200" b="1"', slide)               # heavy title stays bold
        self.assertIn('lang="en" b="1"', slide)                # b="0" on a Black face becomes bold
        self.assertIn('<a:rPr lang="en"/>', slide)             # self-closing props untouched
        self.assertIn('typeface="KaiTi"', slide)
        self.assertIn('typeface="Arial"', theme); self.assertIn('typeface="Angsana New"', theme)
        self.assertEqual(result['bolded'], 2)
        self.assertIn('microsoft-yahei-bold', result['install']); self.assertIn('kaiti-regular', result['install'])


    def test_preview_note_only_for_real_lettering(self):
        from template_fonts import preview_note
        with tempfile.TemporaryDirectory() as d:
            for name, family, expect in (('a', '汉鼎简行书', True), ('b', '方正楷体简体', False), ('c', '思源黑体 CN Bold', False)):
                path = Path(d) / f'{name}.pptx'
                with zipfile.ZipFile(path, 'w') as z:
                    z.writestr('ppt/slides/slide1.xml', f'<p:sld xmlns:a="a" xmlns:p="p"><a:rPr><a:ea typeface="{family}"/></a:rPr></p:sld>')
                self.assertEqual(preview_note(path) is not None, expect, family)


if __name__ == '__main__':
    unittest.main()
