
# *-!-* EXPERIMENTAL *-!- #
# *-!-* UNDER TESTING *-!- #

"""
ipcheck
REQUIRES requests AND IP.py
Checks player's IP addresses using the proxycheck.io API.
To function correctly, a file called "api_key.txt" containing
a valid proxycheck.io API key must exist inside the "ipcheck_data"
directory.
ipcheck automatically caches IP info requests for future queries,
this cache expires after a day, by default.
Needs to be tested a lot.
"""

from IP import IP

import os
import requests
import json
from time import time

from commands import add, admin
from twisted.internet import reactor

NAME = "ipcheck"
VERSION = "1.0.0"
AUTHOR = "Hourai (Yui)"

DATA_DIR = "./scripts/ipcheck_data/"
API_KEY_FILENAME = "api_key.txt"
IP_CACHE_FILENAME = "ip_cache"
PRINT_API_KEY = False

REQUEST_FORMAT = "http://proxycheck.io/v2/%s?key=%s&risk=1&vpn=1"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)" \
             "Chrome/42.0.2311.135 Safari/537.36 Edge/12.246"

HTTP_OK = 200
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_BAD_GATEWAY = 502

# Unix Time, seconds
ONE_MINUTE = 60
ONE_HOUR = 60 * ONE_MINUTE
ONE_DAY = 24 * ONE_HOUR

CACHE_EXPIRE_TIME = ONE_DAY


def log_msg(msg, protocol, print_name=True, warn=False, irc=True, info=False):
    irc_relay = protocol.irc_relay

    print "%s: %s" % (NAME, msg)

    if print_name:
        msg = "%s: %s" % (NAME, msg)

    if warn:  # sets red text color for IRC warning message
        msg = '\x0304' + msg + '\x0f'

    elif info:
        msg = '\x0302' + msg + '\x0f'

    try:
        if irc and irc_relay.factory.bot and irc_relay.factory.bot.colors:
            irc_relay.send(msg)
    except AttributeError as e:
        print "%s: irc bot not initialized." % NAME
        return


