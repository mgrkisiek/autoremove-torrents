#-*- coding:utf-8 -*-
import base64
import json
import os
import socket
import time

try: # for Python 3
    import xmlrpc.client as xmlrpclib
    from urllib.parse import quote, unquote, urlencode, urlparse, urlunparse
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError: # for Python 2.7
    import xmlrpclib
    from urllib import quote, unquote, urlencode
    from urlparse import urlparse, urlunparse
    from urllib2 import Request, urlopen, HTTPError, URLError

from ..torrent import Torrent
from ..clientstatus import ClientStatus
from ..torrentstatus import TorrentStatus
from ..exception.connectionfailure import ConnectionFailure
from ..exception.loginfailure import LoginFailure
from ..exception.nosuchtorrent import NoSuchTorrent
from ..exception.remotefailure import RemoteFailure

# Default XML-RPC mount point of rTorrent behind a web server (e.g. nginx, ruTorrent)
DEFAULT_RPC_PATH = '/RPC2'

# Endpoint of ruTorrent's httprpc plugin. It forwards plain XML-RPC requests to rTorrent,
# but blocks execute.* commands, so torrents are removed through its own API instead
HTTPRPC_PATH = '/plugins/httprpc/action.php'

# Timeout of httprpc API requests, in seconds
HTTPRPC_TIMEOUT = 60

# Torrent fields fetched with d.multicall2, in this order
TORRENT_FIELDS = [
    'd.hash=',
    'd.name=',
    'd.custom1=',           # Label (ruTorrent / Flood store the label here)
    'd.custom=addtime',     # Added time (set by ruTorrent)
    'd.size_bytes=',
    'd.completed_bytes=',
    'd.ratio=',             # Ratio * 1000
    'd.up.total=',
    'd.down.total=',
    'd.up.rate=',
    'd.down.rate=',
    'd.state=',             # 0: stopped, 1: started
    'd.is_active=',         # 0: paused, 1: active
    'd.complete=',
    'd.hashing=',
    'd.message=',
    'd.peers_complete=',    # Connected seeders
    'd.peers_accounted=',   # Connected leechers
    'd.timestamp.started=',
    'd.timestamp.finished=',
    'd.base_path=',
    'd.directory=',
    'd.is_multi_file=',
    'd.free_diskspace=',
]


class SCGITransport(xmlrpclib.Transport):
    '''XML-RPC transport over SCGI (TCP or UNIX socket), which is what rTorrent speaks natively.'''

    def __init__(self, address, *args, **kwargs):
        xmlrpclib.Transport.__init__(self, *args, **kwargs)
        # address is (host, port) for TCP or a path string for a UNIX socket
        self._address = address

    def request(self, host, handler, request_body, verbose=False):
        if not isinstance(request_body, bytes):
            request_body = request_body.encode('utf-8')

        headers = b'CONTENT_LENGTH\x00' + str(len(request_body)).encode('ascii') + b'\x00SCGI\x001\x00'
        payload = str(len(headers)).encode('ascii') + b':' + headers + b',' + request_body

        if isinstance(self._address, tuple):
            sock = socket.create_connection(self._address)
        else:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self._address)
        try:
            sock.sendall(payload)
            chunks = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        finally:
            sock.close()

        response = b''.join(chunks)
        # Strip the HTTP-like headers that rTorrent puts in front of the XML body
        separator = response.find(b'\r\n\r\n')
        body = response[separator + 4:] if separator >= 0 else response

        parser, unmarshaller = self.getparser()
        parser.feed(body)
        parser.close()
        return unmarshaller.close()


