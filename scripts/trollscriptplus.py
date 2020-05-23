"""
Trollscript
idea and basic scripting by Morphman
improved by Leif_The_Head
with the help of thepolm3 and leWizard
-------------------------------------------------
revised and extended by Dr. Morphman
-------------------------------------------------
ported to python3 and piqueserver by:
Hourai [Night-Stalkers]
-------------------------------------------------
"""

# Imports
from twisted.internet.reactor import callLater
from twisted.internet import reactor
from pyspades.contained import FogColor, PlayerLeft, CreatePlayer, BlockAction, WeaponReload
from pyspades.common import make_color
from pyspades.constants import *
from piqueserver.commands import command, get_player
from random import randint

fog_color = FogColor()
player_left = PlayerLeft()
create_player = CreatePlayer()
block_action = BlockAction()
weapon_reload = WeaponReload()


# OPTIONS:

ADDNAME_MESSAGE = "You forgot to give a victim"

# Options for BURN command
BURN_DAMAGE = 5     # Damage per second
BURN_DUR = 21       # Duration in seconds

BURN_FOG_COLOR = (150, 20, 0)
BURN_MESSAGE_VICTIM = "YOU ARE BURNING!"
BURN_MESSAGE_OP = "{victim} is now burning"

# Option for LAUNCH command
LAUNCH_VEL = -5     # Z velocity

LAUNCH_MESSAGE_VICTIM = "You got launched in the air"
LAUNCH_MESSAGE_OP = "Launched {victim}"

# Options for HOLD command
HOLD_DUR = 40       # Duration in seconds
HOLD_HEIGHT = 20    # Height above map

HOLD_MESSAGE_VICTIM = "You are hold for {sec} seconds"
HOLD_MESSAGE_OP = "Holding {victim} at {xp} {yp} {zp} for {sec} seconds"

# Options for TORTURE command
TORTURE_KICK = True     # Kicks player after torture when "True"

TORTURE_MESSAGE_VICTIM = "You will now get a torture. ENJOY!"
TORTURE_MESSAGE_OP = "{victim} is now on a torture."


# definition for some effects
def temp_set_fog(player, color, time):
    NORM_FOG = (128, 232, 255)
    try:
        NORM_FOG = player.protocol.get_fog_color()
    except:
        pass
    send_fog(player, color)
    callLater(time, send_fog, player, NORM_FOG)

def send_fog(player, color):
    fog_color.color = make_color(*color)
    player.send_contained(fog_color)

# Main part with definitions of commands

@command('burn', admin_only=True) #BURN command
def burnsy(connection, *args):
    player = connection
    damage = BURN_DAMAGE
    duration = BURN_DUR
    if len(args)== 0:
        return ADDNAME_MESSAGE
    else:
        if args: player = args[0]
        if len(args)>1: damage = int(args[1])
        if len(args)>2: duration = int(args[2])
        player = get_player(connection.protocol, player)
        for time in range(duration):
            reactor.callLater(time, player.hit, damage)
        temp_set_fog(player,BURN_FOG_COLOR,duration)
        player.send_chat(BURN_MESSAGE_VICTIM)
        message = BURN_MESSAGE_OP.format(victim = player.name)
        return message

@command('hold', admin_only=True)
def holder(connection, *args):
    player = connection
    time = HOLD_DUR
    height = HOLD_HEIGHT
    if len(args)== 0:
        return ADDNAME_MESSAGE
    else:
        if args: player = args[0]
        if len(args)>1: time = int(args[1])
        if len(args)>2: height = int(args[2])
        player = get_player(connection.protocol, player)
        if time > 1800: time = 1800
        x, y, z = player.get_location()
        z = connection.protocol.map.get_z(x, y) - height
        for hold in range(time * 100):        
            reactor.callLater(0.01*hold, player.set_location, (x, y, z))
        victimmessage = HOLD_MESSAGE_VICTIM.format(sec = time)
        player.send_chat(victimmessage)
        message = HOLD_MESSAGE_OP.format(victim = player.name, xp = round(x), yp = round(y), zp = z, sec = time)
        return message

@command('troll')
def flytoohigh(connection, player = None):
    if player is not None:
        player = get_player(connection.protocol, player)
    else: return 'U Failed hard'
    for flug in range(8000):        
        reactor.callLater(0.04*flug, player.set_location, (255, 255, 65 - flug*5))
    return 'Alright he will be launched 40k blocks in the air, are you happy now?!'



