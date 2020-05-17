"""
Bot script by lecom
Based on basicbots.py by hompy.

Bots that use either spade, grenade, SMG or rifle.
No pathfinder implemented, so when they go to a wall, they try to jump over it if they can, else dig through it.
Best on classicgen-like maps.
The "local" thing isnt needed, just add to scripts and start the server.

/addbot [amount] [green|blue]
/set_team [id] [teamname]
/toggleai
/set_bot_power [value] Sets how powerful bots should be (0-1, 1=no bot nerfing,2=OP)
/set_bot_accuracy [value] Sets the bot accuracy (in percent, 100%=aimbots moving around)

Admins can make bots stay on their current position.
Say the word "stay" and "bots" or the name of any bot in the chat for that.
Say "follow me" and the name of any bot in the chat to make bots follow you.
"""

from math import *
from enet import Address
from twisted.internet.reactor import seconds
from pyspades.protocol import BaseConnection
from pyspades.contained import InputData, WeaponInput, SetTool, GrenadePacket, BlockAction, ChatMessage
from pyspades.world import Grenade,cube_line
from pyspades.common import Vertex3
from pyspades.collision import vector_collision
from pyspades.constants import *
from piqueserver.commands import command, admin, add, name, get_team
from piqueserver.scheduler import Scheduler

from random import SystemRandom,randrange,randint,random, choice
from array import array
import textwrap
import gc
from math import isnan
from time import time
from pyspades.types import IDPool

# lazy workaround to pique's new contained pyspades.server implementation
input_data, weapon_input, set_tool, grenade_packet, block_action, chat_message = \
    InputData(), WeaponInput(), SetTool(), GrenadePacket(), BlockAction(), ChatMessage()

DONT_FILL_SERVER=True

#options:
ADD_BOTS_TO_PLAYER_COUNT=False
DIG_THROUGH_WALLS=True
USE_C_CAN_SEE=False #The PySnip C can_see algo is much faster, but makes bots see "around" single blocks

BOTNAMES=['Comrade', 'Comrade']

BOT_RAND_NAMES=['poopskadoodles', 'Nice Memes Kid', 'So White I Glow', 'xPuppyXPunterx', 'Try a Klondike', 'Lol 0 Kills Bro', 'xMrStealYoWifi', 'Art Thoud Livid', 'lord fizzlebutt', 'DJ Yolo Cancer', 'The Gay Gazelle', 'kickagrundle', 'ImADuckOnQuack2', 'Feed Africans', 'Certified Negro', 'Waffle Dipper', 'AssCandles', 'YawnYourBoring', 'MayorMcTurd', 'TheMurderPony', 'freeponyride', 'I Consume Poop', 'POOPIE TROUSERS', 'TittieSprinkle3', 'StupidHobbitses', 'Cinnamon Trolls', 'bearslovepie', 'WTHisthisWTF', 'TheTactitalButt', 'The Jews Won', 'Valid Coupons', 'Earlessjackass', 'PeeInRiver', 'XBoxMakesMeLazy', 'CaretoElaborate', 'C4 3 2 1 BOOM', 'Please Be Quiet', 'OceanSprayDrink', 'SurpassYourAss', 'Mr Derp Herpson', 'myponywillkillu', 'Poopynewb', 'pooptroop', 'OMG  imgona POOP', 'Loads of Toads', 'CatsOnRainbows', 'I Squat 2 Pooh', 'Im White YAY', 'WellHellsBells', 'FluffyKilljoy', 'FOOTAGE x POOP', 'xDooDooBUTTERxx', 'Bullying Policy', 'DaFunkTapus', 'xPoonDogg1977', 'TURDofWONDER9', 'POOKYSNOOKUMS', 'Babyfood Thief', 'HolyCrapThisSux', 'lol I Like Cake', 'Lord Tuki Tuki', 'Soft PWNography', 'DA KARATE KITTY', 'A LONE POP TART', 'About 3257 Jews', 'RacistMailBox', 'funylokinfetus', 'Dave Eats Kids', 'iRassleTurtles', 'FestiveDungheap', 'FTHISNAMEBRO', 'ChimpNotApansy', 'MyMomLetsMePlay', 'Fluffybutnotfat', 'PeepsAndPoops', 'SchizzPoppinov', 'Im White Its Ok', 'My Bear Handz', 'CatAttackHiss', 'JerkStoleMyName', 'GOAT COMMANDER', 'droopy 4skyn', 'His Mail Lover', 'AtomicToast', 'GoGoGoDammitGo', 'RebelSansCause', 'Brock McKickass', 'MercilessMaggot', 'BRBkillingSPREE', 'The Trousers', 'DamnMyKarma', 'xxGODLYWAFFLExx', 'scotchNpancakes', 'V0lCaNiC DiaRia', 'A Gay Pink Pony', 'PooInMyTurban', 'SemiLoyalPet', 'porkisgood', 'HappierEar', 'Giftcard', 'That Jewish Boy', 'doopaloop', 'ChiefofChiefing', 'Spumhole', 'ChildrenPlease', 'BRBgonetopee', 'I KnOw It HuRtZ', 'Tel Me It Hurtz', 'It Hurtz So Bad' , 'A Dustbuster', 'TECHNOPIDGEON', 'HAHAcrunkHAHA', 'GTFO My Pancake', 'Pancakez R yum', 'RapRepRipRopRup', 'randomfantastic', 'My14InchDuck', 'WHAMbulance', 'OMFGNameTaken', 'IsThatAPenguin', 'ThisPartyIsLame', 'AgitatedPigeon', 'HereEatMyShirt', 'Crapasaurus Rex', 'Party Car', 'Kookadooski', 'WorriedBurrito', 'DougFromFinance', 'Did You Get Sad', 'LetMeGetTheBomb', 'cats r my style', 'BombsAndBabies', 'iTackleFatKids', 'Sgt Taco Pants', 'big black dad', 'Like Ten Babies', 'poopngriddles', 'Ouchwhoshotme', 'TootieBubbles', 'OMG I GOT SHOT', 'MiniMcGiggles', 'PooLord', 'cpt underwear', 'hey wait 4 me', 'GoEasyPlz', 'AHNESTLY', 'Prostidude', 'Ivana Fistya', 'TasteThePainbow', 'xKinky Turtlex', 'IpeewhenIpoo', 'HaHaIfarted', 'Anne Frankfurter', 'Pavementpoop', 'lolwrongnumber', 'A Black Midget', 'Poopie McGhee', 'CherrySux', 'Don_Giveachit', 'EdgarAllenPoo', 'GotASegway', 'LookWhatICanDo', 'OneSmugPug', 'IPlayFarmHeroes', 'Vaguely Cynical', 'The Brave Chicken', 'Killertrainz', 'Boomhauer', 'Captain Crunch', 'FuckoffCupid', 'SandWitch', 'PonyCloud', 'PistolPrincess', 'SniperPrincess', 'PurpleBunnySlippers', 'SmittenKitten66', 'IKissedCupid', 'TheBirthdayGirl', 'SuperGurl3000', 'HottieMuffins', 'LadyStepMurder', 'Unicorns25', 'TiaraONtop', 'LilianaVess', 'GlitterGunner', 'CandyStripper', 'SevenofNine', 'GunnerrGurrl']

