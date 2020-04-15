"""
Kraken

by hompy

fixed for 0.75 by thepolm3
updated and improved by lecom (thanks to JohnRambozo for telling me how kraken gameplay was on .63 and for hosting it for a long time)
"""

from collections import deque
from math import *
from random import randrange, uniform, choice
from operator import itemgetter, attrgetter
from itertools import product
 
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from pyspades.server import *
from pyspades.world import Grenade
from pyspades.common import Vertex3, Quaternion, make_color, coordinates, get_color
from pyspades.collision import vector_collision, distance_3d_vector
from pyspades.constants import *
from commands import name, add, get_player, admin
from gc import get_referrers
from pyspades.weapon import Rifle,SMG,Shotgun
from scheduler import Scheduler

NEW_WEAPONS=True
ENABLE_REGEN=True
FAST_RUN=True

NO_WATER_DAMAGE_TIME=10 #Remove water damage after spawning, for n seconds

if NEW_WEAPONS:
	Shotgun.ammo=1
	Shotgun.stock=15
	Shotgun.reload_time=7
	
	Rifle.stock=30
	SMG.stock=90

SHOT_DELAY=.017

BLOCK_REMOVE_TENTACLE_HIT=1
BLOCK_REMOVE_TENTACLE_KILL=2
BLOCK_REMOVE_KRAKEN_KILL=4
	
RESTOCK_TIMER_SPEED=.08
REGEN_TIMER_SPEED=.25
REGEN_PLAYER_RATIO=7 #The length between 2 regen periods is the player count divided by this
RESTOCK_PLAYER_RATIO=12 #Same for ammo
RESTOCK_COUNT=(
	5,
	20,
	2
)

CANNON_SHOT_SPEED=7
 
ALLOW_KRAKEN_COMMAND = True

TRAPPED_FREE_TIME=40
KRAKEN_WIN_ANNOUNCEMENT='Arrrrrrrrrrr! You won and killed all krakens.'
MAP_CHANGE_DELAY=5
KRAKEN_ADD_SCORE=True
KRAKEN_PLAYER_ID=31
USE_DAYCYCLE = False
RESPAWN_TIME = 15
#FALLING_BLOCK_COLOR = 0x606060
FALLING_BLOCK_DAMAGE = 100
FALLING_BLOCK_Z = 0
FALLING_BLOCK_COUNT=15
FALLING_BLOCK_START_DELAY=2
FALLING_BLOCK_COLOR=make_color(40,45,53)
REGEN_ONSET = 2.0
REGEN_FREQUENCY = 0.15
REGEN_AMOUNT = 3
WATER_DAMAGE = 25
GRAB_DAMAGE = 40
EYE_PAIN_TIME = 8.0 if not FAST_RUN else 1.0
KRAKEN_BLACK = make_color(20,20,35)
KRAKEN_BLOOD = make_color(120, 255, 120)
KRAKEN_EYE_SMALL = [
    ( 0, 0, -1, 0xC00000),
    ( 0, 0, -2, 0x400000),
    ( 0, 0, -3, 0xC00000),
    (-1, 0, -1, 0xFF0000),
    (-1, 0, -2, 0xC00000),
    (-1, 0, -3, 0x800000),
    ( 1, 0, -1, 0xFF0000),
    ( 1, 0, -2, 0xC00000),
    ( 1, 0, -3, 0xFFFFFF)]
KRAKEN_EYE_SMALL_CLOSED = [
    (-1, 0, -1, KRAKEN_BLACK),
    (-1, 0, -2, KRAKEN_BLACK),
    (-1, 0, -3, KRAKEN_BLACK),
    ( 1, 0, -1, KRAKEN_BLACK),
    ( 1, 0, -2, KRAKEN_BLACK),
    ( 1, 0, -3, KRAKEN_BLACK),
    ( 0, 0, -1, KRAKEN_BLACK),
    ( 0, 0, -2, KRAKEN_BLACK),
    ( 0, 0, -3, KRAKEN_BLACK)]
 
def conv_color(val):
    return ((val >> 16) & 255, (val >> 8) & 255, val & 255)
 
def cube(s):
    s0, s1 = -s / 2 + 1, s / 2 + 1
    return product(xrange(s0, s1), repeat = 3)
 
def prism(x, y, z, w, d, h):
    return product(xrange(x, x + w), xrange(y, y + d), xrange(z, z + h))
 
def plane(r):
    r0, r1 = -r / 2 + 1, r / 2 + 1
    return product(xrange(r0, r1), repeat = 2)
 
def disc(rr, x = 0, y = 0, min_rr = None):
    for u, v in plane(rr):
        d = u * u + v * v
        if d > rr or (min_rr and d < min_rr):
            continue
        yield x + u, y + v
 
def sphere(r, x = 0, y = 0, z = 0, min_r = None):
    rr = r * r
    min_rr = min_r and min_r * min_r
    for w, v, u in cube(r):
        d = u * u + v * v + w * w
        if d > rr or (min_r and d < min_rr):
            continue
        yield x + u, y + v, z + w
 
def aabb(x, y, z, i, j, k, w, d, h):
    return not (x < i or x > i + w or y < j or y > j + d or z < k or z > k + h)
 
def aabb_centered(x, y, z, i, j, k, s):
    return not (x < i - s or x > i + s or y < j - s or y > j + s or
        z < k - s or z > k + s)
 
def randrangerect(x1, y1, x2, y2):
    return randrange(x1, x2), randrange(y1, y2)
 
def fall_eta(height):
    return 2.0 * (height / 64.0) ** 0.75
 
def is_valid_enemy(player):
    if not player.world_object:
	return False
    return not (player.world_object.dead or
        player.grabbed_by or player.trapped or player.regenerating or player.god)
 
class Animated:
    blocks_per_cycle = 3
    build_interval = 0.01
    build_queue = None
    build_loop = None
    blocks = None
    
    def __init__(self, protocol):
        self.protocol = protocol
        self.build_queue = deque()
        self.build_loop = LoopingCall(self.build_cycle)
        self.build_loop.start(self.build_interval)
        self.blocks = set()
    
    def build_cycle(self):
        if not self.build_queue:
            return        
        blocks_left = self.blocks_per_cycle
        last_color = None
        while self.build_queue and blocks_left > 0:
            x, y, z, color = self.build_queue.popleft()
            if color != last_color:
                self.protocol.set_block_color(color)
                last_color = color
            if self.protocol.build_block(x, y, z, color):
                blocks_left -= 1
 
