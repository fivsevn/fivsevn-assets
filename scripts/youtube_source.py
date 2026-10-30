"""Read a complete, verified public YouTube uploads catalogue and exact dates."""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import time
from urllib.parse import parse_qs, urlparse

import feedparser
import requests


TIMEOUT = (10, 30)
RETRY_DELAYS = (5, 15, 30)
MAX_PAGES = 1000
USER_AGENT = "Mozilla/5.0 (compatible; fivsevn-youtube-sync/2.0)"
BACKFILL_PATH = Path(__file__).with_name("youtube_backfill.json")


@dataclass(frozen=True)
class Video:
    title: str
    video_id: str
    published_at: str | None = None


class IdentityError(RuntimeError):
    """The response belongs to a different channel, playlist, or video."""


def _request(method, url, **kwargs):
    """Retry reads, including the read-only browse POST; never WordPress writes."""
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            response = getattr(requests, method)(url, timeout=TIMEOUT, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            if status is not None and status not in {404, 408, 429} and not 500 <= status < 600:
                raise
            if attempt == len(RETRY_DELAYS):
                raise
            delay = RETRY_DELAYS[attempt]
            print(f"YouTube read: {type(error).__name__}; retrying in {delay}s.", flush=True)
            time.sleep(delay)
    raise RuntimeError("YouTube read exhausted retries")


def _renderers(node, name):
    if isinstance(node, dict):
        if name in node:
            yield node[name]
        for value in node.values():
            yield from _renderers(value, name)
    elif isinstance(node, list):
        for value in node:
            yield from _renderers(value, name)


def _assigned_json(document, variable):
    marker = re.search(r"\b(?:var\s+)?" + re.escape(variable) + r"\s*=\s*", document)
    if not marker:
        raise ValueError(f"YouTube page has no {variable}")
    value, _ = json.JSONDecoder().raw_decode(document[marker.end():])
    if not isinstance(value, dict):
        raise ValueError(f"YouTube {variable} is not an object")
    return value



def _read_page(url, variable, *, required_key=None, **kwargs):
    """Retry HTTP-200 consent/error shells that contain no usable page data."""
    for attempt in range(len(RETRY_DELAYS) + 1):
        response = _request("get", url, **kwargs)
        try:
            data = _assigned_json(response.text, variable)
            if required_key and (not isinstance(data.get(required_key), dict) or not data[required_key]):
                raise ValueError(f"YouTube page has no {required_key}")
            return response.text, data
        except ValueError as error:
            if attempt == len(RETRY_DELAYS):
                raise
            delay = RETRY_DELAYS[attempt]
            print(f"YouTube page data unavailable ({error}); retrying in {delay}s.", flush=True)
            time.sleep(delay)
    raise RuntimeError("YouTube page data exhausted retries")

def _config(document):
    config = {}
    # The first ytcfg.set(...) occurrence may be its function definition.
    for marker in re.finditer(r"\bytcfg\.set\(\s*", document):
        try:
            value, _ = json.JSONDecoder().raw_decode(document[marker.end():])
        except ValueError:
            continue
        if isinstance(value, dict):
            config.update(value)
    return config


def _text(value):
    return value.get("simpleText") or "".join(run.get("text", "") for run in value.get("runs", []))


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("YouTube publication time is missing")
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None or "T" not in value:
        raise ValueError("YouTube publication time must include a time and timezone")
    return date.astimezone(timezone.utc).isoformat()


def _video(title, video_id, published_at=None):
    if not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("YouTube item has no valid video ID")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("YouTube item has no title")
    return Video(title.strip(), video_id, published_at)


def _continuation(card):
    if "continuationItemRenderer" in card:
        command = card["continuationItemRenderer"].get("continuationEndpoint", {})
    else:
        command = card["continuationItemViewModel"].get("continuationCommand", {})
        command = command.get("innertubeCommand", command)
    endpoint = command.get("commandMetadata", {}).get("webCommandMetadata", {}).get("apiUrl")
    if endpoint is not None and endpoint != "/youtubei/v1/browse":
        raise ValueError("Unexpected YouTube continuation endpoint")
    token = command.get("continuationCommand", {}).get("token")
    if not isinstance(token, str) or not token:
        raise ValueError("YouTube continuation has no token")
    return token


def _parse_items(items):
    if not isinstance(items, list):
        raise ValueError("YouTube upload list is missing")
    videos, token = [], None
    for index, item in enumerate(items):
        card = item.get("richItemRenderer", {}).get("content", item)
        if "continuationItemRenderer" in card or "continuationItemViewModel" in card:
            if token is not None or index != len(items) - 1:
                raise ValueError("YouTube continuation is not the unique last item")
            token = _continuation(card)
            continue
        if "playlistVideoRenderer" in card or "videoRenderer" in card:
            data = card.get("playlistVideoRenderer", card.get("videoRenderer"))
            if data.get("isPlayable") is False:
                continue
            title, video_id = _text(data.get("title", {})), data.get("videoId")
        elif "shortsLockupViewModel" in card:
            data = card["shortsLockupViewModel"]
            video_id = data.get("onTap", {}).get("innertubeCommand", {}).get("reelWatchEndpoint", {}).get("videoId")
            title = data.get("overlayMetadata", {}).get("primaryText", {}).get("content")
        elif "lockupViewModel" in card:
            data = card["lockupViewModel"]
            if data.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
                raise ValueError("Unexpected non-video card in YouTube uploads")
            video_id = data.get("contentId")
            title = data.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {}).get("content")
        else:
            raise ValueError("Unknown YouTube uploads card; refusing an incomplete catalogue")
        videos.append(_video(title, video_id))
    return videos, token


