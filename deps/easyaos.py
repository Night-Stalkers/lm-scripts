# -*- coding: utf-8 -*-
# version 1.2
"""

easygre(connection, (x, y, z), (vx, vy, vz), fuse)
 (x, y, z)�̈ʒu����(vx, vy, vz)�̑��x��connection�̃O���l�[�h�𐶐�
 fuse�͋N���܂ł̎��ԁA�w�肹���ɌĂяo���Ǝ����I�ɒ����M�ǂ�


easyblock(connection, (x, y, z), color)
 (x, y, z)�̈ʒu��color(r, g, b)�̃u���b�N�𐶐�
 ���ڒl���w�肷�鑼�Acolor�ɂ�RED,ORANGE,YELLOW,GREEN,SKYBLUE,BLUE,PURPLE,PINK,BEIGE,WHITE,BLACK���g�p�\


easyremove(connection, (x, y, z))
 (x, y, z)�̈ʒu�̃u���b�N���폜


easycollision(connection, (x, y, z), (vx, vy, vz))
 (x, y, z)�̈ʒu����(vx, vy, vz)�̑��x�Ō����o���ꂽ�O���l�[�h���ŏ��Ƀu���b�N�ɏՓ˂���ʒu�Ǝ��Ԃ�Ԃ�
 time, x, y, z�ƕԂ����
 
"""
from pyspades.world import Grenade
from pyspades.constants import *
from pyspades.contained import *
from pyspades.server import *
from pyspades.common import *
from twisted.internet.reactor import callLater
import json

RED = (255, 0, 0)
ORANGE = (255, 128, 0)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)
SKYBLUE = (0, 255, 255)
BLUE = (0, 0, 255)
PURPLE = (128, 0, 128)
PINK = (255, 0, 255)
BEIGE = (255, 255, 192)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

def easygre(connection, (x, y, z), (vx, vy, vz), fuse = 'hitexp'):
	if fuse == 'hitexp':
		fuse=easycollision(connection, (x, y, z), (vx, vy, vz))[0]
	grenade=connection.protocol.world.create_object(Grenade, fuse, Vertex3(x, y, z), None, Vertex3(vx, vy, vz), connection.grenade_exploded)
	grenade_packet.value = fuse
	grenade_packet.player_id = connection.player_id
	grenade_packet.position = (x, y, z)
	grenade_packet.velocity = (vx, vy, vz)
	connection.protocol.send_contained(grenade_packet)
 
def easyblock(connection, (x, y, z), color):
	block_action = BlockAction()
	set_color = SetColor()
	set_color.value = make_color(*color)
	set_color.player_id = 32
	connection.protocol.send_contained(set_color)
	block_action.player_id = 32
	block_action.value=BUILD_BLOCK
	block_action.x = x
	block_action.y = y
	block_action.z = z
	connection.protocol.send_contained(block_action)
	connection.protocol.map.set_point(x, y, z, color)

def easyremove(connection, (x, y, z)):
	block_action = BlockAction()
	block_action.player_id = connection.player_id
	block_action.value = DESTROY_BLOCK
	block_action.x = x
	block_action.y = y
	block_action.z = z
	connection.protocol.send_contained(block_action)
	connection.protocol.map.remove_point(x, y, z)

def easycollision(connection, (x, y, z), (vx, vy, vz)):
	time = 0
	vx = vx * 32.0
	vy = vy * 32.0
	vz = vz * 32.0
	players = connection.team.other.get_players()
	map = connection.protocol.map
	while time <= 3.0:
		x += vx / 100
		y += vy / 100
		z += vz / 100
		vz += 0.32
		time += 0.01
		if map.get_solid(x, y, z):
			return time, x, y, z
	return 3.0, 0, 0, 0