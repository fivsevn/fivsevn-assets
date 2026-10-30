"""Offline contracts from real YouTube RSS, uploads, and watch-page layouts."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import youtube_source as source

CHANNEL = "UC" + "a" * 22
PLAYLIST = "UU" + "a" * 22
OTHER_CHANNEL = "UC" + "b" * 22
FIRST = "AbCdEf123_-"
SECOND = "ZyXwVu987_-"
THIRD = "klmnop456_-"


def video(video_id=FIRST, title="Title #tag", kind="short"):
    if kind == "short":
        return {"shortsLockupViewModel": {
            "onTap": {"innertubeCommand": {"reelWatchEndpoint": {"videoId": video_id}}},
            "overlayMetadata": {"primaryText": {"content": title}},
        }}
    if kind == "lockup":
        return {"lockupViewModel": {"contentId": video_id, "contentType": "LOCKUP_CONTENT_TYPE_VIDEO",
            "metadata": {"lockupMetadataViewModel": {"title": {"content": title}}}}}
    return {kind: {"videoId": video_id, "title": {"simpleText": title}, "isPlayable": True}}


def continuation(token="next", modern=True):
    command = {"commandMetadata": {"webCommandMetadata": {"apiUrl": "/youtubei/v1/browse"}},
        "continuationCommand": {"token": token}}
    if modern:
        return {"continuationItemViewModel": {"continuationCommand": {"innertubeCommand": command}}}
    return {"continuationItemRenderer": {"continuationEndpoint": command}}


def page(items, layout="richGridRenderer", owner=CHANNEL, playlist=PLAYLIST):
    if layout == "section":
        content = {"sectionListRenderer": {"contents": [{"itemSectionRenderer": {"contents": items}}]}}
    else:
        content = {layout: {"contents": items}}
    data = {"header": {"playlistHeaderRenderer": {"playlistId": playlist,
        "ownerEndpoint": {"browseEndpoint": {"browseId": owner}}}},
        "contents": {"twoColumnBrowseResultsRenderer": {"tabs": [{"tabRenderer": {
            "selected": True, "content": content}}]}},
        "sidebar": video("xxxxxxxxxxx", "unrelated recommendation"),
    }
    config = {"INNERTUBE_API_KEY": "public-key", "INNERTUBE_CONTEXT_CLIENT_NAME": 1,
        "INNERTUBE_CLIENT_VERSION": "2.test", "INNERTUBE_CONTEXT": {
            "client": {"clientName": "WEB", "clientVersion": "2.test", "visitorData": "visitor"}}}
    return "function setup(){ytcfg.set(arguments);};ytcfg.set(" + json.dumps(config) + ");<script>var ytInitialData = " + json.dumps(data) + ";</script>"


def response(text="", *, content=None, data=None, status=200):
    result = Mock(status_code=status, text=text, content=text.encode() if content is None else content)
    result.json.return_value = data
    if status >= 400:
        result.raise_for_status.side_effect = source.requests.HTTPError(response=result)
    return result


def next_page(items, target=PLAYLIST):
    return {"onResponseReceivedActions": [{"appendContinuationItemsAction": {
        "targetId": target, "continuationItems": items}}], "sidebar": video("xxxxxxxxxxx")}


def rss(top=CHANNEL[2:], entry_channel=CHANNEL, author=CHANNEL):
    return f'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
<id>yt:channel:{top}</id><yt:channelId>{top}</yt:channelId><title>Example</title>
<author><name>Example</name><uri>https://www.youtube.com/channel/{author}</uri></author>
<entry><id>yt:video:{FIRST}</id><yt:videoId>{FIRST}</yt:videoId><yt:channelId>{entry_channel}</yt:channelId>
<title>RSS first</title><published>2026-10-30T06:23:27+00:00</published></entry>
<entry><id>yt:video:{SECOND}</id><yt:videoId>{SECOND}</yt:videoId><yt:channelId>{entry_channel}</yt:channelId>
<title>RSS second</title><published>2026-10-29T23:23:27-07:00</published></entry></feed>'''.encode()


def watch(video_id=FIRST, channel=CHANNEL, publish_date="2026-10-29T23:23:27-07:00", **micro):
    data = {"videoDetails": {"videoId": video_id, "channelId": channel, "title": "Watch title #one #two"},
        "microformat": {"playerMicroformatRenderer": {"externalVideoId": video_id,
            "externalChannelId": channel, "publishDate": publish_date, **micro}}}
    return "<script>var ytInitialPlayerResponse = " + json.dumps(data) + ";</script>"


class CatalogTests(unittest.TestCase):
    def test_all_first_page_uploads_are_returned_in_source_order(self):
        items = [{"richItemRenderer": {"content": video(FIRST)}}, video(SECOND, "Second", "lockup"),
            video(THIRD, "Third", "videoRenderer")]
        with patch.object(source, "_request", return_value=response(page(items))), \
                patch.object(source, "_rss_videos", return_value=[]):
            result = source.get_channel_videos(CHANNEL, "example")
        self.assertEqual([item.video_id for item in result], [FIRST, SECOND, THIRD])
        self.assertTrue(all(item.published_at is None for item in result))

    def test_classic_and_modern_lists_and_continuation_cards(self):
        for layout in ["richGridRenderer", "playlistVideoListRenderer", "section"]:
            for modern in [False, True]:
                with self.subTest(layout=layout, modern=modern), \
                        patch.object(source, "_request", side_effect=[
                            response(page([video(FIRST), continuation(modern=modern)], layout)),
                            response(data=next_page([video(FIRST), video(SECOND)])),
                        ]) as request, patch.object(source, "_rss_videos", return_value=[]):
                    result = source.get_channel_videos(CHANNEL, "example")
                self.assertEqual([v.video_id for v in result], [FIRST, SECOND])
                args, kwargs = request.call_args
                self.assertEqual(args, ("post", "https://www.youtube.com/youtubei/v1/browse"))
                self.assertEqual(kwargs["json"]["continuation"], "next")
                self.assertEqual(kwargs["headers"]["X-Youtube-Client-Name"], "1")
                self.assertEqual(kwargs["headers"]["X-Goog-Visitor-Id"], "visitor")
                self.assertEqual(kwargs["params"]["key"], "public-key")

    def test_multiple_continuations_traverse_until_no_token(self):
        with patch.object(source, "_request", side_effect=[
            response(page([video(), continuation("page2")])),
            response(data=next_page([video(SECOND), continuation("page3")])),
            response(data=next_page([video(THIRD)])),
        ]), patch.object(source, "_rss_videos", return_value=[]):
            result = source.get_channel_videos(CHANNEL, "example")
        self.assertEqual([v.video_id for v in result], [FIRST, SECOND, THIRD])

    def test_incorrect_owner_and_playlist_fail(self):
        for options in [{"owner": OTHER_CHANNEL}, {"playlist": "UUwrong"}]:
            with self.subTest(options=options), patch.object(source, "_request", return_value=response(page([video()], **options))):
                with self.assertRaises(source.IdentityError):
                    source.get_channel_videos(CHANNEL, "example")

    def test_wrong_continuation_target_fails_before_returning_catalog(self):
        with patch.object(source, "_request", side_effect=[
            response(page([video(), continuation()])), response(data=next_page([video(SECOND)], target="UUwrong")),
        ]), self.assertRaises(source.IdentityError):
            source.get_channel_videos(CHANNEL, "example")

    def test_wrong_continuation_canonical_url_is_rejected(self):
        data = next_page([video(SECOND)])
        data["microformat"] = {"microformatDataRenderer": {"urlCanonical": "https://www.youtube.com/playlist?list=UUwrong"}}
        with self.assertRaises(source.IdentityError):
            source._continuation_items(data, PLAYLIST)

    def test_repeated_token_and_no_progress_are_failures(self):
        for items in [[video(SECOND), continuation()], [video(), continuation("different")]]:
            with self.subTest(items=items), patch.object(source, "_request", side_effect=[
                response(page([video(), continuation()])), response(data=next_page(items)),
            ]), self.assertRaises(ValueError):
                source.get_channel_videos(CHANNEL, "example")

    def test_page_limit_does_not_silently_truncate(self):
        with patch.object(source, "MAX_PAGES", 1), \
                patch.object(source, "_request", return_value=response(page([video(), continuation()]))), \
                self.assertRaisesRegex(RuntimeError, "page limit"):
            source.get_channel_videos(CHANNEL, "example")

    def test_unknown_card_and_missing_continuation_fail(self):
        for card in [{"newUnknownCard": {}}, {"continuationItemRenderer": {}}]:
            with self.subTest(card=card), self.assertRaises(ValueError):
                source._initial_items(source._assigned_json(page([card]), "ytInitialData"), CHANNEL)

    def test_unplayable_hidden_item_is_skipped(self):
        hidden = {"playlistVideoRenderer": {"isPlayable": False, "title": {"simpleText": "Private video"}}}
        result, token = source._initial_items(source._assigned_json(page([hidden, video()]), "ytInitialData"), CHANNEL)
        self.assertEqual([v.video_id for v in result], [FIRST])
        self.assertIsNone(token)

    def test_empty_or_ambiguous_catalog_is_not_success(self):
        with patch.object(source, "_request", return_value=response(page([]))), self.assertRaises(ValueError):
            source.get_channel_videos(CHANNEL, "example")
        with self.assertRaises(ValueError):
            source._assigned_json("<html>consent</html>", "ytInitialData")


class PageRecoveryTests(unittest.TestCase):
    def test_http_200_shell_is_retried_before_reading_complete_catalog(self):
        with patch.object(source, "_request", side_effect=[response('<html>temporary error</html>'), response(page([video()]))]) as request, \
                patch.object(source.time, "sleep") as sleep, patch.object(source, "_rss_videos", return_value=[]):
            result = source.get_channel_videos(CHANNEL, 'example')
        self.assertEqual([v.video_id for v in result], [FIRST])
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(5)

    def test_persistent_shell_fails_after_bounded_attempts(self):
        with patch.object(source, "_request", return_value=response('<html>consent</html>')) as request, \
                patch.object(source.time, "sleep") as sleep, self.assertRaises(ValueError):
            source.get_channel_videos(CHANNEL, 'example')
        self.assertEqual(request.call_count, 4)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [5, 15, 30])

    def test_watch_shell_without_details_is_retried_without_claiming_wrong_channel(self):
        empty_player = '<script>var ytInitialPlayerResponse = {"playabilityStatus":{"status":"ERROR"}};</script>'
        with patch.object(source, "_request", side_effect=[response(empty_player), response(watch())]) as request, \
                patch.object(source.time, "sleep") as sleep:
            result = source.get_video_metadata(FIRST, CHANNEL)
        self.assertEqual(result.video_id, FIRST)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(5)


class RssTests(unittest.TestCase):
    def test_real_feed_omits_uc_only_at_feed_level_and_all_entries_get_dates(self):
        for top in [CHANNEL[2:], CHANNEL]:
            with self.subTest(top=top), patch.object(source, "_request", return_value=response(content=rss(top=top))):
                result = source._rss_videos(CHANNEL)
            self.assertEqual([v.video_id for v in result], [FIRST, SECOND])
            self.assertEqual([v.published_at for v in result], ["2026-10-30T06:23:27+00:00"] * 2)

    def test_different_feed_entry_or_author_identity_is_rejected(self):
        for options in [{"top": OTHER_CHANNEL}, {"top": OTHER_CHANNEL[2:]},
                {"entry_channel": OTHER_CHANNEL}, {"author": OTHER_CHANNEL}]:
            with self.subTest(options=options), patch.object(source, "_request", return_value=response(content=rss(**options))), \
                    self.assertRaises(source.IdentityError):
                source._rss_videos(CHANNEL)

    def test_enrichment_preserves_catalog_order_titles_and_old_entries(self):
        catalog = [source.Video("First catalog", FIRST), source.Video("Second catalog", SECOND), source.Video("Old", THIRD)]
        with patch.object(source, "_get_catalog", return_value=catalog), \
                patch.object(source, "_request", return_value=response(content=rss())):
            result = source.get_channel_videos(CHANNEL, "example")
        self.assertEqual([v.title for v in result], [v.title for v in catalog])
        self.assertTrue(result[0].published_at)
        self.assertTrue(result[1].published_at)
        self.assertIsNone(result[2].published_at)

    def test_rss_outage_allows_watch_date_fallback_but_identity_error_does_not(self):
        catalog = [source.Video("First", FIRST)]
        for error in [source.requests.Timeout(), ValueError("invalid feed")]:
            with self.subTest(error=error), patch.object(source, "_get_catalog", return_value=catalog), \
                    patch.object(source, "_rss_videos", side_effect=error):
                self.assertEqual(source.get_channel_videos(CHANNEL, "example"), catalog)
        with patch.object(source, "_get_catalog", return_value=catalog), \
                patch.object(source, "_rss_videos", side_effect=source.IdentityError("another channel")), \
                self.assertRaises(source.IdentityError):
            source.get_channel_videos(CHANNEL, "example")


class BackfillMetadataTests(unittest.TestCase):
    def test_verified_dates_are_channel_scoped(self):
        record = {'channel_id': CHANNEL, 'videos': [{'video_id': FIRST, 'title': 'Verified', 'published_at': '2026-09-29T09:27:38-07:00'}]}
        path = Mock()
        path.exists.return_value = True
        path.read_text.return_value = json.dumps(record)
        with patch.object(source, 'BACKFILL_PATH', path):
            self.assertEqual(source._backfill_videos(CHANNEL)[FIRST].published_at, '2026-09-29T16:27:38+00:00')
            self.assertEqual(source._backfill_videos(OTHER_CHANNEL), {})

    def test_seed_only_enriches_public_catalog_and_fresh_rss_wins(self):
        seeded = {FIRST: source.Video('Old seed title', FIRST, '2026-09-29T16:27:38Z'),
                  SECOND: source.Video('Seed second', SECOND, '2026-09-29T16:27:39Z'),
                  THIRD: source.Video('Not publicly listed', THIRD, '2026-09-29T16:27:40Z')}
        with patch.object(source, '_get_catalog', return_value=[source.Video('Current title', FIRST), source.Video('Second', SECOND)]), \
                patch.object(source, '_backfill_videos', return_value=seeded), \
                patch.object(source, '_rss_videos', return_value=[source.Video('RSS', SECOND, '2026-10-30T06:23:27Z')]):
            result = source.get_channel_videos(CHANNEL, 'example')
        self.assertEqual([v.video_id for v in result], [FIRST, SECOND])
        self.assertEqual(result[0].title, 'Current title')
        self.assertEqual(result[0].published_at, '2026-09-29T16:27:38Z')
        self.assertEqual(result[1].published_at, '2026-10-30T06:23:27Z')

    def test_checked_in_backfill_has_eleven_unique_exact_dates_and_official_sources(self):
        record = json.loads(source.BACKFILL_PATH.read_text())
        self.assertEqual(len(record['videos']), 11)
        self.assertEqual(len({v['video_id'] for v in record['videos']}), 11)
        for video in record['videos']:
            self.assertEqual(video['source'], 'https://www.youtube.com/watch?v=' + video['video_id'])
            source._timestamp(video['published_at'])
        self.assertEqual(len(source._backfill_videos(record['channel_id'])), 11)


class WatchTests(unittest.TestCase):
    def setUp(self):
        patch.object(source.time, "sleep").start()
        self.addCleanup(patch.stopall)

    def test_verified_watch_metadata_returns_exact_original_utc_time(self):
        with patch.object(source, "_request", return_value=response(watch())):
            result = source.get_video_metadata(FIRST, CHANNEL)
        self.assertEqual(result, source.Video("Watch title #one #two", FIRST, "2026-10-30T06:23:27+00:00"))

    def test_wrong_video_channel_or_microformat_is_rejected(self):
        for options in [{"video_id": SECOND}, {"channel": OTHER_CHANNEL},
                {"externalVideoId": SECOND}, {"externalChannelId": OTHER_CHANNEL}]:
            with self.subTest(options=options), patch.object(source, "_request", return_value=response(watch(**options))), \
                    self.assertRaises(source.IdentityError):
                source.get_video_metadata(FIRST, CHANNEL)

    def test_missing_timezone_or_date_only_is_not_guessed(self):
        for date in [None, "2026-10-30", "2026-10-30T06:23:27"]:
            with self.subTest(date=date), patch.object(source, "_request", return_value=response(watch(publish_date=date))), \
                    self.assertRaises(ValueError):
                source.get_video_metadata(FIRST, CHANNEL)

    def test_unlisted_video_is_not_republished(self):
        with patch.object(source, "_request", return_value=response(watch(isUnlisted=True))), self.assertRaises(ValueError):
            source.get_video_metadata(FIRST, CHANNEL)


class WatchHtmlFallbackTests(unittest.TestCase):
    def setUp(self):
        patch.object(source.time, "sleep").start()
        self.addCleanup(patch.stopall)

    def html(self, *, video_id=FIRST, channel=CHANNEL, current=FIRST, include_player=True):
        page = {"currentVideoEndpoint": {"watchEndpoint": {"videoId": current}}, "contents": {
            "twoColumnWatchNextResults": {"results": {"results": {"contents": [
                {"videoSecondaryInfoRenderer": {"owner": {"videoOwnerRenderer": {
                    "navigationEndpoint": {"browseEndpoint": {"browseId": channel}}}}}},
            ]}}}}, "recommendations": {"channelId": OTHER_CHANNEL}}
        player = '<script>var ytInitialPlayerResponse = {"playabilityStatus":{"status":"ERROR"}};</script>' if include_player else ''
        return (f'<meta itemprop="identifier" content="{video_id}">'
                '<meta itemprop="datePublished" content="2026-09-29T09:27:38-07:00">'
                '<meta property="og:title" content="Old &amp; original">'
                '<script>var ytInitialData = ' + json.dumps(page) + ';</script>' + player)

    def test_limited_or_absent_player_keeps_exact_date_and_verified_owner(self):
        for include_player in [True, False]:
            with self.subTest(include_player=include_player), patch.object(source, '_request', return_value=response(self.html(include_player=include_player))):
                result = source.get_video_metadata(FIRST, CHANNEL)
            self.assertEqual(result, source.Video('Old & original', FIRST, '2026-09-29T16:27:38+00:00'))

    def test_html_video_and_owner_mismatches_remain_hard_failures(self):
        for options in [{'video_id': SECOND}, {'current': SECOND}, {'channel': OTHER_CHANNEL}]:
            with self.subTest(options=options), patch.object(source, '_request', return_value=response(self.html(**options))) as request:
                with self.assertRaises(source.IdentityError):
                    source.get_video_metadata(FIRST, CHANNEL)
                request.assert_called_once()

    def test_partial_html_without_owner_or_exact_date_is_rejected(self):
        for html in [self.html().replace('videoSecondaryInfoRenderer', 'unknownOwner'),
                     self.html().replace('2026-09-29T09:27:38-07:00', '2026-09-29')]:
            with self.subTest(html=html), patch.object(source, '_request', return_value=response(html)):
                with self.assertRaises(ValueError):
                    source.get_video_metadata(FIRST, CHANNEL)


class RetryTests(unittest.TestCase):
    def test_transient_reads_use_bounded_timeout_and_retry_delays(self):
        success = response()
        with patch.object(source.requests, "get", side_effect=[source.requests.Timeout(), response(status=429), response(status=503), success]) as get, \
                patch.object(source.time, "sleep") as sleep:
            self.assertIs(source._request("get", "https://www.youtube.com/playlist"), success)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [5, 15, 30])
        self.assertTrue(all(call.kwargs["timeout"] == (10, 30) for call in get.call_args_list))

    def test_readonly_browse_post_is_retried_but_permanent_error_is_not(self):
        with patch.object(source.requests, "post", side_effect=[response(status=503), response()]) as post, \
                patch.object(source.time, "sleep"):
            source._request("post", "https://www.youtube.com/youtubei/v1/browse")
        self.assertEqual(post.call_count, 2)
        with patch.object(source.requests, "get", return_value=response(status=401)) as get, \
                patch.object(source.time, "sleep") as sleep, self.assertRaises(source.requests.HTTPError):
            source._request("get", "https://www.youtube.com/watch")
        get.assert_called_once()
        sleep.assert_not_called()

    def test_exhausted_reads_fail_after_four_attempts(self):
        with patch.object(source.requests, "get", side_effect=source.requests.Timeout()) as get, \
                patch.object(source.time, "sleep"), self.assertRaises(source.requests.Timeout):
            source._request("get", "https://www.youtube.com/watch")
        self.assertEqual(get.call_count, 4)


if __name__ == "__main__":
    unittest.main()
