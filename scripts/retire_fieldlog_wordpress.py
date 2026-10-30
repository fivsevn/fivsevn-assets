"""Move the verified, retired Fieldlog WordPress copy to recoverable trash."""
import json
import os
import time
from urllib.parse import urlparse
import requests

MANIFEST = [{'id': '260606070658-3522', 'wp_id': 3522}, {'id': '260606070658-3543', 'wp_id': 3543}, {'id': '260606070659', 'wp_id': 3544}, {'id': '260606070700', 'wp_id': 3545}, {'id': '260606070701', 'wp_id': 3546}, {'id': '260611164216', 'wp_id': 3903}, {'id': '260611164632', 'wp_id': 3904}, {'id': '260611165453', 'wp_id': 3905}, {'id': '260611165550', 'wp_id': 3906}, {'id': '260612182918', 'wp_id': 3923}, {'id': '260612182957', 'wp_id': 3924}, {'id': '260612183144', 'wp_id': 3925}, {'id': '260612183542', 'wp_id': 3926}, {'id': '260612184039', 'wp_id': 3927}, {'id': '260622172039', 'wp_id': 4095}, {'id': '260626180431', 'wp_id': 4155}, {'id': '260626180504', 'wp_id': 4156}, {'id': '260710190145', 'wp_id': 4194}, {'id': '260711094838', 'wp_id': 4202}, {'id': '260711094906', 'wp_id': 4203}, {'id': '260711094928', 'wp_id': 4204}, {'id': '260711203908', 'wp_id': 4224}, {'id': '260711203940', 'wp_id': 4225}, {'id': '260712080201', 'wp_id': 4226}, {'id': '260712080248', 'wp_id': 4227}, {'id': '260712080304', 'wp_id': 4228}, {'id': '260712080339', 'wp_id': 4229}, {'id': '260712080348', 'wp_id': 4230}, {'id': '260712215556', 'wp_id': 4236}, {'id': '260712221212', 'wp_id': 4237}, {'id': '260712221233', 'wp_id': 4238}, {'id': '260715084741', 'wp_id': 4246}, {'id': '260715084819', 'wp_id': 4247}, {'id': '260715084923', 'wp_id': 4248}, {'id': '260715090149', 'wp_id': 4251}, {'id': '260715090207', 'wp_id': 4252}, {'id': '260715090230', 'wp_id': 4253}, {'id': '260715090312', 'wp_id': 4254}, {'id': '260715090332', 'wp_id': 4255}, {'id': '260715090344', 'wp_id': 4256}, {'id': '260715090359', 'wp_id': 4257}, {'id': '260715090439', 'wp_id': 4258}, {'id': '260715090824', 'wp_id': 4259}]
EXPECTED = {item['wp_id'] for item in MANIFEST}
CATEGORY = 20425595
PAGE = 1419
BASE = os.environ['WP_BASE_URL'].rstrip('/')
if urlparse(BASE).scheme != 'https' or urlparse(BASE).hostname not in {'fivsevn.com', 'fivsevn.wordpress.com'}:
    raise RuntimeError('Unexpected WordPress site; no content changed')
AUTH = (os.environ['WP_USERNAME'], os.environ['WP_APP_PASSWORD'])

def call(method, endpoint, **kwargs):
    for attempt in range(5):
        result = requests.request(method, BASE + '/wp-json/wp/v2/' + endpoint,
                                  auth=AUTH, timeout=45, **kwargs)
        if result.status_code == 429 and attempt < 4:
            time.sleep(min(60, max(5, int(result.headers.get('Retry-After', '10')))))
            continue
        result.raise_for_status()
        return result
    raise RuntimeError('WordPress rate limit; remaining content retained')

def posts(status):
    found = {}
    for page in range(1, 21):
        response = call('GET', 'posts', params={'categories': CATEGORY, 'status': status,
            'per_page': 100, 'page': page, 'context': 'edit', '_fields': 'id,slug,status,categories'})
        found.update({p['id']: p for p in response.json()})
        if page >= int(response.headers.get('X-WP-TotalPages', '1')):
            return found
    raise RuntimeError('Unexpected category size; no content changed')

receipt = requests.get('https://devlog.fivsevn.com/natsci/fieldlog/build-receipt.json', timeout=45)
receipt.raise_for_status()
archive = receipt.json()
if archive.get('posts') != 43 or set(map(str, archive.get('ids', []))) != {m['id'] for m in MANIFEST}:
    raise RuntimeError('Public archive does not match the approved 43 posts; no content changed')
if len([p for p in archive.get('files', {}) if '/assets/' in p and p.lower().endswith('.webp')]) != 43:
    raise RuntimeError('Public WebP archive is incomplete; no content changed')
published = posts('publish')
trashed = posts('trash')
if set(published) - EXPECTED or not EXPECTED.issubset(set(published) | set(trashed)):
    raise RuntimeError('WordPress category differs from the approved copy; no content changed')
for old in published.values():
    if CATEGORY not in old['categories'] or not old['slug'].startswith('asset-natsci-fieldlog-'):
        raise RuntimeError('Unexpected WordPress post; no content changed')
page = call('GET', 'pages/' + str(PAGE), params={'context': 'edit', '_fields': 'id,slug,status,type'}).json()
if page['id'] != PAGE or page['slug'] != 'natsci' or page['type'] != 'page' or page['status'] not in {'publish', 'trash'}:
    raise RuntimeError('Unexpected old landing page; no content changed')
for post_id in sorted(published):
    result = call('DELETE', 'posts/' + str(post_id), params={'force': 'false'}).json()
    if result.get('status') != 'trash':
        raise RuntimeError('Could not confirm recoverable trash for ' + str(post_id))
    print('Moved retired Fieldlog post to recoverable trash:', post_id, flush=True)
    time.sleep(1.5)
if page['status'] != 'trash':
    result = call('DELETE', 'pages/' + str(PAGE), params={'force': 'false'}).json()
    if result.get('status') != 'trash':
        raise RuntimeError('Could not confirm recoverable trash for old landing page')
if posts('publish') or not EXPECTED.issubset(posts('trash')):
    raise RuntimeError('Retirement verification failed')
print('Verified: all 43 retired posts and the old landing page are in recoverable trash.')
