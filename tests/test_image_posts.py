"""Keep independent boards out of this publisher and retain Bygone behavior."""
from datetime import datetime
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
with patch.dict(os.environ, {'WP_BASE_URL': 'https://wordpress.example.invalid',
                            'WP_USERNAME': 'test', 'WP_APP_PASSWORD': 'test',
                            'CDN_BASE_URL': 'https://cdn.example.invalid'}):
    spec = importlib.util.spec_from_file_location('image_publisher', ROOT / 'scripts/publish_image_posts.py')
    publisher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publisher)


class ImagePublisherTests(unittest.TestCase):
    def test_only_bygone_changed_images_are_targets(self):
        changed = ('A\tnatsci/fieldlog/photo.jpg\nA\tpost/flux/photo.jpg\n'
                   'A\tsavour/photo.jpg\nA\tstills/bygone/old-photo.jpg')
        with patch.dict(os.environ, {'GITHUB_BEFORE': 'a' * 40, 'GITHUB_SHA': 'b' * 40}), \
             patch.object(publisher, 'run_git', return_value=changed), \
             patch.object(Path, 'is_file', return_value=True):
            self.assertEqual(publisher.get_changed_images(), ['stills/bygone/old-photo.jpg'])

    def test_bygone_keeps_filename_title_category_and_image_block(self):
        with patch.object(publisher, 'get_file_commit_time', return_value=datetime.fromisoformat('2026-10-30T12:00:00+08:00')), \
             patch.object(publisher, 'post_already_exists', return_value=False), \
             patch.object(publisher, 'get_category_id_by_slug', return_value=7), \
             patch.object(publisher, 'wp_post', return_value={'link': 'https://wordpress.example.invalid/post'}) as post:
            publisher.publish_image('stills/bygone/old-photo.jpg', {}, {})
        endpoint, payload = post.call_args.args
        self.assertEqual(endpoint, 'posts')
        self.assertEqual(payload['title'], 'old photo')
        self.assertEqual(payload['categories'], [7])
        self.assertEqual(payload['slug'], 'asset-stills-bygone-old-photo-jpg')
        self.assertIn('https://cdn.example.invalid/stills/bygone/old-photo.jpg', payload['content'])
        self.assertIn('<!-- wp:image ', payload['content'])

    def test_no_target_change_never_writes_wordpress(self):
        with patch.object(publisher, 'get_changed_images', return_value=[]), \
             patch.object(publisher, 'wp_post') as post:
            publisher.main()
        post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
