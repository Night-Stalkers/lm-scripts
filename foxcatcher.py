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

Fogshot determination only takes into account horizontal distance to the target,
since the fog isn't affected by height. The vertical distance is only used to
calculate pitch to the target, which is included in the warnings. The pitch itself
isn't useful, however, it provides us with extra info about the conditions which the
fogshot happened.

Author: Hourai (Yui)

Changelog:

    1.1.0:
        * Renamed script (fogshot_warn -> foxcatcher).
        * Autoban feature added. Enable it by doing "/toggle_foxcatcher_autoban" as an admin

"""

from __future__ import division

from math import tan, asin, pi, cos, sqrt, fabs

from commands import add, admin
from pyspades.collision import distance_3d_vector

NAME = "foxcatcher"
VERSION = "1.1.0"
AUTHOR = "Hourai (Yui)"

FOG_DIST = 128  # Self explanatory, do not change this

# Number of incidents before the incidents get broadcasted to the entire server (all the players)
# Regardless of this number, incidents are ALWAYS broadcasted to IRC
MINIMUM_INCIDENTS_TO_BROADCAST = 2

# Enables autobanning
AUTOBAN_ENABLED = False

# Number of incidents in which an automatic ban should be issued
INCIDENTS_TO_AUTOBAN = 4

# Reason shown when autobanning
AUTOBAN_REASON = "Unlimited range hack detected."

# Duration of the ban, in minutes. (0 for permaban)
AUTOBAN_DURATION = 0


@admin
def toggle_foxcatcher_autoban(connection):
    global AUTOBAN_ENABLED
    AUTOBAN_ENABLED = not AUTOBAN_ENABLED
    msg = "Autobanning has been set to: %s" % AUTOBAN_ENABLED
    log_msg(msg, connection.protocol)
    return msg


add(toggle_foxcatcher_autoban)


def log_msg(msg, protocol, print_name=True, warn=False):
    irc_relay = protocol.irc_relay

    print "%s: %s" % (NAME, msg)

    if print_name:
        msg = "%s: %s" % (NAME, msg)

    if warn:  # sets red text color for IRC warning message
        msg = '\x0304' + msg + '\x0f'

    if irc_relay.factory.bot and irc_relay.factory.bot.colors:
        irc_relay.send(msg)


def foxcatcher_info(connection):
    connection.send_chat("This server is running %s %s created by %s!" % (NAME, VERSION, AUTHOR))


def apply_script(protocol, connection, config):
    class FogshotWarnConnection(connection):

        previous_incidents = 0  # Keeps track of previous fogshots

        def on_login(self, name):  # Show version of the script and author when a player joins
            foxcatcher_info(self)
            return connection.on_login(self, name)

        def get_horizontal_dist_to_player(self, player):
            # Calculate horizontal distance and pitch from self to player

            dist = distance_3d_vector(self.world_object.position, player.world_object.position)
            vdist = self.world_object.position.z - player.world_object.position.z

            theta = asin(vdist / dist) * (180 / pi)

            hdist = sqrt(dist ** 2 - vdist ** 2)

            return hdist, theta

        def on_hit(self, hit_amount, hit_player, type_, grenade):
            # Most of the work happens here
            if not grenade:

                hdist, pitch = self.get_horizontal_dist_to_player(hit_player)

                if hdist >= FOG_DIST:
                    msg = "FOGSHOT WARNING: %s (#%d) hit %s at a horizontal distance of %d blocks " \
                          "(pitch: %.1f degrees). Previous incidents by this player: %d" \
                          % (self.name, self.player_id,
                             hit_player.name, int(hdist), pitch,
                             self.previous_incidents)
                    log_msg(msg, self.protocol, print_name=False, warn=True)
                    if self.previous_incidents >= MINIMUM_INCIDENTS_TO_BROADCAST:
                        self.protocol.send_chat(msg)

                    if AUTOBAN_ENABLED and self.previous_incidents >= INCIDENTS_TO_AUTOBAN:
                        msg = "Maximum fogshot incident limit reached by player %s (#%d). Issuing ban..."
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