'''                         PART II                       ''' # stuff that Morph added



@command('getout')
def get_out(self, victim, *args):
    player = get_player(self.protocol, victim)
    if player.has_intel: player.kill()
    if len(args) != 3: player.set_location((550, 550, -50))
    player.set_location((float(args[0]), float(args[1]), float(args[2])))
    return 'Hehe your little friend has been teleported :3'

@command('flash')
def flash(self, victim, *args):
    player = get_player(self.protocol, victim)
    if len(args) > 0:time = int(args[0])
    else: time = 10
    for elapsed_time in range(time*20):
        dat_fog = (randint(0,255), randint(0,255), randint(0,255))
        reactor.callLater(elapsed_time*0.05, send_fog, player, dat_fog)
    send_fog(player, player.protocol.get_fog_color())
    message = 'Commencing seizure on %s for %i seconds.' % (player.name, time)
    return message

@command('nospawn')
def dont_spawn(self, victim):
    player = get_player(self.protocol, victim)
    player.rekt_spawn = True
    message = '%s will not be able to respawn anymore huehuehue.' % (player.name)
    return message

@command('rdmg', 'repeldamage', admin_only=True)
def repel_damage(self, victim):
    player = get_player(self.protocol, victim)
    if player.rekt_damage == True:
        player.rekt_damage = False
        message = "%s will be able to kill people (also called 'hacking') again." % (player.name)
    else:
        player.rekt_damage = True
        message = '%s has entered MASOCHIST MODE!' % (player.name)
    return message

@command('damagemultiplier', 'dmg', admin_only=True)
def damage_multiplicator(self, victim, multiplicator):
    multiplicator = float(multiplicator)
    player = get_player(self.protocol, victim)
    player.rekt_damage_multiplicator = multiplicator
    message = "%s's damage multiplicator was set to %f." % (player.name, multiplicator)
    return message

@command('curse', admin_only=True)
def curse(self, victim, *args):
    if len(args) <= 0: times = 5
    else: times = int(args[0])
    player = get_player(self.protocol, victim)
    player.rekt_curse = times
    message = 'Oh noes, %s has been cursed for %i live times!' % (player.name, player.rekt_curse)
    player.kill()
    return message

@command('confuse', admin_only=True)
def confuse(self, victim, *args):
    if len(args) <= 0: time = 20
    else: time = int(args[0])
    player = get_player(self.protocol, victim)
    for teleports in range(time):
        x = randint(0,512)
        y = randint(0,512)
        reactor.callLater(1*teleports, player.set_location, (x, y, self.protocol.map.get_z(x, y)))
    return '%s has no idea what he is doing for %i seconds.' % (player.name, time)

@command('noammo', admin_only=True)
def remove_ammo(self, victim):
    player = get_player(self.protocol, victim)
    if player.rekt_ammo == False:
        player.rekt_ammo = True
        return '%s seems to have a hole in his gun.' % (player.name)
    else:
        player.rekt_ammo = False
        player.refill()
        return '%s managed to fix his gun' % (player.name)

@command('spam', admin_only=True)
def spam(self, victim, times, interval, *args):
    player = get_player(self.protocol, victim)
    if int(times) >= 1001: times = 1000
    spammessage = ''
    for create_message in range(len(args)):
        spammessage += args[create_message] +' '
    for nagging in range(int(times)):
        reactor.callLater(float(interval)*nagging, player.send_chat, spammessage)
    return 'Poor little %s has to endure spam now.' % (player.name)

@command('leave', admin_only=True)
def leave(self, victim):
    player = get_player(self.protocol, victim)
    for goners in list(self.protocol.players.values()):
        if goners != player:
            player_left.player_id = goners.player_id
            player.send_contained(player_left)
    player.rekt_company = True
    return 'That %s guy has been left forever alone.' % (player.name)

@command('nirvana')
def nirvana(self, victim):
    player = get_player(self.protocol, victim)
    player_left.player_id = player.player_id
    player.send_contained(player_left)
    player.rekt_existence = True
    return 'The holy %s has reached nirvana.' % (player.name)

def nagger(self):
    if self.is_here:
        x,y,z = self.get_location()
        block_action.player_id = self.player_id
        block_action.value = BUILD_BLOCK
        block_action.x = x
        block_action.y = y
        block_action.z = z
        self.send_contained(block_action)

