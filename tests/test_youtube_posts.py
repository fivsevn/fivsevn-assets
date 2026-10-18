"""Offline checks for YouTube feed recovery; no live reads or publishing."""
import importlib.util
import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('youtube_publisher', ROOT / 'scripts/publish_youtube_posts.py')
with patch.dict(os.environ, {
    'WP_BASE_URL': 'https://example.test', 'WP_USERNAME': 'test',
    'WP_APP_PASSWORD': 'test', 'YOUTUBE_FIVSEVN_CHANNEL_ID': 'UCexample',
}):
    publisher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publisher)

VIDEO = 'AbCdEf123_-'
XML = f'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
  <id>yt:channel:UCexample</id><yt:channelId>UCexample</yt:channelId><title>Example</title>
  <entry><id>yt:video:{VIDEO}</id><yt:videoId>{VIDEO}</yt:videoId>
    <title>Example video #tag</title><link rel="alternate" href="https://www.youtube.com/watch?v={VIDEO}"/>
  </entry>
</feed>'''.encode()


def response(status=200, content=XML):
    return SimpleNamespace(status_code=status, content=content)


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.sleep = patch.object(publisher.time, 'sleep').start()
        self.get = patch.object(publisher.requests, 'get').start()
        self.fallback = patch.object(publisher, 'get_latest_uploads_video', side_effect=ValueError('unavailable')).start()
        self.addCleanup(patch.stopall)

    def read(self):
        return publisher.get_latest_youtube_video('UCexample', 'example')

    def test_404_then_valid_feed_recovers_with_a_bounded_request(self):
        self.get.side_effect = [response(404, b'not found'), response()]
        self.assertEqual(self.read(), ('Example video #tag', VIDEO))
        self.sleep.assert_called_once_with(5)
        for call in self.get.call_args_list:
            self.assertEqual(call.kwargs['timeout'], (10, 30))
            self.assertNotIn('auth', call.kwargs)
            self.assertIn('application/atom+xml', call.kwargs['headers']['Accept'])

    def test_timeout_and_server_errors_recover(self):
        self.get.side_effect = [publisher.requests.Timeout(), response(503), response(429), response()]
        self.assertEqual(self.read()[1], VIDEO)
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list], [5, 15, 30])

    def test_persistent_404_fails_without_any_wordpress_operation(self):
        self.get.return_value = response(404)
        with patch.object(publisher, 'get_channel_id', return_value='UCexample'), \
                patch.object(publisher, 'post_already_exists') as exists, \
                patch.object(publisher, 'wp_post') as post:
            with self.assertRaisesRegex(RuntimeError, 'after 4 attempts.*HTTP 404'):
                publisher.publish_latest_for_target(publisher.TARGETS[0], {})
        self.assertEqual(self.get.call_count, 4)
        exists.assert_not_called()
        post.assert_not_called()

    def test_http_200_html_and_malformed_xml_are_not_success(self):
        for invalid in [b'<html>Server error</html>', b'<feed><entry>', b'']:
            with self.subTest(invalid=invalid):
                self.get.reset_mock()
                self.get.side_effect = [response(content=invalid), response()]
                self.assertEqual(self.read()[1], VIDEO)
                self.assertEqual(self.get.call_count, 2)

    def test_persistently_invalid_response_fails(self):
        self.get.return_value = response(content=b'<html>not a feed</html>')
        with self.assertRaisesRegex(RuntimeError, 'after 4 attempts.*invalid feed'):
            self.read()

    def test_empty_or_missing_video_id_feed_is_retried(self):
        empty = XML[:XML.index(b'<entry>')] + b'</feed>'
        no_id = XML.replace(f'<yt:videoId>{VIDEO}</yt:videoId>'.encode(), b'').replace(
            f'https://www.youtube.com/watch?v={VIDEO}'.encode(), b'https://www.youtube.com/')
        for invalid in [empty, no_id]:
            with self.subTest(invalid=invalid):
                self.get.side_effect = [response(content=invalid), response()]
                self.assertEqual(self.read()[1], VIDEO)

    def test_permanent_http_error_fails_without_retries(self):
        self.get.return_value = response(401)
        with self.assertRaisesRegex(RuntimeError, 'HTTP 401'):
            self.read()
        self.get.assert_called_once()
        self.sleep.assert_not_called()

    def test_different_channel_is_rejected(self):
        self.get.return_value = response(content=XML.replace(b'<yt:channelId>UCexample', b'<yt:channelId>UCother'))
        with self.assertRaisesRegex(RuntimeError, 'another channel'):
            self.read()
        self.sleep.assert_not_called()

    def test_shorts_link_fallback_keeps_existing_support(self):
        short = XML.replace(f'<yt:videoId>{VIDEO}</yt:videoId>'.encode(), b'').replace(
            f'watch?v={VIDEO}'.encode(), f'shorts/{VIDEO}'.encode())
        self.get.return_value = response(content=short)
        self.assertEqual(self.read()[1], VIDEO)


class PublishingTests(unittest.TestCase):
    def test_existing_latest_video_is_not_published_again(self):
        with patch.object(publisher, 'get_channel_id', return_value='UCexample'), \
                patch.object(publisher, 'get_latest_youtube_video', return_value=('Title #tag', VIDEO)), \
                patch.object(publisher, 'wp_get', return_value=[{'id': 123}]) as get, \
                patch.object(publisher, 'wp_post') as post:
            publisher.publish_latest_for_target(publisher.TARGETS[0], {})
        self.assertEqual(get.call_args.args[0], 'posts')
        self.assertEqual(get.call_args.args[1]['slug'], f'youtube-{VIDEO}')
        self.assertEqual(get.call_args.args[1]['status'], 'publish,draft,private,future,pending')
        post.assert_not_called()

    def test_new_video_preserves_motion_title_tags_and_native_embed(self):
        with patch.object(publisher, 'get_channel_id', return_value='UCexample'), \
                patch.object(publisher, 'get_latest_youtube_video', return_value=('A title #one #two', VIDEO)), \
                patch.object(publisher, 'post_already_exists', return_value=False), \
                patch.object(publisher, 'get_category_id_by_slug', return_value=7) as category, \
                patch.object(publisher, 'get_tag_ids', return_value=[11, 12]) as tags, \
                patch.object(publisher, 'wp_post', return_value={'link': 'https://example.test/post/'}) as post:
            publisher.publish_latest_for_target(publisher.TARGETS[0], {})
        category.assert_called_once_with('motion')
        tags.assert_called_once_with(['one', 'two'])
        endpoint, payload = post.call_args.args
        self.assertEqual(endpoint, 'posts')
        self.assertEqual(payload['title'], 'A title')
        self.assertEqual(payload['slug'], f'youtube-{VIDEO}')
        self.assertEqual(payload['categories'], [7])
        self.assertEqual(payload['tags'], [11, 12])
        self.assertEqual(payload['format'], 'video')
        self.assertIn('<!-- wp:embed ', payload['content'])
        self.assertIn(f'https://www.youtube.com/watch?v={VIDEO}', payload['content'])
        post.assert_called_once()

    def test_a_failed_wordpress_write_is_not_automatically_replayed(self):
        with patch.object(publisher, 'get_channel_id', return_value='UCexample'), \
                patch.object(publisher, 'get_latest_youtube_video', return_value=('A title', VIDEO)), \
                patch.object(publisher, 'post_already_exists', return_value=False), \
                patch.object(publisher, 'get_category_id_by_slug', return_value=7), \
                patch.object(publisher, 'wp_post', side_effect=publisher.requests.Timeout()) as post:
            with self.assertRaises(publisher.requests.Timeout):
                publisher.publish_latest_for_target(publisher.TARGETS[0], {})
        post.assert_called_once()


class UploadsPageTests(unittest.TestCase):
    def page(self, card, *, owner='UCexample', playlist='UUexample', grid=True, recommendation=None):
        import json
        renderer = {'richGridRenderer': {'contents': [{'richItemRenderer': {'content': card}}]}} if grid else {
            'playlistVideoListRenderer': {'contents': [card]}}
        data = {
            'header': {'playlistHeaderRenderer': {'playlistId': playlist,
                'ownerEndpoint': {'browseEndpoint': {'browseId': owner}}}},
            'contents': {'twoColumnBrowseResultsRenderer': {'tabs': [{'tabRenderer': {'content': renderer}}]}},
        }
        if recommendation is not None: data['recommendations'] = recommendation
        return '<script>var ytInitialData = ' + json.dumps(data) + ';</script>'

    def short(self, title='Title #tag', video=VIDEO):
        return {'shortsLockupViewModel': {
            'onTap': {'innertubeCommand': {'reelWatchEndpoint': {'videoId': video}}},
            'overlayMetadata': {'primaryText': {'content': title}}}}

    def test_modern_shorts_and_regular_video_layouts_preserve_full_titles(self):
        cards = [self.short(), {'lockupViewModel': {'contentId': VIDEO,
            'contentType': 'LOCKUP_CONTENT_TYPE_VIDEO', 'metadata': {
                'lockupMetadataViewModel': {'title': {'content': 'Title #tag'}}}}},
            {'videoRenderer': {'videoId': VIDEO, 'title': {'runs': [{'text': 'Title #tag'}]}}}]
        for card in cards:
            with self.subTest(card=card):
                self.assertEqual(publisher.parse_uploads_page(self.page(card), 'UCexample'), ('Title #tag', VIDEO))

    def test_classic_playlist_layout(self):
        card = {'playlistVideoRenderer': {'videoId': VIDEO, 'isPlayable': True,
            'title': {'simpleText': 'Title #tag'}}}
        self.assertEqual(publisher.parse_uploads_page(self.page(card, grid=False), 'UCexample'), ('Title #tag', VIDEO))

    def test_recommendations_are_not_selected(self):
        self.assertEqual(publisher.parse_uploads_page(self.page(self.short(),
            recommendation=self.short('Wrong title', 'xxxxxxxxxxx')), 'UCexample'), ('Title #tag', VIDEO))

    def test_wrong_channel_or_playlist_is_rejected(self):
        for options in [{'owner': 'UCother'}, {'playlist': 'UUother'}]:
            with self.subTest(options=options), self.assertRaisesRegex(RuntimeError, 'identity'):
                publisher.parse_uploads_page(self.page(self.short(), **options), 'UCexample')

    def test_unknown_or_incomplete_layout_fails_instead_of_selecting_recommendations(self):
        for document in ['<html>Consent required</html>', '<script>var ytInitialData = {broken};</script>',
                self.page({'unknownNewCard': {}}, recommendation=self.short()), self.page(self.short(video='invalid'))]:
            with self.subTest(document=document), self.assertRaises(ValueError):
                publisher.parse_uploads_page(document, 'UCexample')

    def test_rss_404_uses_the_verified_uploads_page_without_waiting(self):
        with patch.object(publisher.requests, 'get', return_value=response(404)), \
                patch.object(publisher, 'get_latest_uploads_video', return_value=('Title #tag', VIDEO)) as fallback, \
                patch.object(publisher.time, 'sleep') as sleep:
            self.assertEqual(publisher.get_latest_youtube_video('UCexample', 'example'), ('Title #tag', VIDEO))
        fallback.assert_called_once_with('UCexample')
        sleep.assert_not_called()

    def test_fallback_timeout_and_page_error_are_retried(self):
        with patch.object(publisher.requests, 'get', side_effect=[response(404), response(404), response()]), \
                patch.object(publisher, 'get_latest_uploads_video', side_effect=[publisher.requests.Timeout(), ValueError('bad page')]), \
                patch.object(publisher.time, 'sleep') as sleep:
            self.assertEqual(publisher.get_latest_youtube_video('UCexample', 'example')[1], VIDEO)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [5, 15])

    def test_fallback_rejects_another_owner_without_wordpress_writes(self):
        with patch.object(publisher.requests, 'get', return_value=response(404)), \
                patch.object(publisher, 'get_latest_uploads_video', side_effect=RuntimeError('identity mismatch')), \
                patch.object(publisher, 'get_channel_id', return_value='UCexample'), \
                patch.object(publisher, 'wp_post') as post:
            with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
                publisher.publish_latest_for_target(publisher.TARGETS[0], {})
        post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
