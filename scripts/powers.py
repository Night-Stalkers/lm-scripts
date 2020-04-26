"""
Changelog

    1.1.0:
        * Reworked Deadly Dice.
        * Reworked Teleportation (Now uses SNEAK + GET COLOR BUTTON, V + E).
        * /checkpowers can now accept ids with #.
        * Added on teleport IRC message.

    1.0.2:
        * Re-enabled regeneration.
    
    1.0.1:
        * /checkpowers can now be used by every player.

    1.0.0:
        * intelrpg2.py -> powers.py
        * Now using semantic versioning.
        * New command /checkpowers id
"""

# Script by Danke!
# Edits by iCherry, Hourai (Yui)
# Bugfix by lecom ;)
from pyspades.server import grenade_packet
from pyspades.world import Grenade
from pyspades.common import Vertex3
from pyspades.collision import distance_3d_vector
from pyspades.server import block_action
from pyspades.constants import *
from commands import add, admin
import random
import commands
import buildbox
import cbc

ARMOR, DEADLY_DICE, TEAMMATE, TELEP, REGEN, POISON, NADEPL, ERECTOR =  xrange(8)
TP_RANGE = [0, 64, 128, 256]

def clearpowers(connection):
    connection.intel_clear()
    return "You've sucessfully lost all your powers!"
add(clearpowers)

def checkpowers(connection, player_id=None):
    proto = connection.protocol
    if player_id[0] == '#':
        player_id = player_id[1:]
    player_id = int(player_id)
    if player_id is None:
        return "No player ID specified."
    else:
        if player_id in proto.players:
            message = ("Player \"%s\" has " % proto.players[player_id].name) + proto.players[player_id].explain_power()
            return message
        else:
            return "Player not found."

add(checkpowers)

def power(connection, value = 8):
    value = int(value)
    if value > 7:
        connection.send_chat("Type /current to see current powers")
        connection.send_chat("Type /powerpref for info on setting prefered power")
        connection.send_chat('2 - Good Teammate     5 - Poison Bullets     6 - Nadesplosion')
        connection.send_chat('1 - Deadly Dice       4 - Regeneration       7 - Erector')
        connection.send_chat('0 - Armor             3 - Teleportation')
        connection.send_chat("Type /power # to read about a power:")
    elif value == ARMOR:
        connection.send_chat("Level 3 - Take 1/8 damage from body-shots and grenades.")
        connection.send_chat("Level 2 - Take 1/4 damage from body-shots and grenades.")
        connection.send_chat("Level 1 - Take 1/2 damage from body-shots and grenades.")
        connection.send_chat("The power of Armor:")
    elif value == DEADLY_DICE:
        connection.send_chat("Level 3 - A 20% chance to instantly kill any target you hit.")
        connection.send_chat("Level 2 - A 15% chance to instantly kill any target you hit.")
        connection.send_chat("Level 1 - A 10% chance to instantly kill any target you hit.")
        connection.send_chat("The power of Deadly Dice:")
    elif value == TEAMMATE:
        connection.send_chat("Good Teammate also cures poison when healing!")
        connection.send_chat("Level 3 - Both levels apply (50 hp total for headshot)")
        connection.send_chat("Level 2 - Every kill you make will heal you and nearby teammates 30 hp.")
        connection.send_chat("Level 1 - Every headshot you make will heal you and nearby teammates 20 hp.")
        connection.send_chat("The power of the Good Teammate:")
    elif value == TELEP:
        connection.send_chat("Level 3 - Range increased to %d and uses increased to 3." % TP_RANGE[3])
        connection.send_chat("Level 2 - Range increased to %d." % TP_RANGE[2])
        connection.send_chat("Level 1 - Press V + E to teleport where you are aiming, maximum range of %d." % TP_RANGE[1])
        connection.send_chat("The power of Teleportation (Toggle with /toggle_teleport):")
    elif value == REGEN:
        connection.send_chat("Regen does not work while poisoned!")
        connection.send_chat("Level 3 - Regenerate 10 HP per second.")
        connection.send_chat("Level 2 - Regenerate 5 HP per second.")
        connection.send_chat("Level 1 - Regenerate 2 HP per second.")
        connection.send_chat("The power of Regeneration:")
    elif value == POISON:
        connection.send_chat("Level 3 - Your bullets do 3 damage per second after hitting")
        connection.send_chat("Level 2 - Your bullets do 2 damage per second after hitting")
        connection.send_chat("Level 1 - Your bullets do 1 damage per second after hitting")
        connection.send_chat("The power of Poison Bullets:")
    elif value == NADEPL:
        connection.send_chat("Level 3 - A 50% chance headshots cause an explosion.")
        connection.send_chat("Level 2 - A 25% chance headshots cause an explosion.")
        connection.send_chat("Level 1 - A 10% chance headshots cause an explosion.")
        connection.send_chat("The power of Nadesplosion:")
    elif value == ERECTOR:
        connection.send_chat("Level 3 - Every block place makes a 6 high pillar (4 uses)")
        connection.send_chat("Level 2 - Every block place makes a 4 high pillar (8 uses)")
        connection.send_chat("Level 1 - Every block place makes a 2 high pillar (10 uses)")
        connection.send_chat("The power of Erector (Toggle with /toggle_erector):")
