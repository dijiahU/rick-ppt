import unittest
from language import LANGUAGES,presentation_request,language_instruction

class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.task={'title':'用中文输入的主题','brief':'请介绍团队如何协作','pages':5,'style':'Designer choice'}
    def test_selected_language_survives(self):
        for code,name in LANGUAGES.items():
            task={**self.task,'language':code}
            self.assertEqual(presentation_request(task)['language'],code)
            self.assertIn(f'{name} ({code})',language_instruction(task))
            self.assertEqual(presentation_request(task)['title'],self.task['title'])
    def test_legacy_not_retroactively_english(self):
        for task in [self.task,{**self.task,'language':None}]:
            self.assertIsNone(presentation_request(task)['language'])
            self.assertIn('legacy',language_instruction(task))
    def test_reject_invalid_language(self):
        for value in ['xx','en; read private files',[],{},1]:
            with self.assertRaises(ValueError):presentation_request({**self.task,'language':value})
    def test_no_unrelated_task_fields(self):
        self.assertNotIn('lease',presentation_request({**self.task,'lease':'private'}))
    def test_edit_has_no_count(self):
        value=presentation_request({**self.task,'mode':'edit'})
        self.assertEqual(value['mode'],'edit')
        self.assertIsNone(value['pages'])
        self.assertEqual(presentation_request(self.task)['mode'],'create')
    def test_invalid_mode(self):
        with self.assertRaises(ValueError):presentation_request({**self.task,'mode':'other'})

if __name__=='__main__':unittest.main()
