"""Offline regression tests for ordered, idempotent Motion publishing."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('youtube_publisher', ROOT / 'scripts/publish_youtube_posts.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)
Video = publisher.Video

CHANNEL = 'UC' + 'a' * 22
OLD = Video('Old #one #two', 'OldVideo001', '2026-09-29T09:27:38-07:00')
MIDDLE = Video('Middle', 'MiddleVid01', '2026-10-01T12:00:00Z')
NEW = Video('New', 'NewVideo001', '2026-10-30T11:20:59+00:00')
TARGET = publisher.TARGETS[0]


class ExistingPostsTests(unittest.TestCase):
    def test_legacy_and_modern_embeds_keep_case_sensitive_ids(self):
        samples = [
            f'<iframe src="https://www.youtube.com/embed/{OLD.video_id}?rel=0"></iframe>',
            f'https://youtu.be/{OLD.video_id}',
            f'https://www.youtube.com/shorts/{OLD.video_id}',
            f'https://www.youtube.com/watch?feature=share&amp;v={OLD.video_id}',
            f'https://www.youtube-nocookie.com/embed/{OLD.video_id}',
            f'https:\\/\\/www.youtube.com\\/watch?v={OLD.video_id}',
        ]
        for content in samples:
            with self.subTest(content=content):
                self.assertEqual(publisher.video_ids_in_post({'content': {'rendered': content}}), {OLD.video_id})
        self.assertEqual(publisher.video_ids_in_post({'content': {'raw': samples[0], 'rendered': samples[1]}}), {OLD.video_id})

    def test_every_wordpress_page_and_unpublished_states_are_checked(self):
        first = [{'slug': str(i), 'content': {'rendered': ''}} for i in range(100)]
        second = [{'slug': 'legacy-old', 'content': {'raw': f'https://youtu.be/{OLD.video_id}'}, 'status': 'draft'}]
        with patch.object(publisher, 'wp_get', side_effect=[first, second]) as get:
            ids, slugs = publisher.existing_video_index()
        self.assertEqual(ids, {OLD.video_id})
        self.assertIn('legacy-old', slugs)
        self.assertEqual([c.args[1]['offset'] for c in get.call_args_list], [0, 100])
        self.assertTrue(all(c.args[1]['status'] == 'publish,draft,private,future,pending' for c in get.call_args_list))
        self.assertTrue(all(c.args[1]['context'] == 'edit' and 'categories' not in c.args[1] for c in get.call_args_list))

    def test_exactly_one_full_page_finishes_with_empty_offset_page(self):
        with patch.object(publisher, 'wp_get', side_effect=[[{'slug': str(i)} for i in range(100)], []]) as get:
            self.assertEqual(len(publisher.existing_video_index()[1]), 100)
        self.assertEqual(get.call_count, 2)


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.channel = patch.object(publisher, 'get_channel_id', return_value=CHANNEL).start()
        self.source = patch.object(publisher, 'get_channel_videos', return_value=[NEW, MIDDLE, OLD]).start()
        self.index = patch.object(publisher, 'existing_video_index', return_value=(set(), set())).start()
        self.exists = patch.object(publisher, 'post_already_exists', return_value=False).start()
        self.category = patch.object(publisher, 'get_category_id_by_slug', return_value=6110).start()
        self.tags = patch.object(publisher, 'get_tag_ids', return_value=[11, 12]).start()
        self.post = patch.object(publisher, 'wp_post', return_value={'link': 'https://example.test/post/'}).start()
        self.addCleanup(patch.stopall)

    def test_all_missing_videos_are_published_oldest_first_with_original_utc_dates(self):
        publisher.publish_for_target(TARGET)
        payloads = [call.args[1] for call in self.post.call_args_list]
        self.assertEqual([p['title'] for p in payloads], ['Old', 'Middle', 'New'])
        self.assertEqual([p['date_gmt'] for p in payloads], ['2026-09-29T16:27:38', '2026-10-01T12:00:00', '2026-10-30T11:20:59'])
        self.assertEqual(payloads[0]['tags'], [11, 12])
        self.tags.assert_called_once_with(['one', 'two'])
        for video, payload in zip([OLD, MIDDLE, NEW], payloads):
            self.assertEqual(payload['slug'], publisher.make_post_slug(video.video_id))
            self.assertEqual(payload['format'], 'video')
            self.assertEqual(payload['categories'], [6110])
            self.assertEqual(payload['status'], 'publish')
            self.assertIn('<!-- wp:embed ', payload['content'])
            self.assertIn(f'https://www.youtube.com/watch?v={video.video_id}', payload['content'])

    def test_existing_newest_does_not_hide_missing_older_videos_or_create_legacy_duplicates(self):
        self.index.return_value = ({NEW.video_id, OLD.video_id}, set())
        publisher.publish_for_target(TARGET)
        self.post.assert_called_once()
        self.assertEqual(self.post.call_args.args[1]['title'], 'Middle')

    def test_unpublished_or_moved_posts_with_stable_slug_remain_untouched(self):
        self.exists.return_value = True
        publisher.publish_for_target(TARGET)
        self.post.assert_not_called()
        self.tags.assert_not_called()

    def test_repeated_video_id_in_source_is_published_only_once(self):
        self.source.return_value = [OLD, OLD]
        publisher.publish_for_target(TARGET)
        self.post.assert_called_once()

    def test_dry_run_never_creates_posts_or_tags(self):
        publisher.publish_for_target(TARGET, dry_run=True)
        self.post.assert_not_called()
        self.tags.assert_not_called()

    def test_all_metadata_is_validated_before_any_wordpress_write(self):
        self.source.return_value = [Video('Without RSS timestamp', NEW.video_id), OLD]
        with patch.object(publisher, 'get_video_metadata', side_effect=ValueError('missing timestamp')):
            with self.assertRaisesRegex(ValueError, 'missing timestamp'):
                publisher.publish_for_target(TARGET)
        self.post.assert_not_called()
        self.tags.assert_not_called()

    def test_watch_metadata_recovers_video_older_than_rss_window(self):
        self.source.return_value = [Video(OLD.title, OLD.video_id)]
        with patch.object(publisher, 'get_video_metadata', return_value=OLD) as metadata:
            publisher.publish_for_target(TARGET)
        metadata.assert_called_once_with(OLD.video_id, CHANNEL)
        self.assertEqual(self.post.call_args.args[1]['date_gmt'], '2026-09-29T16:27:38')

    def test_failed_wordpress_write_is_not_replayed_and_stops_later_posts(self):
        self.post.side_effect = publisher.requests.Timeout()
        with self.assertRaises(publisher.requests.Timeout):
            publisher.publish_for_target(TARGET)
        self.post.assert_called_once()

    def test_next_run_recovers_after_partial_write_without_duplicates(self):
        existing = set()
        self.index.side_effect = lambda: (existing.copy(), set())
        def write(endpoint, payload):
            ids = publisher.video_ids_in_post({'content': payload['content']})
            if MIDDLE.video_id in ids:
                raise publisher.requests.Timeout()
            existing.update(ids)
            return {'link': 'https://example.test/post/'}
        self.post.side_effect = write
        with self.assertRaises(publisher.requests.Timeout):
            publisher.publish_for_target(TARGET)
        self.assertEqual(existing, {OLD.video_id})
        self.post.reset_mock()
        self.post.side_effect = lambda endpoint, payload: {'link': 'https://example.test/post/'}
        publisher.publish_for_target(TARGET)
        self.assertEqual([c.args[1]['title'] for c in self.post.call_args_list], ['Middle', 'New'])

    def test_invalid_timestamps_fail_before_writes(self):
        for timestamp in ['2026-10-30', '2026-10-30T10:00:00', '2999-10-30T10:00:00Z']:
            with self.subTest(timestamp=timestamp):
                self.source.return_value = [Video('Invalid', OLD.video_id, timestamp)]
                with self.assertRaises(ValueError):
                    publisher.publish_for_target(TARGET)
                self.post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