class Tentacle(Animated):
    dead = False
    dying = False
    on_death = None
    on_removed = None
    parent = None
    protocol = None
    origin = None
    up = None
    orientation = None
    start_orientation = None
    target_orientation = None
    lerp_t = None
    facing = None
    sections = None
    radius = 2
    spread = radius / 2.0
    follow = None
    follow_interval = 1.3
    follow_timer = follow_interval
    initial_growth_interval = 0.2
    growth_interval = initial_growth_interval
    growth_timer = growth_interval
    blocks_destroyed = None
    last_block_destroyed = None
    growing = True
    withdraw = False
    grabbed_player = None
    max_hp = None
    
    def __init__(self, protocol, parent, (x, y, z)):
        Animated.__init__(self, protocol)
        self.parent = parent
        self.origin = Vertex3(x, y, z)
        self.up = Vertex3(0.0, 0.0, -1.0)
        self.orientation = Quaternion()
        self.facing = self.orientation.transform_vector(self.up)
        self.sections = []
        self.blocks_destroyed = []
        self.parent.tentacles.append(self)
        self.find_target()
    
    def find_target(self):
        best = None
        best_dist = None
        best_followed = None
        for player in self.protocol.players.values():
            if not is_valid_enemy(player):
                continue
            dist = distance_3d_vector(player.world_object.position, self.origin)
            followed = self.parent.is_enemy_targeted(player)
            if not best or dist < best_dist or best_followed and not followed:
                best, best_dist, best_followed = player, dist, followed
        self.follow = best
    
    def think(self, dt):
        tip = self.sections and self.sections[-1][0] or self.origin
        
        self.follow_timer -= dt
        if self.follow and not is_valid_enemy(self.follow):
            self.find_target()
            if not self.follow:
                self.growth_timer = 0.66
                self.growing = False
                self.withdraw = True
        elif self.follow and self.follow_timer <= 0.0:
            self.follow_timer = self.follow_interval
            follow_pos = self.follow.world_object.position
            direction = follow_pos - tip
            q = self.facing.get_rotation_to(direction)
            self.start_orientation = Quaternion(*self.orientation.get())
            self.target_orientation = q * self.orientation
            self.lerp_t = 0.0
        if self.target_orientation and self.lerp_t <= 1.0:
            self.orientation = self.start_orientation.slerp(
                self.target_orientation, self.lerp_t)
            self.lerp_t += 0.02
        self.facing = self.orientation.transform_vector(self.up)
        self.facing.normalize()
        
        self.growth_timer -= dt
        if self.growth_timer <= 0.0:
            self.growth_timer = self.growth_interval
            if self.growing and self.follow:
                tip = self.grow(tip.copy())
            elif self.withdraw:
                if self.sections:
                    pos, blocks = self.sections.pop()
                    tip = pos
                    for uvw in blocks:
                        if not self.parent.is_location_inside(uvw, skip = self):
                            self.protocol.remove_block(*uvw)
                        self.blocks.discard(uvw)
                else:
                    for uvw in self.blocks:
                        if not self.parent.is_location_inside(uvw, skip = self):
                            self.protocol.remove_block(*uvw)
                    self.dead = True
                    if self.on_removed:
                        self.on_removed(self)
		    self.clear_mem()
		    return

        player = self.grabbed_player
        if player:
            if self.dead or not player.world_object:
                player.grabbed_by = None
                self.grabbed_player = None
            else:
                player.set_location((tip.x, tip.y, tip.z - 1.0))
                if tip.z >= 63:
                    player.got_water_damage = True
		    player.kraken_kill()
                    player.got_water_damage = False
    
    def on_block_destroy(self, x, y, z, mode):
        if mode == SPADE_DESTROY and (x, y, z) in self.blocks:
            return False
    
    def on_block_removed(self, x, y, z):
        xyz = (x, y, z)
        if xyz not in self.blocks:
            return 0
        self.blocks.discard(xyz)
        total_damage = 0.0
        for u, v, w in self.blocks_destroyed:
            xu, yv, zw = x - u, y - v, z - w
            d = sqrt(xu*xu + yv*yv + zw*zw)
            total_damage += d >= 1.0 and 1.0 / d or 1.0
            if total_damage > self.max_hp:
                self.fracture(x, y, z)
                self.last_block_destroyed = None
                self.die()
                if self.on_death:
                    self.on_death(self)
                return BLOCK_REMOVE_TENTACLE_KILL
        if self.last_block_destroyed: #When a block is destroyed, this code is used
            self.protocol.set_block_color(KRAKEN_BLOOD)
            u, v, w = self.last_block_destroyed
            self.protocol.build_block(u, v, w, KRAKEN_BLOOD,force=True)
            self.blocks.add(self.last_block_destroyed)
        self.last_block_destroyed = xyz
        self.blocks_destroyed.append(xyz)
	return BLOCK_REMOVE_TENTACLE_HIT
    
    def die(self):
        self.follow = None
        self.target_orientation = None
        if self.grabbed_player:
            self.grabbed_player.grabbed_by = None
        self.grabbed_player = None
        self.growth_timer = 0.66
        speedup = 2.0 + max(len(self.sections) / 140.0, 1.0)
        self.growth_interval = self.initial_growth_interval / speedup
        self.growing = False
        self.withdraw = True
        self.dying = True
	return
    
    def fracture(self, x, y, z):
        protocol = self.protocol
        radius = self.radius
        for uvw in sphere(int(radius * 1.5), x, y, z):
            if not self.parent.is_location_inside(uvw, skip = self):
                protocol.remove_block(*uvw)
            self.blocks.discard(uvw)
        to_remove = []
        breakpoint = False
        while self.sections:
            pos, blocks = self.sections.pop()
            for uvw in blocks:
                if not self.parent.is_location_inside(uvw, skip = self):
                    if breakpoint:
                        protocol.remove_block(*uvw)
                    else:
                        to_remove.append(uvw)
                self.blocks.discard(uvw)
            if breakpoint:
                break
            i, j, k = pos.get()
            breakpoint = aabb_centered(x, y, z, i, j, k, radius)
        if self.sections:
            self.sections.pop()
        for u, v, w in to_remove:
            protocol.remove_block(u, v, w)
    
    def grow(self, tip):
        if self.sections:
            tip += self.facing * self.spread
        map = self.protocol.map
        radius = self.radius
	if tip.z>60 and len(self.blocks)<20:
		if self.follow:
			if self.follow.world_object:
				if self.follow.world_object.position.z>=62:
					tip.z=60
        ix, iy, iz = int(tip.x), int(tip.y), int(tip.z)
        blocks = []
        destroyed = 0
        for x, y, z in sphere(radius, ix, iy, iz):
            if (x < 0 or x >= 512 or y < 0 or y >= 512 or 
                z < 0 or z >= 63):
                continue
            xyz = (x, y, z)
            if xyz not in self.blocks:
                if not map.get_solid(x, y, z):
                    blocks.append(xyz)
                    self.blocks.add(xyz)
                    self.build_queue.append(xyz + (KRAKEN_BLACK,))
                elif not self.parent.is_location_inside(xyz, skip = self):
                    destroyed += 1
        if destroyed >= radius:
            for x, y, z in sphere(radius + 2, ix, iy, iz, min_r = radius):
                if self.parent.is_location_inside((x, y, z)):
                    continue
                self.protocol.remove_block(x, y, z)
            self.protocol.create_explosion_effect(tip)
        for player in self.protocol.players.values():
            if not is_valid_enemy(player):
                continue
            pos = player.world_object.position
            if vector_collision(pos, tip, radius * 0.75):
                self.follow = None
                self.target_orientation = None
                self.growth_timer = 0.4
                self.growing = False
                self.withdraw = True
                self.grabbed_player = player
                player.grabbed_by = self
                player.set_location((tip.x, tip.y, tip.z - 1.0))
                player.kraken_hit(GRAB_DAMAGE)
                break
        self.sections.append((tip, blocks))
        return tip

    def clear_mem(self):
	self.build_loop.stop()
	self.build_loop=None
	self.build_queue=None
	self.parent.tentacles.pop(self.parent.tentacles.index(self))
	get_referrers(self)
	del self
	self=None
 
