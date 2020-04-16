"""
infiblocks.py
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
Restocks block and ammo on each block placement.
Original Author: ???
Modified by: Hourai (Yui)

Changelog:
    
    1.0.0:
        * Started using Semantic Versioning.
        * Added license.
        * No longer refills health.
        
"""

from commands import add, name


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
                self.set_hp(old_hp)
        
        def on_block_build(self, x, y, z):
            self._infi_refill()
            return connection.on_block_build(self, x, y, z)

        def on_line_build(self, points):
            self._infi_refill()
            return connection.on_line_build(self, points)

    return protocol, BlockConnection