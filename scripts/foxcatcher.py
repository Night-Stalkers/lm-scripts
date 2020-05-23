"""
foxcatcher.py
Copyright (C) 2020 Night-Stalkers

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
"""
foxcatcher
Displays a warning whenever a player hits another player through the fog.
In other words, everytime a player hits a player which is 128+ (horizontal)
blocks away. This is referred to as a fogshot.
At 128 horizontal blocks, players are completely covered by the fog (At least in OS),
so hitting players farther than that is considered to be cheating, thus a
warning is issued to admins. Each time said player lands a hit on a player
which is 128 horizontal blocks away, an incident counter also increases.
This is useful for telling apart false-positives and lucky players
getting a lucky one-time fogshot. Once the incident counter reaches
a certain set amount (MINIMUM_INCIDENTS_TO_BROADCAST), the next incidents
will be broadcasted to the whole server. This is useful in case the server
staff is not available or if there's no one checking IRC chat, thus
players in the server can issue a votekick against the cheating player.

The fog is assumed to be completely opaque at 128. The only visibility
a player has can be described with a cylinder of infinite height, starting
from the bottom of the world all the way to the "sky". The player is at the
center of this cylinder. This cylinder has a radius of 128. Outside this cylinder
everything is obscured by the fog, so other players out of this cylinder shouldn't
be visible to the player in question, under normal conditions that is. Everything
that the player hits outside this cylinder is considered to be a fogshot and is
reported.

Another way to see this is by imagining the game map from a top down perspective.
A player's (absolute) visibility can be described with a circle that has a radius of
128 blocks, with the player being in the center of this circle. Every hit outside
this circle is thus considered to be a fogshot.

Author: Hourai (Yui)

Changelog:

    1.2.0:
        * No longer broadcasts warnings to server, only ban messages.
        * Optimized 2d distance calculation.

    1.1.1:
        * Autobanning is now on by default.

    1.1.0:
        * Renamed script (fogshot_warn -> foxcatcher).
        * Autoban feature added. Enable it by doing "/toggle_foxcatcher_autoban" as an admin.

"""

from math import sqrt

from piqueserver.commands import command
from pyspades.collision import distance_3d_vector

from piqueserver.config import config
irc_options = config.option('irc', {})
irc_cfg = irc_options.get()
irc_enabled = irc_cfg.get('enabled', False)

NAME = "foxcatcher"
VERSION = "1.2.0"
AUTHOR = "Hourai (Yui)"

FOG_DIST = 128  # Self explanatory, do not change this

# Enables autobanning
AUTOBAN_ENABLED = True

# Number of incidents in which an automatic ban should be issued
INCIDENTS_TO_AUTOBAN = 4

# Reason shown when autobanning
AUTOBAN_REASON = "Unlimited range hack detected."

# Duration of the ban, in minutes. (0 for permaban)
AUTOBAN_DURATION = 0


@command('toggle_foxcatcher_autoban', admin_only = True)
def toggle_foxcatcher_autoban(connection):
    global AUTOBAN_ENABLED
    AUTOBAN_ENABLED = not AUTOBAN_ENABLED
    msg = "Autobanning has been set to: %s" % AUTOBAN_ENABLED
    log_msg(msg, connection.protocol)
    return msg

def log_msg(msg, protocol, print_name=True, warn=False):

    print("%s: %s" % (NAME, msg))

    if print_name:
        msg = "%s: %s" % (NAME, msg)

    if warn:  # sets red text color for IRC warning message
        msg = '\x0304' + msg + '\x0f'

    if irc_enabled:
        irc_relay = protocol.irc_relay
        if irc_relay.factory.bot and irc_relay.factory.bot.colors:
            irc_relay.send(msg)


@command("foxcatcher_info")
def foxcatcher_info(connection):
    connection.send_chat("This server is running %s %s created by %s." % (NAME, VERSION, AUTHOR))


def apply_script(protocol, connection, config):
    class FogshotWarnConnection(connection):

        previous_incidents = 0  # Keeps track of previous fogshots

        def get_horizontal_dist_to_player(self, player):

            v1 = self.world_object.position.x, self.world_object.position.y
            v2 = player.world_object.position.x, player.world_object.position.y

            v3 = (v2[0] - v1[0], v2[1] - v1[1])
            hdist = sqrt(v3[0]**2 + v3[1]**2)

            return hdist

        def on_hit(self, hit_amount, hit_player, type_, grenade):
            # Most of the work happens here
            if not grenade:

                hdist = self.get_horizontal_dist_to_player(hit_player)

                if hdist >= FOG_DIST:
                    msg = "FOGSHOT WARNING: %s (#%d) hit %s at a horizontal distance of %d blocks. " \
                          "Previous incidents by this player: %d" \
                          % (self.name, self.player_id,
                             hit_player.name, int(hdist),
                             self.previous_incidents)
                    log_msg(msg, self.protocol, print_name=False, warn=True)

                    if AUTOBAN_ENABLED and self.previous_incidents >= INCIDENTS_TO_AUTOBAN:
                        msg = "Maximum fogshot limit reached by player %s (#%d). Issuing ban..."
                        msg = msg % (self.name, self.player_id)
                        log_msg(msg, self.protocol, print_name=False, warn=True)
                        self.protocol.send_chat(msg)
                        self.ban(AUTOBAN_REASON, AUTOBAN_DURATION)

                    self.previous_incidents += 1

            return connection.on_hit(self, hit_amount, hit_player, type_, grenade)

    class FogshotWarnProtocol(protocol):

        def __init__(self, *args, **kwargs):
            protocol.__init__(self, *args, **kwargs)

            # Show running version on server start
            start_msg = "running version %s by %s" % (VERSION, AUTHOR)
            log_msg(start_msg, self)

    return FogshotWarnProtocol, FogshotWarnConnection