class Eye():
    parent = None
    protocol = None
    dead = False
    blocks = None
    origin_x = None
    pos = None
    base = None
    hits = None
    look_interval_min = 0.8
    look_interval_max = 2.5
    look_timer = look_interval_max
    on_hit = None
    create_call = None
    closed=False
    
    def __init__(self, parent, base, ox, oy, oz, hits = 3):
        self.parent = parent
        self.protocol = parent.protocol
        self.blocks = set()
	if parent.yrotation:
		oy*=-1
		if parent.size<8:
			1
		else:
			oy+=1
	if parent.xrotation:
		ox,oy=(oy,ox)
		oy-=2
        self.pos = parent.origin.copy().translate(ox, oy, oz)
	if parent.xrotation:
		self.origin_x=self.pos.y
	else:
        	self.origin_x=self.pos.x
        self.base = base[:]
        self.hits = hits
        parent.eyes.append(self)
    
    def think(self, dt):
        if not self.blocks:
            return
        self.look_timer -= dt
        if self.look_timer <= 0.0:
            self.look_timer = uniform(self.look_interval_min,
                self.look_interval_max)
	    offset=choice([1,-1])
	    if not self.parent.xrotation:
		if abs(self.pos.x+offset-self.origin_x)<2:
                	self.protocol.set_block_color(KRAKEN_BLACK)
                	for x, y, z in self.blocks:
                	   self.protocol.build_block(x, y, z, KRAKEN_BLACK, 
                	   force = True)
                	self.blocks = set()
			self.pos.x+=offset
                	self.create_instant()
	    else:
		if abs(self.pos.y+offset-self.origin_x)<2:
                	self.protocol.set_block_color(KRAKEN_BLACK)
                	for x, y, z in self.blocks:
                	   self.protocol.build_block(x, y, z, KRAKEN_BLACK, 
                	   force = True)
                	self.blocks = set()
			self.pos.y+=offset
                	self.create_instant()

    
    def create(self, block_queue = None, close = False):
        if block_queue is None:
            block_queue = deque(self.base)
        last_color = None
        x, y, z = self.pos.get()
        x_d = None
        while block_queue:
            u, v, w, color = block_queue[0]
	    if self.parent.xrotation:
		u,v=(v,u)
            if x_d is None:
                x_d = abs(u)
            elif abs(u) != x_d:
                break
            if color != last_color:
                self.protocol.set_block_color(color)
                last_color = color
            u, v, w = x + u, y + v, z + w
            uvw = (u, v, w)
            self.protocol.build_block(u, v, w, color, force = True)
            if not close:
                self.parent.head.discard(uvw)
                self.blocks.add(uvw)
            block_queue.popleft()
        if block_queue:
            self.create_call = reactor.callLater(0.25, self.create, block_queue, close)
	self.closed=close
    
    def create_instant(self, block_list = None):
        if block_list is None:
            block_list = self.base
        last_color = None
        x, y, z = self.pos.get()
        block_list = sorted(block_list, key = itemgetter(3))
        for u, v, w, color in block_list:
	    if self.parent.xrotation:
		u,v=(v,u)
            if color != last_color:
                self.protocol.set_block_color(color)
                last_color = color
            u, v, w = x + u, y + v, z + w
            uvw = (u, v, w)
            self.protocol.build_block(u, v, w, color, force = True)
            self.parent.head.discard(uvw)
            self.blocks.add(uvw)

    def on_block_destroy(self,x,y,z,mode):
	xyz=(x,y,z)
	if xyz not in self.blocks:
		return True
	return not self.closed
    
    def on_block_removed(self, x, y, z):
        xyz = (x, y, z)
        if self.dead or (xyz not in self.blocks) or self.closed:
            return
        protocol = self.protocol
        protocol.create_explosion_effect(Vertex3(x, y, z))
        self.parent.build_queue.append((x, y, z, KRAKEN_BLOOD))
        self.hits -= 1
        if self.hits > 0:
            self.pain()
	    if self.parent.xrotation:
		uvw = (y - self.pos.y, x - self.pos.x, z - self.pos.z)
	    else:
            	uvw = (x - self.pos.x, y - self.pos.y, z - self.pos.z)
            i = [uvwc[:-1] for uvwc in self.base].index(uvw)
            self.base[i] = uvw + (KRAKEN_BLOOD,)
        else:
            self.close()
            self.dead = True
        if self.on_hit:
            self.on_hit(self)
	return
    
    def close(self):
        self.parent.head.update(self.blocks)
        self.blocks.clear()
        if self.create_call and self.create_call.active():
            self.create_call.cancel()
        reactor.callLater(0.5, self.create, deque(KRAKEN_EYE_SMALL_CLOSED),
            close = True)
    
    def pain(self):
        self.close()
        reactor.callLater(EYE_PAIN_TIME, self.create)
        self.look_timer = EYE_PAIN_TIME + self.look_interval_min
 