def _initial_items(data, channel_id):
    playlist_id = "UU" + channel_id[2:]
    headers = list(_renderers(data.get("header", {}), "playlistHeaderRenderer"))
    if len(headers) != 1:
        raise ValueError("YouTube uploads has no unique playlist header")
    header = headers[0]
    owner = header.get("ownerEndpoint", {}).get("browseEndpoint", {}).get("browseId")
    if header.get("playlistId") != playlist_id or owner != channel_id:
        raise IdentityError("YouTube uploads playlist identity does not match the configured channel")
    # Select only the playlist's selected tab, never sidebars or recommendations.
    contents = data.get("contents", {})
    browse = contents.get("twoColumnBrowseResultsRenderer", contents.get("singleColumnBrowseResultsRenderer", {}))
    tabs = [tab["tabRenderer"] for tab in browse.get("tabs", []) if "tabRenderer" in tab]
    selected = [tab for tab in tabs if tab.get("selected")]
    if not selected and len(tabs) == 1:
        selected = tabs
    if len(selected) != 1:
        raise ValueError("YouTube uploads has no unique selected tab")
    scope = selected[0].get("content", {})
    lists = list(_renderers(scope, "playlistVideoListRenderer")) + list(_renderers(scope, "richGridRenderer"))
    if not lists:
        # YouTube's current regular-video layout uses an item section.
        lists = list(_renderers(scope, "itemSectionRenderer"))
    if len(lists) != 1:
        raise ValueError("YouTube uploads has no unique video list")
    return _parse_items(lists[0].get("contents"))


def _continuation_items(response, playlist_id):
    canonical = response.get("microformat", {}).get("microformatDataRenderer", {}).get("urlCanonical")
    if canonical:
        parsed = urlparse(canonical)
        if parsed.hostname not in {"www.youtube.com", "youtube.com"} or parse_qs(parsed.query).get("list") != [playlist_id]:
            raise IdentityError("YouTube continuation belongs to another playlist")
    actions = []
    for group in ("onResponseReceivedActions", "onResponseReceivedEndpoints"):
        for action in response.get(group, []):
            for name in ("appendContinuationItemsAction", "reloadContinuationItemsCommand"):
                if name in action:
                    actions.append(action[name])
    if len(actions) != 1:
        raise ValueError("YouTube continuation has no unique append action")
    action = actions[0]
    # The classic renderer uses a fixed target name; modern lists use the UU ID.
    if action.get("targetId") not in {playlist_id, "VL" + playlist_id, "playlist-video-list"}:
        raise IdentityError("YouTube continuation target does not match the uploads list")
    return _parse_items(action.get("continuationItems"))


