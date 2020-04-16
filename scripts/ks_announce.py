"""
ks_announce.py
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
ks_announce
Announces killstreaks, with custom messages, to the whole server every set number of kills
after a set minimum. These values can be changed by setting "ks_announce_rate" and
"ks_announce_minimum" to any positive integer in config.txt
These variables can also be changed ingame by admininistrators by using the
/set_announce_rate and /set_announce_minimum commands. When these commands are run without
arguments, they return the current values.
The killstreak records are reset every time the map changes. Administrator can forcefully
reset the records at any time by using /clear_killstreak_records.
ks_announce also provides a killstreak record scoreboard, which every player can view by
using /ksboard. Administrators can also broadcast the scoreboard to the server at any
time by using /global_ksboard. The scoreboard is also broadcasted to the whole server
when the game ends and the server advances the rotation.
ksboard shows only the first three position in the records, this may be subject to
change.

Default values:
    ks_announce_rate = 5
    ks_announce_minimum = 5

Using the default settings, a players killstreak will only be broadcasted every 5 kills
after the 5th kill, it is inclusive, so the 5th kill in a killstreak is also announced.

Author: Hourai (Yui)

Changelog:

1.2.1:
    * Removed some debug printing which cluttered console output.

1.2.0:
    * Multiple bugfixes and improvements.
    * IRC commands now work as they should.

1.1.1:
    * Fixed CRITICAL bug where the on_disconnect hook function would never
    finish disconnecting.

1.1.0:
    * Added irc_ksboard broadcast.
    * Fixed new high record bug.
    * Improved ksboard printing.

"""

import random
import operator
import collections

from commands import add, admin

NAME = "ks_announce"
VERSION = "1.2.0"
AUTHOR = "Hourai (Yui)"

N_KILLS_ANNOUNCEMENT = 5
N_KILLS_MINIMUM = 5

KSBOARD_PRINT_FORMAT = "%d. %-12s %4d kills in a row."

MSG_KILLS_UNDER_20 = ["Well done!", "Amazing!", "Brutal!", "It\'s getting hot in here!", "Good job!"]
MSG_KILLS_20_50 = ["Based!", "Holy sh*t!", "Expect ragequits soon!", "Get the camera!", "F*ck this, I am out!",
                   "Being this good should be illegal!", "Votekick incoming!", "EXECUTIONER!", "BLOODBATH!",
                   "EXTERMINATION", "There's only one color!", "MVP!"]
MSG_KILLS_OVER_50 = ["Call the admins!", "GODLIKE!", "Are the bots on?", "Get your sh*t together!", "LOL HACKER!",
                     "This player is not human!", "OVERKILL!", "This is going on Liveleak!", "Is the enemy team awake?",
                     "Huh, missing? What's that?", "Abandon all hope!", "RPGs OP!", "GENOCIDE!", "****!", "WARCRIME!",
                     "UwU!", "OwO!", "...!", "Get a life!", "I have become death!", "God left."]

NAME_KS_UNDER_20 = ["killstreak"]
NAME_KS_20_50 = ["killstreak", "rampage", "destruction", "annihilation", "ass-kicking", "streak", "killing spree"]
NAME_KS_OVER_50 = ["genocide", "warcrime", "assblasting", "KILLSTREAK", "extermination"]

END_KS_UNDER_20 = ["Showstopper!"]
END_KS_20_50 = ["Not on my watch!", "Finally!", "Our lord and saviour!", "Hero!", "A real human being!", "It ends now!",
                "Guardian angel!", "*tips fedora*!", "LOL!", "Terminated!"]
END_KS_OVER_50 = ["DEICIDE!", "REGICIDE!", "God joined."]

MSG_SUICIDE = ["The guilt was too much!", "Whoops!", "Oopsie-Doopsie!", "Huh... what?", "Bruh..."]


def ks_announce_info(connection):
    connection.send_chat("This server is running %s %s created by %s!" % (NAME, VERSION, AUTHOR))


def ksboard(connection):
    proto = connection.protocol

    if len(proto.high_record_all) == 0:
        connection.send_chat("No records yet.")
        return

    ord_ = sorted(proto.high_record_all.items(), key=lambda d: d[1], reverse=True)
    i = 1
    t = []
    for _id, r in ord_:
        t.append(KSBOARD_PRINT_FORMAT % (i, proto.players[_id].name, r))
        if i == 3:
            break
        i += 1
    for i in reversed(t):
        connection.send_chat(i)
    connection.send_chat("Killstreak Records:")