add(power)

@admin
def cheatpower(connection):
    try:
        connection.intel_upgrade()
        connection.send_chat("You have %s" % connection.explain_power())
    except TypeError as e:
        print e
add(cheatpower)

def cheaterectorsBIGKOK(connection):
    connection.erector_uses = connection.erector_uses + 10
add(cheaterectorsBIGKOK)

def toggle_teleport(connection):
    connection.Ttoggle_teleport = not connection.Ttoggle_teleport
    connection.send_chat("Toggled teleport power to %r" % connection.Ttoggle_teleport)
add(toggle_teleport)

def toggle_erector(connection):
    connection.Ttoggle_erector = not connection.Ttoggle_erector
    connection.send_chat("Toggled erector power to %r" % connection.Ttoggle_erector)
add(toggle_erector)

def powerpref(connection, value = 8):
    value = int(value)
    if value > 7:
        connection.send_chat('2 - Good Teammate     5 - Poison Bullets     6 - Nadesplosion')
        connection.send_chat('1 - Deadly Dice       4 - Regeneration       7 - Erector')
        connection.send_chat('0 - Armor             3 - Teleportation')
        connection.send_chat("Type /powerpref # to set a preference")
        connection.send_chat("Preference is ignored on your first intel grab.")
    elif value <= 8:
        connection.intel_power_pref = value
        connection.send_chat("Preference saved.")
add(powerpref)

def current(connection):
    connection.send_chat("Type /clearpowers to remove all your current powers")
    message = "You have " + connection.explain_power()
    return message
add(current)