def _get_catalog(channel_id):
    playlist_id = "UU" + channel_id[2:]
    page_url = "https://www.youtube.com/playlist?list=" + playlist_id + "&hl=en"
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    document, initial_data = _read_page(page_url, "ytInitialData", headers=headers)
    videos, token = _initial_items(initial_data, channel_id)
    catalogue = {video.video_id: video for video in videos}
    config, seen_tokens = _config(document), set()
    for page in range(1, MAX_PAGES + 1):
        if token is None:
            if not catalogue:
                raise ValueError("YouTube uploads contains no public videos")
            return list(catalogue.values())
        if page == MAX_PAGES:
            raise RuntimeError("YouTube uploads exceeded the page limit with unread videos")
        if token in seen_tokens:
            raise ValueError("YouTube uploads repeated a continuation token")
        seen_tokens.add(token)
        context = config.get("INNERTUBE_CONTEXT")
        if not isinstance(context, dict) or not isinstance(context.get("client"), dict):
            raise ValueError("YouTube continuation has no client context")
        version = config.get("INNERTUBE_CLIENT_VERSION") or context["client"].get("clientVersion")
        client = config.get("INNERTUBE_CONTEXT_CLIENT_NAME")
        if client is None or not version:
            raise ValueError("YouTube continuation has no client version or name")
        request_headers = {
            "User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json",
            "Origin": "https://www.youtube.com", "Referer": page_url,
            "X-Youtube-Client-Name": str(client), "X-Youtube-Client-Version": str(version),
        }
        visitor = context["client"].get("visitorData") or config.get("VISITOR_DATA")
        if visitor:
            request_headers["X-Goog-Visitor-Id"] = visitor
        params = {"prettyPrint": "false"}
        if config.get("INNERTUBE_API_KEY"):
            params["key"] = config["INNERTUBE_API_KEY"]
        response = _request(
            "post", "https://www.youtube.com/youtubei/v1/browse", params=params,
            headers=request_headers, json={"context": context, "continuation": token},
        ).json()
        videos, token = _continuation_items(response, playlist_id)
        previous_size = len(catalogue)
        for video in videos:
            catalogue.setdefault(video.video_id, video)
        if len(catalogue) == previous_size:
            raise ValueError("YouTube continuation made no progress")
    raise RuntimeError("YouTube uploads page traversal did not terminate")


def _rss_videos(channel_id):
    response = _request(
        "get", "https://www.youtube.com/feeds/videos.xml", params={"channel_id": channel_id},
        headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml"},
    )
    feed = feedparser.parse(response.content)
    if feed.get("bozo") or not feed.get("version") or not feed.entries:
        raise ValueError("YouTube RSS is malformed or empty")
    source = feed.feed.get("yt_channelid")
    # YouTube currently omits UC only at feed level; entries retain the full ID.
    if source and source not in {channel_id, channel_id[2:]}:
        raise IdentityError("YouTube RSS belongs to another channel")
    if not source:
        raise ValueError("YouTube RSS has no channel identity")
    author = feed.feed.get("author_detail", {}).get("href")
    if author and author.rstrip("/") != "https://www.youtube.com/channel/" + channel_id:
        raise IdentityError("YouTube RSS author belongs to another channel")
    for entry in feed.entries:
        if entry.get("yt_channelid") and entry["yt_channelid"] != channel_id:
            raise IdentityError("YouTube RSS entry belongs to another channel")
    videos = []
    for entry in feed.entries:
        videos.append(_video(entry.get("title"), entry.get("yt_videoid"), _timestamp(entry.get("published"))))
    return videos



def _backfill_videos(channel_id):
    """Exact dates verified from official pages for the historical catch-up."""
    if not BACKFILL_PATH.exists():
        return {}
    record = json.loads(BACKFILL_PATH.read_text())
    if record.get("channel_id") != channel_id:
        return {}
    result = {}
    for item in record.get("videos", []):
        video = _video(item.get("title"), item.get("video_id"), _timestamp(item.get("published_at")))
        if video.video_id in result:
            raise ValueError("Duplicate video in verified YouTube backfill metadata")
        result[video.video_id] = video
    return result