class Kraken(Animated):
    dead = False
    origin = None
    tentacles = None
    head = None
    eyes = None
    max_hp = 10.0
    hp = max_hp
    size = 7
    on_last_tentacle_death = None
    on_death = None
    on_removed = None
    finally_call = None
    phase = 0
    yrotation=False
    xrotation=False
    
    def __init__(self, protocol, (x, y, z)):
        Animated.__init__(self, protocol)
        self.origin = Vertex3(x, y, z)
        self.head = set()
        self.eyes = []
        self.tentacles = []
	self.yrotation=self.protocol.kraken_flip
	self.xrotation=self.protocol.kraken_rotate_x
	self.protocol.kraken_flip=False
	self.protocol.kraken_rotate_x=False
    
    def is_location_inside(self, location, skip = None):
        if location in self.head:
            return True
        for eye in self.eyes:
            if location in eye.blocks:
                return True
        for t in self.tentacles:
            if t is not skip and location in t.blocks:
                return True
        return False
    
    def is_enemy_targeted(self, player):
        for t in self.tentacles:
            if t.follow is player:
                return True
        return False
    
    def on_block_destroy(self, x, y, z, mode):
        for t in self.tentacles:
            if t.on_block_destroy(x, y, z, mode) == False:
		return False
	for eye in self.eyes:
		if eye.on_block_destroy(x,y,z,mode)==False:
			return False
    
    def on_block_removed(self, x, y, z):
	ReturnValue=0
        eye_died = False
        for eye in self.eyes:
            eye.on_block_removed(x, y, z)
            eye_died = eye_died or eye.dead
        if eye_died:
            self.eyes = [eye for eye in self.eyes if not eye.dead]
            if not self.eyes:
                self.die()
		ReturnValue=BLOCK_REMOVE_KRAKEN_KILL
        
        for t in self.tentacles:
            ReturnValue|=t.on_block_removed(x, y, z)
	return ReturnValue
    
    def die(self):
        protocol = self.protocol
        def remove(this, remover, blocks):
            if blocks:
                remover(*blocks.pop())
                reactor.callLater(0.01, this, this, remover, blocks)
            elif self.on_removed:
                self.on_removed(self)
        def explode(this, effect, blocks, left):
            x = self.origin.x + uniform(-5.0, 5.0)
            y = self.origin.y + self.size + 1.0
            z = self.origin.z + uniform(-15.0, 0.0)
            effect(Vertex3(x, y, z))
            if not blocks or left <= 0:
                return
            delay = uniform(0.3, 0.8)
            left -= 1
            reactor.callLater(delay, this, this, effect, blocks, left)
        remove(remove, protocol.remove_block, self.head)
        explode(explode, protocol.create_explosion_effect, self.head, 10)
        
        self.dead = True
        for t in self.tentacles:
            t.die()        
        if self.on_death:
            self.on_death(self)
	clear_mem(self.protocol,self)
    
    def think(self, dt):
        for eye in self.eyes:
            eye.think(dt)
        
        rebuild_list = False
        for t in self.tentacles:
	    if not t:
		continue
            t.think(dt)
            rebuild_list = rebuild_list or t.dead
        if rebuild_list:
	    _tentacles=[]
	    for t in self.tentacles:
		if not t:
			continue
		if t.dead:
			continue
		_tentacles.append(t)
            self.tentacles = _tentacles
            if not self.tentacles and self.on_last_tentacle_death:
                self.on_last_tentacle_death(self)
    
    def hit(self, value, rate):
        hp_bar = self.protocol.hp_bar
        if not hp_bar.shown:
            hp_bar.progress = 1.0 - self.hp / self.max_hp
            hp_bar.show()
        self.hp = max(self.hp - value, 0)
        previous_rate = hp_bar.rate
        hp_bar.get_progress(True)
        hp_bar.rate = rate
        hp_bar.update_rate()
        hp_bar.send_progress()
        target_progress = 1.0 - self.hp / self.max_hp
        delay = (target_progress - hp_bar.progress) / hp_bar.rate_value
        hp_call = hp_bar.hp_call
        if hp_call and hp_call.active():
            if previous_rate == 0:
                hp_call.cancel()
            else:
                hp_call.reset(delay)
                return
	if delay<0:
		delay=0
        hp_bar.hp_call = reactor.callLater(delay, hp_bar.stop)
    
    def create_head(self, head_list, height = None):
        height = height or len(head_list)
        x, y, z = self.origin.get()
        for d in head_list[-height:]:
            for u, v in d:
		if self.yrotation:
			v=-v
		if self.xrotation:
			u,v=(-v,u)
                xyzc = (x + u, y + v, z, KRAKEN_BLACK)
                self.build_queue.append(xyzc)
                self.head.add(xyzc[:-1])
            z -= 1
        if height < len(head_list):
            delay = 0.6
            reactor.callLater(delay, self.create_head, head_list, height + 6)

def clear_kraken_mem(protocol,kraken):
	kraken.build_loop.stop()
	kraken.build_loop=None
	kraken.build_queue=None
	del kraken
	return

@admin
def kraken(connection, value = None):
    protocol = connection.protocol
    if protocol.game_mode != TC_MODE:
        return 'Unfortunately, the game mode is required to be TC. Change it then restart'
    if protocol.boss:
        return "There is already a kraken! Why can't I hold all these krakens?"
    try:
        x, y = coordinates(value)
    except (ValueError):
        return 'Need coordinates where to spawn the kraken, e.g /kraken E3'
    start_kraken(protocol, max(x, 64), max(y, 64))
 
if ALLOW_KRAKEN_COMMAND:
    add(kraken)

@admin
def kraken_const(self, constname, value=None, type=None):
	try:
		constval=globals()[constname]
	except KeyError:
		return 'No such variable'
	if not value or not type:
		return '%s = %s' % (constname, constval)
	if 's' in type:
		pass
	elif 'd' in type:
		value=int(value)
	elif 'f' in type:
		value=float(value)
	elif 'b' in type:
		value=True if value=='True' else False
	else:
		return 'Unknown type'
	globals()[constname]=value
	return 'Set %s(%s) to %s' % (constname, constval, value)

add(kraken_const)

def get_kraken_ratio(protocol):
	if not protocol.kraken_kills:
		return 1.0
	return float(protocol.kraken_deaths)/float(protocol.kraken_kills)

def kraken_ratio(self):
	return ('Kraken kill/death ratio:%s, kills:%s, deaths:%s' % (get_kraken_ratio(self.protocol),
		self.protocol.kraken_kills, self.protocol.kraken_deaths))

add(kraken_ratio)

def kraken_player_ratio(self):
	kraken_ratio=get_kraken_ratio(self.protocol)
	player_count=len(self.protocol.players)
	return ('Kraken ratio/player ratio:%s, player count:%s' % (kraken_ratio/max(1,player_count), player_count))

add(kraken_player_ratio)
 
