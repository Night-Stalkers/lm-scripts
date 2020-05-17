"""
Adds the ability to fire rockets, earned by getting killstreaks.
The number of required kills to unlock and the uses per killstreak
can be customized by setting "rpg_killstreak" and "rpg_increase" to
a number in config.txt. If no setting is found in config.txt, then
the following default values will be used:

rpg_killstreak = 8
rpg_increase = 3

Admins can also modify these values ingame by using /set_rpg_killstreak
and /set_rpg_increase followed by a number greater than zero. If these
commands are run without an argument, then it will display the current
set values.

This script depends on easyaos.py

Original Author: yuyasato (yuya_aos)
Modified by: Hourai(Yui)

Changelog:

    1.3.0:
        * Ported to python3 for Pique support

    1.2.0:
        * Added timed cooldown.
        * Improved some of the messages.

    1.1.3:
        * Added a check to avoid a crash when certain other scripts are used.

    1.1.2:
        * Admin commands now work from IRC.
        * Added original author info.

"""

import sys
sys.path.append('~/.config/piqueserver/scripts/')
from easyaos import *
from twisted.internet.reactor import callLater, seconds
from pyspades.common import Vertex3
from pyspades.world import Grenade
from pyspades.contained import GrenadePacket
import random
from pyspades.constants import *
from piqueserver.commands import admin, command

grenade_packet = GrenadePacket()

VERSION = "1.2.0"

VTradius = 1
vel = 2.0
FF = True
SMOKE = (230, 200, 200)
STREAK_REQ = 8
RPG_ADD_USES = 3
RPG_COOLDOWN_LIMIT = 6 # shots before cooldown
RPG_COOLDOWN_TIME = 1 # minutes


@command('give_rpg', admin_only = True)
def give_rpg(connection, num=None):
    global RPG_ADD_USES
    if num is None:
        num = RPG_ADD_USES
    connection.RPG_uses_remaining += num
    connection.is_on_cooldown = False
    connection.broadcast_chat("You can use RPG now. %d rockets left" % connection.RPG_uses_remaining)

@command('set_rpg_killstreak', admin_only = True)
def set_rpg_killstreak(connection, nkills=None):
    global STREAK_REQ
    if nkills:
        nkills = int(nkills)
        if nkills > 0:
            STREAK_REQ = nkills
            return "RPG killstreak set to %d." % STREAK_REQ
        else:
            return "RPG killstreak can't be zero or less!"
    else:
        return "RPG killstreak is currently set to %d." % STREAK_REQ


@command('set_rpg_increase', admin_only = True)
def set_rpg_increase(connection, ninc=None):
    global RPG_ADD_USES
    if ninc:
        ninc = int(ninc)
        if ninc > 0:
            RPG_ADD_USES = ninc
            return "RPG rockets earned per killstreak set to %d." % RPG_ADD_USES
        else:
            return "RPG rockets earned per killstreak can't be zero or less!"
    else:
        return "RPG rockets earned per killstreak is currently %d." % RPG_ADD_USES


@command('rpg_info')
def rpg_info(connection):
    connection.send_chat("This server is running RPG script %s by yuyasato (yuya_aos), modified by Hourai (Yui)!" % VERSION)
    connection.send_chat("Get %d kills in a row to get %d RPG rockets!" % (STREAK_REQ, RPG_ADD_USES))



