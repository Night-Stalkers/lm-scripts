# -*- coding: utf-8 -*-
"""
Advanced Battle Bot System (v55)

basicbot をもとに改造　20190130 yuyasato

original comment was moved to end of sclipt

"""

import datetime
from random import uniform, randrange,gauss,choice,triangular,shuffle
from enet import Address
from twisted.internet.reactor import seconds, callLater
from pyspades.protocol import BaseConnection
from pyspades.contained import BlockAction, InputData, SetTool, WeaponInput, SetColor, ChatMessage, GrenadePacket
from pyspades.world import Grenade
from pyspades.common import coordinates, to_coordinates, Vertex3
from pyspades.collision import vector_collision
from pyspades.constants import *
from piqueserver.commands import admin, command, get_player, get_team
from copy import copy
from pyspades import contained as loaders
from pyspades.packet import load_client_packet
from pyspades.bytes import ByteReader, ByteWriter
from pyspades.contained import *
from pyspades.server import *
from pyspades.common import *
from math import floor,sin,cos,degrees,radians,atan2,acos,asin,atan
weapon_reload = loaders.WeaponReload()
input_data = InputData()
weapon_input = WeaponInput()
set_color = SetColor()
set_tool = SetTool()
grenade_packet = GrenadePacket()

BOT_IN_BOTH     = True	   #trueなら両チームに入り、チームバランスをキープする
BOT_ADD_PATTERN = 1		   #0:常に一定数（一定数固定）, 1:常に一定数(バランス優先で微増減) 2:人間とbotの和が常に一定数 3:人間一人につき一定数
BOT_ADD_NUM		= 24 	   #「一定数」の値
LITE_MODE       = False    # 軽量粗雑計算
LV_AUTO_ADJUST  = 0       # レベル自動調整モード 0:off 1:human vs bot   2:blue vs green 3:both human/bot and blue/green
BOT_NUM_NAME    = True    # 個体名をID番号名にするか
CPU_LV          = [16,12]   # BOTの強さレベル　平均値とそこから＋－いくらまで分散
BOTMUTE         = True    # bot chat off
DANSA_CALC_NUM  = 5        #段差何段分計算するか
KEIRO_TANSAKU_NUM = 5      #壁回避時経路探索数
ENEMY_SEARCH_FPS  = 4
BOT_UPDATE_RATE   = 1      #60/n FPS （整数）
LVCHANGE_RECONNECT= False  #レベル変更時にリコネクトするか(self.nameにレベル値を入れたい場合)
LV_PRINT = False 			#レベル変化時にprint

DEBUG_VIRTUAL_HIT=False # デバッグ用仮想命中判定

AI_mode = 1	#用途設定

# 0: TOW
# 1: TDM
# 2: arena
# 3: vsBOT(all)
# 4: vsBOT(alone)
# 5: vsBOT(intel)
# 6: DOMINE
# 7: kabadi


if LITE_MODE:
    DANSA_CALC_NUM=2
    KEIRO_TANSAKU_NUM = 2
    ENEMY_SEARCH_FPS  = 4
    BOT_UPDATE_RATE   = 2      #60/n FPS （整数）


### vvvv DO NOT CHANGE HERE vvvv ###
TOWmode = False
TDMmode = False
ARENAmode = False
VSBOTmode = False
VSBOT_alone=False
VSBOT_INTEL=False
DOMINE_FULLmode=False
KABADI_mode=False
### ^^^^ DO NOT change here ^^^^ ###

if AI_mode == 0:
    TOWmode = True
elif AI_mode == 1:
    TDMmode = True
elif AI_mode == 2:
    ARENAmode = True
elif AI_mode == 3:
    BOT_ADD_PATTERN=3
    BOT_ADD_NUM = 8
    VSBOTmode = True
    VSBOT_alone = False
elif AI_mode == 4:
    BOT_ADD_PATTERN=3
    BOT_ADD_NUM = 8
    VSBOTmode = True
    VSBOT_alone = True
elif AI_mode == 5:
    BOT_ADD_PATTERN=3
    BOT_ADD_NUM = 8
    VSBOTmode = True
    VSBOT_INTEL = True
elif AI_mode == 6:
    DOMINE_FULLmode = True
elif AI_mode==7:
    KABADI_mode=True

ARENA_JUNKAI_SECT = 7

#vs bot stage level
LV=[[5,5],[20,10],[30,10],[30,20],[40,10],[35,25],[45,15],[50,10],[60,10],[55,45],[65,35],[75,25],[85,15],[99,1],[99,1],[100,1],[100,1]]

if VSBOTmode or VSBOT_alone:
    BOTMUTE = True
    BOT_IN_BOTH=False
    BOT_ADD_NUM = 10
    BOT_ADD_PATTERN=3
    BOT_NUM_NAME=True
    LV_AUTO_ADJUST  = 0  
    LITE_MODE=True


@command('addbot', admin_only = True)		#BOT追加コマンド 例 : /addbot 5 green
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
        if not bot:
            return "Added %s bot(s)" % i
    return "Added %s bot(s)" % amount

@command('botmute', admin_only = True)		#BOTmute
def botmute(connection):
    global BOTMUTE
    BOTMUTE = not BOTMUTE
    return "BOTMUTE %s" % BOTMUTE

@command('addmode', admin_only = True)		#BOT_ADD_PATTERN
def addmode(connection, num):
    global BOT_ADD_PATTERN
    BOT_ADD_PATTERN = int(num)
    return "BOT_ADD_PATTERN %s" % BOT_ADD_PATTERN

@command('botnum', admin_only = True)		#BOT_ADD_NUM
def botnum(connection, num):
    global BOT_ADD_NUM
    BOT_ADD_NUM = int(num)
    return "BOT_ADD_NUM %s" % BOT_ADD_NUM

@command('stg', admin_only = True)		#stage level
def stage_select(connection,value):
    connection.protocol.stage_level = int(value)
    connection.protocol.send_chat("stage selected : STAGE %d"%connection.protocol.stage_level)
    connection.protocol.stage_level-=1

@command('toggleai', admin_only = True)	#BOTのAIを停止・回復させるコマンド
def toggle_ai(connection):
    protocol = connection.protocol
    protocol.ai_enabled = not protocol.ai_enabled
    if not protocol.ai_enabled:
        for bot in protocol.bots:
            bot.flush_input()
    state = 'enabled' if protocol.ai_enabled else 'disabled'
    protocol.send_chat('AI %s!' % state)
    protocol.irc_say('* %s %s AI' % (connection.name, state))

@command('cpulv', admin_only = True)		#CPUlevel
def cpulv(connection,mean=-1,pm=5):
    if mean<0:
        cpulv=connection.protocol.teamcpulv
        return "%s(Lv%d+-%d) %s(Lv%d+-%d)"%(connection.protocol.blue_team.name,cpulv[0][0],cpulv[0][1],connection.protocol.green_team.name,cpulv[1][0],cpulv[1][1])		
    mean=int(mean)
    pm=int(pm)
    if pm<1:pm=1
    if 0<mean<100:
        global CPU_LV
        CPU_LV=[mean,pm]
        connection.protocol.teamcpulv=[[mean,pm],[mean,pm]]
        return "CPU Lv  %s - %s" %(mean+pm,mean-pm)
    else:
        return "error (Lv should be set in 1-99)"

@command('lv')		#CPUlevel check
def lv(connection,player=None):
    protocol = connection.protocol
    if player == "all":
        for bot in protocol.bots:
            contained = ChatMessage()
            global_message = contained.chat_type == CHAT_ALL
            contained.chat_type = [CHAT_TEAM, CHAT_ALL][int(global_message)]
            contained.value = "Lv.%d"%int(bot.cpulevel*100)
            contained.player_id = bot.player_id
            callLater(bot.player_id/1.5,bot.protocol.broadcast_contained,contained)
        return
    if player is not None:
        player = get_player(protocol, player)
    else:
        return "ERROR : command   /lv [name or #id]"
    if player.local:
        return "%s is BOT Lv.%d"%(player.name, player.cpulevel*100.0)
    else:
        return "player '%s' is not BOT"%player.name

@command('lvset', admin_only = True)		#CPUlevel check
def lvset(connection,player=None, value=None):
    if value == None:
        return "error"
    value = int(value)
    protocol = connection.protocol
    if player is not None:
        player = get_player(protocol, player)
    else:
        return "ERROR : command   /lv [name or #id] value"
    if player.local:
        player.cpulevel = value/100.0
        return "%s is BOT Lv.%d"%(player.name, player.cpulevel*100.0)
    else:
        return "player '%s' is not BOT"%player.name


@command('allref', admin_only = True)		#all bot dissconect and enter again
def allreflesh(connection):
    for botn in list(connection.protocol.players.values()):
        if botn.local:
            callLater(0.01,botn.disconnect)
    callLater(0.1,connection.protocol.bot_num_adjust,True)
    return "all bot refleshed"

@command('ksk')			#arena kasoku
def ksk(connection):
    connection.protocol.arena_kasoku = not connection.protocol.arena_kasoku 
    return "kasoku mode %s"%connection.protocol.arena_kasoku

@command('ksk2')			#arena kasoku
def ksk2(connection):
    connection.protocol.ksk2 = not connection.protocol.arena_kasoku 
    return "kasoku2 mode %s"%connection.protocol.arena_kasoku

@command('debughit', admin_only = True)		#DEBUG_VIRTUAL_HIT
def debughit(connection):
    global DEBUG_VIRTUAL_HIT
    DEBUG_VIRTUAL_HIT = not DEBUG_VIRTUAL_HIT
    return "DEBUG_VIRTUAL_HIT %s" % DEBUG_VIRTUAL_HIT

LINE_COLOR_MAIN=(255,0,0)
LINE_COLOR_SUB=(255,255,0)
LINE_X = 470

TENTNUM = 3



class LocalPeer:
    #address = Address(None, 0)
    address = Address(bytearray('255.255.255.255', 'utf-8'), 0)
    roundTripTime = 0.0
    
    def send(self, *arg, **kw):
        pass
    
    def reset(self):
        pass