def apply_script(protocol, connection, config):
    class IntelPowerConnection(connection):

        def __init__(self, *args, **kwargs):
            self.intel_p_lvl = [0,0,0,0,0,0,0,0]
            connection.__init__(self, *args, **kwargs)

        def on_login(self, name):
            self.intel_clear()
            self.headshot_splode = False
            self.power_kills = 0
            self.erector_uses = 0
            self.Ttoggle_erector = True
            self.Ttoggle_teleport = True
            return connection.on_login(self, name)

        def explain_temp(self):
            message = ""
            message = ("Armor level %s" % self.intel_p_lvl[0]) if self.intel_temp == 0 else message
            message = ("Deadly Dice level %s" % self.intel_p_lvl[1]) if self.intel_temp == 1 else message
            message = ("Good Teammate level %s" % self.intel_p_lvl[2]) if self.intel_temp == 2 else message
            message = ("Teleportation level %s" % self.intel_p_lvl[3]) if self.intel_temp == 3 else message
            message = ("Regeneration level %s" % self.intel_p_lvl[4]) if self.intel_temp == 4 else message
            message = ("Poison Bullets level %s" % self.intel_p_lvl[5]) if self.intel_temp == 5 else message
            message = ("Nadesplosion level %s" % self.intel_p_lvl[6]) if self.intel_temp == 6 else message
            message = ("Erector level %s" % self.intel_p_lvl[7]) if self.intel_temp == 7 else message
            return(message)

        def explain_power(self):
            message = "powers: "
            message += ("Armor level %s, " % self.intel_p_lvl[0]) if self.intel_p_lvl[0] > 0 else ""
            message += ("Deadly Dice level %s, " % self.intel_p_lvl[1]) if self.intel_p_lvl[1] > 0 else ""
            message += ("Good Teammate level %s, " % self.intel_p_lvl[2]) if self.intel_p_lvl[2] > 0 else ""
            message += ("Teleportation level %s, " % self.intel_p_lvl[3]) if self.intel_p_lvl[3] > 0 else ""
            message += ("Regeneration level %s, " % self.intel_p_lvl[4]) if self.intel_p_lvl[4] > 0 else ""
            message += ("Poison Bullets level %s, " % self.intel_p_lvl[5]) if self.intel_p_lvl[5] > 0 else ""
            message += ("Nadesplosion level %s, " % self.intel_p_lvl[6]) if self.intel_p_lvl[6] > 0 else ""
            message += ("Erector level %s, " % self.intel_p_lvl[7]) if self.intel_p_lvl[7] > 0 else ""
            if message == "powers: ":
                message = "no powers"
            else:
                message = message[:-2]
            return(message)

        def nadesplode(self, hit_player):
            self.protocol.world.create_object(Grenade, 0.0, hit_player.world_object.position, None, Vertex3(), self.nadepl_exploded)
            grenade_packet.value = 0.1
            grenade_packet.player_id = self.player_id
            grenade_packet.position = (hit_player.world_object.position.x, hit_player.world_object.position.y, hit_player.world_object.position.z)
            grenade_packet.velocity = (0.0, 0.0, 0.0)
            self.protocol.send_contained(grenade_packet)

        def nadepl_exploded(self, grenade):
            self.headshot_splode = True
            connection.grenade_exploded(self, grenade)

        def on_hit(self, hit_amount, hit_player, type, grenade):
            value = connection.on_hit(self, hit_amount, hit_player, type, grenade)
            if value is not None or hit_player.team == self.team:
                return value
            value = hit_amount
            if hit_player.intel_p_lvl[0] > 0:
                if type != HEADSHOT_KILL and type != MELEE_KILL:
                    if hit_player.intel_p_lvl[0] == 3:
                        value *= .125
                    if hit_player.intel_p_lvl[0] == 2:
                        value *= .25
                    if hit_player.intel_p_lvl[0] == 1:
                        value *= .50
                else:
                    self.send_chat("%s is wearing armor! Aim for the head!" % hit_player.name )
            if self.intel_p_lvl[1] > 0:
                dice_roll = random.randint(1, 100)
                if dice_roll <= 20 and self.intel_p_lvl[1] == 3:
                    value = 100
                    hit_player.send_chat("You have been instakilled by %s !" % self.name)
                    self.send_chat("Alea iacta est... You have rolled the dice of life and instakilled %s!" % hit_player.name)
                if dice_roll <= 15 and self.intel_p_lvl[1] == 2:
                    value = 100
                    hit_player.send_chat("You have been instakilled by %s !" % self.name)
                    self.send_chat("Alea iacta est... You have rolled the dice of life and instakilled %s!" % hit_player.name)
                if dice_roll <= 10 and self.intel_p_lvl[1] == 1:
                    value = 100
                    hit_player.send_chat("You have been instakilled by %s !" % self.name)
                    self.send_chat("Alea iacta est... You have rolled the dice of life and instakilled %s!" % hit_player.name)
            if self.intel_p_lvl[5] > 0:
                hit_player.send_chat("You have been poisoned by %s ! Get to the tent to cure it!" % self.name)
                hit_player.poisoner = self
                hit_player.poison = self.intel_p_lvl[5]

            return value

        def on_kill(self, killer, type, grenade):
            if killer != self and killer is not None:
                self.send_chat("Type /power for more info on Intel Powers")
                self.send_chat("You were killed by %s who had %s" % (killer.name, killer.explain_power()))
                if killer.intel_p_lvl[2] > 0:
                    healcount = 0
                    if killer.intel_p_lvl[2] != 2 and type == HEADSHOT_KILL:
                        healcount += 1
                        killer.heal_team(10)
                    if killer.intel_p_lvl[2] > 1:
                        healcount += 1
                        killer.heal_team(30)
                    if healcount > 0:
                        killer.send_chat("Your kill has healed you and your teammates!")
                if killer.intel_p_lvl[6] > 0 and type == HEADSHOT_KILL:
                    dice_roll = random.randint(1, 100)
                    if dice_roll <= 50 and killer.intel_p_lvl[6] == 3:
                        killer.nadesplode(self)
                    if dice_roll <= 25 and killer.intel_p_lvl[6] == 2:
                        killer.nadesplode(self)
                    if dice_roll <= 10 and killer.intel_p_lvl[6] == 1:
                        killer.nadesplode(self)
                killer.power_kills = killer.power_kills + 1
                if killer.power_kills == 10:
                    killer.power_kills = 0
                    killer.send_chat("You have reached 10 kills, you get a power-up!")
                    killer.intel_upgrade()
            return connection.on_kill(self, killer, type, grenade)

        def on_spawn(self, pos):
            if self.intel_p_lvl[3] == 3:
                self.teleport_uses = 3
            else:
                self.teleport_uses = 2

            if self.intel_p_lvl[7] == 1:
                self.erector_uses = 10
            elif self.intel_p_lvl[7] == 2:
                self.erector_uses = 8
            else:
                self.erector_uses = 4

            self.power_kills = 0
            self.poisoner = None
            self.poison = 0
            self.intel_downgrade()
            self.send_chat("Type /power for more information!")
            self.send_chat("You have %s" % self.explain_power())
            return connection.on_spawn(self, pos)

        def heal_team(self, value):
            for player in self.team.get_players():
                if player is None or player.hp <= 0:
                    return
                dist = distance_3d_vector(self.world_object.position, player.world_object.position)
                if dist <= 16.0 or player == self:
                    player.poison = 0
                    player.poisoner = None
                    player.set_hp(player.hp + value, type = FALL_KILL)
                    if player != self:
                        player.send_chat("You have been healed by %s " % self.name)

        def intel_every_second(self):
            if self is None or self.hp <= 0:
                return
            self.headshot_splode = False
            if self.poison > 0 and self.poisoner is not None and self.poisoner.world_object is not None:
                self.hit(self.poison, self.poisoner)

            elif self.intel_p_lvl[4] > 0:
                if self.intel_p_lvl[4] == 3:
                    self.set_hp(self.hp + 10, type = FALL_KILL)
                if self.intel_p_lvl[4] == 2:
                    self.set_hp(self.hp + 5, type = FALL_KILL)
                if self.intel_p_lvl[4] == 1:
                    self.set_hp(self.hp + 2, type = FALL_KILL)

        def on_refill(self):
            if self.intel_p_lvl[3] == 3:
                self.send_chat("3 teleport uses refilled.")
                self.teleport_uses = 3
            elif self.intel_p_lvl[3] == 2:
                self.send_chat("2 teleport uses refilled.")
                self.teleport_uses = 2
            if self.poison > 0:
                self.send_chat("You have been cured of the poison!")
                self.poison = 0
                self.poisoner = None
            if self.intel_p_lvl[7] == 1:
                self.erector_uses = 10
                self.send_chat("You have 10 Erector uses (2 high)")
            elif self.intel_p_lvl[7] == 2:
                self.erector_uses = 8
                self.send_chat("You have 8 Erector uses (4 high)")
            elif self.intel_p_lvl[7] == 3:
                self.erector_uses = 4
                self.send_chat("You have 4 Erector uses (6 high)")
            return connection.on_refill(self)

        def on_flag_take(self):
            if connection.on_flag_take(self) is not False:
                self.intel_temporary()
                self.send_chat("Bring intel to your base to keep it!")
                self.send_chat("You have temporarily gained power: %s" % self.explain_temp())

        def on_color_set(self, color):
            try:
                if self.intel_p_lvl[3] and self.intel_p_lvl[3] >= 1:
                    if self.world_object.sneak:
                        ray_dist = TP_RANGE[self.intel_p_lvl[3]]
                        location = self.world_object.cast_ray(ray_dist)
                        if location:
                            x, y, z = location
                            self.do_teleport(x, y, z)
                        else:
                            self.send_chat("Teleport out of range!")
            except AttributeError as e:
                # This shouldn't be reached under normal conditions
                print "self.intel_p_lvl not found for player #%d, player is a bot perhaps?" % self.player_id
                print "If you see this message, please report it lol"
                self.intel_clear()
            return connection.on_color_set(self, color)

        def on_flag_capture(self):
            if connection.on_flag_capture(self) is not False:
                self.intel_temp = False
                self.send_chat("Type /power for more information!")
                self.send_chat("You have %s" % self.explain_power())
            connection.on_flag_capture(self)

        def do_teleport(self, x, y, z):
            if (self.Ttoggle_teleport):
                if self != self.team.other.flag.player:
                    if self.teleport_uses == 0:
                        self.send_chat("You've run out of teleport uses!")
                    if self.teleport_uses > 0:
                        self.teleport_uses -= 1
                        self.send_chat("%s teleport uses remaining." % self.teleport_uses)
                        self.clear_tele_area(x, y, z)
                        self.set_location_safe((x, y, z-1))
                        msg = "%s (#%d) used Teleport!" % (self.name, self.player_id)
                        self.protocol.irc_say(msg)
                        print msg
                else:
                    self.send_chat("You can't teleport while holding intel!")
            return

        def sign(self, x):
            return (x > 0) - (x < 0)

        def erect(self, x, y, z, height):
            z2 = min(61, max(0, z - height + self.sign(height)))
            buildbox.build_filled(self.protocol, x, y, z, x, y, z2, self.color, self.god, self.god_build)

        def on_block_build(self, x, y ,z):
            if (self.Ttoggle_erector):
                if self.intel_p_lvl[7] != 0:
                    if self.erector_uses > 0:
                        if self.intel_p_lvl[7] == 1:
                            self.erect(x, y, z, 2)
                        elif self.intel_p_lvl[7] == 2:
                            self.erect(x, y, z, 4)
                        elif self.intel_p_lvl[7] == 3:
                            self.erect(x, y, z, 6)
                        self.erector_uses = self.erector_uses-1
                        if self.erector_uses == 0:
                            self.send_chat("You've run out of erector uses!")
            return connection.on_block_build(self, x, y, z)

        def clear_tele_area(self, x, y, z):
            return
            map = self.protocol.map
            for nade_x in xrange(x - 1, x + 2):
                for nade_y in xrange(y - 1, y + 2):
                    for nade_z in xrange(z - 1, z + 2):
                        if nade_x > 0 and nade_x < 512 and nade_y > 0 and nade_y < 512 and nade_z > 0 and nade_z < 63:
                            map.remove_point(nade_x, nade_y, nade_z)
            block_action.x = x
            block_action.y = y
            block_action.z = z
            block_action.value = 3
            block_action.player_id = self.player_id
            self.protocol.send_contained(block_action, save = True)

        def intel_temporary(self):
            self.intel_temp = self.intel_upgrade()

        def intel_upgrade(self):
            say = self.send_chat
            if sum(self.intel_p_lvl) >= 24:
                say("You have every power maxed out!")
                return False
            dice_roll = random.randint(0, 7)
            if self.intel_power_pref != 8 and sum(self.intel_p_lvl) != 0:
                dice_roll = self.intel_power_pref
                if self.intel_p_lvl[dice_roll] < 3:
                    self.intel_p_lvl[dice_roll] += 1
                    return dice_roll
            while (self.intel_p_lvl[dice_roll] == 3):
                dice_roll = random.randint(0, 7)
            self.intel_power_pref = dice_roll if sum(self.intel_p_lvl) != 0 or self.intel_power_pref == 7 else self.intel_power_pref
            self.intel_p_lvl[dice_roll] += 1
            return dice_roll


        def intel_downgrade(self):
            if self.intel_temp is False:
                return
            self.intel_p_lvl[self.intel_temp] -= 1
            self.intel_temp = False

        def intel_clear(self):
            self.poisoner = None
            self.poison = 0
            self.intel_p_lvl = [0,0,0,0,0,0,0,0]
            self.intel_power_pref = 8
            self.intel_temp = False

    class IntelPowerProtocol(protocol):
        intel_second_counter = 0
        def on_game_end(self):
            for player in self.players.values():
                player.intel_clear()
            self.send_chat("Round is over! Intel Powers have been reset!")
            protocol.on_game_end(self)

        def on_world_update(self):
            self.intel_second_counter += 1
            if self.intel_second_counter >= 90:
                for player in self.players.values():
                    player.intel_every_second()
                self.intel_second_counter = 0
            protocol.on_world_update(self)

    return IntelPowerProtocol, IntelPowerConnection