LOGIC_FPS = 4.0
BOT_TURN_SPEED=.05
AIM_SPEED=.8
SEE_DISTANCE=120
GRENADE_DISTANCE=32
BOT_ACCURACY=20
BOT_POWER=.9

#constants; don't touch them
SPADE_MOVE_SPEED=.25
BLOCK_DELAY=.5

BOTINPUT_DOWN='down'
BOTINPUT_UP='up'
BOTINPUT_RIGHT='right'
BOTINPUT_LEFT='left'

STAND_TIME_TO_BUILD=10*LOGIC_FPS 

class BotWeaponStat_t:
	Accuracy=0
	Distance=0
	HeadShotRate=0
	AimSpeed=0
	Recoil=0
	def __init__(self,accuracy,dist,headshotrate,aimspeed,recoil):
		self.Accuracy=accuracy
		self.Distance=dist
		self.HeadShotRate=headshotrate
		self.AimSpeed=aimspeed
		self.Recoil=recoil

WeaponStats=(
	BotWeaponStat_t(40,70,50,1,.1),
	BotWeaponStat_t(22,45,15,.1,.001),
	BotWeaponStat_t(2,40,10,.01,.5)
)

@command('toggle_bot_server_fill', admin_only=True)
def toggle_bot_server_fill(self):
	global DONT_FILL_SERVER
	DONT_FILL_SERVER=not DONT_FILL_SERVER
	return 'Not filling server: %s' % DONT_FILL_SERVER

@command('clear_bot_pool', admin_only=True)
def clear_bot_pool(self):
	self.protocol.bot_pool=[]
	return 'Cleared bot pool'

@command('show_bot_pool', admin_only=True)
def show_bot_pool(self):
	return_msg='List of bot player ids:'
	for bot in self.protocol.bot_pool:
		return_msg+=' '
		return_msg+=str(bot.player_id)
	return return_msg

@command('show_bot_pool', admin_only=True)
def set_bot_power(self,power):
	global BOT_POWER
	BOT_POWER=float(power)
	return 'Set bot power to %s' % BOT_POWER

@command('set_bot_accuracy', admin_only=True)
def set_bot_accuracy(self,accuracy):
	global BOT_ACCURACY
	BOT_ACCURACY=float(accuracy)
	return 'Set bot accuracy to %s' % BOT_ACCURACY

def _print(message):
	print(message)


class __clear_server_message__:
	message=''

@command('clear_server', admin_only=True)
def clear_server(self):
	playerlist=[]
	protocol=self.protocol
	for player in list(protocol.players.values()): #May not modify dict while iterating, also immune to weird bugs
		playerlist.append(player)
	for player in playerlist:
		player.on_disconnect()
		player.disconnect()
	protocol.connections.clear()
	protocol.players={}
	protocol.player_ids=IDPool()
	protocol.bots=[]
	msg='Cleared server, %s players, %s connections' % (len(protocol.players),len(protocol.connections))
	Scheduler(protocol).call_later(.1,protocol.irc_say,msg)
	Scheduler(protocol).call_later(.1,_print,msg)
	return

@command('clear_server_experimental', admin_only=True)
def clear_server_experimental(self):
	playerlist=[]
	protocol=self.protocol
	for player in list(protocol.players.values()): #May not modify dict while iterating
		playerlist.append(player)
	for player in playerlist:
		player.disconnect()
	protocol.connections.clear()
	protocol.players={}
	protocol.bots=[]
	msg='Cleared server, %s players, %s connections' % (len(protocol.players),len(protocol.connections))
	Scheduler(protocol).call_later(.1,protocol.irc_say,msg)
	Scheduler(protocol).call_later(.1,_print,msg)