def apply_script(protocol, connection, config):
    class BotProtocol(protocol):
        if VSBOTmode:
            if VSBOT_INTEL:
                game_mode = CTF_MODE
            else:
                game_mode = TC_MODE
            
        gamewon = False
        bots = None
        ai_enabled = True
        bot_damage = True
        bullet_visual = False
        BOT_junkai_route = []
        one_sec = 0
        arena_kasoku=False
        ksk2=False
        tmr_start = 0
        kill_score=0
        levelchange=[0,0]
        reflesh_bot=False
        teamcpulv=[copy(CPU_LV),copy(CPU_LV)] #blue green
        noise_blue=[]
        noise_green=[]
        exp_position=[]		
        tdm_tgt_calc = 100
        best_friends_pos = [Vertex3(255,255,0),Vertex3(255,255,0)]
        stage_level = 0
        bot_adjusting=False
        disconnect_suru=[False,False]
        addbot_taiki=[False,False]
        adj_calling=False

        bot_level_average=50
        bot_level_adjust=[0,0]
        bot_level_average_change=0
    
        def kasoku(self):
            if ARENAmode:
                human_alive=False
                for player in list(self.players.values()):
                    if not player.local:
                        if player.hp is not None and player.hp > 0:
                            human_alive=True
                            break
                if not human_alive:
                    blue_saijaku=[None, 10000]
                    blue_saituyo=[None, 0]
                    green_saijaku=[None, 10000]
                    green_saituyo=[None, 0]
                    blue_sum = green_sum = 0
                    for player in self.blue_team.get_players():
                        if player.local:
                            if player.hp is not None and player.hp > 0:
                                if player.aim_at is None or self.ksk2:		
                                    kanousei = player.hp * player.cpulevel
                                    kekka = uniform(0,kanousei)
                                    blue_sum+=kekka
                                    if kekka<=blue_saijaku[1]:
                                        blue_saijaku = [player, kekka]	
                                    if kekka>=blue_saituyo[1]:
                                        blue_saituyo = [player, kekka]	
                    for player in self.green_team.get_players():
                        if player.local:
                            if player.hp is not None and player.hp > 0:
                                if player.aim_at is None or self.ksk2:		
                                    kanousei = player.hp * player.cpulevel
                                    kekka = uniform(0,kanousei)
                                    green_sum+=kekka
                                    if kekka<=green_saijaku[1]:
                                        green_saijaku = [player, kekka]	
                                    if kekka>=green_saituyo[1]:
                                        green_saituyo = [player, kekka]
                    if blue_saijaku[0] is not None and blue_saituyo[0] is not None and green_saijaku[0] is not None and green_saituyo[0] is not None:
                        self.send_chat("remain is only bot. calculating kill result...")
                        if blue_sum>green_sum or (blue_sum==green_sum and random.random()>0.5):
                            green_saijaku[0].kill(blue_saituyo[0], WEAPON_KILL)
                        else:
                            blue_saijaku[0].kill(green_saituyo[0], WEAPON_KILL)

        def add_bot(self, team):
            self.addbot_taiki[team.id]=False
            if len(self.connections) + len(self.bots) >= 32:
                return None
            bot = self.connection_class(self, None)
            bot.join_game(team)
            self.bots.append(bot)
            return bot

        def arena_begun(self):
            for bot in self.bots:
                bot.has_arena_tgt = False

        def line_draw(self):
            x = LINE_X
            for y in range(512):
                for z in range(self.map.get_z(x,y),64):
                    if self.map.get_solid(x,y,z):
                        if self.map.is_surface(x,y,z):
                            self.map.remove_point(x,y,z)
                            self.map.set_point(x, y, z, LINE_COLOR_MAIN)
            for y in range(512):
                for z in range(self.map.get_z(x+1,y),64):
                    if self.map.get_solid(x+1,y,z):
                        if self.map.is_surface(x+1,y,z):
                            self.map.remove_point(x+1,y,z)
                            self.map.set_point(x+1, y, z, LINE_COLOR_SUB)
            for y in range(512):
                for z in range(self.map.get_z(x-1,y),64):
                    if self.map.get_solid(x-1,y,z):
                        if self.map.is_surface(x-1,y,z):
                            self.map.remove_point(x-1,y,z)
                            self.map.set_point(x-1, y, z, LINE_COLOR_SUB)

        def flag_set_pos(self,flag,pos):
            if flag is not None:
                flag.player = None
                flag.set(*pos)
                flag.update()

        def flag_reset(self):
            x=30
            y=uniform(0.1,0.9)*512
            z = self.map.get_z(x,y)
            pos = (x,y,z)
            self.flag_set_pos(self.blue_team.flag, (0,0,0))
            self.flag_set_pos(self.green_team.flag, pos)
    
        def on_game_end(self):
            if VSBOT_INTEL:
                self.flag_reset()
            return protocol.on_game_end(self)

        def get_cp_entities(self):
            entities=[]
            tentpos=[]
            for i in range(TENTNUM):
                entity=Territory(i,self,0,0,0)
                entity.team=None
                entities.append(entity)
            return entities

        def bot_think(self):
            for bot in self.bots:
                if bot.world_object != None:
                    if bot.hp is not None and bot.hp > 0:
                        if self.loop_count % int(UPDATE_FPS / ENEMY_SEARCH_FPS) == bot.player_id % int(UPDATE_FPS / ENEMY_SEARCH_FPS) :
                            callLater(bot.player_id/60,bot.find_nearest_player)
                        if self.loop_count % int(BOT_UPDATE_RATE) ==  bot.player_id%int(BOT_UPDATE_RATE):
                            callLater(bot.player_id/60,bot.update)
        
        def on_world_update(self):
            if self.one_sec>=UPDATE_FPS: # every 1 second
                for team in [self.blue_team,self.green_team]:
                    if self.disconnect_suru[team.id]:
                        if self.bot_bottikick(team):
                            self.disconnect_suru[team.id] = False
                self.one_sec=0
                if self.bots:
                    for bot in self.bots:
                        if bot.world_object is not None:
                            if bot.world_object.position:
                                if bot.hp is not None and bot.hp > 0:
                                    bot.on_position_update()
            self.one_sec+=1

            botonly = True
            for player in list(self.players.values()):
                if not player.local:
                    botonly = False
                    break
                    
            if not botonly:
                if self.bots and self.ai_enabled:
                    self.bot_think()
                if ARENAmode:
                    if self.arena_kasoku:
                        self.kasoku()
                if VSBOTmode:
                    botonly = True
                    for player in list(self.players.values()):
                        if not player.local:
                            botonly = False
                            break
                    player=None
                    plnum = 0
                    plclr = 0
                    if VSBOT_INTEL:
                        flagger = self.green_team.flag.player
                        if flagger is not None:
                            if flagger.world_object:
                                if flagger.hp is not None and flagger.hp > 0 and  flagger.world_object.position.x > LINE_X and not self.gamewon:
                                    flagger.gamewin()
                    for player in self.blue_team.get_players():
                        plnum +=1
                        if player.world_object:
                            if player.hp is not None and player.hp > 0 and  player.world_object.position.x > LINE_X and not self.gamewon:
                                if VSBOT_alone:
                                    player.gamewin()
                                else:
                                    plclr+=1
                    if not VSBOT_alone:
                        if plnum > 0 and plnum == plclr and not self.gamewon:
                            player.gamewin()			
                    if not botonly and player is not None and not self.gamewon:
                        if self.bots and self.ai_enabled:
                            self.bot_think()

                if TDMmode:
                    if self.tdm_tgt_calc <= 0:
                        self.tdm_tgt_calc = 100
                        best_friends_blue = None
                        best_friends_blue_dist = 99999
                        for player in self.blue_team.get_players():
                            if player.world_object_alive_onpos():
                                dist=0
                                for friend in player.team.get_players():
                                    if friend.world_object_alive_onpos():
                                        dist += player.distance_calc(player.world_object.position.get(),friend.world_object.position.get())
                                if dist<best_friends_blue_dist:
                                    best_friends_blue_dist=dist
                                    best_friends_blue = player
                        best_friends_green = None
                        best_friends_green_dist = 99999
                        for player in self.green_team.get_players():
                            if player.world_object_alive_onpos():
                                dist=0
                                for friend in player.team.get_players():
                                    if friend.world_object_alive_onpos():
                                        dist += player.distance_calc(player.world_object.position.get(),friend.world_object.position.get())
                                if dist<best_friends_green_dist:
                                    best_friends_green_dist=dist
                                    best_friends_green = player
                        if best_friends_blue is not None:
                            best_friends_blue = best_friends_blue.world_object.position
                        else:
                            best_friends_blue = Vertex3(255,255,0)
                        if best_friends_green is not None:
                            best_friends_green = best_friends_green.world_object.position
                        else:
                            best_friends_green = Vertex3(255,255,0)
                        self.best_friends_pos = [best_friends_blue, best_friends_green]
                    self.tdm_tgt_calc-=1
            else:
                self.tmr_start = seconds()
                self.kill_score = 0			
            protocol.on_world_update(self)

        def arena_route_get(self):
            extensions = self.map_info.extensions
            if 'BOT_junkai_route' in extensions:
                self.BOT_junkai_route = extensions['BOT_junkai_route']
        
        def on_map_change(self, map):
            if VSBOTmode:
                if VSBOT_INTEL:
                    self.flag_reset()

                self.green_team.locked = True
                if self.stage_level<15:
                    self.stage_level+=1
                self.teamcpulv = [LV[self.stage_level],LV[self.stage_level]]
                self.gamewon = False
            elif LV_AUTO_ADJUST==2:
                self.teamcpulv = [copy(CPU_LV),copy(CPU_LV)]
                self.bot_level_adjust=[0,0]
                self.levelchange=[0,0]
            elif LV_AUTO_ADJUST==3:
                self.teamcpulv = [[self.bot_level_average, CPU_LV[1]],[self.bot_level_average, CPU_LV[1]]]
                self.bot_level_adjust=[0,0]
                self.levelchange=[0,0]
            if ARENAmode:
                callLater(1, self.arena_route_get)
            self.bots = []
            protocol.on_map_change(self, map)
            if VSBOTmode:
                self.line_draw()
        
        def on_map_leave(self):
            for bot in self.bots[:]:
                bot.disconnect()
            self.bots = None
            protocol.on_map_leave(self)

        def bot_num_adjust(self,start=False):
            if not (self.disconnect_suru == [False,False] and self.addbot_taiki==[False,False]):
                return
            if self.bot_adjusting or start:
                if not self.adj_calling:
                    self.adj_calling=True
                    callLater(0.001, self.bot_num_adjust_do)

        def bot_num_adjust_do(self):
            self.adj_calling=False
            self.bot_adjusting = True
            blue, green = self.bot_num_adjust_calc()
            if blue == 0 and green == 0:
                self.bot_adjusting = False
            else:
                if blue>0:
                    self.addbot_taiki[0]=True
                    callLater(0.01, self.add_bot,self.blue_team)
                if green>0:
                    self.addbot_taiki[1]=True
                    callLater(0.01, self.add_bot,self.green_team)
                if blue<0:
                    if not self.bot_bottikick(self.blue_team):
                        self.disconnect_suru[0] = True
                if green<0:
                    if not self.bot_bottikick(self.green_team):
                        self.disconnect_suru[1] = True

        def bot_bottikick(self, team):
            yobi = None
            for bot in team.get_players():
                if bot.local and bot.world_object:
                    if bot.hp is None or bot.hp <= 0:
                        bot.disconnect() #死んでる奴いたらそいつ即刻排除
                        return True
                    if bot.aim_at==None:
                        yobi = bot	#交戦中ではない奴がいたら次点で排除
            if yobi != None:
                yobi.disconnect() 
                return True
            return False

        def bot_num_adjust_calc(self):
            blue_human, blue_bot, green_human, green_bot = self.count_human_bot()
            if BOT_ADD_PATTERN==0:#完全固定
                if BOT_IN_BOTH:
                    blue = blue_human + blue_bot
                    green = green_human + green_bot
                    balance = blue-green
                    bot_over = blue_bot + green_bot - BOT_ADD_NUM
                    if bot_over == 0: #bot数問題無し
                        if balance >=2:#青多すぎ
                            return -1,1
                        elif balance <=-2:#緑多すぎ
                            return 1,-1
                        else:#チームバランス問題無し+-1は許容
                            return 0,0
                    else:
                        if bot_over >1:#bot 2ijou多すぎ
                            return -1,-1
                        elif bot_over > 0:#bot 多すぎ
                            return -1,0
                        elif bot_over < -1:#bot 2ijou少ない
                            return 1,1
                        elif bot_over < 0:#bot 少ない
                            return 1,0
                else:
                    if green_bot > BOT_ADD_NUM: #bot多すぎ
                        return 0,-1
                    elif green_bot < BOT_ADD_NUM: #bot少ない
                        return 0,1
                    else:#bot数問題無し
                        return 0,0
            elif BOT_ADD_PATTERN==1:#条件付き固定
                if BOT_IN_BOTH:
                    blue = blue_human + blue_bot
                    green = green_human + green_bot
                    botnum_over=blue_bot + green_bot - BOT_ADD_NUM
                    balance = blue-green
                    if balance >=1:#青多すぎ
                        if botnum_over>0: #bot数多い
                            return -1,0
                        elif botnum_over<0:#bot少ない	
                            return 0,1
                        else:
                            if balance>1:
                                return -1,1
                            else:
                                return 0,1
                    elif balance<=-1: #green ooi
                        if botnum_over>0: #bot数多い
                            return 0,-1
                        elif botnum_over<0:#bot少ない	
                            return 1,0
                        else:
                            if balance<-1:
                                return 1,-1
                            else:
                                return 1,0
                    else:
                        if botnum_over>1:
                            return -1,-1
                        elif botnum_over<-1:
                            return 1,1
                        else:
                            return 0,0

                else:
                    if green_bot > BOT_ADD_NUM: #bot多すぎ
                        return 0,-1
                    elif green_bot < BOT_ADD_NUM: #bot少ない
                        return 0,1
                    else:#bot数問題無し
                        return 0,0
            elif BOT_ADD_PATTERN==2: #bot + human合計値固定
                blue = blue_human + blue_bot
                green = green_human + green_bot
                botnum_over=blue + green - BOT_ADD_NUM
                if BOT_IN_BOTH:
                    balance = blue-green
                    if balance >0:#青多すぎ
                        if botnum_over>0: #bot数多い
                            return -1,0
                        elif botnum_over<0:#bot少ない	
                            return 0,1
                        else:
                            if balance>1:
                                return -1,1
                            else:
                                return 0,0
                    elif balance<0: #green ooi
                        if botnum_over>0: #bot数多い
                            return 0,-1
                        elif botnum_over<0:#bot少ない	
                            return 1,0
                        else:
                            if balance<-1:
                                return 1,-1
                            else:
                                return 0,0
                    else:
                        if botnum_over>1:
                            return -1,-1
                        elif botnum_over>0: #bot数多い
                            return 0,-1
                        elif botnum_over<-1:
                            return 1,1
                        elif botnum_over<0:#bot少ない	
                            return 0,1
                        else:
                            return 0,0
                else:#この状況ある？
                    if botnum_over >0: #bot多すぎ
                        return 0,-1
                    elif botnum_over < 0: #bot少ない
                        return 0,1
                    else:#bot数問題無し
                        return 0,0
            elif BOT_ADD_PATTERN==3: #比率
                human = blue_human + green_human
                blue = blue_human + blue_bot
                green = green_human + green_bot
                bot = human * BOT_ADD_NUM
                botnum_over=blue_bot + green_bot - bot
                if BOT_IN_BOTH:
                    balance = blue-green
                    if balance >=1:#青多すぎ
                        if botnum_over>0: #bot数多い
                            return -1,0
                        elif botnum_over<0:#bot少ない	
                            return 0,1
                        else:
                            if balance>1:
                                return -1,1
                            else:
                                return 0,0
                    elif balance<=-1: #green ooi
                        if botnum_over>0: #bot数多い
                            return 0,-1
                        elif botnum_over<0:#bot少ない	
                            return 1,0
                        else:
                            if balance<-1:
                                return 1,-1
                            else:
                                return 0,0
                    else:
                        if botnum_over>1:
                            return -1,-1
                        elif botnum_over>0: #bot数多い
                            return 0,-1
                        elif botnum_over<-1:
                            return 1,1
                        elif botnum_over<0:#bot少ない	
                            return 0,1
                        else:
                            return 0,0
                else:
                    if botnum_over > 0: #bot多すぎ
                        return 0,-1
                    elif botnum_over < 0: #bot少ない
                        return 0,1
                    else:#bot数問題無し
                        return 0,0

        def count_human_bot(self):	#spectate は除く
            blue_human  = 0
            blue_bot    = 0
            green_human = 0
            green_bot   = 0
            for player in self.blue_team.get_players():
                if player.local:
                    blue_bot+=1
                else:
                    blue_human+=1
            for player in self.green_team.get_players():
                if player.local:
                    green_bot+=1
                else:
                    green_human+=1
            return blue_human, blue_bot, green_human, green_bot
    
    class BotConnection(connection):
        has_intel = False
        aim = None
        aim_at = None
        input = None
        bot_jump = None
        cpulevel=1
        jumptime=0
        xoff_tebure=0
        yoff_tebure=0
        vel=0
        jisatu=0
        digtime=0
        ikeru=[0,0,0,0]
        toolchangetime =0
        last_fire = 0
        sprinttime=0
        target_direction=[1,0,0]
        smg_shooting=0
        aim_quit = 100
        damaged_block = []
        front_rcog = [[-1]*64, [-1]*64] # [R,L]
        long_recg=0
        crouchinputed = 0
        ave_d_theta=[0]*30
        ave_d_phi=[0]*30
        pre2ori_theta=0
        pre2ori_phi=0

        has_arena_tgt = False
        dir_arena_tgt = 1
        num_arena_tgt = 0
        route_arena_tgt=0
        jikuu_arena_tgt=0
        z_add=0
        enemy_lost=None

        battle_distance = 60

        xoff_okure=0
        yoff_okure=0

        gre_avoiding=False
        gre_ignore=False

        arena_route_destination=0

        next_fire_time=1
        assigned_position=None
        ois = False
        positive_attacker=True

        avoiding_danger_gre=None

        grenade_keep=0
        grenade_pinpull=0
        grenade_keeping=False
        grenade_throw_orienation=1,0,0
        keepinggrephimax=False
        keepinggreoffset=0
        stucking=0
        enemy_lost_temp=None
        stopmotion = False
        battlecrouching=0

        _turn_speed = None
        _turn_vector = None

        large_omega_x=0
        large_omega_y=0

        movezure_x=0
        movezure_y=0
        movezure_z=0
        omega=0
        fireinput=0
        reloadfin=0
        tamakazu=30
        reload_wait=0

        def _get_turn_speed(self):
            return self._turn_speed
        def _set_turn_speed(self, value):
            self._turn_speed = value
            self._turn_vector = Vertex3(cos(value), sin(value), 0.0)
        turn_speed = property(_get_turn_speed, _set_turn_speed)
        
        def __init__(self, protocol, peer):
            if peer is not None:
                return connection.__init__(self, protocol, peer)
            self.local = True
            connection.__init__(self, protocol, LocalPeer())
            self.on_connect()
            #~ self.saved_loaders = None
            self._send_connection_data()
            self.send_map()
            
            self.aim = Vertex3()
            self.target_orientation = Vertex3()
            self.turn_speed = 0.15 # rads per tick
            self.input = set()
            self.color = (0xDF, 0x00, 0xDF)
            self.bot_set_color(self.color)
        
        def join_game(self, team):
            self.team = team
            teamcpulv=self.protocol.teamcpulv[self.team.id]	
            sita= min(99,max(0,teamcpulv[0]-teamcpulv[1]))
            ue  = min(100,max(1,teamcpulv[0]+teamcpulv[1]))
            self.cpulevel=uniform(sita/100.0,ue/100.0)
            
            if BOT_NUM_NAME:
                name = 'B-%s [LV.%s]' % (str(self.player_id), str(int(self.cpulevel*100)))# '%s %s' % (name,str(int(self.cpulevel*100)) )  # 'BOT%s [LV.%s]' % (str(self.player_id), str(int(self.cpulevel*100)))	#'%s %s' % (name,str(self.player_id + 1))
            else:
                namelist= [
                    'The Zero',		#0
                    'Itti',			#1
                    'Huta',			#2
                    'Mii',			#3
                    'SISI',			#4
                    'Go is God',	#5
                    'rock',			#6
                    '007',			#7
                    'hatti',		#8
                    'Qtaro-',		#9
                    'juubee',		#10
                    'inazuma11',	#11
                    'nekomimi',		#12
                    'golgo13',		#13	
                    'simesaba',		#14
                    'OMUSUBI',		#15
                    'kikumon*',		#16
                    'jhon',			#17
                    'bipei',		#18
                    'otimpo',		#19
                    'aeria',		#20
                    'gapoi',		#21
                    'niwaka',		#22
                    'moukin',		#23
                    'isitubute',	#24
                    'nijugorou',	#25
                    'BOB',			#26
                    'nubou',		#27
                    'tako',			#28
                    'sutein',		#29
                    'osoba',		#30
                    'oketu'	,		#31
                    'The LAst']		#32
                name = namelist[self.player_id]
            nameok=True
            for player in list(self.protocol.players.values()):
                if player.name == name:
                    nameok=False
                    break
            if not nameok:
                name += str(self.player_id) 
            self.name = name
            self.bot_property()
            self.protocol.players[self.player_id] = self
            self.on_login(self.name)
            self.spawn()

        def bot_property(self):
            weapon_rdm = random.random()
            self.z_add= gauss(0.3,0.5/3) #頭の中心じゃなくて若干下とか胴狙いとか
            self.battlecrouching=False
            if weapon_rdm>0.4:
                self.set_weapon(RIFLE_WEAPON, True)
                self.battle_distance = uniform(30,110)
                if random.random()<0.2:
                    self.battlecrouching=True
                if weapon_rdm>0.7 or random.random()<self.cpulevel:
                    self.z_add= gauss(0.1,0.2*(1-self.cpulevel)/3)			
            elif weapon_rdm>0.15:
                self.set_weapon(SMG_WEAPON, True)
                self.battle_distance = uniform(10,80)
                if random.random()<self.cpulevel or random.random()<0.2:
                    self.battlecrouching=True
                if weapon_rdm>0.3:
                    self.z_add= gauss(0.5,0.2*(1-self.cpulevel)/3)	#SMGなら胴狙いが多いね
                elif random.random()<self.cpulevel:		
                    self.z_add= gauss(0.1,0.2*(1-self.cpulevel)/3)	#玄人はSMGでもHS狙い	
            else:
                self.set_weapon(SHOTGUN_WEAPON, True)
                self.battle_distance = uniform(10,60)
                if random.random()<0.1:
                    self.battlecrouching=True
                if weapon_rdm>0.05:
                    self.z_add= gauss(0.7,0.3*(1-self.cpulevel)/3)	
            if ARENAmode:self.battle_distance/=2		
            if ARENAmode or TDMmode or VSBOTmode:
                self.positive_attacker= True	#目標点よりプレイヤーを優先して攻撃
            else:
                self.positive_attacker=random.random()>0.1 #Falseなら攻撃受けない限り索敵しないで目標点に突撃
        
        def disconnect(self, data = 0):
            if self:
                if not self.local:
                    callLater(0.1,self.protocol.bot_num_adjust,True)
                    return connection.disconnect(self)
                if self.disconnected:
                    return
                if self in self.protocol.bots:
                    self.protocol.bots.remove(self)
                self.disconnected = True
                self.on_disconnect()
        
        def find_nearest_player(self):
            if self.positive_attacker == False:
                return
            if self.world_object_alive_onpos():
                pos = self.world_object.position
                player_distances = []
                ox,oy,oz = self.world_object.orientation.get()
                for player in self.team.other.get_players():
                    if player.world_object:
                        if player.hp is not None and player.hp > 0:
                            epos=player.world_object.position
                            if vector_collision(pos, epos, 60+ self.cpulevel*65):
                                if self.canseeY(pos,epos)>=0:
                                    ex,ey,ez = epos.get()
                                    px,py,pz = pos.get()
                                    nx,ny,nz = ex-px, ey-py, ez-pz
                                    dist = (nx**2+ny**2+nz**2)**0.5
                                    nasukaku=1
                                    if dist>3:
                                        nx/=dist
                                        ny/=dist
                                        nz/=dist
                                        naiseki = nx*ox + ny*oy + nz*oz
                                        if naiseki>1:
                                            naiseki=1
                                        if naiseki<-1:
                                            naiseki=-1
                                        nasukaku = degrees(acos(naiseki))
                                    if max(self.cpulevel*100,45)>nasukaku or dist<=3:
                                        player_distances.append(((epos - pos), player))
                if len(player_distances) > 0:
                    nearestindex = min(list(range(len(player_distances))), key=lambda i: abs(player_distances[i][0].length_sqr()))
                    self.aim_at = player_distances[nearestindex][1]
                    self.aim_quit = 70
                else:
                    self.aim_quit-=1

        def world_object_alive_onpos(self):
            if self:
                if self.world_object:
                    if self.hp is not None and self.hp > 0:
                        if self.world_object.position:
                            return True
            return False
                            
        def think(self):
            if self.world_object_alive_onpos():
                self.find_nearest_player()
    
        def cast_sensor(self,pos,SENSOR_LENGTH,orientation):	#position戻さないので注意
            self.world_object.position.set(*pos)						
            blk = self.set_cast_reset_ori(self.world_object.orientation.get(),orientation.get(),SENSOR_LENGTH)
            if blk is not None:
                dist = self.distance_calc(blk,self.world_object.position.get())
            else:
                dist=0
            return dist	

        def orientation_calc(self, mypos,tgtpos):	
            d = self.distance_calc(mypos.get(),tgtpos.get())
            if d == 0:
                ori = Vertex3(1,0,0)
                d = 0
                return ori, d
            ori = tgtpos - mypos
            ori.x /=d 
            ori.y /=d 
            ori.z /=d 
            return ori, d

        def canseeY2(self,mypos,ori, d): #cast_rayが信用ならないので自作
            if not self.world_object_alive_onpos():
                return None
            pos = [mypos.x,mypos.y,mypos.z]
            ori = ori.get()
            d_calc = 0.3 #bk

            for calc_do in range(int(d / d_calc)):
                pos[0] += ori[0]*d_calc
                pos[1] += ori[1]*d_calc
                pos[2] += ori[2]*d_calc	
                _x,_y,_z  = floor(pos[0]), floor(pos[1]), floor(pos[2])
                if _x > 511 or _x < 0 or _y > 511 or _y < 0 or _z > 62 or _z < -20:
                    return False
                if _z >= 0:
                    if self.protocol.map.get_solid(_x,_y,_z): 
                        return False
            return True

        def canseeY(self,mypos,tgt_head, No_need_compx=False): #No_need_compxなら指定座標のみ　Falseなら指定座標を頭として胴足まで計算cast_rayも自作の方を使う
            fori = self.world_object.orientation.get()
            ori,d = self.orientation_calc(mypos,tgt_head)
            if self.set_cast_reset_ori(fori,ori.get(),d) is None:
                if No_need_compx:
                    return 0
                if self.canseeY2(mypos,ori, d):
                    return 0
            if not No_need_compx:
                tgt_karada=Vertex3(tgt_head.x,tgt_head.y,tgt_head.z+1)
                ori,d = self.orientation_calc(mypos,tgt_karada)
                if self.set_cast_reset_ori(fori,ori.get(),d) is None:
                    if self.canseeY2(mypos,ori, d):
                        return 1
                tgt_asi=Vertex3(tgt_head.x,tgt_head.y,tgt_head.z+2)
                ori,d = self.orientation_calc(mypos,tgt_asi)
                if self.set_cast_reset_ori(fori,ori.get(),d) is None:
                    if self.canseeY2(mypos,ori, d):
                        return 2
            return -1

        def set_cast_reset_ori(self,fori,ori,d):
            obj = self.world_object
            obj.set_orientation(*ori)
            ret = obj.cast_ray(d)
            obj.set_orientation(*fori)
            return ret

        def forward_recognition(self,px,py,pz,distf,TGT_ORIENT,SENSOR_LENGTH):
            if TGT_ORIENT.y==0:
                Rx, Ry = floor(px-TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5+distf*TGT_ORIENT.x)+0.505, floor(py+TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5+distf*TGT_ORIENT.y)+0.505
                Lx, Ly = floor(px+TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5+distf*TGT_ORIENT.x)+0.505, floor(py-TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5+distf*TGT_ORIENT.y)+0.505
            elif 0.05<((TGT_ORIENT.x/TGT_ORIENT.y)**2)**0.05<20:
                Rx, Ry = px-TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5+distf*TGT_ORIENT.x, py+TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5+distf*TGT_ORIENT.y
                Lx, Ly = px+TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5+distf*TGT_ORIENT.x, py-TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5+distf*TGT_ORIENT.y
            else:
                Rx, Ry = floor(px-TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5+distf*TGT_ORIENT.x)+0.505, floor(py+TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5+distf*TGT_ORIENT.y)+0.505
                Lx, Ly = floor(px+TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5+distf*TGT_ORIENT.x)+0.505, floor(py-TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5+distf*TGT_ORIENT.y)+0.505
            for rl in range(2):
                for h in range(3):
                    if self.front_rcog[rl][int(pz+h)]<0:
                        if rl==0:
                            RLx = Rx
                            RLy = Ry
                        else:
                            RLx = Lx
                            RLy = Ly
                        d=self.cast_sensor((RLx,RLy,pz+h),SENSOR_LENGTH-distf, TGT_ORIENT)
                        if d>0:d+=distf
                        self.front_rcog[rl][int(pz+h)]=d

            c0r=self.front_rcog[0][int(pz)]
            c1r=self.front_rcog[0][int(pz+1)]
            c2r=self.front_rcog[0][int(pz+2)]

            c0l=self.front_rcog[1][int(pz)]
            c1l=self.front_rcog[1][int(pz+1)]
            c2l=self.front_rcog[1][int(pz+2)]

            pattern = 1
            AP = 0
            AP_CROUCH = 20
            AP_JUMP = 5
            AP_DANSA = 1