def apply_script(protocol, connection, config):
    global RPG_COOLDOWN_TIME
    global RPG_COOLDOWN_LIMIT
    global STREAK_REQ
    global RPG_ADD_USES

    STREAK_REQ = int(config.get("rpg_killstreak", STREAK_REQ))
    RPG_ADD_USES = int(config.get("rpg_increase", RPG_ADD_USES))
    RPG_COOLDOWN_TIME = int(config.get("rpg_cooldown_time", RPG_COOLDOWN_TIME))
    RPG_COOLDOWN_LIMIT = int(config.get("rpg_cooldown_limit", RPG_COOLDOWN_LIMIT))

    class RPGConnection(connection):
        trace_0 = (0, 0, 0)
        trace_1 = (0, 0, 0)
        trace_2 = (-1, -1, -1)
        RPG_uses_remaining = 0
        is_on_cooldown = False
        RPG_uses_on_this_life = 0

        def _undo_cooldown(self):
            if self.is_on_cooldown == True:
                self.is_on_cooldown = False
                r = "rockets" if self.RPG_uses_remaining > 1 else "rocket"
                self.send_chat("Your RPG is no longer on COOLDOWN! %s left: %d" % (r, self.RPG_uses_remaining))
                msg = "%s (#%d) is no longer in RPG COOLDOWN." % (self.name, self.player_id)
                print(msg)
                self.protocol.irc_say(msg)

        def on_login(self, name):
            rpg_info(self)
            return connection.on_login(self, name)

        def has_remaining_rpg(self):
            if self.RPG_uses_remaining > 0:
                return True
            else:
                return False

        def on_spawn(self, pos):
            self.RPG_uses_remaining = 0
            self.RPG_uses_on_this_life = 0
            self.is_on_cooldown = False
            return connection.on_spawn(self, pos)

        def add_score(self, score):
            if self.streak % STREAK_REQ == 0 and self.streak > 0:
                self.RPG_uses_remaining += RPG_ADD_USES
                self.refill()
                if not self.is_on_cooldown:
                    self.send_chat("You can use RPG now. %d rockets left" %
                                   self.RPG_uses_remaining)
                    self.send_chat("Hold grenade and hold both left & right mouse buttons for 3 seconds.")
                else:
                    self.send_chat("You get RPG ammo but your RPG is on COOLDOWN! %d rockets left." % self.RPG_uses_remaining)

                msg = "%s is on a %d killstreak and gets RPG ammo!" % (self.name, self.streak)
                self.protocol.broadcast_chat(msg)
                self.protocol.irc_say(msg)
            return connection.add_score(self, score)

        def rpg(self, xxx_todo_changeme, xxx_todo_changeme1):
            (x, y, z) = xxx_todo_changeme
            (vx, vy, vz) = xxx_todo_changeme1
            if self.world_object is None:
                return
            if self.trace_2[0] >= 0:
                easyremove(self, self.trace_2)
            x += vx
            y += vy
            z += vz
            VTfuse = False
            if FF:
                for player in list(self.protocol.players.values()):
                    xa, ya, za = player.get_location()
                    xr, yr, zr = xa - x, ya - y, za - z
                    if xr ** 2 + yr ** 2 + zr ** 2 <= VTradius ** 2 and not player == self:
                        VTfuse = True
                        break
            else:
                for player in self.team.other.get_players():
                    xa, ya, za = player.get_location()
                    xr, yr, zr = xa - x, ya - y, za - z
                    if xr ** 2 + yr ** 2 + zr ** 2 <= VTradius ** 2 and not player == self:
                        VTfuse = True
                        break

            if self.protocol.map.get_solid(x + vx, y + vy,
                                           z + vz) or x < 2 or x > 509 or y < 2 or y > 509 or z < 1 or z > 63 or VTfuse:
                if self.trace_2[0] >= 0:
                    easyremove(self, self.trace_2)
                easyremove(self, self.trace_1)
                easyremove(self, self.trace_0)
                self.trace_2 = (-1, -1, -1)
                self.high_explosive(x, y, z)

            else:
                callLater(0.03 / vel, self.rpg, (x, y, z), (vx, vy, vz))
                self.trace_2 = self.trace_1
                self.trace_1 = self.trace_0
                self.trace_0 = (x, y, z)
                easyblock(self, self.trace_0, SMOKE)

        def high_explosive(self, x, y, z):
            count = 0
            grenade = self.protocol.world.create_object(Grenade, count, Vertex3(x, y, z), None, Vertex3(0, 0, 0),
                                                        self.grenade_exploded)
            grenade_packet.value = count
            grenade_packet.player_id = self.player_id
            grenade_packet.position = (x, y, z)
            grenade_packet.velocity = (0, 0, 0.0)
            self.protocol.broadcast_contained(grenade_packet)
            while count < 50:
                callLater(count / 10000.0, self.makegre, x, y, z, count < 15)
                count += 1

        def makegre(self, x, y, z, exp):
            sigma = 2.0
            (xg, yg, zg) = (random.gauss(0, sigma), random.gauss(0, sigma), random.gauss(0, sigma))
            xp, yp, zp = x + xg, y + yg, z + zg
            grenade = self.protocol.world.create_object(Grenade, 0, Vertex3(xp, yp, zp), None, Vertex3(0, 0, 0),
                                                        self.grenade_exploded)
            if exp:
                grenade_packet.value = 0
                grenade_packet.player_id = self.player_id
                grenade_packet.position = (xp, yp, zp)
                grenade_packet.velocity = (0, 0, 0)
                self.protocol.broadcast_contained(grenade_packet)

        def on_grenade(self, time_left):
            if self.world_object.primary_fire and self.world_object.secondary_fire:
                if self.has_remaining_rpg():
                    if not self.is_on_cooldown and self.trace_2[0] < 0:
                        x, y, z = self.world_object.position.get()
                        vx, vy, vz = self.world_object.orientation.get()
                        if z + vz >= 1:
                            self.rpg((x + vx * 2, y + vy * 2, z + vz * 2), (vx, vy, vz))
                            self.RPG_uses_remaining -= 1
                            self.RPG_uses_on_this_life += 1
                            r = "rockets" if self.RPG_uses_remaining > 1 else "rocket"
                            self.send_chat("%d RPG %s left." % (self.RPG_uses_remaining, r))
                            if (self.RPG_uses_on_this_life % RPG_COOLDOWN_LIMIT == 0):
                                self.is_on_cooldown = True
                                m = "minutes" if RPG_COOLDOWN_TIME > 1 else "minute"
                                self.send_chat("Your RPG is now on COOLDOWN for %d %s!" % (RPG_COOLDOWN_TIME, m))
                                msg = "%s (#%d) enters RPG COOLDOWN." % (self.name, self.player_id)
                                print(msg)
                                self.protocol.irc_say(msg)
                                callLater(RPG_COOLDOWN_TIME*60, self._undo_cooldown)
                        else:
                            self.send_chat("Too high to shot RPG!")
                    elif self.trace_2[0] > 0:
                        self.send_chat("Wait a bit more before firing rockets!")
                    else:
                        self.send_chat("Your RPG is in COOLDOWN!")
                    return False
                else:
                    r = "rockets" if self.RPG_uses_remaining > 1 else "rocket"
                    self.send_chat("no RPG %s left." % r)
                    return False
            return connection.on_grenade(self, time_left)

        def on_secondary_fire_set(self, secondary):
            if secondary:
                if self.tool == GRENADE_TOOL and self.world_object.primary_fire:
                    if self.has_remaining_rpg():
                        r = "rockets" if self.RPG_uses_remaining > 1 else "rocket"
                        self.send_chat("To fire RPG, HOLD both right&left click! %s left: %d" %
                                       (r, self.RPG_uses_remaining))
                    else:
                        self.send_chat("you don't have RPG")
            return connection.on_secondary_fire_set(self, secondary)

    return protocol, RPGConnection