class IPCheck(object):

    def __init__(self, proto):
        self.has_api_key = False
        self.api_key = ""
        self.enabled = True
        self.proto = proto
        self.ip_cache = dict()
        self.current_timestamp = int(time())
        self.last_timestamp = 0

        log_msg("running version %s by %s" % (VERSION, AUTHOR), self.proto)

    def start(self):
        self.has_api_key = self._load_api_key()

        if not self.has_api_key:
            self.enabled = False
            log_msg("API KEY NOT FOUND, IPCHECK DISABLED!", self.proto, warn=True)

        self._load_ip_cache_file()

        if "TS" in self.ip_cache:
            self.last_timestamp = self.ip_cache["TS"]
        else:
            self.last_timestamp = self.current_timestamp
            self.ip_cache["TS"] = self.current_timestamp

        if self._check_timestamps(CACHE_EXPIRE_TIME):
            log_msg("IP cache file is too old, cache file ignored.", self.proto)
            self.ip_cache = {}

        log_msg("ipcheck is now ready!", self.proto, info=True)

    def check_ip(self, ip):
        if self.enabled:
            resp, cached = self._get_ip_info(ip)
            resp[u'cached'] = cached
            return resp
        else:
            return {u'IPCHECK DISABLED!'}

    def dump(self):
        log_msg("Saving cache file to disk.", self.proto)
        self._dump_ip_cache_to_file()

    def verify_current_cache(self, time_period):
        log_msg("Verifying current IP cache...", self.proto)

        current_time = int(time())
        diff = current_time - self.last_timestamp
        if diff > time_period:
            log_msg("IP cache too old, emptying cache.", self.proto)
            self.last_timestamp = current_time
            self.current_timestamp = current_time
            self.ip_cache = {"TS": current_time}
        else:
            log_msg("Current IP cache OK.", self.proto)

    def _get_ip_info(self, ip):
        if ip == IP("127.0.0.1") or ip == IP("255.255.255.255") or ip.ip[0] == 192:
            return json.loads('{"status": "ok", "127.0.0.1": {"type":"localhost"}}'), False
        if self._ip_already_exists(ip):
            return self._get_ip_info_from_cache(ip), True
        r = requests.get(REQUEST_FORMAT % (ip, self.api_key))
        if r.status_code == HTTP_OK:
            self._new_cache_entry(ip, r.json())
            return r.json(), False
        elif r.status_code == HTTP_FORBIDDEN:
            return json.loads('{"status": "forbidden"}'), False
        elif r.status_code == HTTP_BAD_GATEWAY:
            return json.loads('{"status": "bad_gateway"}'), False
        elif r.status_code == HTTP_NOT_FOUND:
            return json.loads('{"status": "not_found"}'), False
        elif r.status_code == HTTP_INTERNAL_SERVER_ERROR:
            return json.loads('{"status": "internal_server_error"}'), False

    def _load_ip_cache_file(self):
        #log_msg(os.getcwd(), self.proto)
        if os.path.exists(DATA_DIR + IP_CACHE_FILENAME):
            log_msg("Cache file found.", self.proto, irc=True)
            with open(DATA_DIR + IP_CACHE_FILENAME, "r") as fcache:
                cache = fcache.read()
                self.ip_cache = json.loads(cache)
                log_msg("Cache file loaded.", self.proto, irc=True)
            return True
        else:
            log_msg("Cache file not found.", self.proto, irc=True)
            return False

    def _dump_ip_cache_to_file(self):
        #log_msg(os.getcwd(), self.proto)
        with open(DATA_DIR + IP_CACHE_FILENAME, "w+") as fcache:
            cache = json.dumps(self.ip_cache)
            fcache.write(cache)

    def _get_ip_info_from_cache(self, ip):
        for ip_record in self.ip_cache:
            if ip_record == ip.ip_str:
                return self.ip_cache[ip_record]

    def _ip_already_exists(self, ip):
        return ip.ip_str in self.ip_cache

    def _load_api_key(self):
        #log_msg(os.getcwd(), self.proto)
        if os.path.exists(DATA_DIR + API_KEY_FILENAME):
            with open(DATA_DIR + API_KEY_FILENAME) as f:
                lines = []
                for line in f:
                    lines.append(line.rstrip())
                self.api_key = lines[0]
                log_msg("API KEY found!", self.proto)
                if PRINT_API_KEY:
                    log_msg("[%s]" % self.api_key, self.proto, irc=False)
            return True
        else:
            log_msg("API key file not found.", self.proto, irc=False)
            return False

    def _new_cache_entry(self, ip, info):
        self.ip_cache[ip.ip_str] = info

    def _check_timestamps(self, time_period):
        diff = self.current_timestamp - self.last_timestamp
        if self.current_timestamp == self.last_timestamp:
            return False
        elif diff > time_period:
            return True
        else:
            return False


def apply_script(protocol, connection, config):

    class IPCheckProtocol(protocol):

        def __init__(self, *args, **kwargs):
            protocol.__init__(self, *args, **kwargs)

            self.ipcheck = IPCheck(self)
            self.test = 1
            reactor.callLater(5, self.ipcheck.start)

        def on_map_leave(self):
            self.ipcheck.verify_current_cache(CACHE_EXPIRE_TIME)
            self.ipcheck.dump()
            return protocol.on_map_leave(self)

    class IPCheckConnection(connection):

        def __init__(self, *args, **kwargs):
            connection.__init__(self, *args, **kwargs)

        def on_login(self, name):
            ip = IP(self.address[0])
            result = self.protocol.ipcheck.check_ip(ip)
            log_msg("Player \"%s\" IP ADRRESS INFO: %s" % (name, str(result)), self.protocol, info=True)
            return connection.on_login(self, name)

    return IPCheckProtocol, IPCheckConnection