#		0	#		-1	#	   6661	#	   6662	#	  6663	#		666	#	
#	0		#	H	X	#	H	X	#	H	X	#	H	X	#	H	X	#	
#	1		#	B		#	B	 X	#	B	 X	#	B		#	B	r	#
#	2		#	B		#	B	 X	#	B		#	B	 X	#	B	r	#
################################################## 
            if c0r + c0l +  c1r + c1l +  c2r + c2l ==0  : # 前方障害なし
                pattern = 0
                AP+=0

            elif c1r + c1l +  c2r + c2l== 0 :# -1 しゃがめば通れる
                pattern = -1
                AP+=AP_CROUCH

            elif (0<c0r<=c1r+0.1 and 0<c0r<=c2r+0.1) or (0<c0l<=c1l+0.1 and 0<c0l<=c2l+0.1) : # DAME 無条件で前方障害有り判定
                pattern = 6661
                AP+=0
            elif (0<c0r<=c1r+0.1 and c2r==0) or (0<c0l<=c1l+0.1 and c2l==0) : # DAME 無条件で前方障害有り判定
                pattern = 6662
                AP+=0
            elif (0<c0r<=c2r+0.1 and c1r==0) or (0<c0l<=c2l+0.1 and c1l==0) : # DAME 無条件で前方障害有り判定
                pattern = 6663
                AP+=0
            if 0<pattern<666:
#		A	#		B	#		C	#		D	#	
#	0		#	H	 -	#	H	 X	#	0	 X-	#	
#	1		#	B	 X	#	B		#	1	X 	#
#	2	X	#	B	X	#	B	X	#	2	r-	#
################################################## 
                if c0r + c0l +  c1r + c1l == 0 : # A
                    AP+=AP_DANSA
                    pattern = 1
                elif c1r>c2r+0.1>0 or c1l>c2l+0.1>0: #B
                    AP+=AP_DANSA
                    pattern = 1 
                elif (c1r == 0 and c0r>c2r+0.1>0 )or(c1l==0 and c0l>c2l+0.1>0): #C
                    AP+=AP_DANSA
                    pattern = 1 

                elif (c0r>c1r+0.1>0 or c0r==0) or (c0l>c1l+0.1>0 or c0l==0): #D
                    AP+=AP_JUMP
                    pattern = 2
                else:
                    pattern = -99
            dist=0
            if pattern ==1 or pattern == 2:
                UEtemae = 1.5
                if pattern ==1:
                    if min(c2r,c2l)==0:
                        dist = max(0,max(c2r,c2l)-UEtemae)	#土台ブロック存在地点の1.5bk手前から探索
                    else:
                        dist = max(0,min(c2r,c2l)-UEtemae)
                else:
                    if min(c1r,c1l)==0:
                        dist = max(0,max(c1r,c1l)-UEtemae)
                    else:
                        dist = max(0,min(c1r,c1l)-UEtemae)
                for rl in range(2):
                    h = -1
                    if self.front_rcog[rl][int(pz+h)]<0:
                        if rl==0:
                            RLx = Rx
                            RLy = Ry
                        else:
                            RLx = Lx
                            RLy = Ly
                        d=self.cast_sensor((RLx+(dist-distf)*TGT_ORIENT.x,RLy+(dist-distf)*TGT_ORIENT.y,pz+h),SENSOR_LENGTH-dist, TGT_ORIENT)
                        if d>0:d+=dist
                        self.front_rcog[rl][int(pz+h)]=d
                cu1r=self.front_rcog[0][int(pz-1)]
                cu1l=self.front_rcog[1][int(pz-1)]
                if 0<cu1r<=c2r+0.1 or  0<cu1l<=c2l+0.1:
                    pattern = 777
                elif pattern == 2:

                    for rl in range(2):
                        h = -2
                        if self.front_rcog[rl][int(pz+h)]<0:
                            if rl==0:
                                RLx = Rx
                                RLy = Ry
                            else:
                                RLx = Lx
                                RLy = Ly
                            d=self.cast_sensor((RLx+(dist-distf)*TGT_ORIENT.x,RLy+(dist-distf)*TGT_ORIENT.y,pz+h),SENSOR_LENGTH-dist, TGT_ORIENT)
                            if d>0:d+=dist
                            self.front_rcog[rl][int(pz+h)]=d
                    cu2r=self.front_rcog[0][int(pz-2)]
                    cu2l=self.front_rcog[1][int(pz-2)]

                    if 0<cu2r<=c1r+0.1 or  0<cu2l<=c1l+0.1:
                        pattern = 888					
            return pattern, AP,(dist+distf)

        def enitity_add_remove(self,entity):
            collides = vector_collision(entity, 
                self.world_object.position, TC_CAPTURE_DISTANCE)
            if self in entity.players:
                self.assigned_position = None
                if not collides:
                    entity.remove_player(self)
            else:
                if collides:
                    self.assigned_position = None
                    entity.add_player(self)

        def tgt_pos_update(self):
            px,py,pzo = self.world_object.position.get()

            if self.world_object.crouch:
                pz=pzo-1
            else:
                pz=pzo

            if VSBOTmode:
                pla=None
                for pla in self.protocol.blue_team.get_players():
                    break
                if pla is not None: 
                    dist =999
                    pl = None
                    lowx = 600
                    for player in self.protocol.blue_team.get_players():
                        if player.world_object:
                            if player.hp is not None and player.hp > 0:
                                xpl = player.world_object.position.x
                                if lowx > xpl:
                                    lowx = xpl
                                dist_pl = player.distance_calc((px,py,pzo),player.world_object.position.get())
                                if dist_pl<dist:
                                    dist=dist_pl
                                    pl = player
                    if dist>150 or (lowx-30>px ):
                        self.respawn_time = 0
                        self.set_hp(0)
                    elif pl != None:
                        self.assigned_position = pl.world_object.position


            elif TOWmode:
                n = 0
                hidari_team = self.protocol.entities[n].team
                for n in range(16):
                    if self.protocol.entities[n].team != hidari_team:break
                if self.team == hidari_team:
                    tgt_entity = self.protocol.entities[n]
                    self.assigned_position = self.protocol.entities[n]
                else:
                    tgt_entity = self.protocol.entities[n-1]
                    self.assigned_position = self.protocol.entities[n-1]
                self.enitity_add_remove(tgt_entity)

            elif DOMINE_FULLmode:
                dist = 9999
                tgt_entity=None
                for entity in self.protocol.entities:
                    if entity.team != self.team or entity.capturing_team == self.team.other:
                        d = self.distance_calc(entity.get(),self.world_object.position.get())
                        if d < dist:
                            tgt_entity=entity
                            dist=d
                if tgt_entity == None:
                    tgt_entity = choice(self.protocol.entities)
                self.assigned_position = tgt_entity
                self.enitity_add_remove(tgt_entity)

            elif TDMmode:
                if self.team == self.protocol.blue_team:
                    self.assigned_position = self.protocol.best_friends_pos[1]
                elif self.team == self.protocol.green_team:
                    self.assigned_position = self.protocol.best_friends_pos[0]

            elif ARENAmode:
                if not self.gre_avoiding:
                    if self.enemy_lost is not None:
                        self.route_optimization(self.enemy_lost)
                        self.enemy_lost=None
                    else:
                        if random.random()<0.1:
                            noise_pos = self.noise_check()
                            if noise_pos is not None:
                                self.route_optimization(noise_pos[0],noise_pos[2])
                junkai_route = self.protocol.BOT_junkai_route

                if self.has_arena_tgt:
                    ii = self.num_arena_tgt
                    choiced_route = self.route_arena_tgt 
                    tpos = junkai_route[choiced_route][ii] 
                    d = self.distance_calc(tpos,self.world_object.position.get())
                    if d < max(5, 0.3*ARENA_JUNKAI_SECT):
                        if self.arena_route_destination>0:
                            self.arena_route_destination-=1	
                        self.jikuu_arena_tgt = 0
                        ii+=self.dir_arena_tgt
                        if 0 <= ii <= len(junkai_route[choiced_route])-1:
                            self.num_arena_tgt = ii
                            tpos = junkai_route[choiced_route][ii]
                        else:
                             self.has_arena_tgt = False
                    self.jikuu_arena_tgt += d
                    if self.jikuu_arena_tgt > ARENA_JUNKAI_SECT * UPDATE_FPS * 10:
                        self.has_arena_tgt = False
                    self.assigned_position=Vertex3(*tpos)
                else:
                    self.jikuu_arena_tgt = 0
                    routenum=len(junkai_route)
                    routechoce = list(range(routenum))
                    shuffle(routechoce)
                    mie = []
                    sibu = []
                    for choiced_route in routechoce:
                        i = 0
                        mie = []
                        sibu=[]
                        mind = 999
                        for junkaipos in junkai_route[choiced_route]:
                            d = self.distance_calc(junkaipos,self.world_object.position.get())
                            if d<mind+2*ARENA_JUNKAI_SECT:
                                if self.canseeY(self.world_object.position,Vertex3(*junkaipos),True)>=0:
                                    mie.append([i,d])
                                    if mind>=d:
                                        mind=d
                                else:
                                    sibu.append([i,d])
                            i+=1
                        if mind<4*ARENA_JUNKAI_SECT:
                            break
                    kouho=[]
                    for pt in mie:
                        if pt[1]<=mind+2*ARENA_JUNKAI_SECT:
                            kouho.append(pt[0])
                    if kouho ==[]:
                        if mie !=[]:
                            for pt in mie:
                                if pt[1]<=d+5*ARENA_JUNKAI_SECT:
                                    kouho.append(pt[0])
                    if kouho ==[]:
                        if mie !=[]:
                            for pt in mie:
                                kouho.append(pt[0])
                    if kouho ==[]:
                        if mie ==[]:
                            for pt in sibu:
                                kouho.append(pt[0])
                    if kouho !=[]:
                        ii = choice(kouho)
                        tpos = junkai_route[choiced_route][ii] 
                        self.assigned_position = Vertex3(*tpos)
                        self.route_arena_tgt = choiced_route
                        self.has_arena_tgt = True
                        self.dir_arena_tgt = choice([-1,1])
                        self.num_arena_tgt = ii
                    else:
                        self.assigned_position=None

            elif KABADI_mode:
                if not (self.gre_avoiding and not self.gre_ignore):
                    if self.team==self.protocol.blue_team:
                        dir=1
                    elif self.team==self.protocol.green_team:
                        dir=-1
                    if self.enemy_lost is not None:
                        if (self.enemy_lost[0]-self.world_object.position.x)*dir>0:
                            self.assigned_position=Vertex3(*self.enemy_lost)
                            if self.distance_calc(self.enemy_lost,self.world_object.position.get())<10:
                                self.enemy_lost=None
                    else:
                        self.assigned_position = Vertex3(dir*255+255, self.world_object.position.y, self.world_object.position.z)
    
            if not ARENAmode:
                if self.gre_avoiding and not self.gre_ignore and self.avoiding_danger_gre:
                    self.assigned_position =self.grenade_avoiding_direction(Vertex3(*self.avoiding_danger_gre))		
            if 	self.assigned_position is None:
                dd = 0
            else:
                apx,apy,apz = self.assigned_position.get()
                xd = apx - px
                yd = apy - py
                dd = (xd**2 + yd**2)**(0.5)
            if dd == 0:
                self.target_direction = Vertex3(1, 0, 0)
            else:
                self.target_direction = Vertex3(xd/dd, yd/dd, 0)
            if dd<3 and not (self.gre_avoiding and not self.gre_ignore):
                self.stopmotion = True
            else:
                self.stopmotion = False

        def grenade_avoiding_direction(self, grepos):
            pos=self.world_object.position
            difpos = grepos-pos
            tgtpos = pos-difpos*5
            return tgtpos

        def route_optimization(self,tpos,data=None,avoid=False):
            junkai_route = self.protocol.BOT_junkai_route
            routenum=len(junkai_route)
            routechoce = list(range(routenum))
            shuffle(routechoce)
            kouho=[]
            spos = self.world_object.position.get()
            dist_dakyou = abs(self.world_object.position.x - tpos[0]) + abs(self.world_object.position.y - tpos[1])
            mindist = 999
            if data:
                for choiced_route in routechoce:#脈ありルートを順に探索
                    if data[choiced_route] !=[]:
                        templist=[]
                        for num, pos in enumerate(junkai_route[choiced_route]):
                            d = self.distance_calc(pos,spos)
                            if d<ARENA_JUNKAI_SECT*2:
                                if self.canseeY(Vertex3(*pos),self.world_object.position,True)>=0:
                                    templist.append(num)
                        tempmin = [999,0,1]
                        if templist !=[]:
                            for P in templist:
                                for T in data[choiced_route]:
                                    sect = abs(T-P)
                                    if sect<tempmin[0]:
                                        if T>=P:
                                            dir = 1
                                        else:
                                            dir = -1
                                        tempmin=[sect,P,dir]
                        if mindist>tempmin[0]:
                            mindist=tempmin[0]
                            routenum=choiced_route
                            direct=tempmin[2]
                            if avoid:
                                direct=tempmin[2]*-1 #グレネード回避時反転
                            num=tempmin[1]
                            pos=junkai_route[routenum][num]
                            kouho = [routenum, direct, num, pos]
                            if sect*ARENA_JUNKAI_SECT<dist_dakyou: #最短じゃなくてもある程度で妥協
                                break
            else:
                for choiced_route in routechoce:#全ルートを順に探索
                        templistP=[]
                        templistT=[]
                        for num, pos in enumerate(junkai_route[choiced_route]):
                            dP = self.distance_calc(pos,spos)
                            if dP<ARENA_JUNKAI_SECT:
                                if self.canseeY(Vertex3(*pos),self.world_object.position,True)>=0:
                                    templistP.append(num)
                            dT = self.distance_calc(pos,tpos)
                            if dT<ARENA_JUNKAI_SECT:
                                if self.canseeY(Vertex3(*pos),Vertex3(*tpos),True)>=0:
                                    templistT.append(num)
                        tempmin = [999,0,1]
                        if templistP !=[] and templistT !=[] :
                            for P in templistP:
                                for T in templistT:
                                    sect = abs(T-P)
                                    if sect<tempmin[0]:
                                        if T>=P:
                                            dir = 1
                                        else:
                                            dir = -1
                                        tempmin=[sect,P,dir]
                        if mindist>tempmin[0]:
                            mindist=tempmin[0]
                            routenum=choiced_route
                            direct=tempmin[2]
                            if avoid:
                                direct=tempmin[2]*-1 #グレネード回避時反転
                            num=tempmin[1]
                            pos=junkai_route[routenum][num]
                            kouho = [routenum, direct, num, pos]
                
            if kouho !=[] and mindist<20:
                tpos = kouho[3]
                self.assigned_position = Vertex3(*tpos)
                self.arena_route_destination = 15
                self.route_arena_tgt = kouho[0]
                self.has_arena_tgt = True
                self.dir_arena_tgt = kouho[1]
                self.num_arena_tgt = kouho[2]

        def on_position_update(self):
            if self.world_object_alive_onpos():
                if not (self.world_object.sneak or self.world_object.crouch):
                    if self.world_object.up or self.world_object.down or self.world_object.right or self.world_object.left:
                        if self.world_object.sprint:
                            self.noise(2)
                        else:
                            self.noise(1)
            return connection.on_position_update(self)

        def _on_reload(self):
            if self.world_object_alive_onpos():
                self.noise(3)
            return connection._on_reload(self)

        def on_animation_update(self, jump, crouch, sneak, sprint):
            if self.world_object_alive_onpos():
                if jump:
                    self.noise(2)
            return connection.on_animation_update(self, jump, crouch, sneak, sprint)

        def near_point_mem(self,point):
            junkai_route = self.protocol.BOT_junkai_route
            routenum=len(junkai_route)
            mem=[]
            for route in range(routenum):#全ルートを順に探索
                mem.append([])
                for num, pos in enumerate(junkai_route[route]):
                    d = self.distance_calc(point,pos)
                    if d<ARENA_JUNKAI_SECT*2:
                        if self.canseeY(Vertex3(*point),Vertex3(*pos),True)>=0:
                            mem[route].append(num)
                                                    #	ルート１：なし
                                                    #	ルート２：５，６
                                                    #	ルート３：３，４
                                                    #	ルート４：なし
                                                    #	の場合	mem=[[],[5,6],[3,4],[]]

            return mem

        def noise(self,type):#type:1=step, 2=dash,jump, 3=reload, 4=fire
            pos = self.world_object.position.get()
            if self.team == self.protocol.blue_team:
                mem=self.near_point_mem(pos)
                self.protocol.noise_blue.append([pos,type,mem])
                callLater(1.5, self.protocol.noise_blue.pop, 0)
            else:
                mem=self.near_point_mem(pos)
                self.protocol.noise_green.append([pos,type,mem])
                callLater(1.5, self.protocol.noise_green.pop, 0)

        def noise_check(self):
            mind=999
            if self.team == self.protocol.green_team:
                noiselist = self.protocol.noise_blue
            else:
                noiselist = self.protocol.noise_green
            noise_tgt=None
            noise_tgt_type=0
            spos=self.world_object.position.get()
            for noise in noiselist:
                d = self.distance_calc(noise[0],spos)
                if d<128:
                    d/=noise[1]
                    if d<mind:
                        mind=d
                        noise_tgt=noise
            if self.cpulevel*random.random()*100*2+20>mind and mind<128:
                if 15-self.arena_route_destination>mind/2.0:
                    return noise_tgt
            return None
        
        def enemy_lost_giveup(self,pos):
            if self.enemy_lost==pos:
                self.enemy_lost=None	

        def grenade_avoid(self):
            # Fix from Monstarules: Avoid multiple calls of seconds()
            vSeconds=seconds()
            if self.world_object_alive_onpos():
                if self.protocol.exp_position==[]:
                    return False				
                if self.gre_avoiding:
                    return False
                minfuse=vSeconds+100
                danger_gre=None
                spos=self.world_object.position.get()
                for expos in self.protocol.exp_position:
                    who=expos[0]
                    where=expos[1]
                    when=expos[2]
                    if minfuse-vSeconds>0:  # if it<0 then that will already exploded, so ignore #by yuyasato
                        if who.team ==self.team.other or who==self:
                            d = self.distance_calc(where,spos)		
                            if d<20:
                                if when<minfuse:
                                    minfuse=when
                                    danger_gre=[where,expos[3]]
                if danger_gre is not None:
                    self.gre_avoiding=True
                    if random.random()<0.1:
                        self.gre_ignore=True
                    # Fix from Monstarules: Prevents assertions from callLater being called for having less than 0 seconds
                    minfuse-=vSeconds
                    if minfuse<0:
                        minfuse=0
                    callLater(minfuse, self.gre_avoid_fin)
                    if ARENAmode:
                        self.route_optimization(danger_gre[0],danger_gre[1],True)
                    else:
                        self.avoiding_danger_gre = danger_gre[0]
                    return True
            return False

        def gre_avoid_fin(self):
            self.gre_avoiding=False
            self.avoiding_danger_gre=None
            self.gre_ignore=False
            if self.world_object_alive_onpos():	#first only check w_o_a_o #by yuyasato
                if not self.grenade_avoid():
                    self.tgt_pos_update()		
        
        def on_grenade_thrown(self, grenade):
            fuse = grenade.fuse
            exptime=seconds()+fuse
            dt=0.1
            vx,vy,vz =grenade.velocity.get()
            vx*=(0.533*dt)
            vy*=(0.533*dt)
            vz*=(0.533*dt)
            g=0.01667*0.533*dt
            x,y,z=grenade.position.get()
            t=0.0
            map = self.protocol.map
            for countt in range(int(3*UPDATE_FPS/dt)):
                vz+=g
                x0=x
                y0=y
                z0=z
                x+=vx
                y+=vy
                z+=vz
                t+=dt
                if map.get_solid(x,y,z) or (not 0<x<511) or (not 0<y<511) or (z>63):
                    if floor(z)!=floor(z0):
                        vz*=-0.36
                        vx*=0.36
                        vy*=0.36
                    elif floor(x)!=floor(x0):
                        vx*=-0.36
                        vz*=0.36
                        vy*=0.36
                    elif floor(y)!=floor(y0):
                        vy*=-0.36
                        vx*=0.36
                        vz*=0.36
                    x=x0+vx
                    y=y0+vy
                    z=z0+vz
                if t>=fuse*UPDATE_FPS:
                    mem=self.near_point_mem((x,y,z))
                    gredata=[self, (x,y,z),exptime,mem]
                    self.protocol.exp_position.append(gredata)
                    callLater(fuse, self.removegrenadelist, gredata)
                    break
            return connection.on_grenade_thrown(self, grenade)		

        def removegrenadelist(self,value):
            self.protocol.exp_position.remove(value)

        def grephifunc(self,botpos,tgtpos):
            ex,ey,ez=tgtpos
            px,py,pz=botpos
            rx,rz=((ex-px)**2+(ey-py)**2)**0.5,ez-pz
            g=0.01667*0.533
            ve=0.533
            I=(g*rx*rx)/(2*ve*ve)
            b=rx/I
            c=1-rz/I
            root = b*b-4*c
            if root>0:
                tan1 =(-b+root**0.5)/2
                tan2 =(-b-root**0.5)/2
                phi1 = degrees(atan(tan1))
                phi2 = degrees(atan(tan2))
                return min(phi1,phi2),max(phi1,phi2)
            else:
                return False,False			

        def grenade_calc(self,tgtpos,onlyori=False,pin=False):
            botpos = self.world_object.position.get()

            lv10=(self.cpulevel*100)**0.5
            dt = 1.0#/lv10

            ex,ey,ez=tgtpos
            px,py,pz=botpos
            dx,dy,dz=ex-px,ey-py,ez-pz
            d=(dx**2+dy**2+dz**2)**0.5
            dx/=d
            dy/=d
            dz/=d
            map = self.protocol.map

            if onlyori:
                ex,ey,ez=tgtpos
                ex+=dx*self.keepinggreoffset
                ey+=dy*self.keepinggreoffset
                ez+=dz*self.keepinggreoffset
                phi,phi2 = self.grephifunc(botpos,(ex,ey,ez))
                dx,dy,dz=ex-px,ey-py,ez-pz
                theta = degrees(atan2(dy,dx))
                if self.keepinggrephimax:
                    phi=max(phi,phi2)
                cosp=cos(radians(phi))
                vx,vy,vz = cos(radians(theta))*cosp, sin(radians(theta))*cosp, sin(radians(phi))
                return vx,vy,vz
            offsetposlist = choice([[-3,-5,0,5,3],[-3,-5,5,3,0], [5,-3,0,3,-5], [5,3,0,-3,-5],[0,-3,-5,5,3], [0,5,-3,3,-5]])
            if pin:
                offsetposlist=[self.keepinggreoffset]

            for offsetpos in offsetposlist:
                ex,ey,ez=tgtpos
                ex+=dx*offsetpos
                ey+=dy*offsetpos
                ez+=dz*offsetpos
                phi1,phi2 = self.grephifunc(botpos,(ex,ey,ez))
                if pin:
                    if self.keepinggrephimax:
                        phitemp1,phitemp2=phi1,phi2
                        phi1 = max(phitemp1,phitemp2)
                        phi2 = min(phitemp1,phitemp2)
                    else:
                        phitemp1,phitemp2=phi1,phi2
                        phi1 = min(phitemp1,phitemp2)
                        phi2 = max(phitemp1,phitemp2)
                                        
                for phi in [phi1,phi2]:
                    if (offsetpos<0 and phi == max(phi1,phi2)) or (offsetpos>=0 and min(phi1,phi2)):
                        theta = degrees(atan2(ey-py,ex-px))
                        cosp=cos(radians(phi))
                        vx,vy,vz = cos(radians(theta))*cosp, sin(radians(theta))*cosp, sin(radians(phi))
                        if onlyori:
                            return vx,vy,vz
                        t=0.0
                        x,y,z=botpos
                        d=999
                        kabe = 0
                        vx*=0.533*dt
                        vy*=0.533*dt
                        vz*=0.533*dt
                        g=0.01667*0.533*dt
                        for countt in range(int(3*UPDATE_FPS)):
                            vz+=g
                            x0=x
                            y0=y
                            z0=z
                            x+=vx
                            y+=vy
                            z+=vz
                            t+=dt
                            if map.get_solid(x,y,z) or (not 0<x<511) or (not 0<y<511) or (z>63):
                                if kabe>2:
                                    break
                                kabe+=1
                                if floor(z)!=floor(z0):
                                    vz*=-0.36
                                    vx*=0.36
                                    vy*=0.36
                                elif floor(x)!=floor(x0):
                                    vx*=-0.36
                                    vz*=0.36
                                    vy*=0.36
                                elif floor(y)!=floor(y0):
                                    vy*=-0.36
                                    vx*=0.36
                                    vz*=0.36
                                x=x0+vx
                                y=y0+vy
                                z=z0+vz
                            if vz>0 and z>ez+4:
                                break
                            if vx>0 and x > ex+5:
                                break
                            if vx<0 and x < ex-5:
                                break
                            if vy>0 and y > ey+5:
                                break
                            if vy<0 and y < ey-5:
                                break
                            dd=self.distance_calc((x,y,z),tgtpos)
                            if d>dd:
                                d=dd
                            else:
                                if d<10:
                                    if phi == max(phi2,phi1):
                                        self.keepinggrephimax = True
                                    self.keepinggreoffset = offsetpos
                                    dx,dy,dz=ex-px,ey-py,ez-pz
                                    theta = degrees(atan2(dy,dx))
                                    cosp=cos(radians(phi))
                                    self.grenade_throw_orienation = cos(radians(theta))*cosp, sin(radians(theta))*cosp, sin(radians(phi))
                                    return phi,t/UPDATE_FPS+random.random()*(1-self.cpulevel)
            return False,False	
    
        def grenade_toolchange(self):
            if self.tool != GRENADE_TOOL:
                tgtpos = copy(self.enemy_lost_temp)
                botpos = self.world_object.position.get()
                d = self.distance_calc(botpos,tgtpos)
                if d>15 or self.canseeY(self.world_object.position,Vertex3(tgtpos[0],tgtpos[1],tgtpos[2]+2))<0:

                    self.set_tool(GRENADE_TOOL)
                    self.toolchangetime = seconds()
                    callLater(0.5+random.random()*(1-self.cpulevel)/2, self.grenade_pin)

        def grenade_pin(self):
            if seconds() - self.toolchangetime>0.5 and self.tool == GRENADE_TOOL and not self.grenade_keeping:
                if self.aim_at and self.enemy_lost_temp != None and self.world_object_alive_onpos():
                    tgtpos = copy(self.enemy_lost_temp)
                    botpos = self.world_object.position.get()
                    d = self.distance_calc(botpos,tgtpos)
                    if d>15 or self.canseeY(self.world_object.position,Vertex3(tgtpos[0],tgtpos[1],tgtpos[2]+2))<0:
                        phi,time=self.grenade_calc(tgtpos,False,True)
                        if phi:
                            time=max(0.4, time+0.2+uniform(-0.3,0.7)*(1-self.cpulevel))
                            if random.random()<0.2:time=0.9 #たまにすぐ投げる
                            dx = tgtpos[0]-botpos[0]
                            dy = tgtpos[1]-botpos[1]
                            theta = degrees(atan2(dy,dx))#+uniform(-10,10)*(1-self.cpulevel)
                            cosp=cos(radians(phi))
                            vx,vy,vz = cos(radians(theta))*cosp, sin(radians(theta))*cosp, sin(radians(phi))
                            self.grenade_throw_orienation=vx,vy,vz
                            self.grenade_keep=seconds()+3-time
                            self.grenade_pinpull=seconds()
                            return
                callLater(0.1, self.grenade_unset)

        def grenade_final_check(self,tgtpos,time):
            botpos = self.world_object.position.get()
            map = self.protocol.map
            vx,vy,vz = self.world_object.orientation.get()
            x,y,z=botpos
            vx*=0.533
            vy*=0.533
            vz*=0.533
            g=0.01667*0.533
            for count in range(int(time*UPDATE_FPS)):
                vz+=g
                x0=x
                y0=y
                z0=z
                x+=vx
                y+=vy
                z+=vz
                if map.get_solid(x,y,z) or (not 0<x<511) or (not 0<y<511) or (z>63):
                    if floor(z)!=floor(z0):
                        vz*=-0.36
                        vx*=0.36
                        vy*=0.36
                    elif floor(x)!=floor(x0):
                        vx*=-0.36
                        vz*=0.36
                        vy*=0.36
                    elif floor(y)!=floor(y0):
                        vy*=-0.36
                        vx*=0.36
                        vz*=0.36
                    x=x0+vx
                    y=y0+vy
                    z=z0+vz
            dd=self.distance_calc((x,y,z),tgtpos)
            return dd<15

        def grenade_release(self):
            time = 3-(seconds()-self.grenade_pinpull)
            tgtpos = copy(self.enemy_lost_temp)
            if 0.2<time<3 and self.grenade_final_check(tgtpos,time):
                pos = self.world_object.position
                velo = self.world_object.orientation
                if not DEBUG_VIRTUAL_HIT:
                    grenade = self.protocol.world.create_object(world.Grenade, time, pos, None, velo, self.grenade_exploded)
                    grenade.team = self.team
                    self.on_grenade_thrown(grenade)
                grenade_packet.value = time
                grenade_packet.player_id = self.player_id
                grenade_packet.position = pos.get()
                grenade_packet.velocity = velo.get()
                self.protocol.broadcast_contained(grenade_packet)
                self.grenades-=1
            self.grenade_keep=0
            if self.tool == GRENADE_TOOL:
                callLater(0.1, self.grenade_unset)

        def grenade_unset(self):
            if self.tool == GRENADE_TOOL and not self.grenade_keeping:
                self.set_tool(WEAPON_TOOL)
                self.toolchangetime = seconds()
            
        def inputcrouch(self, crouchadd, defcrouch):
            inputedtime = seconds() - self.crouchinputed
            lostime = 0.7-(self.cpulevel/2)
            if inputedtime > lostime:
                if crouchadd:
                    if not defcrouch:
                        self.input.add('crouch') 
                    else:	
                        self.input.discard('crouch') 
                    self.crouchinputed = seconds()			
            elif inputedtime < lostime/2:
                if not defcrouch:
                    self.input.add('crouch') 
                else:	
                    self.input.discard('crouch') 

        def inputfire(self):
            if self.fireinput>0:
                self.fireinput-=1
                self.input.add('primary_fire')

        def new_gosa(self,fired):
            if fired:
                R = (1-self.cpulevel)*(4.5 - random.random())
                if random.random()>self.cpulevel:
                    R-=(1-self.cpulevel)*random.random()
                theta = uniform(0,360)
                xoff = R*cos(radians(theta))/1.5
                yoff = R*sin(radians(theta))
            else:
                R = (1-self.cpulevel)*5+10
                theta = uniform(0,360)
                xoff = R*cos(radians(theta))
                yoff = R*sin(radians(theta))			
            return xoff, yoff

        def late_gosa(self): #狙点収束まで時間がかかるシステム
            off_r = (self.xoff_okure**2+self.yoff_okure**2)**0.5
            if off_r==0:
                return 0, 0
            d_okure=100/off_r *((1-self.cpulevel)/2+0.5)				#ここの係数は検討の余地あり
            d_backokure = 1.0/d_okure							#1サイクルで1/nだけ中心に近づく
            x_back = d_backokure * self.xoff_okure
            y_back = d_backokure * self.yoff_okure
            self.xoff_okure -= x_back
            self.yoff_okure -= y_back*3
            return x_back, y_back

        def rotate_ave(self,list):
            sum=0
            num=0
            for th in list:
                if th!=0:
                    if abs(th) != max(abs(max(list)),abs(min(list))):
                        sum+=th
                        num+=1.0
            if num>0:
                ave=sum/num
            else:
                ave=0
            return ave

        def rotate_gosa(self):#旋回量に応じて誤差蓄積+大旋回時は旋回量オーバー
            self.large_omega_x *=(1.0- 1.0/(40/(self.cpulevel*0.2+0.8)))
            self.large_omega_y *=(1.0- 1.0/(40/(self.cpulevel*0.2+0.8)))
            theta_ave = self.rotate_ave(self.ave_d_theta)
            phi_ave = self.rotate_ave(self.ave_d_phi)
            self.large_omega_x += theta_ave*(0.7-(self.cpulevel/2))/2
            self.large_omega_y += phi_ave*(1-self.cpulevel)/2
            self.large_omega_x=max( min( (1-self.cpulevel)*15 , self.large_omega_x) , (1-self.cpulevel)*(-15))
            self.large_omega_y=max( min( (1-self.cpulevel)*5 , self.large_omega_y) , (1-self.cpulevel)*(-5))
            self.omega += (random.random()-0.5)*0.2-self.omega/600

        def tebure_gosa(self):
            self.xoff_tebure+=gauss(0, ((1-self.cpulevel/2)*0.2*0.02))-(self.xoff_tebure*0.001)
            self.yoff_tebure+=gauss(0, ((1-self.cpulevel/2)*0.2*0.02))-(self.yoff_tebure*0.001)
            self.xoff_tebure=max( min( (1-self.cpulevel)*5 , self.xoff_tebure) , (1-self.cpulevel)*(-5))
            self.yoff_tebure=max( min( (1-self.cpulevel)*3 , self.yoff_tebure) , (1-self.cpulevel)*(-3))

        def moving_target_gosa(self):
            self.vel+=gauss(0, (1-self.cpulevel)*0.2)-(self.vel*0.3*self.cpulevel)
            self.vel=max( min((1-self.cpulevel)*5 , self.vel) , (1-self.cpulevel)*(-5))	#動目標の速度誤認係数
            target_obj = self.aim_at.world_object
            aim_at_vel = target_obj.velocity
            xdiff=aim_at_vel.x*self.vel-self.movezure_x
            ydiff=aim_at_vel.y*self.vel-self.movezure_y
            zdiff=aim_at_vel.z*self.vel-self.movezure_z
            self.movezure_x+=xdiff*0.2*(self.cpulevel)
            self.movezure_y+=ydiff*0.2*(self.cpulevel)
            self.movezure_z+=zdiff*0.2*(self.cpulevel)

        def update(self):
            if not self.world_object_alive_onpos():
                return

            second = seconds()
            obj = self.world_object
            pos = obj.position
            ori = obj.orientation
            spade_using =False
            digging = False
        
            self.flush_input()
            xt,yt,zt=ori.get()

            preori_theta = degrees(atan2(yt,xt))
            preori_phi = degrees(asin(zt))	 
            d_phi = preori_phi - self.pre2ori_phi 
            if preori_theta > 0:
                if self.pre2ori_theta<0 and preori_theta - self.pre2ori_theta>180:
                    d_theta = 360 - (preori_theta - self.pre2ori_theta)
                else:
                    d_theta = preori_theta - self.pre2ori_theta
            else:
                if self.pre2ori_theta>0 and preori_theta - self.pre2ori_theta<-180:
                    d_theta = -360 - (preori_theta - self.pre2ori_theta)
                else:
                    d_theta = preori_theta - self.pre2ori_theta
            self.pre2ori_theta = preori_theta
            self.pre2ori_phi = preori_phi
            self.ave_d_theta.pop(0)
            self.ave_d_theta.append(d_theta)
            self.ave_d_phi.pop(0)
            self.ave_d_phi.append(d_phi)
            self.grenade_avoid()
            self.inputfire()
            if not self.world_object_alive_onpos():
                return

            if not ARENAmode:
                if self.gre_avoiding and not self.gre_ignore:
                    if self.distance_calc(self.avoiding_danger_gre,self.world_object.position.get())<30:
                        self.tgt_pos_update()

            if self.aim_at and self.aim_at.world_object and not (self.gre_avoiding and not self.gre_ignore): #射撃対象敵プレイヤー認識状態
                self.enemy_lost=None
                crouchadd = False
                defcrouch=False
                target_obj = self.aim_at.world_object
                aim_at_pos = target_obj.position
                canseepos = self.canseeY(pos,aim_at_pos)
                xt,yt,zt=target_obj.orientation.get()				
                self.aim.set_vector(aim_at_pos)
                self.aim -= pos
                distance_to_aim = self.aim.normalize()
                if self.battle_distance < distance_to_aim:#目標遠いなら進む
                    self.input.add('up')	
                if self.grenade_keeping and self.tool == GRENADE_TOOL:	#grenadeピン抜き保持中
                    if self.enemy_lost_temp ==None or distance_to_aim<15 or random.random()<0.005:#目標15bk内接近or低確率
                        obj.set_orientation(*self.grenade_throw_orienation)
                        self.grenade_keeping=False
                        self.grenade_release()														#即時投擲
                        self.input.discard('primary_fire')
                        callLater(0.1, self.grenade_unset)
                    else:
                        self.grenade_throw_orienation= self.grenade_calc(self.enemy_lost_temp,True) #目標座標に対し保持角度修正
                if canseepos>=0:  #目標視認可能状況
                    self.enemy_lost_temp=aim_at_pos.get()
                    self.aim_quit=100

                    #回避行動制御
                    if self.aim_at.tool==WEAPON_TOOL: #敵が銃を所持
                        diff = target_obj.orientation - self.aim	
                        diff = diff.length_sqr()								#敵狙点方向と彼我のなす角
                        if diff > 0.01 and self.cpulevel>0.3:
                            p_dot = target_obj.orientation.perp_dot(self.aim)
                            if 0.1 > p_dot > -0.1:
                                if self.cpulevel>0.5:
                                    if random.random()<self.cpulevel and random.random()<30/distance_to_aim**2 and random.random() > 0.95: #ジャンプ回避
                                        if seconds()-self.jumptime>0.5 and obj.velocity.z**2<0.0001:
                                            self.jumptime=seconds()
                                            self.input.add('jump')
                                if random.random() < self.cpulevel**2/4-0.04: #屈伸回避
                                    crouchadd = True
                            if 0.1 > p_dot > 0.0:
                                self.input.add('right')
                            elif 0.0 > p_dot > -0.1:
                                self.input.add('left')

                    #狙点制御
                    #狙点誤差
                    self.moving_target_gosa()#動目標誤認
                    aim_at_pos_future = Vertex3(aim_at_pos.x + self.movezure_x, aim_at_pos.y + self.movezure_y, aim_at_pos.z+self.movezure_z) #動目標の予測位置誤認後位置
                    if canseepos==0:	#頭が見える場合
                        aim_at_pos_future.z += self.z_add #胴狙いの場合を反映
                    else:
                        aim_at_pos_future.z += canseepos #狙点を腰か足の見える方に移動

                    self.aim.set_vector(aim_at_pos_future)
                    self.aim -= pos
                    distance_to_aim = self.aim.normalize()

                    x_back, y_back = self.late_gosa()	#狙点の収束遅延
                    self.tebure_gosa()					#手ぶれ分
                    self.rotate_gosa() 					#直近旋回角依存誤差
