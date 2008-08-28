#
#    Uncomplicated VM Builder
#    Copyright (C) 2007-2008 Canonical
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
from   VMBuilder.util import run_cmd
import VMBuilder.disk as disk
import VMBuilder
import logging
import glob
import sys

class Suite(object):
    def __init__(self, vm):
        self.vm = vm

    def check_arch_validity(self, arch):
        """Checks whether the given arch is valid for this suite"""
        raise NotImplemented('Suite subclasses need to implement the check_arch_validity method')