@admin
def global_ksboard(connection):
    proto = connection.protocol

    if len(proto.high_record_all) == 0:
        proto.send_chat("No records yet.")
        return

    ord_ = sorted(proto.high_record_all.items(), key=lambda d: d[1], reverse=True)
    i = 1
    t = []
    for _id, r in ord_:
        t.append(KSBOARD_PRINT_FORMAT % (i, proto.players[_id].name, r))
        if i == 3:
            break
        i += 1
    for i in reversed(t):
        proto.send_chat(i)
    proto.send_chat("Killstreak Records:")
    proto.irc_say("ks_announce: global ksboard broadcasted by %s" % connection.name)


@admin
def irc_ksboard(connection):
    proto = connection.protocol

    if len(proto.high_record_all) == 0:
        proto.irc_say("No records yet.")
        return

    ord_ = sorted(proto.high_record_all.items(), key=lambda d: d[1], reverse=True)
    i = 1
    t = []
    proto.send_chat("Killstreak Records:")
    for _id, r in ord_:
        t.append(KSBOARD_PRINT_FORMAT % (i, proto.players[_id].name, r))
        if i == 5:
            break
        i += 1
    for i in t:
        proto.irc_say(i)

    proto.irc_say("ks_announce: IRC ksboard broadcasted by %s" % connection.name)


@admin
def show_hks_info(connection):

    proto = connection.protocol
    msg = "%s ABS_: %d ID_ABS: %d" % (str(proto.high_record_all), proto.absolute_high_record,
                                      proto.abs_r_id)
    # msg = str(connection.protocol.high_record_all) + "ABS_:" + connection.protocol.absolute_high_record + \
    #    "ID_ABS:" + connection.protocol.abs_r_id
    pre = "\nks_announce: HKS_INFO request (%s)\n" % connection.name
    return pre + msg


@admin
def clear_killstreak_records(connection):
    connection.protocol.high_record_all = {}
    connection.protocol.absolute_high_record = 0
    connection.protocol.abs_r_id = 0
    for p in connection.protocol.players.values():
        p.streak, p.high_record = 0, 0
    connection.protocol.send_chat("Killstreak records have been cleared.")
    connection.protocol.irc_say("ks_announce: %s has resetted killstreak records." % connection.name)


@admin
def set_announce_rate(connection, nk=None):
    if nk is not None:
        global N_KILLS_ANNOUNCEMENT
        N_KILLS_ANNOUNCEMENT = int(nk)
        connection.protocol.irc_say("ks_announce: %s set killstreak announce rate to %d." % (connection.name,
                                                                                             N_KILLS_ANNOUNCEMENT))
        return "Killstreaks will now be announced every %d kills." % N_KILLS_ANNOUNCEMENT
    else:
        global N_KILLS_ANNOUNCEMENT
        return "Killstreaks are currently announced every %d kills." % N_KILLS_ANNOUNCEMENT


@admin
def set_announce_minimum(connection, nk=None):
    if nk is not None:
        global N_KILLS_MINIMUM
        N_KILLS_MINIMUM = int(nk)
        connection.protocol.irc_say("ks_announce: %s set killstreak announce minimum kills to %d." % (connection.name,
                                                                                                      N_KILLS_MINIMUM))
        return "Killstreaks will now be announced after %d kills." % N_KILLS_MINIMUM
    else:
        global N_KILLS_MINIMUM
        return "Killstreaks are currently announced after %d kills." % N_KILLS_MINIMUM


add(ks_announce_info)
add(show_hks_info)
add(clear_killstreak_records)
add(ksboard)
add(global_ksboard)
add(set_announce_rate)
add(set_announce_minimum)
add(irc_ksboard)