@command('toggle_master_bot_data', admin_only=True)
def toggle_master_bot_data(self):
	global ADD_BOTS_TO_PLAYER_COUNT
	ADD_BOTS_TO_PLAYER_COUNT=not ADD_BOTS_TO_PLAYER_COUNT
	self.protocol.update_master()
	return 'Adding bot count to player count on server list is set to %s' % ADD_BOTS_TO_PLAYER_COUNT

@command('addbot', admin_only=True)
def add_bot(connection, amount = None, team = None):
    protocol = connection.protocol
    if team:
        bot_team = get_team(connection, team)
    blue, green = protocol.blue_team, protocol.green_team
    amount = int(amount or 1)
    for i in range(amount):
        if not team:
            bot_team = blue if blue.count() < green.count() else green
        bot = protocol.add_bot(bot_team)
        protocol.update_master()
        if not bot:
            return "Added %s bot(s)" % i
    return "Added %s bot(s)" % amount

@command('show_bots')
def show_bots(self):
	for bot in self.protocol.bots:
		print(('player id:%s' % bot.player_id))
	return

@command('toggle_ai', admin_only=True)
def toggle_ai(connection):
    protocol = connection.protocol
    protocol.ai_enabled = not protocol.ai_enabled
    if not protocol.ai_enabled:
        for bot in protocol.bots:
            bot.flush_input()
    state = 'enabled' if protocol.ai_enabled else 'disabled'
    protocol.send_chat('AI %s!' % state)
    protocol.irc_say('* %s %s AI' % (connection.name, state))

@command('set_team', admin_only=True)
def set_team(self,id,teamname):
	if id[0]=='#':
		id=id[1:]
	bot=self.protocol.players[int(id)]
	for team in list(self.protocol.teams.values()):
		if team.name.lower()==teamname.lower():
			break
	bot.set_team(team)
	return 'Switched %s to team %s' % (bot.name,team.name)

class LocalPeer:
    address = Address(b"255.255.255.255", 0)
    roundTripTime = 0.0
    eventData=GAME_VERSION
    reliableDataInTransit=None
    def send(self, *arg, **kw):
        return
    
    def reset(self):
        pass

AI_COMMANDS_STAY=1
AI_COMMANDS_FOLLOW=2

class Bot_AI_t:
	Commands=0
	Follow=None
	OldPos=Vertex3(0,0,0)
	staying_time=0
	b_staying_time=0
	WobbleTimer=0
	GoBack=0
	acquire_targets=True
	aim_at=None
	attack_call=None
	game_target=None
	def __init__(self):
		return