def start_kraken(protocol, x, y, hardcore = False, finally_call = None):
    y += 32
    boss = Kraken(protocol, (x, y - 12, 63))
    protocol.boss = boss
    protocol.map_change_on_kraken_win=hardcore
    if USE_DAYCYCLE and protocol.daycycle_loop.running:
        protocol.daycycle_loop.stop()
    
    arena = getattr(protocol.map_info.info, 'arena', None)
    if arena:
        arena_center = (int((arena[2] - arena[0]) / 2.0 + arena[0]),
            int((arena[3] - arena[1]) / 2.0 + arena[1]))
        arena_radius = min(arena[2] - arena[0], arena[3] - arena[1]) / 2.0
    
    def randring():
        min_r, max_r = 12.0, 32.0
        r = uniform(min_r, max_r)
        a = uniform(0.0, pi)
        return x + cos(a) * r, y + sin(a) * r, 63
    
    def randring_arena():
        if not arena:
            return randring()
        r = uniform(arena_radius, arena_radius * 1.2)
        a = uniform(0.0, 2*pi)
        x, y = arena_center
        return x + cos(a) * r, y + sin(a) * r, 63
    
    def minor_hit(caller = None):
        boss.hit(1.0, 1)
        caller.on_removed = None
    
    def major_hit(caller = None):
        boss.hit(3.0, 1)
    
    def major_hit_and_progress(caller = None):
        caller.on_hit = major_hit
        major_hit()
        progress()
    
    def major_hit_and_pain(caller = None):
        major_hit()
        boss_alive = False
        for eye in caller.parent.eyes:
            if eye is not caller and not eye.dead:
                eye.pain()
                boss_alive = True
        if boss_alive and caller.dead:
            falling_blocks_start()
    
    def respawn_tentacle(caller = None):
        if boss and not boss.dead:
            reactor.callLater(5.0-float(FAST_RUN)*4.0, spawn_tentacles, 1, True)
    
    def spawn_tentacles(amount, respawn = False, fast = False, arena = False,
        no_hit = False):
        if not hardcore:
            toughness = max(3.0, min(10.0, len(protocol.players) * 0.5))
        else:
            toughness = max(5.0, min(13.0, len(protocol.players) * 0.85))
        if boss and not boss.dead:
            for i in xrange(amount):
                origin = randring_arena() if arena else randring()
                t = Tentacle(protocol, boss, origin)
                t.max_hp = toughness
                t.growth_timer = uniform(i * 1.0, i * 1.2)
                if hardcore:
                    t.initial_growth_interval *= 0.8
                if fast:
                    t.initial_growth_interval *= 0.5
                else:
                    t.follow_timer = 2.0
                t.growth_interval = t.initial_growth_interval
                if respawn:
                    t.on_removed = respawn_tentacle
                elif not no_hit:
                    t.on_death = minor_hit
                    t.on_removed = minor_hit
    
    def falling_blocks_cycle():
        alive_players = filter(is_valid_enemy, protocol.players.values())
        if not alive_players:
            return
        player = choice(alive_players)
        x, y, z = player.world_object.position.get()
        protocol.create_falling_block(int(x), int(y), randrange(2, 4), 2)
    
    def falling_blocks_start():
        protocol.send_chat('LOOK UP!', global_message = True)
        for i in range(FALLING_BLOCK_COUNT):
            reactor.callLater(i * 0.4+FALLING_BLOCK_START_DELAY, falling_blocks_cycle)
    
    def squid_head():
        h = []
        for i in xrange(37, 5, -2):
            h.append(list(disc(i, min_rr = i - 15)))
        return h
    
    def squid_head_large():
        h = []
        for i in xrange(42, 3, -2):
            ii = int(i ** 1.3)
            h.append(list(disc(ii, y = int(sqrt(i)), min_rr = i + 10)))
        return h
    
    def regenerate_players():
        for player in protocol.players.values():
	    if not player.world_object:
		continue
	    player.free_from_kraken()
            player.last_hit = reactor.seconds()
            player.regenerating = True
            if not player.world_object.dead:
                player.regen_loop.start(REGEN_FREQUENCY)
            else:
                player.spawn(player.world_object.position.get())
    
    def round_end(caller = None):
        regenerate_players()
        reactor.callLater(8.0-float(FAST_RUN)*7.0, progress)
    
    def round_end_delay(caller = None):
        reactor.callLater(10.0-float(FAST_RUN)*9.0, round_end)
    
    def round_start(caller = None):
        for player in protocol.players.values():
            player.regenerating = False
    
    def progress_delay(caller = None):
        reactor.callLater(6.0-float(FAST_RUN)*5.0, progress)
    
    def victory(caller = None):
        regenerate_players()
        if USE_DAYCYCLE:
            protocol.current_time = 23.30
            protocol.update_day_color()
    
    def cleanup(caller = None):
        round_start()
	clear_mem(protocol,protocol.boss)
        protocol.boss = None
        if USE_DAYCYCLE and protocol.daycycle_loop.running:
            protocol.daycycle_loop.stop()
        if caller.finally_call:
            caller.finally_call(caller)
	if protocol.map_change_on_kraken_win:
		protocol.send_chat(KRAKEN_WIN_ANNOUNCEMENT,True)
		reactor.callLater(MAP_CHANGE_DELAY,protocol.advance_rotation,'The round was won.')
    
    def red_sky():
        if USE_DAYCYCLE:
            protocol.day_colors = [
                ( 0.00, (0.5527, 0.24, 0.94), False),
                ( 0.10, (0.0,    0.05, 0.05), True),
                ( 0.20, (0.0,    1.00, 0.34), False),
                (23.30, (0.0,    1.00, 0.34), False),
                (23.50, (0.5527, 0.24, 0.94), False)]
            protocol.current_time = 0.00
            protocol.target_color_index = 0
            protocol.update_day_color()
            if not protocol.daycycle_loop.running:
                protocol.daycycle_loop.start(protocol.day_update_frequency)
    
    progress = None
    
    def progress_normal(caller = None):
        boss.phase += 1
        round_start()
        
        if boss.phase == 1:
            boss.on_last_tentacle_death = progress_delay
            spawn_tentacles(2)
        elif boss.phase == 2:
            boss.on_last_tentacle_death = round_end
            spawn_tentacles(4)
        elif boss.phase == 3:
            boss.on_last_tentacle_death = round_end
            spawn_tentacles(3, fast = True)
        elif boss.phase == 4:
            boss.on_last_tentacle_death = None
            boss.on_death = round_end_delay
            boss.size = 7
            boss.create_head(squid_head())
            eye = Eye(boss, KRAKEN_EYE_SMALL, 0, 5, -1, hits = 5)
            eye.on_hit = major_hit_and_progress
            reactor.callLater(7.0-float(FAST_RUN)*6.0, eye.create)
        elif boss.phase == 5:
            spawn_tentacles(3, respawn = True)
            spawn_tentacles(2, arena = True, no_hit = True)
        elif boss.phase == 6:
            falling_blocks_start()
            reactor.callLater(15.0-float(FAST_RUN)*14.0, round_end)
        elif boss.phase == 7:
            boss.dead = False
            boss.on_last_tentacle_death = round_end
            spawn_tentacles(4, fast = True, arena = True)
        elif boss.phase == 8:
            red_sky()
            boss.on_last_tentacle_death = None
            boss.on_death = victory
            boss.on_removed = cleanup
            boss.finally_call = finally_call
            boss.origin.y -= 24
            boss.size = 16
            boss.create_head(squid_head_large())
            eye = Eye(boss, KRAKEN_EYE_SMALL, 0, 16, -2, hits = 4)
            eye.on_hit = major_hit_and_pain
            reactor.callLater(16.0-float(FAST_RUN)*15.0, eye.create)
            eye = Eye(boss, KRAKEN_EYE_SMALL, 0, 14, -6, hits = 4)
            eye.on_hit = major_hit_and_pain
            reactor.callLater(16.0-float(FAST_RUN)*15.0, eye.create)
            reactor.callLater(18.0-float(FAST_RUN)*17.0, spawn_tentacles, 5, respawn = True)
    
    def progress_hardcore(caller = None):
        boss.phase += 1
        round_start()
        
        if boss.phase == 1:
            boss.on_last_tentacle_death = progress_delay
            spawn_tentacles(3)
            falling_blocks_start()
        elif boss.phase == 2:
            boss.on_last_tentacle_death = round_end
            spawn_tentacles(4, fast = True)
        elif boss.phase == 3:
            boss.on_last_tentacle_death = None
            boss.on_death = round_end_delay
            boss.size = 7
            boss.create_head(squid_head())
            eye = Eye(boss, KRAKEN_EYE_SMALL, 0, 5, -1, hits = 8)
            eye.look_interval_min *= 0.8
            eye.look_interval_max *= 0.6
            eye.on_hit = major_hit_and_progress
            reactor.callLater(7.0-float(FAST_RUN)*6.0, eye.create)
        elif boss.phase == 4:
            spawn_tentacles(3, respawn = True)
            spawn_tentacles(3, arena = True, no_hit = True)
        elif boss.phase == 5:
            boss.dead = False
            boss.on_last_tentacle_death = round_end
            spawn_tentacles(5, fast = True, arena = True)
        elif boss.phase == 6:
            red_sky()
            boss.on_last_tentacle_death = None
            boss.on_death = victory
            boss.on_removed = cleanup
            boss.finally_call = finally_call
            boss.origin.y -= 24
            boss.size = 16
            boss.create_head(squid_head_large())
            eye = Eye(boss, KRAKEN_EYE_SMALL, 0, 16, -2, hits = 6)
            eye.look_interval_min *= 0.8
            eye.look_interval_max *= 0.6
            eye.on_hit = major_hit_and_pain
            reactor.callLater(16.0-float(FAST_RUN)*15.0, eye.create)
            eye = Eye(boss, KRAKEN_EYE_SMALL, 0, 14, -6, hits = 6)
            eye.look_interval_min *= 0.8
            eye.look_interval_max *= 0.6
            eye.on_hit = major_hit_and_pain
            reactor.callLater(16.0-float(FAST_RUN)*15.0, eye.create)
            reactor.callLater(18.0-float(FAST_RUN)*17.0, spawn_tentacles, 5, respawn = True)
            reactor.callLater(14.0-float(FAST_RUN)*13.0, falling_blocks_start)
    
    boss.blocks_per_cycle = 2
    boss.build_interval = 0.01
    if not hardcore:
        progress = progress_normal
        boss.hp = boss.max_hp = 2.0 + 4.0 + 3.0 + 5*3.0 + 4.0 + (4 + 4)*3.0
    else:
        progress = progress_hardcore
        boss.hp = boss.max_hp = 3.0 + 4.0 + 8*3.0 + 5.0 + (6 + 6)*3.0
    progress()
    return boss

