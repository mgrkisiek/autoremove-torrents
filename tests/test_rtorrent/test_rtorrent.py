#-*- coding:utf-8 -*-
# Tests the rTorrent client against an in-process fake rTorrent XML-RPC server
import socket
import threading
import time
import pytest

import json

try: # for Python 3
    from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCDispatcher, SimpleXMLRPCRequestHandler
    from urllib.parse import parse_qs
except ImportError: # for Python 2.7
    from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCDispatcher, SimpleXMLRPCRequestHandler
    from urlparse import parse_qs

from autoremovetorrents import logger
from autoremovetorrents.client.rtorrent import rTorrent, TORRENT_FIELDS
from autoremovetorrents.strategy import Strategy
from autoremovetorrents.torrentstatus import TorrentStatus
from autoremovetorrents.exception.loginfailure import LoginFailure

NOW = 1700000000

def _torrent(hash_, name, label, state=1, active=1, complete=1, hashing=0, message='',
             finished=NOW - 7200, multi=1):
    return {
        'd.hash=': hash_, 'd.name=': name, 'd.custom1=': label, 'd.custom=addtime': str(NOW - 86400),
        'd.size_bytes=': 1000, 'd.completed_bytes=': 1000 if complete else 250, 'd.ratio=': 1500,
        'd.up.total=': 1500, 'd.down.total=': 1000, 'd.up.rate=': 10 if complete else 0,
        'd.down.rate=': 0 if complete else 20, 'd.state=': state, 'd.is_active=': active,
        'd.complete=': complete, 'd.hashing=': hashing, 'd.message=': message,
        'd.peers_complete=': 2, 'd.peers_accounted=': 3, 'd.timestamp.started=': NOW - 10000,
        'd.timestamp.finished=': finished if complete else 0, 'd.base_path=': '/data/' + name,
        'd.directory=': '/data/' + name if multi else '/data', 'd.is_multi_file=': multi,
        'd.free_diskspace=': 5 * (1 << 20),
    }


class FakeRTorrent(object):
    def __init__(self):
        self.torrents = {
            'A' * 40: _torrent('A' * 40, 'movie', 'Movies'),
            'B' * 40: _torrent('B' * 40, 'show', 'TV%2CShows,HD'), # Flood-style tags, URL-encoded
            'C' * 40: _torrent('C' * 40, 'paused', '', active=0),
            'D' * 40: _torrent('D' * 40, 'broken', 'Movies', state=0, message='Tracker: error'),
            'E' * 40: _torrent('E' * 40, 'leeching', 'Keep', complete=0),
        }
        self.executed = []
        self.erased_with_data = []

    def register(self, dispatcher):
        dispatcher.register_multicall_functions()
        for name, func in [
            ('system.client_version', lambda: '0.9.8'),
            ('system.library_version', lambda: '0.13.8'),
            ('throttle.global_down.rate', lambda: 100),
            ('throttle.global_down.total', lambda: 1000),
            ('throttle.global_up.rate', lambda: 200),
            ('throttle.global_up.total', lambda: 2000),
            ('d.multicall2', self.d_multicall2),
            ('t.multicall', self.t_multicall),
            ('d.erase', self.d_erase),
            ('d.hash', self.d_hash),
            ('execute.throw', self.execute_throw),
        ]:
            dispatcher.register_function(func, name)

    def d_multicall2(self, target, view, *fields):
        assert list(fields) == TORRENT_FIELDS
        return [[t[f] for f in fields] for t in self.torrents.values()]

    def t_multicall(self, hash_, target, *fields):
        return [['https://tracker.site1.com/announce', 10, 4], ['udp://tracker.site2.com:80', -1, 1]]

    def d_erase(self, hash_):
        if hash_ not in self.torrents:
            raise Exception('Could not find info-hash.')
        del self.torrents[hash_]
        return 0

    def d_hash(self, hash_):
        if hash_ not in self.torrents:
            raise Exception('Could not find info-hash.')
        return hash_

    def execute_throw(self, target, *args):
        self.executed.append(list(args))
        return 0


def _serve_http(fake):
    server = SimpleXMLRPCServer(('127.0.0.1', 0), logRequests=False, allow_none=True)
    fake.register(server)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return 'http://127.0.0.1:%d' % server.server_address[1], server.shutdown


HTTPRPC_PATH = '/rutorrent/plugins/httprpc/action.php'


def _serve_httprpc(fake):
    # Mimics ruTorrent's httprpc plugin: XML-RPC is forwarded to rTorrent except execute.*,
    # and form-encoded requests use the httprpc API
    class Handler(SimpleXMLRPCRequestHandler):
        rpc_paths = (HTTPRPC_PATH,)

        def do_POST(self):
            if self.path != HTTPRPC_PATH or self.headers.get('Authorization') != 'Basic dXNlcjpwYXNz': # user:pass
                self.send_response(401)
                self.end_headers()
                return
            body = self.rfile.read(int(self.headers['Content-Length']))
            if self.headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded'):
                self._reply(json.dumps(self._httprpc(parse_qs(body.decode('utf-8')))).encode('utf-8'))
            elif b'execute.' in body:
                self.send_response(403)
                self.end_headers()
            else:
                self._reply(self.server._marshaled_dispatch(body))

        def _httprpc(self, form):
            mode, hashes = form['mode'][0], form.get('hash', [])
            if mode not in ('remove', 'removewithdata') or any(h not in fake.torrents for h in hashes):
                return False
            for h in hashes:
                del fake.torrents[h]
                if mode == 'removewithdata':
                    fake.erased_with_data.append((h, form['v'][0]))
            return ['0'] * len(hashes)

        def _reply(self, data):
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = SimpleXMLRPCServer(('127.0.0.1', 0), requestHandler=Handler, logRequests=False, allow_none=True)
    fake.register(server)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return 'http://127.0.0.1:%d%s' % (server.server_address[1], HTTPRPC_PATH), server.shutdown


