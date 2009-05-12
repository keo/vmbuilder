#
#    Uncomplicated VM Builder
#    Copyright (C) 2007-2008 Canonical Ltd.
#    
#    See AUTHORS for list of contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import suite
import logging
import VMBuilder.disk as disk
from   VMBuilder.util import run_cmd
from   VMBuilder.plugins.ubuntu.intrepid import Intrepid

class Jaunty(Intrepid):
    xen_kernel_flavour = 'server'
    ec2_kernel_info = { 'i386' : 'aki-c553b4ac', 'amd64' : 'aki-d653b4bf' }
    ec2_ramdisk_info = { 'i386' : 'ari-c253b4ab', 'amd64' : 'ari-d753b4be' }

    def mangle_grub_menu_lst(self):
        bootdev = disk.bootpart(self.vm.disks)
        run_cmd('sed', '-ie', 's/^# kopt=root=\([^ ]*\)\(.*\)/# kopt=root=UUID=%s\\2/g' % bootdev.fs.uuid, '%s/boot/grub/menu.lst' % self.destdir)
        run_cmd('sed', '-ie', 's/^# groot.*/# groot=%s/g' % bootdev.fs.uuid, '%s/boot/grub/menu.lst' % self.destdir)
        run_cmd('sed', '-ie', '/^# kopt_2_6/ d', '%s/boot/grub/menu.lst' % self.destdir)

    def update_passwords(self):
        # Set the user password, using using defaults from /etc/login.defs (ie, no need to specify '-m')
        self.run_in_target('chpasswd', stdin=('%s:%s\n' % (self.vm.user, getattr(self.vm, 'pass'))))

        # Lock root account only if we didn't set the root password
        if self.vm.rootpass:
            self.run_in_target('chpasswd', stdin=('%s:%s\n' % ('root', self.vm.rootpass)))
        else:
            self.run_in_target('chpasswd', '-e', stdin='root:!\n')

