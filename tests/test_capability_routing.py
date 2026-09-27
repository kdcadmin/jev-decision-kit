import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cabinet
from host.gate import available_gates


class CapabilityRoutingTests(unittest.TestCase):
    def names(self, task):
        return {s['name'] for s in cabinet.route_task(task, 'test', record=False)['skills']}

    def test_video_requests_from_call_history(self):
        for task in ('vox', '做一个vox视频', '做一个视频', '帮我制作视频', '用 VOX 做个视频'):
            with self.subTest(task=task):
                self.assertIn('vox-style-intro-video', self.names(task))

    def test_development_tasks(self):
        for task, name in (
            ('帮我写一个爬虫代码', 'test-driven-development'),
            ('写一个 Python 脚本', 'test-driven-development'),
            ('帮我开发一个 API 接口', 'fullstack-dev'),
            ('帮我做一个前端页面', 'frontend-dev'),
            ('开发一个 Android 应用', 'android-native-dev'),
            ('开发一个 iOS 应用', 'ios-application-dev'),
            ('用 Flutter 开发应用', 'flutter-dev'),
            ('用 React Native 开发应用', 'react-native-dev'),
            ('帮我修复这个 bug', 'systematic-debugging'),
            ('重构这段代码', 'code-refactoring'),
            ('用 shader-dev 写一个着色器', 'shader-dev'),
        ):
            with self.subTest(task=task):
                self.assertIn(name, self.names(task))

    def test_explanations_and_negations_do_not_execute(self):
        for task in ('vox 是什么', '不要用 vox', '视频制作是什么意思',
                     '爬虫代码是什么', '这段代码什么意思', '不要写代码',
                     '解释 shader-dev 有什么用', '不要用 shader-dev'):
            with self.subTest(task=task):
                self.assertEqual(set(), self.names(task))

    def test_selection_tracks_installed_files_not_category(self):
        with tempfile.TemporaryDirectory() as folder:
            skill = Path(folder)
            (skill / 'SKILL.md').write_text('video', encoding='utf-8')
            catalog = {'skills': [{'name': 'vox-style-intro-video', 'category': 'other', 'path': folder}]}
            self.assertIn('vox-video', {g['id'] for g in available_gates(catalog)})
            (skill / 'SKILL.md').unlink()
            self.assertEqual([], available_gates(catalog))

    def test_unavailable_capabilities_are_not_invented(self):
        with patch.object(cabinet, 'load_catalog', return_value={'skills': []}):
            self.assertEqual(set(), self.names('做一个vox视频，写一个爬虫代码'))

    def test_expanded_request_wording(self):
        cases = (
            ('帮我做视频', {'vox-style-intro-video'}),
            ('做一段视频', {'vox-style-intro-video'}),
            ('做个 vox 风格的视频可以吗', {'vox-style-intro-video'}),
            ('能不能帮我写一个爬虫', {'test-driven-development'}),
            ('帮我写一段 Python 代码', {'test-driven-development'}),
            ('帮我写个程序', {'test-driven-development'}),
            ('请用 python 实现一个排序算法', {'test-driven-development'}),
            ('帮我开发一个API', {'fullstack-dev'}),
            ('做个 React 页面', {'frontend-dev'}),
            ('帮我修一下这段代码的错误', {'systematic-debugging'}),
            ('帮我做一个前端页面，再写一个爬虫', {'frontend-dev', 'test-driven-development'}),
            ('做一个vox视频，再把说明写成 Word', {'vox-style-intro-video', 'docx'}),
            ('不要 vox，只要写一个爬虫', {'test-driven-development'}),
            ('不要写代码，只做一个vox视频', {'vox-style-intro-video'}),
            ('先别用 vox，还是用 vox 吧', {'vox-style-intro-video'}),
            ('用 vox-style-intro-video 做介绍片', {'vox-style-intro-video'}),
            ('用 fullstack-dev 开发后端', {'fullstack-dev'}),
            ('用 shader-dev 和 pixel-art 做着色器和像素图', {'shader-dev', 'pixel-art'}),
            ('不要 shader-dev，只用 pixel-art', {'pixel-art'}),
            ('给我剪辑这段实拍视频', {'openmontage'}),
            ('把实拍素材做成一个视频', {'openmontage'}),
            ('用 Python 写一个视频处理脚本', {'test-driven-development'}),
            ('不需要写爬虫，只做一个 vox 视频', {'vox-style-intro-video'}),
            ('写一个后端 API，再做一个前端页面', {'fullstack-dev', 'frontend-dev'}),
        )
        for task, expected in cases:
            with self.subTest(task=task):
                self.assertEqual(expected, self.names(task))

    def test_expanded_non_action_wording(self):
        for task in (
            '爬虫怎么写', 'Python 脚本是什么', '前端和后端有什么区别',
            'Flutter 怎么用', 'Android 是什么', 'React Native 是什么',
            'bug 是什么意思', '调试和重构有什么区别',
            '不需要 vox', '不用制作视频', '不要用 fullstack-dev',
            'shader-dev 是什么', 'pixel-art 有什么用',
            'vox-style-intro-video 是什么', '我喜欢 Android 手机',
            '今天看了一个前端教程', '这个视频的脚本讲得不错',
            '帮我写一个短视频脚本',
        ):
            with self.subTest(task=task):
                self.assertEqual(set(), self.names(task))

    def test_every_installed_skill_can_be_named_and_declined(self):
        catalog = cabinet.load_catalog()
        names = {s['name'] for s in catalog['skills']
                 if (Path(s.get('path') or '') / 'SKILL.md').is_file()}
        for name in sorted(names):
            with self.subTest(name=name, mode='select'):
                self.assertIn(name, self.names('请使用 ' + name))
            with self.subTest(name=name, mode='decline'):
                self.assertNotIn(name, self.names('不要使用 ' + name))
            with self.subTest(name=name, mode='explain'):
                self.assertNotIn(name, self.names(name + ' 是什么'))


if __name__ == '__main__':
    unittest.main()