def apply_script(protocol, connection, config):
    class BotProtocol(protocol):
        bots = None
        bot_pool=[]
        ai_enabled = True
        ai_game_mode=True

        def add_bot(self, team):
            if len(self.connections) + len(self.bots) >= (31-int(DONT_FILL_SERVER)):
                return None
            if not len(self.bot_pool):
                bot = self.connection_class(self, None)
            else:
                bot=self.bot_pool.pop()
            self.bots.append(bot)
            if not bot.AI:
                    bot.AI=Bot_AI_t()
            bot.join_game(team)
            return bot
        
        def on_world_update(self):
            if self.bots and self.ai_enabled:
                do_logic = self.loop_count % int(UPDATE_FPS / LOGIC_FPS) == 0
                for bot in self.bots:
                    if not bot.world_object:
                        continue
                    if do_logic:
                        bot.think()
                    bot.update()
            protocol.on_world_update(self)
        
        def on_map_change(self, map):
            self.bots=[]
            self.ai_game_mode=True
            protocol.on_map_change(self, map)
        
        def advance_rotation(self, message=None):
            if not self.bots:
                return protocol.advance_rotation(self, message)
            for bot in self.bots[:]:
                bot.disconnect()
            self.bots = []
            protocol.advance_rotation(self, message)

        def update_master(self):
            if self.master_connection is None or not ADD_BOTS_TO_PLAYER_COUNT:
                return protocol.update_master(self)
            count = 0
            for connection in list(self.connections.values()):
                if connection.player_id is not None:
                    count += 1
            count+=len(self.bots)
            self.master_connection.set_count(count)
            return

        def is_walkable(self,pos):
                go_up=self.map.get_solid(*pos.get())==True
                pos.z-=1
                go_up|=int(self.map.get_solid(*pos.get())==True)*2
                pos.z-=1
                obstacle=int(self.map.get_solid(*pos.get())==True) and go_up
                pos.z+=2
                return (obstacle,go_up)

    class BotConnection(connection):
        aim = None
        input = None
        can_see=None
        AI=None
        
        _turn_speed = None
        _turn_vector = None
        def _get_turn_speed(self):
            return self._turn_speed
        def _set_turn_speed(self, value):
            self._turn_speed = value
            self._turn_vector = Vertex3(cos(value), sin(value), 0.0)
        turn_speed = property(_get_turn_speed, _set_turn_speed)
        
        def __init__(self, protocol, peer):
            if peer is not None:
                return connection.__init__(self, protocol, peer)
            if not self.AI:
                  self.AI=Bot_AI_t()
            connection.__init__(self, protocol, LocalPeer())
            self.on_connect()
            #~ self.saved_loaders = None
            self._send_connection_data()
            self.send_map()
            
            self.aim = Vertex3()
            self.target_orientation = Vertex3()
            self.turn_speed = 0.15 # rads per tick
            self.input = set()
            self.can_see=self.world_object.can_see if USE_C_CAN_SEE else self._can_see

        def on_login(self,name):
                if self.AI:
                        return connection.on_login(self,name)
                for _bname in BOTNAMES:
                        if len(name)>=len(_bname):
                                same_name=True
                                for i in range(len(_bname)):
                                        same_name&=name[i]==_bname[i]
                                if same_name and len(name) in range(len(BOTNAME)+1,len(_bname)+3):
                                        self.disconnect(ERROR_KICKED)
                return connection.on_login(self,name)
        
        def join_game(self, team):
            self.name = BOTNAMES[team.id]+str(self.player_id)
            #self.name=choice(BOT_RAND_NAMES)
            #while self.protocol.players.keys().count(self.name):
            #    self.name=choice(BOT_RAND_NAMES)
            if len(self.name)>=15:
                self.name=self.name[0:15]
            self.team = team
            self.set_weapon(randrange(2), True)
            self.protocol.players[self.player_id] = self
            self.on_login(self.name)
            self._set_turn_speed(BOT_TURN_SPEED)
            self.spawn()
        
        def disconnect(self, data = 0):
            if not self.AI:
                return connection.disconnect(self)
            if self.disconnected:
                return
            if self in self.protocol.bots:
                  self.protocol.bots.remove(self)
            self.cancel_attack()
            self.disconnected = True
            self.on_disconnect()
        
        def think(self):
            obj = self.world_object
            if not obj or not self.team or self.team.id==-1:
                return 0

            pos = obj.position
            protocol=self.protocol
            mindist=SEE_DISTANCE
            Old_aim_at=self.AI.aim_at
            search_target=True

            if self.AI.aim_at:
                if self.AI.aim_at.AI:
                        target=self.AI.aim_at.AI.aim_at
                        if target:
                                search_target&=target.player_id!=self.player_id

            if self.AI.acquire_targets and search_target:
                self.AI.aim_at=None
                for player in self.team.other.get_players():
                    if not player.hp:
                        continue
                    if not player.world_object:
                        continue
                    player_pos=player.world_object.position
                    dist=(pos-player_pos).length()
                    if dist>mindist:
                        continue
                    if not self.can_see(*player_pos.get()):
                        continue
                    if player.invisible:
                        continue
                    self.AI.aim_at=player
                    mindist=dist

            #replicate player functionality: cap the intel in CTF, cap territories in TC
            if protocol.ai_game_mode:
                if protocol.game_mode == CTF_MODE:
                        other_flag = self.team.other.flag
                        if vector_collision(pos, self.team.base):
                                if other_flag.player is self:
                                        self.capture_flag()
                                self.check_refill()
                        if not other_flag.player and vector_collision(pos, other_flag):
                                self.take_flag()
                elif protocol.game_mode==TC_MODE and (not self.AI.game_target or self.AI.game_target.team==self.team):
                        entities=protocol.entities
                        teamid=self.team.id
                        dest=None
                        min_dist=512*512*64
                        for entity in entities:
                                if entity.team:
                                        if entity.team.id==teamid:
                                                continue
                                dist=(pos-entity).length()
                                if dist>min_dist:
                                        continue
                                min_dist=dist
                                dest=entity
                        if not dest:
                                protocol.ai_game_mode=False
                        self.AI.game_target=dest

            if Old_aim_at and self.AI.aim_at:
                if self.AI.aim_at.player_id!=Old_aim_at.player_id and self.AI.attacking and self.tool!=SPADE_TOOL:
                        self.cancel_attack()
            if self.AI.aim_at:
                 dist=(pos-self.AI.aim_at.world_object.position).length()
                 spade_range=8
                 if self.tool==SPADE_TOOL:
                        if dist>=spade_range:
                                self.set_tool(WEAPON_TOOL)
                 elif self.tool==WEAPON_TOOL:
                        if dist<spade_range:
                                self.set_tool(SPADE_TOOL)

            return 1

        def set_random_tool(self):
                if randrange(100)<80:
                        self.set_tool(WEAPON_TOOL)
                elif not randrange(3):
                        self.set_tool(SPADE_TOOL)
                elif self.grenades:
                        self.set_tool(GRENADE_TOOL)
                else:
                        self.set_tool(WEAPON_TOOL)

        def bot_build_block(self,pos):
                block_action.x, block_action.y, block_action.z=pos
                block_action.player_id=self.player_id
                block_action.value=BUILD_BLOCK
                self.protocol.send_contained(block_action)

        def on_block(self):
                self.AI.attack_call=None
                if 1:
                        self.blocks-=1
                        pos=self.world_object.position
                        dpos=list(self.get_dirpos().get())
                        dpos[2]+=2
                        for i in range(2):
                                if dpos[2]>=63:
                                        continue
                                if not self.protocol.map.get_solid(*dpos):
                                        self.bot_build_block(dpos)
                                        self.protocol.map.set_point(dpos[0],dpos[1],dpos[2],self.color)
                                dpos[2]+=1
                self.set_random_tool()
                self.AI.b_staying_time=0
                self.AI.attacking=False
                self.AI.acquire_targets=True
        
        def update(self):
            obj = self.world_object
            if not obj:
                    return
            pos = obj.position
            ori = obj.orientation
            Range=int(WeaponStats[self.weapon_object.id].Distance*BOT_POWER)
            weapon=self.weapon
            id=self.weapon_object.id
            if not self.hp:
                return 
            if self.tool==GRENADE_TOOL:
                Range=GRENADE_DISTANCE
            elif self.tool==SPADE_TOOL:
                Range=3.0
            if self.AI.aim_at and self.AI.aim_at.world_object and self.tool!=BLOCK_TOOL:
                self.AI.aim_at_pos = self.AI.aim_at.world_object.position
                can_see=self.can_see(*self.AI.aim_at_pos.get())
                self.aim.set_vector(self.AI.aim_at_pos)
                self.aim -= pos
                distance=self.aim.length()
                distance_to_aim = self.aim.normalize() # don't move this line
                #look at the target if it's within sight
                if can_see:
                    self.target_orientation.set_vector(self.aim)
                #attack or follow
                if self.AI.acquire_targets and (self.tool!=BLOCK_TOOL or self.AI.staying_time<10):
                    if distance<Range and self.AI.aim_at.team.id!=self.team.id and self.AI.aim_at.hp:
                        if not self.AI.attacking and can_see and (ori-self.target_orientation).length()<.2:
                                if self.tool==GRENADE_TOOL:
                                        self.AI.attack_call = Scheduler(self.protocol).call_later(3.0, self.throw_grenade,5.0)
                                        self.AI.attacking=True
                                elif self.tool==SPADE_TOOL:
                                        self.AI.attack_call=Scheduler(self.protocol).call_later(SPADE_MOVE_SPEED,self.on_spade)
                                        self.AI.attacking=True
                                elif self.tool==WEAPON_TOOL:
                                        WaitTime=self.weapon_object.delay
                                        WaitTime+=WeaponStats[self.weapon_object.id].AimSpeed*BOT_POWER
                                        self.AI.attack_call=Scheduler(self.protocol).call_later(WaitTime,self.on_shoot)
                                        self.AI.attacking=True
                                else:
                                        self.set_random_tool()
                    elif not self.AI.Follow or distance_to_aim>4:
                        self.input.add(BOTINPUT_UP)
                    
            #cap the flag
            elif (not self.AI.Follow or not self.AI.aim_at) and self.protocol.ai_game_mode and not self.AI.Commands:
                if self.protocol.game_mode==CTF_MODE:
                        flag=self.team.other.flag
                        Carrying_flag=self.team.other.flag.player
                        if Carrying_flag:
                                Carrying_flag=self.team.other.flag.player.player_id==self.player_id
                        else:
                                Carrying_flag=False
                        if (not	Carrying_flag or not flag.player):
                                self.aim.set_vector(Vertex3(flag.x-pos.x,flag.y-pos.y,0).normal())
                                self.target_orientation.set_vector(self.aim)
                                self.input.add(BOTINPUT_UP)
                        elif Carrying_flag:
                                base=self.team.base
                                self.aim.set_vector(Vertex3(base.x-pos.x,base.y-pos.y,0).normal())
                                self.target_orientation.set_vector(self.aim)
                                self.input.add(BOTINPUT_UP)
                elif self.protocol.game_mode==TC_MODE:
                        dest=self.AI.game_target
                        if dest:
                                collides=vector_collision(dest,pos,TC_CAPTURE_DISTANCE)
                                capturing=self in dest.players
                                if collides and not capturing:
                                        dest.add_player(self)
                                elif not collides and capturing:
                                        dest.remove_player(self)
                                if not collides:
                                        self.target_orientation.set_vector((dest-pos).normal())
                                        self.input.add(BOTINPUT_UP)

            """if self.AI.b_staying_time>=STAND_TIME_TO_BUILD:
                self.AI.b_staying_time=0
                if not randint(0,10):
                        if not self.AI.attacking:
                                if self.AI.aim_at:
                                        self.set_tool(BLOCK_TOOL)
                                        self.AI.attack_call=Scheduler(self.protocol).call_later(BLOCK_DELAY,self.on_block)
                                        self.AI.attacking=True
                                else:
                                        self.set_random_tool()
                        else:
                                self.AI.acquire_targets=False
                self.input.discard(BOTINPUT_UP)"""

            #needed to hold primary fire
            if (self.tool==GRENADE_TOOL or self.tool==SPADE_TOOL) and self.AI.attacking:
                self.input.add('primary_fire')

            if self.AI.Follow and not self.AI.aim_at:
                if not self.AI.Follow.hp or not self.AI.Follow.world_object:
                        self.AI.Follow=None
                else:
                        vdist=self.AI.Follow.world_object.position-pos
                        self.target_orientation.set_vector(vdist.normal())
                        if vdist.length()>=8.0:
                                self.input.add(BOTINPUT_UP)

            # orientate towards target
            diff = ori - self.target_orientation
            diff.z = 0.0
            diff = diff.length_sqr()
            if diff > 0.001:
                p_dot = ori.perp_dot(self.target_orientation)
                if p_dot > 0.0:
                    ori.rotate(self._turn_vector)
                else:
                    ori.unrotate(self._turn_vector)
                new_p_dot = ori.perp_dot(self.target_orientation)
                if new_p_dot * p_dot < 0.0:
                    ori.set_vector(self.target_orientation)
                    self.on_orientation_update(*self.target_orientation.get())
            else:
                ori.set_vector(self.target_orientation)
                self.on_orientation_update(*self.target_orientation.get())
            obj.set_orientation(*ori.get())

            if BOTINPUT_UP in self.input:
                dirpos=self.get_dirpos()
                dirpos.z+=2
                walkable=self.protocol.is_walkable(dirpos)
                if not walkable[0] and walkable[1]>1:
                        self.input.add('jump')
            

            if self.AI.WobbleTimer:
                if int(self.AI.WobbleTimer)%2:
                        self.input.add(BOTINPUT_LEFT)
                else:
                        self.input.add(BOTINPUT_RIGHT)
                self.AI.WobbleTimer-=.008

            if self.AI.GoBack>0 and not self.AI.aim_at:
                self.input.discard(BOTINPUT_UP)
                self.input.add(BOTINPUT_DOWN)
                self.AI.GoBack-=1
            
            if self.AI.aim_at or 'jump' in self.input:
                self.AI.GoBack=0
                self.AI.WobbleTimer=0.0

            if self.AI.Commands&AI_COMMANDS_STAY:
                self.input.discard(BOTINPUT_DOWN)
                self.input.discard(BOTINPUT_UP)
                self.input.discard(BOTINPUT_RIGHT)
                self.input.discard(BOTINPUT_LEFT)

            """if BOTINPUT_UP in self.input and self.tool!=BLOCK_TOOL:
                self.AI.b_staying_time=0
            else:
                self.AI.staying_time+=1
                if self.AI.aim_at and self.AI.staying_time>=STAND_TIME_TO_BUILD:
                        if self.tool!=BLOCK_TOOL:
                                self.set_tool(BLOCK_TOOL)
                                self.cancel_attack()
                        self.input.discard(BOTINPUT_UP)"""

            if self.AI.aim_at:
                self.AI.b_staying_time+=1
                
            if BOTINPUT_UP in self.input and not self.AI.aim_at:
                dist=(self.AI.OldPos-self.world_object.position)
                dist.z=0
                dist=dist.length()
                if dist<.01 and not self.AI.WobbleTimer:
                        if not self.AI.aim_at:
                                self.AI.staying_time+=1
                                if self.AI.staying_time>=5:
                                        self.AI.WobbleTimer=randint(5,8) #Random stuff for brute-force pathfinding ;)
                                        self.AI.GoBack=randint(40,50)
                                        self.AI.staying_time=0
                elif dist>=.01:
                        self.AI.staying_time=0
                        self.AI.WobbleTimer=0.0
                        self.AI.GoBack=0
                self.AI.OldPos=self.world_object.position.copy()
                        
            self.flush_input()
        
        def flush_input(self):
            input = self.input
            world_object = self.world_object
            if not world_object:
                return
            z_vel = world_object.velocity.z
            if 'jump' in input and not (z_vel >= 0.0 and z_vel < 0.017):
                input.discard('jump')
            input_changed = not (
                ('up' in input) == world_object.up and
                ('down' in input) == world_object.down and
                ('left' in input) == world_object.left and
                ('right' in input) == world_object.right and
                ('jump' in input) == world_object.jump and
                ('crouch' in input) == world_object.crouch and
                ('sneak' in input) == world_object.sneak and
                ('sprint' in input) == world_object.sprint)
            if input_changed:
                if not self.freeze_animation:
                    world_object.set_walk('up' in input, 'down' in input,
                        'left' in input, 'right' in input)
                    world_object.set_animation('jump' in input, 'crouch' in input,
                        'sneak' in input, 'sprint' in input)
                if (not self.filter_visibility_data and
                    not self.filter_animation_data):
                    input_data.player_id = self.player_id
                    input_data.up = world_object.up
                    input_data.down = world_object.down
                    input_data.left = world_object.left
                    input_data.right = world_object.right
                    input_data.jump = world_object.jump
                    input_data.crouch = world_object.crouch
                    input_data.sneak = world_object.sneak
                    input_data.sprint = world_object.sprint
                    self.protocol.send_contained(input_data)
            primary = 'primary_fire' in input
            secondary = 'secondary_fire' in input
            shoot_changed = not (
                primary == world_object.primary_fire and
                secondary == world_object.secondary_fire)
            if shoot_changed:
                if primary != world_object.primary_fire:
                    if self.tool == WEAPON_TOOL:
                        self.weapon_object.set_shoot(primary)
                    if self.tool == WEAPON_TOOL or self.tool == SPADE_TOOL:
                        self.on_shoot_set(primary)
                world_object.primary_fire = primary
                world_object.secondary_fire = secondary
                if not self.filter_visibility_data:
                    weapon_input.player_id = self.player_id
                    weapon_input.primary = primary
                    weapon_input.secondary = secondary
                    self.protocol.send_contained(weapon_input)
            input.clear()
        
        def set_tool(self, tool):
            if self.on_tool_set_attempt(tool) == False:
                return
            self.tool = tool
            if self.tool == WEAPON_TOOL:
                self.on_shoot_set(self.world_object.primary_fire)
                self.weapon_object.set_shoot(self.world_object.primary_fire)
            self.on_tool_changed(self.tool)
            if self.filter_visibility_data:
                return
            set_tool.player_id = self.player_id
            set_tool.value = self.tool
            self.protocol.send_contained(set_tool)

        def on_shoot(self):
                self.AI.attack_call=None
                if not self.AI.aim_at or not self.AI.attacking or not self.hp:
                        return
                if not self.world_object or self.team.id==-1 or not self.AI.aim_at.world_object or self.AI.aim_at.team.id==-1:
                        return
                self.weapon_object.reloading=False
                self.weapon_object.current_ammo-=1
                pos=self.world_object.position
                ori=self.world_object.orientation

                aimpos=list(self.AI.aim_at.world_object.position.get())
                BlocksSeeing=0
                SeeHead=self.can_see(*aimpos)
                BlocksSeeing+=int(SeeHead)
                aimpos[2]+=1
                BlocksSeeing+=int(self.can_see(*aimpos))
                if not self.AI.aim_at.world_object.crouch:
                        aimpos[2]+=1
                        BlocksSeeing+=int(self.can_see(*aimpos))

                Accuracy=int(BOT_ACCURACY*WeaponStats[self.weapon_object.id].Accuracy*BlocksSeeing*BOT_POWER)
                dist=(pos-self.AI.aim_at.world_object.position).length()
                Accuracy*=WeaponStats[self.weapon_object.id].Distance
                Accuracy/=dist
                Accuracy=int(Accuracy)
                HeadShotChance=int(WeaponStats[self.weapon_object.id].HeadShotRate*BOT_POWER)
                RandIntNumber=30000
                if self.AI.aim_at.world_object.crouch:
                        RandIntNumber=2000
                if randrange(RandIntNumber)<Accuracy:
                        DamageType=0 if randrange(5) else 2
                        if randrange(100)<HeadShotChance:
                                DamageType=1
                        if DamageType==1 and not SeeHead:
                                DamageType=0
                        _DamageType=HEADSHOT_KILL if DamageType<2 else WEAPON_KILL
                        weapon_damage=self.weapon_object.get_damage(DamageType,pos,self.AI.aim_at.world_object.position)
                        damage=self.on_hit(weapon_damage,self.AI.aim_at,_DamageType,None)
                        if damage!=False:
                                if damage!=None:
                                        weapon_damage=damage
                                if weapon_damage:
                                        self.AI.aim_at.hit(weapon_damage,self,_DamageType)
                else:
                        _ori=[0,0,0]
                        i=randint(0,1)
                        _ori[i]=random()/6*(-1 if not randint(0,1) else 1)
                        self.on_orientation_update(*(ori+Vertex3(*_ori)).get())
                if not self.weapon_object.current_ammo:
                        self.weapon_object.reload()
                self.on_orientation_update(ori.x,ori.y,ori.z-WeaponStats[self.weapon_object.id].Recoil)
                self.input.add('primary_fire')
                self.flush_input()
                self.AI.attacking=False
                return
        
        def throw_grenade(self, time_left):
            self.AI.attack_call=None
            if self.on_grenade(time_left) == False or not self.AI.attacking:
                return
            obj = self.world_object
            vel=obj.orientation.copy()
            vel*=max(1,random()+.5)
            vel+=Vertex3(random(),random(),random())
            grenade = self.protocol.world.create_object(Grenade, time_left,
                obj.position, None, vel, self.grenade_exploded)
            grenade.team = self.team
            self.on_grenade_thrown(grenade)
            if self.filter_visibility_data:
                return
            grenade_packet.player_id = self.player_id
            grenade_packet.value = time_left
            grenade_packet.position = grenade.position.get()
            grenade_packet.velocity = grenade.velocity.get()
            self.protocol.send_contained(grenade_packet)
            self.AI.attacking=False
            self.AI.attack_call=None
            if not self.grenades:
                self.set_random_tool()

        def _on_spade(self):
                self.AI.attack_call=None
                self.AI.attacking=False
                return

        def on_spade(self):
                if not self.AI.attacking or not self.hp:
                        return
                if self.AI.aim_at:
                        damage=self.on_hit(self.protocol.melee_damage,self.AI.aim_at,MELEE_KILL,None)
                        if damage and self.AI.aim_at.hp:
                                self.AI.aim_at.set_hp(self.AI.aim_at.hp-damage,hit_by=self,type=MELEE_KILL,
                                        hit_indicator=self.world_object.position.get())
                self.AI.attack_call=Scheduler(self.protocol).call_later(SPADE_MOVE_SPEED,self._on_spade)
                self.AI.attacking=True
                self.input.add('primary_fire')
                self.flush_input()
                pos=[int(coord) for coord in self.get_dirpos().get()]
                #Yes, this could be done much better with block_action.value=SPADE_DESTROY
                block_action.player_id=self.player_id
                block_action.value=SPADE_DESTROY
                block_action.x=pos[0]
                block_action.y=pos[1]
                block_action.z=pos[2]
                self.protocol.send_contained(block_action)
                for z in range(max(0,pos[2]-1),pos[2]):
                        self.protocol.map.remove_point(pos[0],pos[1],z)
                return
        
        def on_spawn(self, pos):
            if not self.AI:
                return connection.on_spawn(self, pos)
            self.world_object.set_orientation(1.0, 0.0, 0.0)
            self.aim.set_vector(self.world_object.orientation)
            self.target_orientation.set_vector(self.aim)
            self.AI.aim_at = None
            self.AI.acquire_targets = True
            self.set_random_tool()
            self.weapon_object.current_ammo=self.weapon_object.ammo
            self.weapon_object.current_stock=self.weapon_object.stock
            self.AI.attacking=False
            self.AI.attack_call=None
            self.blocks=50
            connection.on_spawn(self, pos)

        def cancel_attack(self):
                if self.AI.attack_call:
                        self.AI.attack_call.cancel()
                        self.AI.attack_call=None
                self.AI.attacking=False
                return
        
        def on_connect(self):
            if self.AI:
                return connection.on_connect(self)
            max_players = min(32, self.protocol.max_players)
            protocol = self.protocol
            if len(protocol.connections) + len(protocol.bots) > max_players:
                if len(self.protocol.bots):
                        protocol.bots[-1].disconnect()
                else:
                        self.disconnect()
                        return
            connection.on_connect(self)

        def on_disconnect(self):
            for bot in self.protocol.bots:
                if bot.AI.aim_at is self:
                    bot.AI.aim_at = None
                if bot.AI.Follow is self:
                    bot.AI.Follow=None
            connection.on_disconnect(self)
        
        def on_kill(self, killer, type, grenade):
            if not self.AI:
                return connection.on_kill(self,killer,type,grenade)
            self.cancel_attack()
            for bot in self.protocol.bots:
                if bot.AI.aim_at is self:
                    bot.AI.aim_at = None
            self.AI.aim_at=None
            return connection.on_kill(self, killer, type, grenade)

        def on_hit(self,hit_amount,player,type,grenade=None):
                if player and player.player_id!=self.player_id and player.AI and not self.AI:
                        player.AI.aim_at=self
                return connection.on_hit(self,hit_amount,player,type,grenade)

        def _connection_ack(self):
                if self.AI:
                        return
                return connection._connection_ack(self)
        
        def _send_connection_data(self):
            if self.AI:
                if self.player_id is None:
                    self.player_id = self.protocol.player_ids.pop()
                return
            connection._send_connection_data(self)
        
        def timer_received(self, value):
            if self.AI:
                return
            connection.timer_received(self, value)
        
        def send_loader(self, loader, ack = False, byte = 0):
            if self.AI:
                return
            return connection.send_loader(self, loader, ack, byte)

        def get_dirpos(self):
                dir=self.world_object.orientation
                _dir=Vertex3(copysign(1,dir.x) if abs(dir.x)>.5 else 0,copysign(1,dir.y) if abs(dir.y)>.5 else 0,0)
                return self.world_object.position+_dir

        def on_chat(self,msg,global_chat=False):
                _msg=msg
                msg=msg.lower()
                BoolAction=bool(not('don\'t' in msg or 'dont' in msg or 'no' in msg or 'not' in msg))
                Players=[]
                for player in list(self.protocol.players.values()):
                        if not player.AI:
                                continue
                        if player.name.lower() in msg or 'bots' in msg:
                                Players.append(player)
                if not len(Players):
                        return connection.on_chat(self,_msg,global_chat)
                if 'follow' in msg and self.admin:
                        for player in Players:
                                if player.team.id!=self.team.id:
                                        continue
                                player.AI.Follow=self if BoolAction else None
                                if BoolAction:
                                        player.AI.Commands|=AI_COMMANDS_FOLLOW
                                else:
                                        player.AI.Commands&=~AI_COMMANDS_FOLLOW
                                Scheduler(self.protocol).call_later(.5,player.say_chat,
                                'I will %s follow you %s' % (('' if BoolAction else 'not'),self.name),True)
                if 'stay' in msg and self.admin:
                        for player in Players:
                                if player.AI:
                                        if BoolAction:
                                                player.AI.Commands|=AI_COMMANDS_STAY
                                        else:
                                                player.AI.Commands&=~AI_COMMANDS_STAY
                                        Scheduler(self.protocol).call_later(.5,player.say_chat,
                                        'Ok, I %s stay here' % ('will' if BoolAction else 'won\'t'),True)
                return connection.on_chat(self,_msg,global_chat)

        def send_map(self,data=None):
                if self.AI:
                        return
                return connection.send_map(self,data)

        def say_chat(self,text,send_global=False):
                if self.deaf:
                        return
                chat_message.chat_type=CHAT_ALL if send_global else CHAT_TEAM
                chat_message.player_id=self.player_id
                lines=textwrap.wrap(text,MAX_CHAT_SIZE-1)
                for line in lines:
                        chat_message.value=line
                        self.protocol.send_contained(chat_message)
                return

        def _can_see(self,x,y,z):
                if isnan(x) or isnan(y) or isnan(z):
                        print(('ERROR: %d %d %d CONTAINS NaN!' % (x, y, z)))
                        return
                pos=self.world_object.position
                if isnan(pos.x) or isnan(pos.y) or isnan(pos.z):
                        print(('ERROR: BOT POSITION %d %d %d CONTAINS NaN!' % pos.get()))
                        return
                line=cube_line(x,y,z,*pos.get())
                get_solid=self.protocol.map.get_solid
                for p in line:
                        if not get_solid(*p):
                                continue
                        return False
                return True

        def send_contained(self,contained,sequence=False):
                if self.AI:
                        return
                return connection.send_contained(self,contained,sequence)

        def loader_received(self,loader):
                if self.AI:
                        return
                return connection.loader_received(self,loader)

    return BotProtocol, BotConnection