def clear_mem(protocol,kraken):
	return
	kraken.build_queue=None
	if kraken.build_loop:
		kraken.build_loop.stop()
		kraken.build_loop=None
	
 
class BossTerritory(Territory):
    shown = False
    hp_call = None
    
    def add_player(self, player):
        return
    
    def remove_player(self, player):
        return
    
    def update_rate(self):
        self.rate_value = self.rate * TC_CAPTURE_RATE
        self.capturing_team = (self.rate_value < 0 and
            self.protocol.blue_team or self.protocol.green_team)
        self.start = reactor.seconds()
    
    def show(self):
        self.shown = True
        for player in self.protocol.players.values():
            self.update_for_player(player)
    
    def hide(self):
        self.shown = False
        self.update()
    
    def stop(self):
        self.rate = 0
        self.get_progress(True)
        self.update_rate()
        self.send_progress()
        self.hp_call = reactor.callLater(3.0, self.hide)
    
    def update_for_player(self, connection, orientation = None):
	if not connection.world_object:
		return
        x, y, z = orientation or connection.world_object.orientation.get()
        v = Vertex3(x, y, 0.0)
        v.normalize()
        v *= -10.0
        v += connection.world_object.position
        move_object.object_type = self.id
        move_object.state = self.team and self.team.id or NEUTRAL_TEAM
        move_object.x = v.x
        move_object.y = v.y
        move_object.z = v.z
        connection.send_contained(move_object)
 