def apply_script(protocol, connection, config):
    global N_KILLS_ANNOUNCEMENT
    global N_KILLS_MINIMUM

    N_KILLS_ANNOUNCEMENT = config.get("ks_announce_rate", N_KILLS_ANNOUNCEMENT)
    N_KILLS_MINIMUM = config.get("ks_announce_minimum", N_KILLS_MINIMUM)

    connection.high_record = 0
    protocol.high_record_all = dict()
    protocol.absolute_high_record = 0
    protocol.abs_r_id = 0

    class KSConnection(connection):

        streak_msg = "...?"
        streak_name = "killstreak"
        streak_msg_suicide = "...?"
        end_streak_msg = "...!"

        def on_disconnect(self):
            if self.player_id in protocol.high_record_all:
                del self.protocol.high_record_all[self.player_id]
            self.recalc_max()
            return connection.on_disconnect(self)

        def recalc_max(self):
            tmax, tid = 0, 0
            for _id, r in self.protocol.high_record_all.iteritems():
                if r > tmax:
                    tmax = r
                    tid = _id

            self.protocol.absolute_high_record = tmax
            self.protocol.abs_r_id = tid

        def add_score(self, score):

            if self.streak > self.high_record:
                self.high_record = self.streak
                self.protocol.high_record_all[self.player_id] = self.high_record

                self.recalc_max()

            if self.streak % N_KILLS_ANNOUNCEMENT == 0 and self.streak >= N_KILLS_MINIMUM:

                if self.streak < 20:
                    self.streak_msg = random.choice(MSG_KILLS_UNDER_20)
                    self.streak_name = random.choice(NAME_KS_UNDER_20)

                elif 20 <= self.streak < 50:
                    self.streak_msg = random.choice(MSG_KILLS_20_50)
                    self.streak_name = random.choice(NAME_KS_20_50)

                elif 50 <= self.streak:
                    if self.streak == 50:
                        self.protocol.send_chat("%s IS DESTROYING THE ENEMY TEAM!" % self.name)
                    self.streak_msg = random.choice(MSG_KILLS_OVER_50)
                    self.streak_name = random.choice(NAME_KS_OVER_50)

                self.protocol.send_chat("%s %s is on a %d kill %s!" % (self.streak_msg, self.name, self.streak,
                                                                       self.streak_name))
                self.protocol.irc_say("player %s (#%d) is on a %d killstreak." % (self.name, self.player_id,
                                                                                  self.streak))
            return connection.add_score(self, score)

        def on_kill(self, by, type_, grenade):

            if self.streak >= N_KILLS_MINIMUM:
                if by is not None and by.player_id != self.player_id:

                    if self.streak < 20:
                        self.end_streak_msg = random.choice(END_KS_UNDER_20)
                    elif 20 <= self.streak < 50:
                        self.end_streak_msg = random.choice(END_KS_20_50)
                    elif 50 <= self.streak:
                        self.end_streak_msg = random.choice(END_KS_OVER_50)

                    self.protocol.send_chat("%s %s ended %s's %d kill %s!" % (self.end_streak_msg, by.name,
                                                                              self.name, self.streak, self.streak_name))
                    self.protocol.irc_say("%s ended %s's %d kill killstreak." % (by.name, self.name,
                                                                                 self.streak))
                    by.send_chat("You have been healed and resupplied!")
                    by.refill()
                elif by is None or (by.player_id == self.player_id and grenade):
                    self.streak_msg_suicide = random.choice(MSG_SUICIDE)
                    self.protocol.send_chat("%s %s ended his own %d kill %s!" % (self.streak_msg_suicide,
                                                                                 self.name, self.streak,
                                                                                 self.streak_name))
                    self.protocol.irc_say("%s ended his own %d kill killstreak" % (self.name, self.streak))

                if self.streak >= self.protocol.absolute_high_record:
                    self.protocol.send_chat("New killstreak record in this match! %s: %d kills in a row." %
                                            (self.name, self.streak))
                    self.protocol.irc_say("New killstreak record in this match. %s with %d kills in a row."
                                          % (self.name, self.streak))

            return connection.on_kill(self, by, type_, grenade)

        def on_login(self, name):
            ks_announce_info(self)
            return connection.on_login(self, name)

    class KSProtocol(protocol):

        def __init__(self, *args, **kwargs):
            protocol.__init__(self, *args, **kwargs)

            start_msg = "%s: running version %s by %s" % (NAME, VERSION, AUTHOR)
            print start_msg

        def global_ksboard_proto(self):

            print "ks_announce: ksboard broadcasted to all players."
            self.irc_say("ks_announce: ksboard broadcasted to all players.")

            proto = self

            if len(proto.high_record_all) == 0:
                proto.send_chat("No records yet.")
                return

            ord_ = sorted(proto.high_record_all.items(), key=lambda d: d[1], reverse=True)
            i = 1
            t = []
            for _id, r in ord_:
                t.append(KSBOARD_PRINT_FORMAT % (i, proto.players[_id].name, r))
                if i == 3:
                    break
                i += 1
            for i in reversed(t):
                proto.send_chat(i)
            proto.send_chat("Killstreak Records:")

        def clear_killstreak_records_proto(self):
            print "ks_announce: clearing server killstreak records."
            self.irc_say("ks_announce: clearing server killstreak records.")
            protocol.high_record_all = {}
            protocol.absolute_high_record = 0
            protocol.abs_r_id = 0
            for p in self.players.values():
                p.streak, p.high_record = 0, 0
            print "ks_announce: done."
            self.irc_say("ks_announce: done")

        def advance_rotation(self, msg=None):
            self.global_ksboard_proto()
            return protocol.advance_rotation(self, msg)

        def on_map_change(self, _map):
            self.clear_killstreak_records_proto()
            return protocol.on_map_change(self, _map)

    return KSProtocol, KSConnection
