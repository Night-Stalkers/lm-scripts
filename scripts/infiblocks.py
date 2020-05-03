"""
Restocks block and ammo on each block placement.
Original Author: ???
Modified by: Hourai (Yui)

Changelog:
    
    1.0.1:
        * Fixed a bug in which placing a block would cause a hit effect
        on voxlap based clients.
    1.0.0:
        * Started using Semantic Versioning.
        * Added license.
        * No longer refills health.
        
"""

from commands import add, name
from pyspades.constants import *

@name('blocks')
def toggle_infi_blocks(connection):
    protocol = connection.protocol
    if connection in protocol.players:
        connection.infi_blocks = not connection.infi_blocks
        return "You are {} infinite blocks mode.".format(["out of", "now in"][int(connection.infi_blocks)])


add(toggle_infi_blocks)


def apply_script(protocol, connection, config):

    class BlockConnection(connection):
        infi_blocks = True

        def _infi_refill(self):
            if self.infi_blocks:
                old_hp = self.hp
                self.refill()
                self.set_hp(old_hp, type = FALL_KILL)
        
        def on_block_build(self, x, y, z):
            self._infi_refill()
            return connection.on_block_build(self, x, y, z)

        def on_line_build(self, points):
            self._infi_refill()
            return connection.on_line_build(self, points)

    return protocol, BlockConnection