def apply_script(protocol, connection, config):

    class BossProtocol(protocol):
        game_mode = TC_MODE
        boss = None
        boss_ready = True
        hp_bar = None
	max_connections=min(protocol.max_connections,31)
	map_change_on_kraken_win=False
	kraken_kills=0
	kraken_deaths=0
	kraken_flip=False
	kraken_rotate_x=False

	new_spawn_pos=False
        
        def start_kraken(self, x, y, hardcore = False, finally_call = None):
            return start_kraken(self, x, y, hardcore, finally_call)
        
        def on_world_update(self):
            if self.boss:
                self.boss.think(UPDATE_FREQUENCY)
            protocol.on_world_update(self)
        
        def on_map_change(self, map):
            self.boss = None
            self.boss_ready = getattr(self.map_info.info, 'boss', False)
	    self.new_spawn_pos=getattr(self.map_info.info, 'new_spawn_pos', False)
            self.hp_bar = None
	    self.kraken_kills=0
	    self.kraken_deaths=0
	    self.kraken_flip=False
	    self.kraken_rotate_x=False
            protocol.on_map_change(self, map)
        
        def get_cp_entities(self):
            if 1:
                if USE_DAYCYCLE:
                    if self.daycycle_loop and self.daycycle_loop.running:
                        self.daycycle_loop.stop()
                self.boss_ready = True
                self.hp_bar = BossTerritory(0, self, 0.0, 0.0, 0.0)
                self.hp_bar.team = self.green_team
                return [self.hp_bar]
            return protocol.get_cp_entities(self)
        
        def create_explosion_effect(self, position):
            self.world.create_object(Grenade, 0.0, position, None, 
                Vertex3(), None)
            grenade_packet.value = 0.0
            grenade_packet.player_id = 32
            grenade_packet.position = position.get()
            grenade_packet.velocity = (0.0, 0.0, 0.0)
            self.send_contained(grenade_packet)
        
        def falling_block_collide(self, x, y, z, size):
            #if not self.map.get_solid(x, y, z):
	    if 1:
            	new_z = self.map.get_height(x, y)
            	if new_z > z:
                    remaining = fall_eta(abs(new_z - z))
                    reactor.callLater(remaining, self.falling_block_collide,
                        x, y, new_z, size)
                    return
            for player in self.players.values():
		if not player.world_object:
		    continue
                i, j, k = player.world_object.position.get()
                s = size + 3.0
                if aabb(i, j, k, x - 1.5, y - 1.5, z - 5.0, s, s, 6.0):
                    	player.kraken_hit(FALLING_BLOCK_DAMAGE)
            half_size = int(ceil(size / 2.0))
            ox, oy = x - half_size, y - half_size
            for u, v, w in prism(ox, oy, z - 1, size, size, 2):
		if w<62:
                	self.remove_block(u, v, w, user = True)
            self.create_explosion_effect(Vertex3(x, y, z))
        
        def create_falling_block(self, x, y, size, height):
            self.set_block_color(FALLING_BLOCK_COLOR)
            half_size = int(ceil(size / 2.0))
            ox, oy = x - half_size, y - half_size
            for u, v, w in prism(ox, oy, FALLING_BLOCK_Z, size, size, height):
                self.build_block(u, v, w, FALLING_BLOCK_COLOR)
            self.remove_block(ox, oy, FALLING_BLOCK_Z)
            
            z = self.map.get_z(x, y)
            eta = fall_eta(z - FALLING_BLOCK_Z)
            reactor.callLater(eta, self.falling_block_collide, x, y, z, size)
        
        def set_block_color(self, color):
            set_color.value = color
            set_color.player_id = 32
            self.send_contained(set_color, save = True)
        
        def remove_block(self, x, y, z, user = False):
            if z >= 63:
                return False
            self.map.remove_point(x, y, z)
            block_action.value = DESTROY_BLOCK
            block_action.player_id = 32
            block_action.x = x
            block_action.y = y
            block_action.z = z
            self.send_contained(block_action)
            return True
        
        def build_block(self, x, y, z, color, force = False):
            if force and self.map.get_solid(x,y,z):
                self.remove_block(x, y, z)
            if not self.map.get_solid(x, y, z):
                self.map.set_point(x, y, z, get_color(color))
                block_action.value = BUILD_BLOCK
                block_action.player_id = 32
                block_action.x = x
                block_action.y = y
                block_action.z = z
                self.send_contained(block_action)
                return True
            return False

	def kraken_lose(self):
		self.send_chat('ALL PLAYERS WERE EATEN! GAME OVER!',True)
		if KRAKEN_ADD_SCORE:
			intel_capture.player_id=KRAKEN_PLAYER_ID
			intel_capture.winning=True
			self.send_contained(intel_capture)
		Scheduler(self).call_later(MAP_CHANGE_DELAY,self.advance_rotation,'The round was lost.')

	def is_indestructable(self,x,y,z):
            if self.boss:
                if self.boss.on_block_destroy(x, y, z, DESTROY_BLOCK) == False:
                    return True
                if self.boss.head and (x, y, z) in self.boss.head:
                    return True
	    return protocol.is_indestructable(self,x,y,z)

    class BossConnection(connection):
        regenerating = False
        trapped = False
        got_water_damage = False
        grabbed_by = None
        last_hit = None
        regen_loop = None
	NoWaterDamageTimer = 0
	FireLoop=None
	RegenTimer=1
	RestockTimer=1
        
        def __init__(self, *arg, **kw):
            connection.__init__(self, *arg, **kw)
            self.regen_loop = LoopingCall(self.regen_cycle)

	def on_login(self,name):
		if KRAKEN_ADD_SCORE:
			create_player.x=0
			create_player.y=0
			create_player.z=0
			create_player.player_id=KRAKEN_PLAYER_ID
			create_player.name='a tentacle'
			create_player.team=1
			set_tool.player_id=KRAKEN_PLAYER_ID
			set_tool.value=SPADE_TOOL
			self.send_contained(create_player)
			self.send_contained(set_tool)
		return connection.on_login(self,name)

        def regen_cycle(self):
            if (not self.regenerating or self.god or
                self.world_object is None or self.world_object.dead):
                self.regen_loop.stop()
                return
            last_hit = self.last_hit
            if last_hit and reactor.seconds() - last_hit < REGEN_ONSET:
                return
            if self.hp < 100 - REGEN_AMOUNT:
                self.set_hp(self.hp + REGEN_AMOUNT, type = FALL_KILL)
            else:
                self.refill()
                self.regen_loop.stop()
        
        def get_spawn_location(self):
            if self.protocol.boss and self.world_object and not self.trapped and not self.protocol.new_spawn_pos:
                return self.world_object.position.get()
            return connection.get_spawn_location(self)
        
        def get_respawn_time(self):
            if self.protocol.boss and self.trapped:
                return 2
            return connection.get_respawn_time(self)

	def sync_ammo(self):
		weapon_reload.player_id=self.player_id
		weapon_reload.clip_ammo=self.weapon_object.current_ammo
		weapon_reload.reserve_ammo=self.weapon_object.current_stock
		self.send_contained(weapon_reload)
        
        def on_spawn(self, pos):
            if self.trapped:
                self.set_location(self.protocol.boss.origin.get())
		self.check_trapped()
	    self.NoWaterDamageTimer=NO_WATER_DAMAGE_TIME
	    if self.weapon_object:
		stock=self.weapon_object.current_stock
		#self.weapon_object.current_stock=int(stock*get_kraken_ratio(self.protocol))
	    self.sync_ammo()
            return connection.on_spawn(self, pos)

	def on_refill(self):
		connection.on_refill(self)
		self.sync_ammo()
		return
        
        def on_reset(self):
            self.regenerating = False
            self.trapped = False
            self.got_water_damage = False
            self.grabbed_by = None
            self.last_hit = None
            if self.regen_loop and self.regen_loop.running:
                self.regen_loop.stop()
            connection.on_reset(self)
        
        def on_disconnect(self):
            if self.regen_loop and self.regen_loop.running:
                self.regen_loop.stop()
            self.regen_loop = None
            connection.on_disconnect(self)
        
        def on_kill(self, killer, type, grenade):
	    if killer:
		if self.player_id!=killer.player_id:
			return False
            if self.protocol.boss:
                if self.grabbed_by:
                    self.grabbed_by.grabbed_player = None
                self.grabbed_by = None
                if (self.protocol.boss and not self.protocol.boss.dead and
                    self.protocol.boss.head and self.world_object.position.z>=61):
                    self.trapped = True
                else:
                    self.send_chat('You died! Yell at your friends to walk '
                        'over you to revive you.')
            connection.on_kill(self, killer, type, grenade)
        
        def on_weapon_set(self, value):
            if self.protocol.boss and self.regenerating:
                self.weapon = value
                self.set_weapon(self.weapon, no_kill = True)
                self.spawn(self.world_object.position.get())
                return False
	    if value==2 and NEW_WEAPONS:
		self.send_chat('BE CAREFUL: THIS WEAPON IS RELOADING VERY SLOW')
            return connection.on_weapon_set(self, value)

	def free_from_kraken(self):
		if not self.trapped:
			return
		self.trapped=False
		OldValue=self.protocol.new_spawn_pos
		self.protocol.new_spawn_pos=True
		self.spawn()
		self.protocol.new_spawn_pos=OldValue
		self.send_chat('The squid spit you out. Save your mateys!')

	def check_trapped(self):
		TrappedPlayerCount=0
		PlayerCount=0
	    	for player in self.protocol.players.values():
			if player.world_object and player.team.id!=-1:
				PlayerCount+=1
				if not player.trapped:
					TrappedPlayerCount+=1
		if TrappedPlayerCount<PlayerCount and PlayerCount:
			Time=TRAPPED_FREE_TIME
			Scheduler(self.protocol).call_later(Time,self.free_from_kraken)
			self.send_chat('The kraken ate you! You have to wait %s seconds until it spits you out!' % Time)
		else:
			self.protocol.kraken_lose()
		return
        
        def on_orientation_update(self, x, y, z):
            if self.protocol.hp_bar and self.protocol.hp_bar.shown:
                self.protocol.hp_bar.update_for_player(self, (x, y, z))
            connection.on_orientation_update(self, x, y, z)

	def environment_hit(self,value):
		if self.trapped or self.NoWaterDamageTimer:
			return
		if self.protocol.boss:
			if (not self.protocol.boss.dead) and self.protocol.boss.head:
				value=WATER_DAMAGE
			self.kraken_hit(value)
			return
		return connection.environment_hit(self,value)
        
        def on_position_update(self):
	    if self.NoWaterDamageTimer:
	    	self.NoWaterDamageTimer-=1
            if not self.protocol.boss_ready:
                connection.on_position_update(self)
                return
	    if self.world_object:
            	if (not self.world_object.dead and not self.grabbed_by \
            	    and not self.trapped):
            	    for player in self.protocol.players.values():
			if not player.world_object:
				continue
            	        if player is not self and player.world_object.dead:
               	         pos = player.world_object.position
               	         if vector_collision(self.world_object.position, pos):
				    if player.spawn_call:
					player.spawn_call.cancel()
               	         	    player.spawn(pos.get())
            if self.protocol.hp_bar and self.protocol.hp_bar.shown:
                self.protocol.hp_bar.update_for_player(self)
	    if self.weapon_object and ENABLE_REGEN:
		self.RestockTimer-=RESTOCK_TIMER_SPEED
		if self.RestockTimer<=0:
			self.weapon_object.current_stock+=RESTOCK_COUNT[self.weapon_object.id]
			self.sync_ammo()
			self.RestockTimer=max(1,len(self.protocol.players)/RESTOCK_PLAYER_RATIO)
	    if self.world_object and self.hp and ENABLE_REGEN:
		if self.world_object.position.z<61 and self.hp<100:
	    			self.RegenTimer-=REGEN_TIMER_SPEED
				if self.RegenTimer<=0:
					self.set_hp(self.hp+1,type=FALL_KILL)
					self.RegenTimer=max(1,len(self.protocol.players)/REGEN_PLAYER_RATIO)
            connection.on_position_update(self)
        
        def on_block_build_attempt(self, x, y, z):
            if self.trapped:
                return False
            return connection.on_block_build(self, x, y, z)
        
        def on_block_destroy(self, x, y, z, mode):
            if self.trapped:
                return False
	    if self.protocol.is_indestructable(x,y,z):
		return False
	    if NEW_WEAPONS:
	 	   if self.weapon_object.id!=1 and mode==DESTROY_BLOCK and self.tool!=SPADE_TOOL:
			return False
            return connection.on_block_destroy(self, x, y, z, mode)

        def on_block_removed(self, x, y, z):
            if self.protocol.boss:
		ReturnValue=self.protocol.boss.on_block_removed(x,y,z)
		if ReturnValue:
			if KRAKEN_ADD_SCORE and ReturnValue&BLOCK_REMOVE_TENTACLE_KILL:
				kill_action.kill_type=self.tool
				kill_action.killer_id=self.player_id
				kill_action.player_id=KRAKEN_PLAYER_ID
				kill_action.respawn_time=0
				self.protocol.send_contained(kill_action)
				try:
					self.ratio_kills+=1
				except AttributeError:
					1
				self.streak+=1
				self.add_score(1)
			if ReturnValue&BLOCK_REMOVE_KRAKEN_KILL:
				intel_capture.player_id=self.player_id
				intel_capture.winning=True
				self.protocol.send_contained(intel_capture)
				self.add_score(10)
			self.protocol.kraken_deaths+=1
            connection.on_block_removed(self, x, y, z)
        
        def on_hit(self, hit_amount, player, type, grenade):
            self.last_hit = reactor.seconds()
            if self.regenerating and not self.regen_loop.running:
                self.regen_loop.start(REGEN_FREQUENCY)
            if self.protocol.boss_ready:
                if self is player and self.hp:
                    if hit_amount >= self.hp:
                        return self.hp - 1
            return connection.on_hit(self, hit_amount, player, type, grenade)
        
        def on_fall(self, damage):
            if self.grabbed_by or self.regenerating:
                return False
            self.last_hit = reactor.seconds()
            if self.regenerating and not self.regen_loop.running:
                self.regen_loop.start(REGEN_FREQUENCY)
            return connection.on_fall(self, damage)

	def on_line_build_attempt(self,points):
		if self.trapped:
			return False
		return connection.on_line_build_attempt(self,points)

	def kraken_hit(self,value):
		if self.hp<=value:
			self.kraken_kill()
			return
		KrakenPosition=None
		if self.protocol.boss:
			KrakenPosition=self.protocol.boss.origin.get()
		self.set_hp(self.hp-value,type=MELEE_KILL,hit_indicator=KrakenPosition)

	def kraken_kill(self):
	    if not self.hp or self.world_object.dead:
		return
	    if KRAKEN_ADD_SCORE:
	    	self.best_streak=max(self.best_streak,self.streak)
	    	self.streak=0
	    	kill_action.kill_type=MELEE_KILL
	    	kill_action.killer_id=KRAKEN_PLAYER_ID
	    	kill_action.player_id=self.player_id
	    	kill_action.respawn_time=self.get_respawn_time()+1
	    	self.world_object.dead=True
		self.hp=None
		self.weapon_object.reset()
	    	self.on_kill(self,MELEE_KILL,None)
	    	self.protocol.send_contained(kill_action)
		if self.spawn_call:
			self.spawn_call.cancel()
			self.spawn_call=None
	    	self.respawn()
	    else:
	    	self.kill(type=FALL_KILL)
	    self.protocol.kraken_kills+=1
	    return

	def player_remove_block(self,x,y,z):
		self.on_block_destroy(x,y,z,DESTROY_BLOCK)
		if z<61 and self.protocol.map.get_solid(x,y,z) and \
			not self.protocol.is_indestructable(x,y,z) and not self.trapped:
				if not self.on_block_removed(x,y,z):
					block_action.x,block_action.y,block_action.z=(x,y,z)
					block_action.player_id=self.player_id
					block_action.value=DESTROY_BLOCK
					self.protocol.send_contained(block_action)
					self.protocol.map.remove_point(x,y,z)
		return 0

	def shotgun_explosion(self,pos):
		block_action.player_id=self.player_id
		block_action.value=DESTROY_BLOCK
		for x in xrange(-1,2):
			for y in xrange(-1,2):
				for z in xrange(-1,2):
					xpos=pos[0]+x
					ypos=pos[1]+y
					zpos=pos[2]+z
					self.player_remove_block(xpos,ypos,zpos)
		return

	def on_shotgun_shoot(self):
		self.FireLoop=None
		if not self.world_object:
			return
		if not self.world_object.primary_fire or self.tool!=WEAPON_TOOL or not self.weapon_object.current_ammo:
			return
		pos=self.world_object.cast_ray(725)
		if pos:
			pos=list(pos)
			dist=(Vertex3(*pos)-self.world_object.position).length()/self.world_object.orientation.length()
			time=dist*.36/(CANNON_SHOT_SPEED+2)**2/1.4
			grenade_packet.value=time
			grenade_packet.player_id=32
			grenade_packet.position=self.world_object.position.get()
			grenade_packet.velocity=(self.world_object.orientation*CANNON_SHOT_SPEED).get()
			self.protocol.send_contained(grenade_packet)
			Scheduler(self.protocol).call_later(time,self.shotgun_explosion,pos)
		self.FireLoop=Scheduler(self.protocol).call_later(Shotgun.delay+SHOT_DELAY,self.on_shotgun_shoot)
		return

	def on_rifle_shoot(self):
		self.FireLoop=None
		if not self.world_object:
			return
		if not self.world_object.primary_fire or self.tool!=WEAPON_TOOL or not self.weapon_object.current_ammo:
			return
		pos=self.world_object.cast_ray(725)
		if pos:
			self.player_remove_block(*pos)
		self.FireLoop=Scheduler(self.protocol).call_later(Rifle.delay+SHOT_DELAY,self.on_rifle_shoot)
		return

	def on_shoot_set(self,fire):
		connection.on_shoot_set(self,fire)
		if NEW_WEAPONS:
			if self.world_object and self.tool==WEAPON_TOOL and fire:
				self.world_object.primary_fire=1
				if fire and not self.FireLoop:
					if not self.weapon_object.id:
						self.on_rifle_shoot()
					if self.weapon_object.id==2:
						self.on_shotgun_shoot()
		return
	
    return BossProtocol, BossConnection
