import unittest
from font_assets import deployment_defaults
from workflow import deployment_font_instruction

class TypographyTests(unittest.TestCase):
    def test_linux_instruction_and_published_defaults_have_the_same_baseline(self):
        defaults=deployment_defaults('linux');text=deployment_font_instruction('linux')
        self.assertEqual(defaults['east_asian'],'Noto Serif CJK SC')
        self.assertIn(defaults['latin'],text);self.assertIn(defaults['east_asian'],text)
        self.assertIn('take precedence',text);self.assertIn('recipient availability',text)

    def test_mac_retains_existing_windows_wps_default(self):
        defaults=deployment_defaults('darwin');text=deployment_font_instruction('darwin')
        self.assertEqual(defaults,{'latin':'Times New Roman','east_asian':'SimSun','target':'Windows WPS'})
        self.assertIn('Times New Roman',text);self.assertIn('SimSun',text)

if __name__=='__main__':unittest.main()