def _serve_scgi(fake):
    dispatcher = SimpleXMLRPCDispatcher(allow_none=True, encoding=None)
    fake.register(dispatcher)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    listener.listen(5)
    running = [True]

    def loop():
        while running[0]:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            data = b''
            while b',' not in data:
                data += conn.recv(4096)
            length, rest = data.split(b':', 1)
            while len(rest) < int(length) + 1:
                rest += conn.recv(4096)
            headers = rest[:int(length)].split(b'\x00')
            content_length = int(headers[headers.index(b'CONTENT_LENGTH') + 1])
            body = rest[int(length) + 1:]
            while len(body) < content_length:
                body += conn.recv(4096)
            response = dispatcher._marshaled_dispatch(body)
            conn.sendall(b'Status: 200 OK\r\nContent-Type: text/xml\r\n\r\n' + response)
            conn.close()

    threading.Thread(target=loop, daemon=True).start()

    def stop():
        running[0] = False
        listener.close()
    return 'scgi://127.0.0.1:%d' % listener.getsockname()[1], stop


@pytest.fixture(params=['http', 'scgi', 'httprpc'])
def client(request, mocker):
    mocker.patch('time.time', return_value=NOW)
    fake = FakeRTorrent()
    host, stop = {'http': _serve_http, 'scgi': _serve_scgi, 'httprpc': _serve_httprpc}[request.param](fake)
    c = rTorrent(host)
    if request.param == 'httprpc':
        c.login('user', 'pass')
    else:
        c.login('', '')
    c.mode = request.param
    c.fake = fake
    yield c
    stop()


def test_info(client):
    assert client.version() == 'rTorrent 0.9.8'
    assert client.api_version() == 'libtorrent 0.13.8'
    cs = client.client_status()
    assert (cs.download_speed, cs.total_downloaded, cs.upload_speed, cs.total_uploaded) == (100, 1000, 200, 2000)
    assert cs.free_space('/data') == 5 * (1 << 20)


def test_properties(client):
    torrents = {t.name: t for t in (client.torrent_properties(h) for h in client.torrents_list())}
    assert len(torrents) == 5

    movie = torrents['movie']
    assert movie.label == ['Movies'] and movie.category == ['Movies']
    assert movie.status == TorrentStatus.Uploading and not movie.stalled
    assert movie.ratio == 1.5 and movie.progress == 1
    assert movie.seeding_time == 7200 and movie.create_time == NOW - 86400
    assert movie.seeder == 10 and movie.leecher == 5
    assert movie.connected_seeder == 2 and movie.connected_leecher == 3
    assert movie.tracker == ['https://tracker.site1.com/announce', 'udp://tracker.site2.com:80']

    assert torrents['show'].label == ['TV,Shows', 'HD']
    assert torrents['paused'].label == [] and torrents['paused'].status == TorrentStatus.Paused
    assert torrents['broken'].status == TorrentStatus.Error
    assert torrents['leeching'].status == TorrentStatus.Downloading
    assert torrents['leeching'].progress == 0.25 and torrents['leeching'].seeding_time == 0


def test_label_strategy(client):
    logger.Logger.init()
    torrents = set(client.torrent_properties(h) for h in client.torrents_list())
    stgy = Strategy('labels', {'labels': ['Movies', 'HD'], 'excluded_labels': 'Keep', 'ratio': 1})
    stgy.execute(client.client_status(), torrents)
    assert set(t.name for t in stgy.remove_list) == {'movie', 'show', 'broken'}


def test_remove(client):
    if client.mode == 'httprpc':
        return # Covered by test_remove_httprpc

    client.torrents_list()
    success, failed = client.remove_torrents(['A' * 40, 'F' * 40], False)
    assert success == ['A' * 40] and len(failed) == 1 and failed[0]['hash'] == 'F' * 40
    assert client.fake.executed == []

    success, failed = client.remove_torrents(['B' * 40], True)
    assert success == ['B' * 40] and failed == []
    assert client.fake.executed == [['rm', '-rf', '--', '/data/show']]
    assert 'B' * 40 not in client.fake.torrents


@pytest.mark.parametrize('client', ['httprpc'], indirect=True)
def test_remove_httprpc(client):
    client.torrents_list()
    success, failed = client.remove_torrents(['A' * 40, 'F' * 40], False)
    assert success == ['A' * 40] and len(failed) == 1 and failed[0]['hash'] == 'F' * 40
    assert 'A' * 40 not in client.fake.torrents and client.fake.erased_with_data == []

    # Data is deleted through ruTorrent's erasedata plugin, never with execute.*
    success, failed = client.remove_torrents(['B' * 40], True)
    assert success == ['B' * 40] and failed == []
    assert client.fake.erased_with_data == [('B' * 40, '1')]
    assert client.fake.executed == []


def test_httprpc_unauthorized(mocker):
    fake = FakeRTorrent()
    host, stop = _serve_httprpc(fake)
    try:
        with pytest.raises(LoginFailure):
            rTorrent(host).login('user', 'wrong')
    finally:
        stop()
