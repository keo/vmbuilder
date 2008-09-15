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
import glob
import logging
import os
import suite
import shutil
import VMBuilder.disk as disk
from   VMBuilder.util import run_cmd

class Dapper(suite.Suite):
    updategrub = "/sbin/update-grub"
    grubroot = "/lib/grub"
    valid_flavours = { 'i386' :  ['386', '686', '686-smp', 'k7', 'k7-smp', 'server', 'server-bigiron'],
                       'amd64' : ['amd64-generic', 'amd64-k8', 'amd64-k8-smp', 'amd64-server', 'amd64-xeon']}
    default_flavour = { 'i386' : 'server', 'amd64' : 'amd64-server' }
    disk_prefix = 'hd'

    def check_kernel_flavour(self, arch, flavour):
        return flavour in self.valid_flavours[arch]

    def check_arch_validity(self, arch):
        return arch in self.valid_flavours.keys()
        
    def install(self, destdir):
        self.destdir = destdir

        logging.debug("debootstrapping")
        self.debootstrap()

        logging.debug("Setting up sources.list")
        self.install_sources_list()

        logging.debug("Installing fstab")
        self.install_fstab()

        logging.debug("Creating devices")
        self.create_devices()
    
        if self.vm.hypervisor.needs_bootloader:
            logging.debug("Installing grub")
            self.install_grub()
        
        logging.debug("Configuring guest networking")
        self.config_network()

        logging.debug("Preventing daemons from starting")
        self.prevent_daemons_starting()

        if self.vm.hypervisor.needs_bootloader:
            logging.debug("Installing menu.list")
            self.install_menu_lst()

            logging.debug("Installing kernel")
            self.install_kernel()

            logging.debug("Creating device.map")
            self.install_device_map()

        logging.debug("Installing extra packages")
        self.install_extras()

        
        logging.debug("Creating initial user")
        self.create_initial_user()

        self.install_authorized_keys()

        logging.debug("Unmounting volatile lrm filesystems")
        self.unmount_volatile()

        logging.debug("Unpreventing daemons from starting")
        self.unprevent_daemons_starting()

    def install_authorized_keys(self):
        if self.vm.ssh_key:
            os.mkdir('%s/root/.ssh' % self.destdir, 0700)
            shutil.copy(self.vm.ssh_key, '%s/root/.ssh/authorized_keys' % self.destdir)
            os.chmod('%s/root/.ssh/authorized_keys' % self.destdir, 0644)
        if self.vm.ssh_user_key:
            os.mkdir('%s/home/%s/.ssh' % (self.destdir, self.vm.user), 0700)
            shutil.copy(self.vm.ssh_user_key, '%s/home/%s/.ssh/authorized_keys' % (self.destdir, self.vm.user))
            os.chmod('%s/home/%s/.ssh/authorized_keys' % (self.destdir, self.vm.user), 0644)

    def create_initial_user(self):
        self.run_in_target('adduser', '--disabled-password', '--gecos', self.vm.name, self.vm.user)
        self.run_in_target('chpasswd', stdin=('%s:%s\n' % (self.vm.user, getattr(self.vm, 'pass'))))
        self.run_in_target('addgroup', '--system', 'admin')
        self.run_in_target('adduser', self.vm.user, 'admin')
        fp = open('%s/etc/sudoers' %  self.destdir, 'a')
        fp.write("""

# Members of the admin group may gain root privileges
%admin ALL=(ALL) ALL
""")
        fp.close()
        for group in ['adm', 'audio', 'cdrom', 'dialout', 'floppy', 'video', 'plugdev', 'dip', 'netdev', 'powerdev', 'lpadmin', 'scanner']:
            self.run_in_target('adduser', self.vm.user, group, ignore_fail=True)

        # Lock root account
        self.run_in_target('chpasswd', stdin='root:!\n')

    def kernel_name(self):
        return 'linux-image-%s' % (self.vm.flavour or self.default_flavour[self.vm.arch],)

    def config_network(self):
        logging.debug("ip: %s" % self.vm.ip)

        if self.vm.ip != 'dhcp':
            numip = long(inet_aton(self.vm.ip))
            if self.vm.net == 'X.X.X.0':
                self.vm.net = inet_ntoa(string( numip ^ 0x000F ))
            if self.vm.bcast == 'X.X.X.255':
                self.vm.bcast = inet_ntoa(string( (numip ^ 0x000F) + 0xF ))
            if self.vm.gw == 'X.X.X.1':
                self.vm.gw = inet_ntoa(string( (numip ^ 0x000F ) + 0x1 ))
            if self.vm.dns == 'X.X.X.1':
                self.vm.dns = inet_ntoa(string( (numip ^ 0x000F ) + 0x1 ) )

            logging.debug("net: %s" % self.vm.net)
            logging.debug("broadcast: %s" % self.vm.bcast)
            logging.debug("gateway: %s" % self.vm.gw)
            logging.debug("dns: %s" % self.vm.dns)

        self.install_file('/etc/hostname', self.vm.hostname)
        self.install_file('/etc/hosts', '''127.0.0.1 localhost
127.0.1.1 %s.%s %s

# The following lines are desirable for IPv6 capable hosts
::1 ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
ff02::3 ip6-allhosts''' % (self.vm.hostname, self.vm.domain, self.vm.hostname))

        interfaces = '''# This file describes the network interfaces available on your system
# and how to activate them. For more information, see interfaces(5).

# The loopback network interface
auto lo
iface lo inet loopback

# The primary network interface
auto eth0 '''
        if self.vm.ip == 'dhcp':
            interfaces += '''
ifface eth0 inet dhcp
'''
        else:
            interfaces += '''
iface eth0 inet static
        address %s
        netmask %s 
        network %s
        broadcast %s
        gateway %s
        # dns-* options are implemented by the resolvconf package, if installed
        dns-nameservers %s
        dns-search %s''' % (self.vm.ip, self.vm.mask, self.vm.net, self.vm.bcast, self.vm.gw, self.vm.dns, self.vm.domain)
        
        self.install_file('/etc/network/interfaces', interfaces)

    def unprevent_daemons_starting(self):
        os.unlink('%s/usr/sbin/policy-rc.d' % self.destdir)

    def prevent_daemons_starting(self):
        path = '%s/usr/sbin/policy-rc.d' % self.destdir
        fp  = open(path, 'w')
        fp.write("""#!/bin/sh

while true; do
    case "$1" in
        -*)
            shift
            ;;
        makedev)
            exit 0
            ;;
        x11-common)
            exit 0
            ;;
        *)
            exit 101
            ;;
    esac
done
""")
        os.chmod(path, 0755)

    def install_extras(self):
        if not self.vm.addpkg and not self.vm.removepkg:
            return
        cmd = ['apt-get', 'install', '-y', '--force-yes']
        cmd += self.vm.addpkg or []
        cmd += ['%s-' % pkg for pkg in self.vm.removepkg or []]
        self.run_in_target(*cmd)
        
    def unmount_volatile(self):
        for mntpnt in glob.glob('%s/lib/modules/*/volatile' % self.destdir):
            logging.debug("Unmounting %s" % mntpnt)
            run_cmd('umount', mntpnt)

    def install_menu_lst(self):
        run_cmd('mount', '--bind', '/dev', '%s/dev' % self.destdir)
        self.vm.add_clean_cmd('umount', '%s/dev' % self.destdir, ignore_fail=True)

        self.run_in_target('mount', '-t', 'proc', 'proc', '/proc')
        self.vm.add_clean_cmd('umount', '%s/proc' % self.destdir, ignore_fail=True)

        self.run_in_target(self.updategrub, '-y')
        self.mangle_grub_menu_lst()
        self.run_in_target(self.updategrub)
        self.run_in_target('grub-set-default', '0')

        run_cmd('umount', '%s/dev' % self.destdir)
        run_cmd('umount', '%s/proc' % self.destdir)

    def mangle_grub_menu_lst(self):
        bootdev = disk.bootpart(self.vm.disks)
        run_cmd('sed', '-ie', 's/^# kopt=root=\([^ ]*\)\(.*\)/# kopt=root=\/dev\/hd%s%d\\2/g' % (bootdev.disk.devletters, bootdev.get_index()+1), '%s/boot/grub/menu.lst' % self.destdir)
        run_cmd('sed', '-ie', 's/^# groot.*/# groot %s/g' % bootdev.get_grub_id(), '%s/boot/grub/menu.lst' % self.destdir)
        run_cmd('sed', '-ie', '/^# kopt_2_6/ d', '%s/boot/grub/menu.lst' % self.destdir)

    def install_sources_list(self):
        self.install_file('/etc/apt/sources.list', self.sources_list())
        self.run_in_target('apt-get', 'update')

    def sources_list(self):
        lines = []
        components = self.vm.components = ['main', 'universe', 'restricted']
        lines.append('# This is your shiny, new sources.list')
        lines.append('deb %s %s %s' % (self.vm.mirror, self.vm.suite, ' '.join(self.vm.components)))
        lines.append('deb %s %s-updates %s' % (self.vm.mirror, self.vm.suite, ' '.join(self.vm.components)))
        lines.append('deb %s %s-security %s' % (self.vm.mirror, self.vm.suite, ' '.join(self.vm.components)))
        lines.append('deb http://security.ubuntu.com/ubuntu %s-security %s' % (self.vm.suite, ' '.join(self.vm.components)))

        if self.vm.ppa:
            lines += ['deb http://ppa.launchpad.net/%s/ubuntu %s %s' % (ppa, self.vm.suite, ' '.join(self.vm.components)) for ppa in self.vm.ppa]

        return ''.join(['%s\n' % line for line in lines])

    def install_fstab(self):
        self.install_file('/etc/fstab', self.fstab())

    def install_device_map(self):
        self.install_file('/boot/grub/device.map', self.device_map())

    def device_map(self):
        return '\n'.join(['(%s) /dev/%s%s' % (self.disk_prefix, disk.get_grub_id(), disk.devletters) for disk in self.vm.disks])

    def debootstrap(self):
        cmd = ['/usr/sbin/debootstrap', '--arch=%s' % self.vm.arch, self.vm.suite, self.destdir ]
        if self.vm.mirror:
            cmd += [self.vm.mirror]
        run_cmd(*cmd)

    def install_kernel(self):
        self.install_file('/etc/kernel-img.conf', ''' 
do_symlinks = yes
relative_links = yes
do_bootfloppy = no
do_initrd = yes
link_in_boot = no
postinst_hook = %s
postrm_hook = %s
do_bootloader = no''' % (self.updategrub, self.updategrub))
        run_cmd('chroot', self.destdir, 'apt-get', '--force-yes', '-y', 'install', self.kernel_name(), 'grub')

    def install_grub(self):
        self.run_in_target('apt-get', '--force-yes', '-y', 'install', 'grub')
        run_cmd('cp', '-a', '%s%s/%s/' % (self.destdir, self.grubroot, self.vm.arch == 'amd64' and 'x86_64-pc' or 'i386-pc'), '%s/boot/grub' % self.destdir) 

    def fstab(self):
        retval = '''# /etc/fstab: static file system information.
#
# <file system>                                 <mount point>   <type>  <options>       <dump>  <pass>
proc                                            /proc           proc    defaults        0       0
'''
        parts = disk.get_ordered_partitions(self.vm.disks)
        for part in parts:
            retval += "/dev/%s%-38s %15s %7s %15s %d       %d\n" % (self.disk_prefix, part.get_suffix(), part.mntpnt, part.fstab_fstype(), part.fstab_options(), 0, 0)
        return retval

    def create_devices(self):
        import VMBuilder.plugins.xen

        if isinstance(self.vm.hypervisor, VMBuilder.plugins.xen.Xen):
            self.run_in_target('mknod', '/dev/xvda', 'b', '202', '0')
            self.run_in_target('mknod', '/dev/xvda1', 'b', '202', '1')
            self.run_in_target('mknod', '/dev/xvda2', 'b', '202', '2')
            self.run_in_target('mknod', '/dev/xvda3', 'b', '202', '3')
            self.run_in_target('mknod', '/dev/xvc0', 'c', '204', '191')

    def install_file(self, path, contents):
        fp = open('%s%s' % (self.destdir, path), 'w')
        fp.write(contents)
        fp.close()

    def run_in_target(self, *args, **kwargs):
        return run_cmd('chroot', self.destdir, *args, **kwargs)