def get_channel_videos(channel_id: str, target_name: str) -> list[Video]:
    """Return every public upload, newest first, with RSS dates when available."""
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", channel_id):
        raise ValueError("A full UC... YouTube channel ID is required")
    catalogue = _get_catalog(channel_id)
    try:
        dated = {video.video_id: video for video in _rss_videos(channel_id)}
    except IdentityError:
        raise
    except (requests.RequestException, ValueError) as error:
        print(f"YouTube RSS [{target_name}] unavailable ({type(error).__name__}); using verified uploads and watch dates.", flush=True)
        dated = {}
    # A seeded date only applies to videos still in this verified public catalogue.
    dates = _backfill_videos(channel_id)
    dates.update(dated)
    result = [replace(video, published_at=dates[video.video_id].published_at) if video.video_id in dates else video for video in catalogue]
    print(f"Read {len(result)} verified public YouTube uploads [{target_name}].", flush=True)
    return result



class _WatchMeta(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = attrs.get("itemprop") or attrs.get("property") or attrs.get("name")
            if key in {"identifier", "datePublished", "og:title"}:
                self.values.setdefault(key, []).append(attrs.get("content", ""))


def _watch_html_metadata(document, video_id, channel_id):
    """Use independent SEO and watch-page owner data when playback is limited."""
    metadata = _WatchMeta()
    metadata.feed(document)
    values = {}
    for key in ("identifier", "datePublished", "og:title"):
        unique = set(metadata.values.get(key, []))
        if len(unique) != 1 or not next(iter(unique)):
            raise ValueError(f"YouTube watch page has no unique {key}")
        values[key] = next(iter(unique))
    page = _assigned_json(document, "ytInitialData")
    current = page.get("currentVideoEndpoint", {}).get("watchEndpoint", {}).get("videoId")
    if not current:
        raise ValueError("YouTube watch page has no current video identity")
    if current != video_id or values["identifier"] != video_id:
        raise IdentityError(f"YouTube watch HTML does not match requested video {video_id}")
    contents = page.get("contents", {}).get("twoColumnWatchNextResults", {}).get("results", {}).get("results", {}).get("contents", [])
    owners = [item["videoSecondaryInfoRenderer"].get("owner", {}).get("videoOwnerRenderer", {}).get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId")
              for item in contents if "videoSecondaryInfoRenderer" in item]
    if len(owners) != 1 or not owners[0]:
        raise ValueError("YouTube watch page has no unique video owner")
    if owners[0] != channel_id:
        raise IdentityError(f"YouTube watch HTML for {video_id} belongs to another channel")
    return _video(values["og:title"], video_id, _timestamp(values["datePublished"]))


def _parse_watch_metadata(document, video_id, channel_id):
    try:
        data = _assigned_json(document, "ytInitialPlayerResponse")
    except ValueError:
        return _watch_html_metadata(document, video_id, channel_id)
    details = data.get("videoDetails") or {}
    microformat = data.get("microformat", {}).get("playerMicroformatRenderer", {})
    if microformat.get("externalVideoId", video_id) != video_id or microformat.get("externalChannelId", channel_id) != channel_id:
        raise IdentityError("YouTube watch microformat belongs to another video or channel")
    if details.get("isPrivate") or microformat.get("isUnlisted"):
        raise ValueError("YouTube watch video is no longer public")
    if not details:
        return _watch_html_metadata(document, video_id, channel_id)
    if details.get("videoId") != video_id or details.get("channelId") != channel_id:
        raise IdentityError(f"YouTube watch metadata does not match requested video {video_id} and channel")
    return _video(details.get("title"), video_id, _timestamp(microformat.get("publishDate")))


def get_video_metadata(video_id: str, channel_id: str) -> Video:
    """Read a missing upload's verified original time, even if playback is limited."""
    _video("validate", video_id)
    for attempt in range(len(RETRY_DELAYS) + 1):
        # The official Shorts route exposes the same verified page metadata and
        # can remain available when the regular watch route is playback-limited.
        url = "https://www.youtube.com/watch" if attempt % 2 == 0 else f"https://www.youtube.com/shorts/{video_id}"
        params = {"v": video_id, "hl": "en"} if attempt % 2 == 0 else {"hl": "en"}
        response = _request(
            "get", url, params=params,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        )
        try:
            return _parse_watch_metadata(response.text, video_id, channel_id)
        except ValueError as error:
            if attempt == len(RETRY_DELAYS):
                raise
            delay = RETRY_DELAYS[attempt]
            print(f"YouTube watch metadata {video_id} unavailable ({error}); retrying in {delay}s.", flush=True)
            time.sleep(delay)
    raise RuntimeError("YouTube watch metadata exhausted retries")