@command('nag', admin_only=True)
def nag(self, victim, time):
    player = get_player(self.protocol, victim)
    for nagging in range(int(time)*2): reactor.callLater(nagging*0.5, nagger, player)
    return '%s will listen to strange voices now.' % (player.name)

@command('prison', admin_only=True)
def jail(self, victim):
    player = get_player(self.protocol, victim)
    if player.rekt_prison==False:
        player.rekt_prison = True
        player.set_location((self.protocol.prison_x - 5,self.protocol.prison_y-5, self.protocol.prison_z+5))
        return '%s has been sent to prison.' % (player.name)
    else:
        player.rekt_prison = False
        player.kill()
        return '%s has been discharged from prison.' % (player.name)

@command('buildprison', 'bp', admin_only=True)
def rebuild_prison(self):
    self.protocol.build_prison()
    return 'Prison has been restored, reconnect to make it visible.'

@command('namechange', 'nc', admin_only=True)
def name_change(self, victim, *args):
    self = get_player(self.protocol, victim)
    dat_name = ''
    old_name = self.name
    for kitten in range(len(args)):
        if kitten == len(args)-1: dat_name += str(args[kitten])
        else: dat_name += (str(args[kitten]) + ' ')
    if len(dat_name) > 15 : return 'The name must contain less than 15 characters!'
    if len(dat_name) <= 0: return 'The name must consist of at least one character!'
    self.name = dat_name
    self.world_object.name = dat_name
    self.printable_name = dat_name
    player_left.player_id = self.player_id
    self.protocol.send_contained(player_left)
    del self.protocol.players[self.player_id]
    create_player.player_id = self.player_id
    create_player.weapon = self.weapon
    create_player.team = self.team.id
    create_player.name = dat_name
    self.protocol.send_contained(create_player)
    self.protocol.players[self.player_id]=self
    self.protocol.irc_say(old_name + " has been renamed to " + dat_name)
    return old_name + " has been renamed to " + dat_name

@command('messagechange', 'msg', admin_only=True)
def change_messages(self, victim, *args):
    player = get_player(self.protocol, victim)
    if player.rekt_chat:
        player.rekt_chat = False
        return '%s obtained the ability to talk sense (hopefully).' % (player.name)
    else:
        player.rekt_chat = True 
        dat_chat = ''
        for kitten in range(len(args)): dat_chat += (str(args[kitten]) + ' ')
        player.rekt_chat_value = dat_chat
        return "%s's messages will be modified now." % (player.name)

@command('cocaine', 'c', admin_only=True)
def make_hyper(self, victim):
    player = get_player(self.protocol, victim)
    player.rekt_orientation = not player.rekt_orientation
    if player.rekt_orientation: return '%s feels HYPER!' % player.name
    else: return '%s is clean now.' % player.name

@command('showtrollcommands', 'stc', admin_only=True)
def show_troll_commands(self):
    return '/burn /hold /cocaine /spam /namechange /messagechange /nag /prison /noammo /nirvana /leave /confuse /curse /getout /flash /nospawn /repeldamage /damagemultiplier /troll'

'''@alias('tban')
@admin
@name('trollban')
def troll_ban(self, victim, type, *args):
    reason = ''
    for words in range(len(args)): reason += (args[words] + ' ')
    player = get_player(self.protocol, victim)
    data = {player.name.lower(), str(player.address), type, reason}
    rekt_bans = open('rekt.txt', 'a')
    rekt_bans.write(str(data)+'\n')
    rekt_bans.close()
    return '%s has been added to the troll list.' % player.name
commands.add(troll_ban)'''