class rTorrent(object):
    def __init__(self, host):
        # Host, examples:
        #   http://127.0.0.1/RPC2       (XML-RPC mounted on a web server)
        #   https://seedbox.example.com/rutorrent/plugins/httprpc/action.php
        #   scgi://127.0.0.1:5000       (rTorrent network.scgi.open_port)
        #   scgi:///home/user/.rtorrent.sock (rTorrent network.scgi.open_local)
        self._host = host
        self._proxy = None
        # URL and Authorization header of ruTorrent's httprpc plugin, when the host points to it
        self._httprpc_url = None
        self._httprpc_headers = {}
        # Torrent properties cache
        self._torrent_cache = {}
        self._refresh_expire_time = 30
        self._last_refresh = 0

    # Create the XML-RPC proxy and verify the connection
    def login(self, username, password):
        parsed = urlparse(self._host)
        scheme = parsed.scheme.lower()

        if scheme == 'scgi':
            if parsed.hostname:
                address = (parsed.hostname, parsed.port if parsed.port else 5000)
            else:
                address = parsed.path # UNIX socket
            # The URL is not used for SCGI, but ServerProxy needs a valid one
            self._proxy = xmlrpclib.ServerProxy('http://localhost' + DEFAULT_RPC_PATH,
                transport=SCGITransport(address), allow_none=True)
        elif scheme in ('http', 'https'):
            netloc = parsed.netloc.rsplit('@', 1)[-1] # Drop credentials from the URL if any
            if username:
                netloc = '%s:%s@%s' % (quote(username, safe=''), quote(password or '', safe=''), netloc)
            path = parsed.path if parsed.path not in ('', '/') else DEFAULT_RPC_PATH
            url = urlunparse((scheme, netloc, path, parsed.params, parsed.query, ''))
            self._proxy = xmlrpclib.ServerProxy(url, allow_none=True)

            if path.rstrip('/').endswith(HTTPRPC_PATH):
                self._httprpc_url = urlunparse((scheme, parsed.netloc.rsplit('@', 1)[-1], path, parsed.params, parsed.query, ''))
                self._httprpc_headers = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    # Some web servers drop requests with urllib's default User-Agent
                    'User-Agent': 'autoremove-torrents',
                }
                if username:
                    token = base64.b64encode(('%s:%s' % (username, password or '')).encode('utf-8')).decode('ascii')
                    self._httprpc_headers['Authorization'] = 'Basic ' + token
        else:
            raise ConnectionFailure("Unsupported scheme '%s' for rTorrent. "
                "Use http://, https:// or scgi://." % parsed.scheme)

        # Make a test call
        self._call('system.client_version')

    # A caller to call rTorrent XML-RPC API; includes exception processing
    def _call(self, method, *args):
        try:
            return getattr(self._proxy, method)(*args)
        except xmlrpclib.ProtocolError as e:
            if e.errcode == 401:
                raise LoginFailure('Unauthorized user.')
            raise RemoteFailure('%d %s' % (e.errcode, e.errmsg))
        except xmlrpclib.Fault as e:
            raise RemoteFailure(e.faultString)
        except (socket.error, IOError, OSError) as e:
            raise ConnectionFailure(str(e))

    # Call ruTorrent's httprpc API (form-encoded request, JSON response)
    def _httprpc(self, fields):
        request = Request(self._httprpc_url, data=urlencode(fields).encode('utf-8'), headers=self._httprpc_headers)
        try:
            response = urlopen(request, timeout=HTTPRPC_TIMEOUT)
            try:
                body = response.read()
            finally:
                response.close()
        except HTTPError as e:
            if e.code == 401:
                raise LoginFailure('Unauthorized user.')
            raise RemoteFailure('%d %s' % (e.code, e.reason))
        except (URLError, socket.error, IOError, OSError) as e:
            raise ConnectionFailure(str(e))

        try:
            result = json.loads(body.decode('utf-8'))
        except ValueError:
            raise RemoteFailure('Unexpected response from ruTorrent: %r' % body[:200])
        # httprpc answers `false` when rTorrent rejects the commands
        if result is False:
            raise RemoteFailure('ruTorrent rejected the request.')
        return result

    # Check whether rTorrent still has the torrent
    def _has_torrent(self, torrent_hash):
        try:
            self._call('d.hash', torrent_hash)
            return True
        except RemoteFailure:
            return False

    # Get client status
    def client_status(self):
        cs = ClientStatus()
        cs.free_space = self.remote_free_space
        cs.download_speed = self._call('throttle.global_down.rate')
        cs.total_downloaded = self._call('throttle.global_down.total')
        cs.upload_speed = self._call('throttle.global_up.rate')
        cs.total_uploaded = self._call('throttle.global_up.total')
        return cs

    # Get rTorrent version
    def version(self):
        return 'rTorrent %s' % self._call('system.client_version')

    # Get API version (libtorrent version)
    def api_version(self):
        return 'libtorrent %s' % self._call('system.library_version')

    # Get torrent list (and cache their properties)
    def torrents_list(self):
        rows = self._call('d.multicall2', '', 'main', *TORRENT_FIELDS)
        names = [field.split('=')[0] if not field.startswith('d.custom=') else 'd.custom.' + field.split('=')[1]
            for field in TORRENT_FIELDS]
        torrents = {}
        for row in rows:
            torrent = dict(zip(names, row))
            torrent['trackers'] = []
            torrents[torrent['d.hash']] = torrent

        # Fetch trackers of all torrents in one round trip
        if len(torrents) > 0:
            multicall = xmlrpclib.MultiCall(self._proxy)
            hashes = list(torrents)
            for hash_ in hashes:
                multicall.t.multicall(hash_, '', 't.url=', 't.scrape_complete=', 't.scrape_incomplete=')
            try:
                for hash_, trackers in zip(hashes, multicall()):
                    torrents[hash_]['trackers'] = trackers
            except xmlrpclib.Fault as e:
                raise RemoteFailure(e.faultString)
            except (socket.error, IOError, OSError) as e:
                raise ConnectionFailure(str(e))

        self._torrent_cache = torrents
        self._last_refresh = time.time()
        return list(torrents)

    # Get torrent properties
    def torrent_properties(self, torrent_hash):
        if time.time() - self._last_refresh > self._refresh_expire_time:
            self.torrents_list()
        if torrent_hash not in self._torrent_cache:
            raise NoSuchTorrent("No such torrent of hash '%s'." % torrent_hash)
        torrent = self._torrent_cache[torrent_hash]
        now = time.time()

        torrent_obj = Torrent()
        torrent_obj.hash = torrent['d.hash']
        torrent_obj.name = torrent['d.name']
        # Labels; in rTorrent the label also acts as the category
        torrent_obj.label = rTorrent._parse_labels(torrent['d.custom1'])
        torrent_obj.category = list(torrent_obj.label)
        torrent_obj.tracker = [tracker[0] for tracker in torrent['trackers']]
        torrent_obj.status = rTorrent._judge_status(torrent)
        if torrent_obj.status == TorrentStatus.Uploading:
            torrent_obj.stalled = torrent['d.up.rate'] == 0
        elif torrent_obj.status == TorrentStatus.Downloading:
            torrent_obj.stalled = torrent['d.down.rate'] == 0
        else:
            torrent_obj.stalled = False
        torrent_obj.size = torrent['d.size_bytes']
        torrent_obj.ratio = torrent['d.ratio'] / 1000.0
        torrent_obj.uploaded = torrent['d.up.total']
        torrent_obj.downloaded = torrent['d.down.total']

        started = torrent['d.timestamp.started']
        finished = torrent['d.timestamp.finished']
        try:
            added = int(torrent['d.custom.addtime'])
        except (TypeError, ValueError):
            added = 0
        torrent_obj.create_time = added if added > 0 else started
        torrent_obj.seeding_time = max(0, int(now - finished)) \
            if torrent['d.complete'] and finished > 0 else 0
        download_start = started if started > 0 else torrent_obj.create_time
        download_end = finished if finished > 0 else now
        torrent_obj.downloading_time = max(0, int(download_end - download_start)) if download_start > 0 else 0

        torrent_obj.upload_speed = torrent['d.up.rate']
        torrent_obj.download_speed = torrent['d.down.rate']
        torrent_obj.seeder = sum([max(0, tracker[1]) for tracker in torrent['trackers']])
        torrent_obj.connected_seeder = torrent['d.peers_complete']
        torrent_obj.leecher = sum([max(0, tracker[2]) for tracker in torrent['trackers']])
        torrent_obj.connected_leecher = torrent['d.peers_accounted']
        torrent_obj.average_upload_speed = torrent_obj.uploaded / torrent_obj.seeding_time \
            if torrent_obj.seeding_time > 0 else 0
        torrent_obj.average_download_speed = torrent_obj.downloaded / torrent_obj.downloading_time \
            if torrent_obj.downloading_time > 0 else 0
        torrent_obj.progress = float(torrent['d.completed_bytes']) / torrent['d.size_bytes'] \
            if torrent['d.size_bytes'] > 0 else 0

        return torrent_obj

    # Get free space of the disk where `path` is located
    # rTorrent has no generic free-space method, so we use d.free_diskspace of a torrent stored under `path`
    def remote_free_space(self, path):
        if time.time() - self._last_refresh > self._refresh_expire_time:
            self.torrents_list()
        path = path.rstrip('/') + '/'
        for torrent in self._torrent_cache.values():
            directory = torrent['d.directory'].rstrip('/') + '/'
            if directory.startswith(path):
                return torrent['d.free_diskspace']
        # Fall back to any torrent, it is usually on the same disk
        for torrent in self._torrent_cache.values():
            return torrent['d.free_diskspace']
        return None

    # Parse labels stored in d.custom1
    # ruTorrent stores a single URL-encoded label; Flood stores comma-separated URL-encoded tags
    @staticmethod
    def _parse_labels(raw):
        labels = []
        for part in (raw or '').split(','):
            label = unquote(part).strip()
            if len(label) > 0 and label not in labels:
                labels.append(label)
        return labels

    # Judge torrent status
    @staticmethod
    def _judge_status(torrent):
        if torrent['d.hashing'] != 0:
            return TorrentStatus.Checking
        if torrent['d.state'] == 0:
            return TorrentStatus.Error if len(torrent['d.message']) > 0 else TorrentStatus.Stopped
        if torrent['d.is_active'] == 0:
            return TorrentStatus.Paused
        if torrent['d.complete'] != 0:
            return TorrentStatus.Uploading
        return TorrentStatus.Downloading

    # Path of the torrent's data on the rTorrent host
    def _data_path(self, torrent_hash):
        torrent = self._torrent_cache.get(torrent_hash)
        if torrent is None:
            base_path = self._call('d.base_path', torrent_hash)
            directory = self._call('d.directory', torrent_hash)
            is_multi_file = self._call('d.is_multi_file', torrent_hash)
            name = self._call('d.name', torrent_hash)
        else:
            base_path = torrent['d.base_path']
            directory = torrent['d.directory']
            is_multi_file = torrent['d.is_multi_file']
            name = torrent['d.name']
        if base_path:
            return base_path
        # base_path is empty for closed torrents
        return directory if is_multi_file else os.path.join(directory, name)

    # Batch remove torrents
    # Return values: (success_hash_list, failed_hash_list : [{'hash': ..., 'reason': ...}, ...])
    def remove_torrents(self, torrent_hash_list, remove_data):
        success = []
        failed = []
        for torrent_hash in torrent_hash_list:
            try:
                if self._httprpc_url is not None:
                    self._remove_via_httprpc(torrent_hash, remove_data)
                    success.append(torrent_hash)
                    continue
                data_path = self._data_path(torrent_hash) if remove_data else None
                self._call('d.erase', torrent_hash)
                if remove_data:
                    # d.erase never deletes files, so remove them on the rTorrent host
                    if data_path and data_path.rstrip('/') not in ('', '.'):
                        self._call('execute.throw', '', 'rm', '-rf', '--', data_path)
                success.append(torrent_hash)
            except Exception as e:
                failed.append({
                    'hash': torrent_hash,
                    'reason': str(e),
                })
        return (success, failed)

    # Remove a torrent through ruTorrent's httprpc plugin
    # With remove_data, the data is deleted by ruTorrent's erasedata plugin, like "Remove and delete data" in the web UI
    def _remove_via_httprpc(self, torrent_hash, remove_data):
        if remove_data:
            self._httprpc([('mode', 'removewithdata'), ('hash', torrent_hash), ('v', '1')])
        else:
            self._httprpc([('mode', 'remove'), ('hash', torrent_hash)])
        if self._has_torrent(torrent_hash):
            raise RemoteFailure('The torrent is still in rTorrent after removing it.')