#					print "%.3f, %.3f, %.3f, (%.2f,%.2f,%.2f) "%(self.xoff_tebure, self.xoff_okure, self.large_omega_x,self.movezure_x,self.movezure_y,self.movezure_z)
                    self.target_orientation.set_vector(self.aim)
                    theta = degrees(atan2(self.target_orientation.y,self.target_orientation.x))
                    phi = degrees(asin(self.target_orientation.z))
                    theta += self.xoff_tebure + self.xoff_okure + self.large_omega_x*self.omega	#各要素誤差を目標方向への正確角度に加算
                    phi += self.yoff_tebure + self.yoff_okure + self.large_omega_y*self.omega
                    newz = sin(radians(phi))
                    newxy = cos(radians(phi))
                    newx = cos(radians(theta))*newxy
                    newy = sin(radians(theta))*newxy
                    self.target_orientation =Vertex3(newx,newy,newz)#加算後角度決定
                    diff = ori - self.target_orientation #現状角と目標角の差分
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
                    else:
                        ori.set_vector(self.target_orientation)
                    if self.grenade_keeping: #grenadeピン抜き保持中は射角に修正
                        obj.set_orientation(*self.grenade_throw_orienation)

                    #攻撃制御
                    if self.tool != GRENADE_TOOL: 							#grenade持っていない場合、低確率でグレネード使おうとする。彼我高低差があると確率大
                        if random.random()<self.cpulevel and random.random()<0.001*abs(self.aim_at.world_object.position.z-self.world_object.position.z) and self.grenades>0:
                            if 20<distance_to_aim<50:
                                phai,time = self.grenade_calc(self.enemy_lost_temp)
                                if phai: self.grenade_toolchange()
                    if seconds() - self.toolchangetime > 0.5 and self.tool == WEAPON_TOOL and seconds() - self.sprinttime>0.5: # 射撃可能条件
                            if distance_to_aim < 135:#目標視認可能距離 
                                self.fire_weapon()	#射撃指示
                    if self.battlecrouching and self.tool == WEAPON_TOOL:
                        cpos = Vertex3(pos.x,pos.y,pos.z+1.1)
                        if self.world_object.crouch:
                            crouchcansee=0
                        else:
                            crouchcansee = self.canseeY(cpos,aim_at_pos)
                        if crouchcansee>=0: #しゃがんでも見えるなら
                            defcrouch=True #しゃがみがデフォ
                            self.input.add('crouch')
                else: #目標追尾中だが見えない状況
                    if self.aim_quit<=60:
                        if random.random()**2/60>self.cpulevel:
                            self.bot_reload()
                    if self.enemy_lost_temp != None and self.grenades>0:	#目標ロスト＝遮蔽物に隠れた可能性が高いので高確率でグレネードを投げる
                        if self.tool != GRENADE_TOOL and random.random()<self.cpulevel*0.01:
                            phai,time = self.grenade_calc(self.enemy_lost_temp)
                            if phai:
                                self.grenade_toolchange()
                    if self.tool != GRENADE_TOOL:
                        self.aim_quit-=1
                    self.smg_shooting=0
                    if self.aim_quit<=0:
                        if self.aim_at.world_object_alive_onpos():
                            self.enemy_lost=self.enemy_lost_temp
                            callLater(7, self.enemy_lost_giveup, self.aim_at.world_object.position.get())
                        self.aim_at=None #目標見えない状況が継続により目標指定解除, モードによってはロスト地点へ捜索開始

                self.inputcrouch(crouchadd, defcrouch)
                self.has_arena_tgt = False

                if self.tool == GRENADE_TOOL:
                    if self.grenades<=0:
                        callLater(0.01, self.grenade_unset)
                    if seconds() - self.toolchangetime>0.5 and self.grenades>0:
                        if self.grenade_keep>seconds():
                            self.grenade_keeping=True
                            obj.set_orientation(*self.grenade_throw_orienation)
                            self.input.add('primary_fire')
                        else:
                            if self.grenade_keeping:
                                obj.set_orientation(*self.grenade_throw_orienation)
                                self.grenade_keeping=False
                                self.grenade_release()
                            self.input.discard('primary_fire')
                            callLater(3, self.grenade_unset)
                self.reload_wait=(self.cpulevel*300+40)*(random.random()+1.5)/2
            else:#攻撃対象の敵指定無し状態
                self.reload_wait-=1
                if self.reload_wait<=0:
                    self.bot_reload()
                self.xoff_okure, self.yoff_okure = self.new_gosa(False) #誤差収束リセット
                px,py,pzo = pos.get()
                self.tgt_pos_update()
                if self.stopmotion:
                    self.input.discard('up')
                    self.input.discard('down')
                    self.input.discard('left')
                    self.input.discard('right')
                    self.input.discard('jump')
                    self.input.discard('sprint')
                    self.input.add('crouch')
                elif seconds() - self.stucking<0.5:
                    self.input.discard('up')
                    self.input.add('down')
                    self.input.discard('left')
                    self.input.discard('right')
                    self.input.discard('jump')
                    self.input.add('sprint')
                    self.input.discard('crouch')
                    if random.random()<0.8:
                        if self.player_id%3==1:
                            self.input.add('left')
                        elif self.player_id%3==2:
                            self.input.add('right')
                    self.has_arena_tgt = False
                else:
                    if self.world_object.crouch:
                        pz=pzo-1
                    else:
                        pz=pzo
                    ox,oy,oz = self.world_object.orientation.get()
                    SENSOR_LENGTH=30
                    if ARENAmode:
                        SENSOR_LENGTH = int(ARENA_JUNKAI_SECT/2)
                    TGT_ORIENT = self.target_direction

                    #目標方向長距離障害探知
                    if self.long_recg>=10: #n回に一回だけ長距離探知
                        self.long_recg=0
                        if pz >= 60:#海
                            if TGT_ORIENT.y==0:
                                Rx, Ry = floor(px-TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5)+0.505, floor(py+TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5)+0.505
                                Lx, Ly = floor(px+TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5)+0.505, floor(py-TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5)+0.505
                            elif 0.05<((TGT_ORIENT.x/TGT_ORIENT.y)**2)**0.05<20:
                                Rx, Ry = px-TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5, py+TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5
                                Lx, Ly = px+TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5, py-TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5
                            else:
                                Rx, Ry = floor(px-TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5)+0.505, floor(py+TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5)+0.505
                                Lx, Ly = floor(px+TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5)+0.505, floor(py-TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5)+0.505
                            c0r=self.cast_sensor((Rx,Ry,pz),SENSOR_LENGTH, TGT_ORIENT)
                            c1r=self.cast_sensor((Rx,Ry,pz-1),SENSOR_LENGTH, TGT_ORIENT)				
                            c2r=self.cast_sensor((Rx,Ry,pz-2),SENSOR_LENGTH, TGT_ORIENT)	
                            c0l=self.cast_sensor((Lx,Ly, pz),SENSOR_LENGTH, TGT_ORIENT)
                            c1l=self.cast_sensor((Lx,Ly, pz-1),SENSOR_LENGTH, TGT_ORIENT)				
                            c2l=self.cast_sensor((Lx,Ly, pz-2),SENSOR_LENGTH, TGT_ORIENT)	
                            sumc = c0r+c1r+c2r+c0l+c1l+c2l
                            if sumc >0:
                                cdr=self.cast_sensor((Rx,Ry,pz+1),SENSOR_LENGTH, TGT_ORIENT)
                                cdl=self.cast_sensor((Lx,Ly,pz+1),SENSOR_LENGTH, TGT_ORIENT)
                                if c2r>0 and c1r>0:
                                    if c2r>c1r:c2r=0
                                if c1r>0 and c0r>0:
                                    if c1r>c0r:c1r=0
                                if c0r>0 and cdr>0:
                                    if c0r>cdr:c0r=0	
                                if c2l>0 and c1l>0:
                                    if c2l>c1l:c2l=0
                                if c1l>0 and c0l>0:
                                    if c1l>c0l:c1l=0
                                if c0l>0 and cdl>0:
                                    if c0l>cdl:c0l=0	
                            AP= sumc = c0r+c1r+c2r+c0l+c1l+c2l
                            AP*=1000					
                            self.world_object.position.set(px,py,pz) 
                        else:#陸上
                            if TGT_ORIENT.y==0:
                                Rx, Ry = floor(px-TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5)+0.505, floor(py+TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5)+0.505
                                Lx, Ly = floor(px+TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5)+0.505, floor(py-TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5)+0.505
                            elif 0.05<((TGT_ORIENT.x/TGT_ORIENT.y)**2)**0.05<20:
                                Rx, Ry = px-TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5, py+TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5
                                Lx, Ly = px+TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5, py-TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5
                            else:
                                Rx, Ry = floor(px-TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5)+0.505, floor(py+TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5)+0.505
                                Lx, Ly = floor(px+TGT_ORIENT.y*0.47-TGT_ORIENT.x*0.5)+0.505, floor(py-TGT_ORIENT.x*0.47-TGT_ORIENT.y*0.5)+0.505

                            z_plus = 0
                            AP=0
                            self.front_rcog = [[-1]*64, [-1]*64] # [R,L]
                            dist=0
                            for ii in range(DANSA_CALC_NUM): #高さ2の段差をn段分計算
                                pattern, APplus,dist = self.forward_recognition(px,py,pz-z_plus,dist,TGT_ORIENT,SENSOR_LENGTH)
                                AP+=APplus
                                z_plus+=pattern
                                self.world_object.position.set(px,py,pz)
                                if 0<pattern<666:
                                    continue
                                break
                            if pattern <666:
                                sumc = 0
                            else:
                                sumc = pattern
                                AP = pattern
                            self.world_object.position.set(px,py,pzo)
                            if AP>0:#長距離障害発見時、最適針路探索する
                                nowori = Vertex3(ox,oy,oz) #現在進行方向
                                z_plus = 0
                                APn=0
                                dist=0
                                self.front_rcog = [[-1]*64, [-1]*64] # [R,L]
                                for ii in range(DANSA_CALC_NUM):	
                                    pattern, APplus,dist = self.forward_recognition(px,py,pz-z_plus,dist,nowori,SENSOR_LENGTH)
                                    APn+=APplus
                                    z_plus+=pattern
                                    self.world_object.position.set(px,py,pz)
                                    if 0<pattern<666:
                                        continue
                                    break
                                if pattern <666:
                                    sumc = 0
                                else:
                                    sumc = pattern
                                    APn = pattern
                                if APn>=AP-15:
                                    nowori = TGT_ORIENT
                                else:
                                    AP=APn
                                self.world_object.position.set(px,py,pz)	
                                if self.world_object.velocity.z**2<0.01: #落下状態では進行方向制御しない
                                    if AP>666:	#進行不能針路
                                        r0=self.cast_sensor((Rx, Ry,pz),SENSOR_LENGTH, nowori)
                                        r1=self.cast_sensor((Rx, Ry,pz+1),SENSOR_LENGTH, nowori)
                                        if r0==0: 
                                            r0=SENSOR_LENGTH+2
                                        if r1==0: 
                                            r1=SENSOR_LENGTH+2
                                        l0=self.cast_sensor((Lx, Ly,pz),SENSOR_LENGTH, nowori)
                                        l1=self.cast_sensor((Lx, Ly,pz+1),SENSOR_LENGTH, nowori)
                                        if l0==0:
                                            l0=SENSOR_LENGTH+2
                                        if l1==0:
                                            l1=SENSOR_LENGTH+2
                                        self.world_object.position.set(px,py,pz)
                                        distc=min(r0,r1)+min(l0,l1)
                                        opt = [ox,oy,distc]
                                        if distc<SENSOR_LENGTH*2:
                                            AJ_DEG = max(min(90,177/(2-SENSOR_LENGTH)*distc/2+180-(177/(2-SENSOR_LENGTH)*2)),4)
                                            tdeg = degrees(atan2(TGT_ORIENT.y,TGT_ORIENT.x))
                                            deg = degrees(atan2(oy,ox))
                                            ttdddeg = (tdeg - deg)
                                            if ttdddeg>180:
                                                ttdddeg = ttdddeg-360
                                            for nn in range(KEIRO_TANSAKU_NUM):
                                                if 45>ttdddeg>-45:
                                                    trim=0.5
                                                elif -90>ttdddeg:
                                                    trim = 1
                                                elif 90<ttdddeg:
                                                    trim = 0
                                                elif 45<ttdddeg:
                                                    trim = 0.2
                                                else:
                                                    trim = 0.8			
                                                ddeg =(random.random()-trim)*AJ_DEG #+-deg
                                                ddeg += deg
                                                oxi =cos(radians(ddeg))
                                                oyi =sin(radians(ddeg))
                                                norm = (oxi**2+oyi**2+oz**2)**0.5
                                                oxi /=norm 
                                                oyi /=norm  
                                                oz /=norm 
                                                optori =  Vertex3(oxi,oyi,oz)
                                                if oyi==0:
                                                    Rx, Ry = floor(px-oyi*0.47-oxi*0.5)+0.505, floor(py+oxi*0.47-oyi*0.5)+0.505
                                                    Lx, Ly = floor(px+oyi*0.47-oxi*0.5)+0.505, floor(py-oxi*0.47-oyi*0.5)+0.505
                                                elif 0.05<((oxi/oyi)**2)**0.05<20:
                                                    Rx, Ry = px-oyi*0.47-oxi*0.5,py+oxi*0.47-oyi*0.5
                                                    Lx, Ly = px+oyi*0.47-oxi*0.5,py-oxi*0.47-oyi*0.5
                                                else:
                                                    Rx, Ry = floor(px-oyi*0.47-oxi*0.5)+0.505, floor(py+oxi*0.47-oyi*0.5)+0.505
                                                    Lx, Ly = floor(px+oyi*0.47-oxi*0.5)+0.505, floor(py-oxi*0.47-oyi*0.5)+0.505
                                                r0=self.cast_sensor((Rx, Ry,pz),SENSOR_LENGTH, optori)
                                                r1=self.cast_sensor((Rx, Ry,pz+1),SENSOR_LENGTH, optori)
                                                if r0==0: 
                                                    r0=SENSOR_LENGTH+2
                                                if r1==0: 
                                                    r1=SENSOR_LENGTH+2
                                                l0=self.cast_sensor((Lx, Ly,pz),SENSOR_LENGTH, optori)
                                                l1=self.cast_sensor((Lx, Ly,pz+1),SENSOR_LENGTH, optori)
                                                if l0==0:
                                                    l0=SENSOR_LENGTH+2
                                                if l1==0:
                                                    l1=SENSOR_LENGTH+2
                                                self.world_object.position.set(px,py,pz)
                                                distc=min(r0,r1)+min(l0,l1)
                                                if distc<SENSOR_LENGTH*2:
                                                    if distc>opt[2]:
                                                        opt = [oxi,oyi,distc]
                                                else:
                                                    opt = [oxi,oyi,999]
                                                    break
                                            ox =opt[0]
                                            oy =opt[1]
                                        norm = (ox**2+oy**2+oz**2)**0.5
                                        ox /=norm 
                                        oy /=norm 
                                        oz /=norm 
                                    else: #進行不能ではないが障害があり進路変更が望ましい
                                        opt = [ox,oy]
                                        tdeg = degrees(atan2(TGT_ORIENT.y,TGT_ORIENT.x))
                                        deg = degrees(atan2(oy,ox))
                                        ttdddeg = (tdeg - deg)
                                        if ttdddeg>180:
                                            ttdddeg = ttdddeg-360
                                        for nn in range(max(1,min(3,AP))):
                                            if 45>ttdddeg>-45:
                                                trim=0.5
                                            elif -90>ttdddeg:
                                                trim = 1
                                            elif 90<ttdddeg:
                                                trim = 0
                                            elif 45<ttdddeg:
                                                trim = 0.2
                                            else:
                                                trim = 0.8
                                            ddeg = (random.random()-trim)*max(1,min(5,AP)) #+-deg
                                            ddeg += deg
                                            oxi =cos(radians(ddeg))
                                            oyi =sin(radians(ddeg))
                                            norm = (oxi**2+oyi**2+oz**2)**0.5
                                            oxi /=norm 
                                            oyi /=norm  
                                            oz /=norm 
                                            optori =  Vertex3(oxi,oyi,oz)
                                            z_plus = 0
                                            APn=0
                                            dist=0
                                            self.front_rcog = [[-1]*64, [-1]*64] # [R,L]
                                            for iii in range(DANSA_CALC_NUM):
                                                pattern, APplus,dist = self.forward_recognition(px,py,pz-z_plus,dist,optori,SENSOR_LENGTH)
                                                APn+=APplus
                                                z_plus+=pattern
                                                self.world_object.position.set(px,py,pz)
                                                if 0<pattern<666:
                                                    continue
                                                break
                                            if pattern <666:
                                                sumc = 0
                                            else:
                                                sumc = pattern
                                                APn = pattern
                                            if APn==0:
                                                opt = [oxi,oyi]
                                                break
                                            elif APn<AP:
                                                opt = [oxi,oyi]
                                                AP=APn		
                                        ox =opt[0]
                                        oy =opt[1]
                                        norm = (ox**2+oy**2+oz**2)**0.5
                                        ox /=norm 
                                        oy /=norm 
                                        oz /=norm 	
                            else:#長距離障害なし、目的方向に進む
                                AP=-1
                                ox,oy,oz = TGT_ORIENT.get()
                    else:
                        AP=0
                        self.long_recg+=1
                    self.world_object.position.set(px,py,pzo)
                    orient =ox,oy,oz
                    obj.set_orientation(ox,oy,oz)
                    self.aim.set_vector(obj.orientation)
                    self.target_orientation.set_vector(self.aim)
                    self.input.add('up')
                    setori = Vertex3(ox,oy,oz)
                    if AP>=0:					#短距離障害検知
                        SENSOR_LENGTH=3
                        umi = 0
                        if pz>=60:
                            umi = 1
                            SENSOR_LENGTH=2
                        self.front_rcog = [[-1]*64, [-1]*64] # [R,L]
                        dist=0
                        pattern, APplus,dist = self.forward_recognition(px,py,pz-umi,dist,setori,SENSOR_LENGTH)
                        self.world_object.position.set(px,py,pzo)
                        frt = 1
                        jumping = False
                        if pattern+umi==0: #前方直近障害なし
                            self.input.add('sprint')
                        elif pattern+umi==1: #前方直近1段差
                            self.input.discard('sprint')
                        elif pattern+umi==-1: #しゃがめば通れる
                            self.input.add('crouch')
                        elif pattern+umi==2: #ジャンプでいける壁
                            if dist<1.5:
                                jumping = True
                                self.input.add('jump')
                            else:
                                self.input.discard('sprint')
                        else:	#完全に正面が壁な状況　左右5ブロック分横にずれたら正面が開けるかを判定
                            SENSOR_LENGTH_I=10
                            for i in range (5):
                                if TGT_ORIENT.y==0:
                                    Rx, Ry = floor(px-TGT_ORIENT.y*(0.47+i)-TGT_ORIENT.x*0.5)+0.505, floor(py+TGT_ORIENT.x*(0.47+i)-TGT_ORIENT.y*0.5)+0.505
                                    Lx, Ly = floor(px+TGT_ORIENT.y*(0.47+i)-TGT_ORIENT.x*0.5)+0.505, floor(py-TGT_ORIENT.x*(0.47+i)-TGT_ORIENT.y*0.5)+0.505
                                elif 0.05<((TGT_ORIENT.x/TGT_ORIENT.y)**2)**0.05<20:
                                    Rx, Ry = px-TGT_ORIENT.y*(0.47+i)-TGT_ORIENT.x*0.5, py+TGT_ORIENT.x*(0.47+i)-TGT_ORIENT.y*0.5
                                    Lx, Ly = px+TGT_ORIENT.y*(0.47+i)-TGT_ORIENT.x*0.5, py-TGT_ORIENT.x*(0.47+i)-TGT_ORIENT.y*0.5
                                else:
                                    Rx, Ry = floor(px-TGT_ORIENT.y*(0.47+i)-TGT_ORIENT.x*0.5)+0.505, floor(py+TGT_ORIENT.x*(0.47+i)-TGT_ORIENT.y*0.5)+0.505
                                    Lx, Ly = floor(px+TGT_ORIENT.y*(0.47+i)-TGT_ORIENT.x*0.5)+0.505, floor(py-TGT_ORIENT.x*(0.47+i)-TGT_ORIENT.y*0.5)+0.505
                                fr = 0
                                for zz in range(3):
                                    fr+=self.cast_sensor((Rx,Ry,pz+zz),SENSOR_LENGTH_I, TGT_ORIENT)
                                    if fr>0:break
                                fl = 0
                                for zz in range(3):
                                    fl+=self.cast_sensor((Lx,Ly,pz+zz),SENSOR_LENGTH_I, TGT_ORIENT)
                                    if fl>0:break
                                self.world_object.position.set(px,py,pzo)
                                if fr==0:
                                    if TGT_ORIENT.y==0:
                                        Rx, Ry = floor(px-TGT_ORIENT.y*(0.47+i)+TGT_ORIENT.x*frt)+0.505, floor(py+TGT_ORIENT.x*(0.47+i)+TGT_ORIENT.y*frt)+0.505
                                    elif 0.05<((TGT_ORIENT.x/TGT_ORIENT.y)**2)**0.05<20:
                                        Rx, Ry = px-TGT_ORIENT.y*(0.47+i)+TGT_ORIENT.x*frt, py+TGT_ORIENT.x*(0.47+i)+TGT_ORIENT.y*frt
                                    else:
                                        Rx, Ry = floor(px-TGT_ORIENT.y*(0.47+i)+TGT_ORIENT.x*frt)+0.505, floor(py+TGT_ORIENT.x*(0.47+i)+TGT_ORIENT.y*frt)+0.505
                                    self.ikeru = [floor(Rx)+0.5,floor(Ry)+0.5,pz,200]
                                    break
                                if fl==0:
                                    if TGT_ORIENT.y==0:
                                        Lx, Ly = floor(px+TGT_ORIENT.y*(0.47+i)+TGT_ORIENT.x*frt)+0.505, floor(py-TGT_ORIENT.x*(0.47+i)+TGT_ORIENT.y*frt)+0.505
                                    elif 0.05<((TGT_ORIENT.x/TGT_ORIENT.y)**2)**0.05<20:
                                        Lx, Ly = px+TGT_ORIENT.y*(0.47+i)+TGT_ORIENT.x*frt, py-TGT_ORIENT.x*(0.47+i)+TGT_ORIENT.y*frt
                                    else:
                                        Lx, Ly = floor(px+TGT_ORIENT.y*(0.47+i)+TGT_ORIENT.x*frt)+0.505, floor(py-TGT_ORIENT.x*(0.47+i)+TGT_ORIENT.y*frt)+0.505
                                    self.ikeru = [floor(Lx)+0.5,floor(Ly)+0.5,pz,200]
                                    break
                        if self.ikeru[3]>0:	#狭路通行モード
                            self.ikeru[3]-=1
                            oxi = (self.ikeru[0])-px
                            oyi = (self.ikeru[1])-py
                            ozi = 0
                            norm = (oxi**2+oyi**2+ozi**2)**0.5
                            if norm>frt-0.5:
                                oxi /=norm 
                                oyi /=norm 
                                ozi /=norm 
                                orient =oxi,oyi,ozi
                                obj.set_orientation(oxi,oyi,ozi)
                                self.aim.set_vector(obj.orientation)
                                self.target_orientation.set_vector(self.aim)
                            else:
                                self.ikeru = [0,0,0,0]
                        else:
                            self.ikeru = [0,0,0,0]						
                        if  (self.world_object.velocity.x**2 + self.world_object.velocity.y**2)**0.5 < 0.0001: #停止状況
                            self.input.discard('sprint')	#とりあえず走るのを止める
                            if self.protocol.map.get_solid(px,py,pz): #しゃがんでない時の頭の位置にブロックがある
                                if not self.protocol.map.get_solid(px,py,pz+1): #しゃがんでない時の頭の位置+1にブロックがない
                                    self.input.add('crouch')
                            if (self.ikeru[3]>0 and self.jisatu>10) or self.jisatu>30:
                                if not self.protocol.building:
                                    self.has_arena_tgt = False
                                    self.stucking=seconds()
                                else:
                                    spade_using = True
                                    if self.tool != SPADE_TOOL:
                                        self.set_tool(SPADE_TOOL)
                                        self.toolchangetime = seconds()	
                                    if seconds() - self.toolchangetime>0.5 and self.tool == SPADE_TOOL:	
                                        digging = self.spadeing()
                            self.jisatu+=1
                            if self.jisatu>1000:
                                self.kill()
                        elif self.jisatu>0:
                            self.jisatu-=1
                        if jumping:
                            if seconds()-self.jumptime>0.5 and obj.velocity.z**2<0.0001:
                                self.input.discard('sprint')
                                self.jumptime=seconds()
                            else:
                                self.input.discard('jump')
                    else:
                        self.input.add('sprint') #前方長距離障害なし
            if self.world_object.velocity.z<-0.01:
                self.input.discard('sprint')
            if not digging:
                self.digtime=seconds()
            if self. tool == SPADE_TOOL and not spade_using:
                self.toolchangetime =  seconds()
                self.set_tool(WEAPON_TOOL)
            if self.world_object.sprint:
                self.sprinttime	=seconds()
            try:
                self.AHT_bot_orient()
            except:
                pass

        def posset_castray(self,pos,d):
            self.world_object.position.set(*pos)			
            return self.world_object.cast_ray(d)
        
        def spadeing(self):
            digging=False
            obj= self.world_object
            px,py,pzo=obj.position.get()
            if self.world_object.crouch:
                pz=pzo-1
            else:
                pz=pzo
            ox = obj.orientation.x
            oy = obj.orientation.y
            if obj.orientation.y==0:
                Cx, Cy = floor(px-ox*0.7)+0.505, floor(py-oy*0.7)+0.505
                Rx, Ry = floor(px-oy*0.47-ox*0.7)+0.505, floor(py+ox*0.47-oy*0.7)+0.505
                Lx, Ly = floor(px+oy*0.47-ox*0.7)+0.505, floor(py-ox*0.47-oy*0.7)+0.505
            elif 0.05<((obj.orientation.x/obj.orientation.y)**2)**0.05<20:
                Cx, Cy = px-ox*0.7, py-oy*0.7
                Rx, Ry = px-oy*0.47-ox*0.7, py+ox*0.47-oy*0.7
                Lx, Ly = px+oy*0.47-ox*0.7, py-ox*0.47-oy*0.7
            else:
                Cx, Cy = floor(px-ox*0.7)+0.505, floor(py-oy*0.7)+0.505
                Rx, Ry = floor(px-oy*0.47-ox*0.7)+0.505, floor(py+ox*0.47-oy*0.7)+0.505
                Lx, Ly = floor(px+oy*0.47-ox*0.7)+0.505, floor(py-ox*0.47-oy*0.7)+0.505
            tgtblockc1 = self.posset_castray((Cx,Cy,pz+1),3)
            tgtblockr1 = self.posset_castray((Rx,Ry,pz+1),3)
            tgtblockl1 = self.posset_castray((Lx,Ly,pz+1),3)
            type = SPADE_DESTROY	#胴位置にブロックあれば右クリ破壊
            if tgtblockl1 is None and tgtblockr1 is None and tgtblockc1 is None:
                tgtblockc0 = self.posset_castray((Cx,Cy,pz),3)
                tgtblockr0 = self.posset_castray((Rx,Ry,pz),3)
                tgtblockl0 = self.posset_castray((Lx,Ly,pz),3)	#胴位置なしかつ頭位置ありでも右クリ破壊
                if tgtblockl0 is None and tgtblockr0 is None and tgtblockc0 is None:
                    tgtblockc2 = self.posset_castray((Cx,Cy,pz+2),2)
                    tgtblockr2 = self.posset_castray((Rx,Ry,pz+2),2)
                    tgtblockl2 = self.posset_castray((Lx,Ly,pz+2),2)	#胴頭位置なしかつ足位置ありなら左クリ破壊
                    tgtblock = self.spade_tgt_block(tgtblockc2,tgtblockr2,tgtblockl2)
                    type = DESTROY_BLOCK
                else:
                    tgtblock = self.spade_tgt_block(tgtblockc0,tgtblockr0,tgtblockl0)
            else:
                tgtblock = self.spade_tgt_block(tgtblockc1,tgtblockr1,tgtblockl1)
            self.world_object.position.set(px,py,pz)
            if tgtblock is not None:
                digging = True 
                if type == DESTROY_BLOCK:
                    self.input.add('primary_fire')
                    if seconds() - self.digtime>0.5:
                        self.digtime=seconds()
                        self.digy(tgtblock[0],tgtblock[1],tgtblock[2], type)
                else:
                    self.input.add('secondary_fire')
                    if seconds() - self.digtime>0.7:
                        self.digtime=seconds()
                        self.digy(tgtblock[0],tgtblock[1],tgtblock[2], type)
            return digging

        def spade_tgt_block(self,c,r,l):
            pos=self.world_object.position.get()
            if c is not None:
                distc = self.distance_calc(c,pos)
                if distc<10:
                    return c
            if r is not None:
                distr = self.distance_calc(r,pos)
            else:
                distr = 10
            if l is not None:
                distl = self.distance_calc(l,pos)
            else:
                distl = 10
            if distr<distl:
                return r
            else:
                return l
        
        def distance_calc(self,a,b):
            try:
                dx = a[0] - b[0]
                dy = a[1] - b[1]
                dz = a[2] - b[2]
                return (dx**2+dy**2+dz**2)**0.5
            except:
                return 0

        def digy(self,x,y,z,value = SPADE_DESTROY):
            if not (0<=x<=511 and 0<=y<=511 and 0<=z<=60):
                return
            map = self.protocol.map
            if not map.get_solid(x, y, z):
                return
            pos = self.world_object.position
            if self.on_block_destroy(x, y, z, value) == False:
                return
            elif value == DESTROY_BLOCK:
                if map.destroy_point(x, y, z):
                    self.blocks = min(50, self.blocks + 1)
                    self.on_block_removed(x, y, z)
                    self.block_destroying(x, y, z)
            elif value == SPADE_DESTROY:
                for zz in [-1,0,1]:
                    for xx in [-1,0,1]:	
                        if map.destroy_point(x+xx, y, z+zz):
                            self.on_block_removed(x+xx, y, z+zz)
                            self.block_destroying(x+xx, y, z+zz)
                    if map.destroy_point(x, y+1, z+zz):
                        self.on_block_removed(x, y+1, z+zz)
                        self.block_destroying(x, y+1, z+zz)
                    if map.destroy_point(x, y-1, z+zz):
                        self.on_block_removed(x, y-1, z+zz)
                        self.block_destroying(x, y-1, z+zz)
            self.protocol.update_entities()			

        def block_destroying(self,x,y,z):
                block_action = BlockAction()
                block_action.player_id = self.player_id
                block_action.value = 1
                block_action.x = x
                block_action.y = y
                block_action.z = z
                self.protocol.broadcast_contained(block_action)
                self.protocol.map.remove_point(x, y, z)

        def flush_input(self):
            input = self.input
            world_object = self.world_object
            if world_object:
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
                        self.protocol.broadcast_contained(input_data)
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
                        self.protocol.broadcast_contained(weapon_input)
                input.clear()

        def set_tool(self, tool):
            if self.on_tool_set_attempt(tool) == False:
                return
            self.tool = tool
            if self.tool == WEAPON_TOOL:
                if self.world_object:
                    self.on_shoot_set(self.world_object.primary_fire)
                    self.weapon_object.set_shoot(self.world_object.primary_fire)
            self.on_tool_changed(self.tool)
            if self.filter_visibility_data:
                return
            set_tool.player_id = self.player_id
            set_tool.value = self.tool
            self.protocol.broadcast_contained(set_tool)
        
        def bot_set_color(self, color):
            if self.on_color_set_attempt(color) == False:
                return
            self.color = color
            self.on_color_set(color)			
            set_color.value = make_color(*color)
            set_color.player_id = self.player_id
            self.protocol.broadcast_contained(set_color, sender = self, save = True)

        def bot_reload(self):
            if self.tool == WEAPON_TOOL and seconds() > self.reloadfin:
                if self.weapon == RIFLE_WEAPON:
                    magsize = 10
                    meyasu = 8
                    rtime = 2.5
                elif self.weapon == SMG_WEAPON:
                    magsize = 30
                    meyasu = 24
                    rtime = 2.5
                elif self.weapon == SHOTGUN_WEAPON:
                    magsize = 6
                    meyasu = 5
                    rtime = 0.5
                if self.tamakazu < meyasu:
                    weapon_reload.player_id = self.player_id
                    weapon_reload.clip_ammo = self.weapon_object.current_ammo
                    weapon_reload.reserve_ammo = self.weapon_object.current_stock
                    self.protocol.broadcast_contained(weapon_reload)
                    self.tamakazu=magsize
                    self.reloadfin=seconds()+rtime
        
        def bot_bullet(self):
            if not self.world_object_alive_onpos():
                return None
            botpos = self.world_object.position.get()
            botori = self.world_object.orientation.get()
            if self.weapon == RIFLE_WEAPON:
                bure = 0.9
            elif self.weapon == SMG_WEAPON:
                bure = 1.4
            elif self.weapon == SHOTGUN_WEAPON:
                bure = 8.5
            theta = degrees(atan2(botori[1],botori[0]))
            phi = degrees(asin(botori[2]))
            V_bure = gauss(0,bure/2.0)
            H_bure = gauss(0,bure/2.0)
            oxy = cos(radians(phi+V_bure))
            ox = oxy*cos(radians(theta+H_bure))
            oy = oxy*sin(radians(theta+H_bure))
            oz = sin(radians(phi+V_bure))
            pos = [botpos[0],botpos[1],botpos[2]]
            ori = ox,oy,oz 
            d_calc = 0.3 #bk
            #最近傍敵までの距離を測定し、そこまで当たり判定計算省略
            nearest_dist=130
            farest_dist = 0
            calcd_player_list=[]
            for player in self.team.other.get_players():
                if player.world_object:
                    ppos=player.world_object.position.get()
                    dist_p=self.distance_calc(pos,ppos)
                    if dist_p<130:
                        px,py,pz=ppos
                        rx,ry,rz=px-botpos[0],py-botpos[1],pz-botpos[2]
                        gaiseki = ry*oz - rz*oy, rz*ox - rx*oz, rx*oy - ry*ox
                        diff_vect = (gaiseki[0]**2 + gaiseki[1]**2 + gaiseki[2]**2)**0.5 #ある程度なす角の小さい物だけを選別
                        if diff_vect<3.5:
                            calcd_player_list.append(player)
                            if nearest_dist>dist_p:
                                nearest_dist=dist_p
                            if farest_dist<dist_p:
                                farest_dist=dist_p
            distance_fly = 0
            for calc_do in range(int(128 / d_calc)):
                pos[0] += ori[0]*d_calc
                pos[1] += ori[1]*d_calc
                pos[2] += ori[2]*d_calc
                distance_fly +=d_calc
                round_pos = (floor(pos[0]), floor(pos[1]), floor(pos[2]))
                _x,_y,_z = round_pos
                if _x > 511 or _x < 0 or _y > 511 or _y < 0 or _z > 62 or _z < -20:
                    return None
                if _z >= 0:
                    if self.protocol.map.get_solid(*round_pos): 
                        return round_pos
                if farest_dist+4 > distance_fly and distance_fly > nearest_dist -4: #最近傍敵プレイヤーに十分接近したら当たり判定計算開始
                    if self.team != None:
                        for player in calcd_player_list:
                            if player.world_object:
                                vpx,vpy,vpz = player.world_object.position.get()
                                vox,voy,voz = player.world_object.orientation.get()
                                x,y,z=pos[0]-vpx-0.05*vox, pos[1]-vpy-0.05*voy, pos[2]-vpz-0.05
                                hit= 0
                                if self.world_object.crouch:
                                    if voy==0:
                                        if -0.3 < z < 0.3:
                                            if -0.3 < x < 0.3:
                                                if -0.3 < y < 0.3:
                                                    hit = 1
                                        elif 0.3<= z < 0.9:
                                            if (vox>0 and -0.7 < x < 0.2) or (vox<0 and -0.2 < x < 0.7):
                                                if -0.4 < y < 0.4:
                                                    hit = 2
                                        elif 0.9<= z < 1.3:
                                            if (vox>0 and -0.4 < x < 0.2) or (vox<0 and -0.2 < x < 0.4):
                                                if -0.4 < y < -0.15 or 0.15 <y < 0.4:
                                                    hit = 3
                                    elif vox==0:
                                        if -0.3 < z < 0.3:
                                            if -0.3 < x < 0.3:
                                                if -0.3 < y < 0.3:
                                                    hit = 1
                                        elif 0.3<= z < 0.9:
                                            if (voy>0 and -0.7 < y < 0.2) or (voy<0 and -0.2 < y < 0.7):
                                                if -0.4 < x < 0.4:
                                                    hit = 2
                                        elif 0.9<= z < 1.3:
                                            if (voy>0 and -0.4 < y < 0.2) or (voy<0 and -0.2 < y < 0.4):
                                                if -0.4 < x < -0.15 or 0.15 <x < 0.4:
                                                    hit = 3
                                    else:
                                        k=vox/voy
                                        if -0.3 < z < 0.3 :# z axis head shot
                                            mae   = -k*x+0.3/voy
                                            usiro = -k*x-0.3/voy
                                            hidari=  x/k+0.3/vox
                                            migi  =  x/k-0.3/vox
                                            if min(mae,usiro) < y < max(mae,usiro):#前後方向命中判定中心+-0.3bk
                                                if min(migi,hidari) < y < max(migi,hidari) :#HS判定　首の上下動は無視
                                                    hit = 1
                                        elif  0.3 <= z < 1.3 :# z axis body or asi shot:
                                            mae   = -k*x+0.2/voy
                                            hidari=  x/k+0.4/vox
                                            migi  =  x/k-0.4/vox
                                            if min(migi,hidari) < y < max(migi,hidari) :#平面方向あたり	手は無視
                                                if 0.3 <= z < 0.9 :# z axis body shot:
                                                    ketu = -k*x-0.7/voy
                                                    if min(mae,ketu) < y < max(mae,ketu):#前後方向命中判定中心+-0.2bk
                                                        hit = 2
                                                elif 0.9<= z < 1.3:# z axis asi shot:
                                                    kakato = -k*x-0.4/voy
                                                    hidariutiasi=  x/k+0.15/vox
                                                    migiutiasi  =  x/k-0.15/vox
                                                    if min(mae,kakato) < y < max(mae,kakato):#前後方向命中判定中心+-0.2bk
                                                        if not (min(hidariutiasi,migiutiasi) < y < max(hidariutiasi,migiutiasi)):
                                                                 hit = 3
                                else:
                                    if voy==0:
                                        if -0.3 < z < 0.3:
                                            if -0.3 < x < 0.3:
                                                if -0.3 < y < 0.3:
                                                    hit = 1
                                        elif 0.3<= z < 1.3:
                                            if -0.2 < x < 0.2:
                                                if -0.4 < y < 0.4:
                                                    hit = 2
                                        elif 1.3<= z < 2.3:
                                            if -0.2 < x < 0.2:
                                                if -0.4 < y < -0.15 or 0.15 <y < 0.4:
                                                    hit = 3
                                    elif vox==0:
                                        if -0.3 < z < 0.3:
                                            if -0.3 < x < 0.3:
                                                if -0.3 < y < 0.3:
                                                    hit = 1
                                        elif 0.3<= z < 1.3:
                                            if -0.4 < x < 0.4:
                                                if -0.2 < y < 0.2:
                                                    hit = 2
                                        elif 1.3<= z < 2.3:
                                            if -0.4 < x < -0.15 or 0.15 < x < 0.4:
                                                if -0.2 < y < 0.2:
                                                    hit = 3
                                    else:	
                                        k=vox/voy
                                        if -0.3 < z < 0.3 :# z axis head shot
                                            mae   = -k*x+0.3/voy
                                            usiro = -k*x-0.3/voy
                                            hidari=  x/k+0.3/vox
                                            migi  =  x/k-0.3/vox
                                            if min(mae,usiro) < y < max(mae,usiro):#前後方向命中判定中心+-0.3bk
                                                if min(migi,hidari) < y < max(migi,hidari) :#HS判定　首の上下動は無視
                                                    hit = 1
                                        elif  0.3 <= z < 2.3 :# z axis body or asi shot: #しゃがみを考慮してない
                                            mae   = -k*x+0.2/voy
                                            usiro = -k*x-0.2/voy
                                            hidari=  x/k+0.4/vox
                                            migi  =  x/k-0.4/vox
                                            hidariutiasi=  x/k+0.15/vox
                                            migiutiasi  =  x/k-0.15/vox
                                            if min(mae,usiro) < y < max(mae,usiro):#前後方向命中判定中心+-0.2bk
                                                if min(migi,hidari) < y < max(migi,hidari) :#平面方向あたり	手は無視
                                                    if 0.3 <= z < 1.3 :# z axis body shot:
                                                        hit = 2
                                                    elif 1.2<= z < 2.3:# z axis asi shot:
                                                        if not (min(hidariutiasi,migiutiasi) < y < max(hidariutiasi,migiutiasi)):
                                                             hit = 3
                                if hit==1:
                                    if self.weapon == RIFLE_WEAPON:
                                        dmg = 100
                                    elif self.weapon == SMG_WEAPON:
                                        dmg = 75
                                    elif self.weapon == SHOTGUN_WEAPON:
                                        dmg = 37
                                    if VSBOTmode:
                                        dmg/=2
                                    if DEBUG_VIRTUAL_HIT:
                                        debugmessage="HIT : headshot, %s, %s"%(self.name,self.weapon)
                                        player.send_chat(debugmessage)
                                        print(debugmessage)
                                        dmg=0						
                                elif hit==2:
                                    if self.weapon == RIFLE_WEAPON:
                                        dmg = 49
                                    elif self.weapon == SMG_WEAPON:
                                        dmg = 29
                                    elif self.weapon == SHOTGUN_WEAPON:
                                        dmg = 26
                                    if VSBOTmode:
                                        dmg/=2
                                    if DEBUG_VIRTUAL_HIT:
                                        debugmessage="HIT : body, %s, %s"%(self.name,self.weapon)
                                        player.send_chat(debugmessage)
                                        print(debugmessage)
                                        dmg=0						
                                elif hit==3:
                                    if self.weapon == RIFLE_WEAPON:
                                        dmg = 33
                                    elif self.weapon == SMG_WEAPON:
                                        dmg = 18
                                    elif self.weapon == SHOTGUN_WEAPON:
                                        dmg = 16
                                    if VSBOTmode:
                                        dmg/=2
                                    if DEBUG_VIRTUAL_HIT:
                                        debugmessage="HIT : asi, %s, %s"%(self.name,self.weapon)
                                        player.send_chat(debugmessage)
                                        print(debugmessage)
                                        dmg=0						
                                if hit>=2:
                                    if self.on_hit(dmg, player, WEAPON_KILL, None) != False:
                                        player.hit(dmg, self, WEAPON_KILL)
                                        return None	
                                elif hit>=1:
                                    if self.on_hit(dmg, player, HEADSHOT_KILL, None) != False:
                                        player.hit(dmg, self, HEADSHOT_KILL)
                                        return None			

        def fire_weapon(self):
            if self.world_object_alive_onpos():
                now = seconds()
                if self.weapon == SMG_WEAPON:
                    cooltime = 0.11
                elif self.weapon == RIFLE_WEAPON:
                    cooltime = 0.6
                elif self.weapon == SHOTGUN_WEAPON:
                    cooltime = 1.1
                if now-self.last_fire>cooltime and self.tamakazu>0 and now > self.reloadfin:#射撃可能なタイミングか判定 残弾確認
                    if self.smg_shooting>0 or now-self.last_fire>self.next_fire_time:#予定間隔空けたか判定（SMGなら連射可）
                        self.next_fire_time=uniform(0,(1.2-self.cpulevel)*2.5)+1.1	#次の射撃の予定間隔
                        if self.weapon == SMG_WEAPON:
                            if self.smg_shooting>0:
                                self.smg_shooting-=1
                            else:
                                self.smg_shooting=int(triangular(1, 30, 7))
                        else:
                            self.smg_shooting=0
                        self.tamakazu-=1
                        self.input.add('primary_fire')
                        self.fireinput=4
                        if self.tamakazu<=0:
                            self.bot_reload()
                        if self.protocol.bot_damage == True:
                            blkhit = self.bot_bullet() #射撃実行、当たり判定計算（プレイヤー優先、ブロックは次いで）
                            if blkhit:#ブロック衝突判定有れば破壊処理
                                if blkhit in self.damaged_block:
                                    self.damaged_block.remove(blkhit)
                                    self.fire_block_break(*blkhit)
                                else:
                                    self.damaged_block.append(blkhit) #めんどくさいので武器問わず2発で崩壊
                            if self.weapon == SHOTGUN_WEAPON: #SGの場合さらに7回同一処理
                                for n in range(7):
                                    blkhit = self.bot_bullet()
                                    if blkhit:
                                        if blkhit in self.damaged_block:
                                            self.damaged_block.remove(blkhit)
                                            self.fire_block_break(*blkhit)
                                        else:
                                            self.damaged_block.append(blkhit)
                        #リコイル計算
                        theta = degrees(atan2(self.world_object.orientation.y,self.world_object.orientation.x))
                        phi = degrees(asin(self.world_object.orientation.z))
                        DEFAULT_RECOIL_V=0.716
                        DEFAULT_RECOIL_H=0.05
                        if self.weapon == RIFLE_WEAPON:
                            weapon_ratio = 4.0
                        elif self.weapon == SMG_WEAPON:
                            weapon_ratio = 1.0
                        elif self.weapon == SHOTGUN_WEAPON:
                            weapon_ratio = 4.0
                        RECOIL_H=gauss(0, DEFAULT_RECOIL_H*weapon_ratio/3)
                        RECOIL_V = DEFAULT_RECOIL_V*weapon_ratio
                        recoil_control=0
                        if random.random()<self.cpulevel:#超反応リコイルコントロール
                            recoil_control= gauss(RECOIL_V*0.5, (1.3-self.cpulevel)*RECOIL_V*0.5/3.0)+RECOIL_V*0.35
                        ox = cos(radians(theta+RECOIL_H))
                        oy = sin(radians(theta+RECOIL_H))
                        oz = sin(radians(phi-RECOIL_V))	
                        self.xoff_okure+=RECOIL_H
                        self.yoff_okure-=(RECOIL_V-recoil_control)
                        self.world_object.set_orientation(ox,oy,oz)
                        self.aim.set_vector(self.world_object.orientation)
                        self.target_orientation.set_vector(self.aim) #リコイル後のorientationに変更 iminasage
                        xoff,yoff = self.new_gosa(True) #誤差収束リセット
                        self.xoff_okure += xoff
                        self.yoff_okure += yoff #self.new_gosa(True) #誤差収束リセット

                        self.last_fire = now

        def fire_block_break(self,x,y,z):
            if not (0<=x<=511 and 0<=y<=511 and 0<=z<=60):
                return
            value = DESTROY_BLOCK
            map = self.protocol.map
            if not map.get_solid(x, y, z):
                return
            pos = self.world_object.position
            if self.on_block_destroy(x, y, z, value) == False:
                return
            if map.destroy_point(x, y, z):
                self.on_block_removed(x, y, z)
                block_action = BlockAction()
                block_action.x = x
                block_action.y = y
                block_action.z = z
                block_action.value = value
                block_action.player_id = self.player_id
                self.protocol.broadcast_contained(block_action, save = True)
                self.protocol.update_entities()
        
        def on_hit(self, damage, hitplayer, type, grenade):
            if hitplayer.local:
                if self.team != hitplayer.team:
                    if hitplayer.canseeY(hitplayer.world_object.position, self.world_object.position)>=0:
                        hitplayer.aim_at = self		#攻撃を受けた場合攻撃対象に強制変更設定
            return connection.on_hit(self, damage, hitplayer, type, grenade)

        def on_spawn(self, pos):
            if self.protocol.bot_adjusting and self.local:
                if self.protocol.disconnect_suru[self.team.id]:
                    id = self.team.id
                    self.disconnect()
                    self.protocol.disconnect_suru[id]=False
                    return False
                self.protocol.bot_num_adjust()
            if not self.protocol.bot_adjusting:
                self.protocol.bot_num_adjust(True)
            if not self.local:
                return connection.on_spawn(self, pos)	#人間の処理終わり
            #レベルを調整する	
            teamcpulv = self.protocol.teamcpulv[self.team.id]
            sita= min(99,max(0,teamcpulv[0]-teamcpulv[1]))
            ue  = min(100,max(1,teamcpulv[0]+teamcpulv[1]))
            if self.protocol.reflesh_bot and not sita<self.cpulevel*100<ue:	#lvが既定の範囲内に無い
                if LV_PRINT:	print("LEVEL_CHANGE",self.team.name, teamcpulv[0])
                self.protocol.reflesh_bot=False
                if LVCHANGE_RECONNECT:
                    callLater(0.001,self.disconnect)
                    callLater(0.01,self.protocol.add_bot,self.team)#鯖に入りなおしてレベルを変えてくれ
                else:
                    self.cpulevel=uniform(sita/100.0,ue/100.0)#鯖に出入りしないで内部数値だけ変える
                    self.bot_property()
                lvsum=0
                numsum=0
                for bot in list(self.protocol.players.values()):
                    if bot.local and bot.team==self.team:
                        lvsum+=bot.cpulevel*100
                        numsum+=1.0
                if not sita<lvsum/numsum<ue:#チーム全体の平均値が規定値に無い場合は変化を継続
                    self.protocol.reflesh_bot=True
            if self.world_object:										
                if self.team == self.protocol.blue_team:
                    self.target_direction = Vertex3(1,0,0)
                else:
                    self.target_direction = Vertex3(-1,0,0)
                self.world_object.set_orientation(*self.target_direction.get())
                self.aim.set_vector(self.world_object.orientation)
                self.target_orientation.set_vector(self.aim)
                self.set_tool(WEAPON_TOOL)
                self.aim_at = self.assigned_position= None
                self.jisatu=0
                self.ikeru=[0,0,0,0]
                self.has_arena_tgt =self.stopmotion= False
                self.xoff_tebure = self.yoff_tebure = self.xoff_okure = self.yoff_okure = self.vel =self.large_omega_x=self.large_omega_y=self.omega=0
                self.movezure_x=self.movezure_y=self.movezure_z=0
                self.smg_shooting= self.aim_quit=self.long_recg=self.stucking=0
                self.ave_d_theta=[0]*30
                self.ave_d_phi=[0]*30
                self.pre2ori_theta = self.pre2ori_phi=0
                self.enemy_lost=self.enemy_lost_temp=None
                self.gre_avoiding=self.gre_ignore=False
                self.avoiding_danger_gre=None
                self.grenade_keep=self.grenade_pinpull=self.keepinggreoffset=0
                self.grenade_keeping=self.keepinggrephimax=False
                self.grenade_throw_orienation=1,0,0
                self.reloadfin=0
                if self.weapon == RIFLE_WEAPON:
                    self.tamakazu=10
                elif self.weapon == SMG_WEAPON:
                    self.tamakazu=30
                elif self.weapon == SHOTGUN_WEAPON:
                    self.tamakazu=6
                blue_human, blue_bot, green_human, green_bot = self.protocol.count_human_bot()
                humannum=blue_human+green_human
                if VSBOTmode:
                    if humannum<4:
                        self.respawn_time = self.protocol.respawn_time
                    else:
                        self.respawn_time = self.protocol.respawn_time-humannum
                self.damaged_block = []
                connection.on_spawn(self, pos)
                self.color = (0xDF, 0x00, 0xDF)
                self.bot_set_color(self.color) 

        def get_spawn_location(self):
            if VSBOTmode:
                living_player = []
                for player in self.protocol.blue_team.get_players():
                    if player.hp is not None and player.hp > 0:
                        living_player.append(player)
                if self.team == self.protocol.blue_team:
                    if len(living_player)>=2:
                        mother = choice(living_player)
                    elif len(living_player)==1:
                        mother = living_player[0]
                    else:
                        mother = None
                    if mother is None:
                        x,y,z = 1,uniform(255-150,255+150),1
                    else:
                        x,y,z = mother.world_object.position.get()
                    return x,y,z
                if self.team== self.protocol.green_team:
                    nx,ny= uniform(120,150), uniform(-50,50)
                    if len(living_player)>=1:
                        if len(living_player)>=2:
                            tgt = choice(living_player)
                        elif len(living_player)==1:
                            tgt = living_player[0]
                        tgt = choice(living_player)
                        tobj = tgt.world_object
                        px,py,pz=tobj.position.get()
                        if random>0.5:
                            vx,vy,vz = tobj.velocity.get()
                            vxy = (vx**2 + vy**2 )**0.5
                            if vxy>0.2:
                                theta = atan2(vy, vx)
                                xx = nx*cos(theta) - ny*sin(theta)
                                yy = nx*sin(theta) + ny*cos(theta)
                                nx,ny = xx , yy
                        sx,sy = px + nx , py + ny 
                        sx = min(511, max(0, sx))
                        sy = min(511, max(0, sy))
                        sz = self.protocol.map.get_z(sx,sy)
    
                        return sx,sy,sz
                    else:
                        return 170, uniform(255-150,255+150), 0
            return connection.get_spawn_location(self)

        def gamewin(self):
            self.protocol.gamewon = True
            self.protocol.reset_game(self)
            print("stage %s cleared"%self.protocol.stage_level)
            self.protocol.send_chat('OO00ooooooooooooooooo00OO')
            self.protocol.send_chat('O0o     C L E A R     o0O')
            self.protocol.send_chat('O0o      STAGE %s      o0O'%self.protocol.stage_level)
            self.protocol.send_chat('OO00ooooooooooooooooo00OO')
            if len(self.protocol.connections) != 0:
                f = open('vsbot_gamelog.txt', 'a') 
                memnames=""
                for player in self.protocol.blue_team.get_players():
                    memnames+=player.name+" "
                tim = seconds() - self.protocol.tmr_start
                str="stage%s clear!  time:%dsec  kill:%d  players:%d (%s) "%(self.protocol.stage_level,tim,self.protocol.kill_score, len(self.protocol.connections), memnames.rstrip())
                date = "%s"%datetime.datetime.now()
                date = date[:-7]
                date = "%s  "%date
                f.write(date+" "+str+'\n') 
                f.close()
                print(str)
            self.protocol.send_chat(str)
            self.protocol.on_game_end()
        
        def on_connect(self):
            if self.local:
                return connection.on_connect(self)
            callLater(0.1,self.protocol.bot_num_adjust,True)
            protocol = self.protocol
            if len(protocol.connections) + len(protocol.bots) > 32:
                protocol.bots[-1].disconnect()
            connection.on_connect(self)

        def on_join(self):
            if self.local:
                return connection.on_join(self)
            callLater(0.1,self.protocol.bot_num_adjust,True)
            protocol = self.protocol
            if len(protocol.connections) + len(protocol.bots) > 32:
                protocol.bots[-1].disconnect()
            connection.on_join(self)

        def on_team_join(self, team):
            if not self.local:
                callLater(0.1,self.protocol.bot_num_adjust,True)
                if not self.ois:
                    self.ois = True	
                    for bot in self.protocol.bots:
                        bot.bot_chat_choice("ois")
                if BOT_IN_BOTH:	#チーム間の人間比率が偏ってる場合、人間多いチームをチームFULL扱いにする
                    blue_human, blue_bot, green_human, green_bot = self.protocol.count_human_bot()
                    if blue_human<green_human:
                        if team == self.protocol.green_team:
                            self.send_chat("Team is full, moved to %s" % self.protocol.blue_team.name)
                            return False
                    elif blue_human>green_human:
                        if team == self.protocol.blue_team:
                            self.send_chat("Team is full, moved to %s" % self.protocol.green_team.name)
                            return False
            return connection.on_team_join(self, team)	

        def chat_analysis(self,chat):
            bot_giwaku=["bot", "npc", "Bot", "BOT", "NPC"]
            aimbot=["aimbot","AimBot", "AIMBOT"]

            if any(word in chat for word in bot_giwaku):
                if not any(word in chat for word in aimbot):
                    for bot in self.protocol.bots:
                        bot.bot_chat_choice("botjane")
            ois=["ois", "oiu", "uio", "hola", "hello", "hi!", "hi ", "Hola"]
            if any(word in chat for word in ois):
                for bot in self.protocol.bots:
                    bot.bot_chat_choice("ois")

        def on_chat(self, value, global_message):
            if global_message and not self.local:
                self.chat_analysis(value)
            return connection.on_chat(self, value, global_message)

        def bot_chat_choice(self,topic):
            message = "default_bot_message"
            if topic == "ois":
                list_ois = ("hello","ho","hola","Hola!","hey","hello","HOLA","s","hola","hellow","br?","hi","HELLO","Hi","hi","Hi","hi","HI","hello","uis","os","ou","oiu",
                    "us","oiu","oiu","oiu","iu","hola","YEA!","ois","HOLA","ois","ois","oiu","us","iu","hisasiburi", "oius","oisu","YAA", "hola", "hi","oi","u","ois","oiu")
                message=choice(list_ois)
                say_or_not=0.05
                say_time=7
            elif topic == "sinda":
                list_sinda = ("umee","dameka","aa","gununu","majikaa","osikatta","atatta?","kusso","wtf xD","shitgun :/",":/","wtf man","wtgf","wwwwtttfff","ll smg gay",":o",
                    "LAAAG","the lag is real}","what","op shit","laggy server","no so bad this lag","Wtf?. Hp?","aaaa lag","xd","XD good","xD ya","nice","NOOOOOOOOOOOOOOOOO",
                    "lafg","jjajajaaj","xdddddd","XD",":'C","NAAA",">:v",">:V","nuv","damn","DAMN","DAMN","damn ","lagging cunt","damn it","fuck","te di headshot","inmoratal",
                    "good","jaja","jajajaja","Hp?","huh","pfff","pfft","WWTF","nice","nice kill","good kill","lol","jaja}","uups","oooooooooooo","haaaaaaaaaaa","laaaag","where",
                    "hack","xd","xd","lag","xdddddd","hay","xd","lol?","hp?","lagg","LAAAAAAAAAG!","WTF","WTF","jajajaja","jajjajjaajajja","SHITgunner","NOOB","HAX","sinda","uson",
                    "ee","fuck","fack","kuso","kusso","ti","tikusyo","aa","aaaaa","uaa","kuso","guu","gununu","ahii","tuyoi","umaina","hack","tii","yarareta","mumu","fuuuckkk",
                    "aaaaaa","kono","hack","hacker","majika", "kussooo","kusou","yabe", "fuee", "aan","an","kuu","kuso","sinda")
                message=choice(list_sinda)
                say_or_not=0.02
                say_time=1
            elif topic == "botjane":
                list_botjane = ("who is bot?","darega","darega bot jai","dorega bot da", "bot irunoka","dore bot", "is there any bots?", "bot?", "Im not bot", "are you bot?", "who?", "who", "dore", "idk", 
                    "is all green bot?","I am human", "ore ha ningen da", "bot ja nee yo", "bot janaiyo", "omae bot nanoka", "koitu bot ka?", "is he bot?", "i think he is bot",
                     "really?", "oh really?", "bot is strong", "ore ningen", "bot dore", "wakaran", "dare ga bot nanoka wakaran", "minnna ningen  deha", "I think all player is human",
                    "there is no NPC", "ore to omae igai zennin bot dayo", "all players are bots except I and you", "Im a perfect human", "no bots in servers", "is there any bot?", "they have pretty fking good aim",
                    "bots can talk to each other?","did you make them?", "i think there are only 5-6 of us humans", "im prettys ure there are bots here", "how many humans are here?")
                message=choice(list_botjane)
                say_or_not=0.25
                say_time=8
            elif topic == "zakko":
                list_zakko = ("noob","noobs","lol", "yeah", "haha","hehe","nob","nooooob","noob","zako","zakko", "zakkk", "zazazaza","yowa","kkkkk","llolol","lmao","pya-","noobs",
                    "za-ko","bot ni makete yannno wwww", "www","wwwww","otintin biro-n", "you are loser", "syosen haibokusya jakee", "weweewewewe","nuv","NOOB","NOOOOOB")
                message=choice(list_zakko)
                say_or_not=0.7
                say_time=1
            if random.random()<say_or_not:
                callLater(random.random()*say_time+0.3, self.bot_chat_say,message)

        def bot_chat_say(self, message):
            if not BOTMUTE and self:
                if self.name != None:
                    contained = ChatMessage()
                    global_message = contained.chat_type == CHAT_ALL
                    contained.chat_type = [CHAT_TEAM, CHAT_ALL][int(global_message)]
                    contained.value = message
                    contained.player_id = self.player_id
                    self.protocol.broadcast_contained(contained)
                    self.on_chat(message, global_message)

        def on_disconnect(self):
            for bot in self.protocol.bots:
                if bot.aim_at is self:
                    bot.aim_at = None
            if VSBOTmode:
                if not self.local:
                    if self.world_object:
                        self.on_kill(self, 0, None)
            connection.on_disconnect(self)

        def respawn(self):
            if VSBOTmode and not VSBOT_alone:
                if not self.local:
                    if self.team.spectator:
                        self.spawn_call = callLater(0.01, self.spawn)
                    else:
                        if self.spawn_call is None:
                            self.spawn_call = callLater(114514,None)
                        return False
            return connection.respawn(self)	

        def aim_at_reset(self):
            self.aim_at = None
        
        def on_kill(self, killer, type, grenade):
            if LV_AUTO_ADJUST>=1:
                if self and killer:
                    if self!=killer:
                        blue_human, blue_bot, green_human, green_bot = self.protocol.count_human_bot()
                        if self.team==self.protocol.blue_team:
                            selfman=float(blue_human+blue_bot)
                            otherman=float(green_human+green_bot)
                        if self.team==self.protocol.green_team:
                            otherman=float(blue_human+blue_bot)
                            selfman=float(green_human+green_bot)
                        ratio=otherman/selfman
                        if LV_AUTO_ADJUST==1 or LV_AUTO_ADJUST==3 : # bot vs human adj
                            if self.local or killer.local and not (self.local and killer.local): # bot and human 1;1
                                if self.local:
                                    self.protocol.bot_level_average_change+=ratio
                                    teamcpulv=self.protocol.teamcpulv[self.team.id]
                                if killer.local:
                                    self.protocol.bot_level_average_change-=1.0
                                    teamcpulv=self.protocol.teamcpulv[killer.team.id]
                                if not -0.5*5<self.protocol.bot_level_average_change<0.5*5:
                                    self.protocol.bot_level_average+=self.protocol.bot_level_average_change
                                    self.protocol.bot_level_average=min(99+teamcpulv[1], max(1-teamcpulv[1], self.protocol.bot_level_average))
                                    for i in range(2):
                                        self.protocol.teamcpulv[i][0]=min(99+teamcpulv[i], max(1-teamcpulv[i], self.protocol.bot_level_average+self.protocol.bot_level_adjust[i]))
                                    self.protocol.reflesh_bot=True
                                    self.protocol.bot_level_average_change=0
                                if not self.protocol.reflesh_bot:
                                    lvsum=0
                                    numsum=0
                                    for bot in list(self.protocol.players.values()):
                                        if bot.local:
                                            lvsum+=bot.cpulevel
                                            numsum+=1.0
                                    if not teamcpulv[0]-teamcpulv[1]<lvsum/numsum<teamcpulv[0]+teamcpulv[1]:
                                        self.protocol.reflesh_bot=True
                        if LV_AUTO_ADJUST==2 or LV_AUTO_ADJUST==3 : # blue vs green adj
                            self.protocol.levelchange[self.team.id]+=ratio
                            self.protocol.levelchange[killer.team.id]-=1.0
                            for hito in [self, killer]:
                                teamcpulv=self.protocol.teamcpulv[hito.team.id]
                                if not -0.5*teamcpulv[1]<self.protocol.levelchange[hito.team.id]<0.5*teamcpulv[1]:
                                    self.protocol.bot_level_adjust[hito.team.id]+=self.protocol.levelchange[hito.team.id]
                                    self.protocol.teamcpulv[hito.team.id][0]=min(99+teamcpulv[1], max(1-teamcpulv[1],self.protocol.bot_level_average+self.protocol.bot_level_adjust[hito.team.id]))
                                    self.protocol.levelchange[hito.team.id]=0
                                    self.protocol.reflesh_bot=True
            for bot in self.protocol.bots:
                if bot.aim_at == self:
                    callLater(0.2+(1-self.cpulevel)*random.random(),bot.aim_at_reset)
            if self.local:
                if killer:
                    if killer != self:
                        self.bot_chat_choice("sinda")
                        self.protocol.kill_score+=1	
        #	if killer.local:
        #		if not self.local:
        #				killer.bot_chat_choice("zakko")
            if VSBOTmode:
                pos = self.world_object.position
                if self.team == self.protocol.blue_team or self.team.spectator:  
                    if VSBOT_alone:
                        self.respawn_time = 30
                    else:
                        self.respawn_time = -1
                    for bot in self.protocol.bots:
                        if bot.aim_at is self:
                            bot.aim_at = None
                    arive=0
                    for human in self.protocol.blue_team.get_players():
                        if self!=human:
                            if (human.hp) and (human.world_object): 
                                arive+=1
                    if arive<=0:
                        callLater(1.00,self.protocol.send_chat,'     ---------------------------')
                        callLater(1.01,self.protocol.send_chat,'     --   G A M E   O V E R   --')
                        callLater(1.02,self.protocol.send_chat,'     --  All human were dead  --')
                        callLater(1.03,self.protocol.send_chat,'     ---------------------------')
                        if len(self.protocol.connections) != 0:
                            f = open('vsbot_gamelog.txt', 'a') 
                            memnames=""
                            for player in self.protocol.blue_team.get_players():
                                memnames+=player.name+" "
                            tim = seconds() - self.protocol.tmr_start
                            highx = 0
                            for player in self.protocol.blue_team.get_players():
                                if player.world_object:
                                        xpl = player.world_object.position.x
                                        if highx < xpl:
                                            highx = xpl
                            str="GAMEOVER(stage%s)  FRONT:x=%d  time:%dsec  kill:%d  players:%d (%s)"%(self.protocol.stage_level,highx,tim,self.protocol.kill_score, len(self.protocol.connections), memnames.rstrip())
                            date = "%s"%datetime.datetime.now()
                            date = date[:-7]
                            date = "%s  "%date
                            f.write(date+str+'\n') 
                            f.close()
                            print(str)
                            self.protocol.send_chat(str)
                        self.protocol.kill_score = 0				
                        self.protocol.tmr_start = seconds()
                        if VSBOT_INTEL:
                            self.protocol.flag_reset()
                        callLater(5, self.all_sosei)
                    else:
                        self.protocol.send_chat("%s was killed in %s !!  (%s humans alive)"%(self.name,to_coordinates(pos.x, pos.y),arive ))
                                            
                                            
            return connection.on_kill(self, killer, type, grenade)
                
        def on_shoot_set(self, first):	
            if self.world_object_alive_onpos():		
                if first and self.tool == WEAPON_TOOL:
                    self.noise(4)
                    self.FCcontact(self.world_object.orientation.get())
            return connection.on_shoot_set(self, first)
        
        def _send_connection_data(self):
            if self.local:
                if self.player_id is None:
                    self.player_id = self.protocol.player_ids.pop()
                return
            connection._send_connection_data(self)
        
        def send_map(self, data = None):
            if self.local:
                self.on_join()
                return
            connection.send_map(self, data)
        
        def timer_received(self, value):
            if self.local:
                return
            connection.timer_received(self, value)
        
        def send_loader(self, loader, ack = False, byte = 0):
            if self.local:
                return
            return connection.send_loader(self, loader, ack, byte)

        def FCcontact(self,ori):		#至近弾検知で交戦開始	
            if self.world_object_alive_onpos():
                for player in self.team.other.get_players():
                    if player.local:#敵bot全員の座標を確認して、射線となす角が一定以下ならそのbotのヘイトを受ける
                        epos= player.world_object.position
                        pos=self.world_object.position
                        if player.canseeY(epos, pos)>=0:
                            ex,ey,ez = epos.get()
                            px,py,pz = pos.get()
                            nx,ny,nz = ex-px, ey-py, ez-pz
                            dist = (nx**2+ny**2+nz**2)**0.5
                            if dist<125:
                                nx/=dist
                                ny/=dist
                                nz/=dist
                                ox,oy,oz=ori
                                naiseki = nx*ox + ny*oy + nz*oz
                                if naiseki>1:
                                    naiseki=1
                                if naiseki<-1:
                                    naiseki=-1
                                nasukaku = degrees(acos(naiseki))
                                if nasukaku<10:
                                    if player.aim_at == None:
                                        player.aim_at = self

        def on_orientation_update(self, ox, oy, oz):
            if self.world_object_alive_onpos():
                if self.world_object.primary_fire and self.tool == WEAPON_TOOL:
                    self.FCcontact((ox,oy,oz))
            return connection.on_orientation_update(self, ox, oy, oz)

    return BotProtocol, BotConnection

#original comment
#
# BASIC BOTS
#
# fakes a connection and partially replicates player behavior
# 
# pathfinding was stripped out since it is unfinished and depended
# on the C++ navigation module
# 
# requires adding the 'local' attribute to server.py's ServerConnection
# 
# *** 201,206 ****
# --- 201,207 ----
#	   last_block = None
#	   map_data = None
#	   last_position_update = None
# +	 local = False
#	   
#	   def __init__(self, *arg, **kw):
#		   BaseConnection.__init__(self, *arg, **kw)
# *** 211,216 ****
# --- 212,219 ----
#		   self.rapids = SlidingWindow(RAPID_WINDOW_ENTRIES)
#	   
#	   def on_connect(self):
# +		 if self.local:
# +			 return
#		   if self.peer.eventData != self.protocol.version:
#			   self.disconnect(ERROR_WRONG_VERSION)
#			   return
# 
# bots should stare at you and pull the pin on a grenade when you get too close
# /addbot [amount] [green|blue]
# /toggleai