def apply_script(protocol, connection, config):

    class trollconnection(connection):
        is_here = False
        has_intel = False
        rekt_spawn = False
        rekt_damage = False
        rekt_damage_multiplicator = 1.0
        rekt_curse = 0
        rekt_ammo = False
        rekt_existence = False
        rekt_company = False
        rekt_prison = False
        rekt_chat = False
        rekt_chat_value = None
        rekt_orientation = False


        def on_hit(self, hit_amount, hit_player, kill_type, grenade):
            if self.rekt_damage_multiplicator != 1.0:
                amount = connection.on_hit(self, hit_amount, hit_player, kill_type, grenade)
                if amount != False and amount != None:
                    new_hit_amount = amount * self.rekt_damage_multiplicator
                    return new_hit_amount
                else:
                    return False
            
            if self.rekt_damage and self.team != hit_player.team:
                if hit_amount >= self.hp: self.kill(hit_player, kill_type, grenade)
                else: self.set_hp(self.hp - hit_amount)
                return False

            if self.rekt_prison: return False

            return connection.on_hit(self, hit_amount, hit_player, kill_type, grenade)

        def on_spawn(self,pos):
            if self.rekt_curse > 0:
                self.rekt_curse -= 1
                x,y,z = pos
                self.set_location((x, y, -62))
            if self.rekt_existence:
                player_left.player_id = self.player_id
                self.send_contained(player_left)
            if self.rekt_spawn: return False
            if self.rekt_prison: self.set_location((self.protocol.prison_x - 5,self.protocol.prison_y-5, self.protocol.prison_z+5)) 
            for player in list(self.protocol.players.values()):
                if player.rekt_company and player != self:
                    player_left.player_id = self.player_id
                    player.send_contained(player_left)   
            return connection.on_spawn(self, pos)

        def on_block_build_attempt(self, x, y, z):
            if self.rekt_prison or (self.protocol.prison_x+1>=x>=self.protocol.prison_x-11 and self.protocol.prison_y+1>=y>=self.protocol.prison_y-11 and self.protocol.prison_z+11>=z>=self.protocol.prison_z-1):  return False
            return connection.on_block_build_attempt(self, x, y, z)

        def on_line_build_attempt(self, points):
            for stuff in points: 
                if (self.protocol.prison_x+1>=stuff[0]>=self.protocol.prison_x-11 and self.protocol.prison_y+1>=stuff[1]>=self.protocol.prison_y-11 and self.protocol.prison_z+11>=stuff[2]>=self.protocol.prison_z-1):  return False
            if self.rekt_prison: return False
            return connection.on_line_build_attempt(self, points)

        def on_block_destroy(self, x, y, z, mode):
            if self.rekt_prison or (x,y,z) in self.protocol.indestructable or mode == 3: return False
            return connection.on_block_destroy(self, x, y, z, mode)

        def on_grenade(self, grenade):
            if self.rekt_prison: return False
            return connection.on_grenade(self, grenade)

        def on_walk_update(self, up, down, left, right):
            if self.rekt_ammo:
                weapon_reload.player_id = self.player_id
                weapon_reload.clip_ammo = 0
                weapon_reload.reserve_ammo = 0
                self.send_contained(weapon_reload)
            return connection.on_walk_update(self, up, down, left, right)

        def on_join(self):
            self.is_here = True
            return connection.on_join(self)

        def on_disconnect(self):
            self.is_here = False
            return connection.on_disconnect(self)

        def on_chat(self, value, global_message):
            if self.rekt_chat: value = self.rekt_chat_value
            return connection.on_chat(self, value, global_message)
    
        def on_orientation_update(self, x, y, z):
            if self.rekt_orientation:
                result = self.world_object.cast_ray(100)
                if result == None or self.has_intel: self.set_hp(self.hp - 2, kill_type = FALL_KILL)
                else: self.set_location((result[0],result[1],result[2]-1))
            return connection.on_orientation_update(self, x, y, z)

        def get_respawn_time(self):
            if self.rekt_prison: return 0
            return connection.get_respawn_time(self)

        def on_flag_take(self):
            self.has_intel = True
            return connection.on_flag_take(self)

        def on_flag_drop(self):
            self.has_intel = False
            return connection.on_flag_drop

    class trollprotocol(protocol):

        indestructable = []
        prison_x = 260
        prison_y = 260
        prison_z = 11

        def build_prison(self):   
            self.indestructable = []
            for x in range(10):
                for y in range(10):
                    for z in range(10):
                        if y==0 or y==9 or x==0 or x==9 or z==0 or z==9: 
                            self.map.set_point(self.prison_x - x, self.prison_y - y, self.prison_z + z, self.map.get_color(self.prison_x - x, self.prison_y - y,self.map.get_z(self.prison_x - x, self.prison_y - y)))
                            self.indestructable.append((self.prison_x - x, self.prison_y - y, self.prison_z + z))

        def on_map_change(self, map):
            self.build_prison()
            return protocol.on_map_change(self, map)

    return trollprotocol, trollconnection
