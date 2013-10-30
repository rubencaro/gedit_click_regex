# -*- coding: utf8 -*-
#  Click Regex plugin for gedit
#
#  Copyright (C) 2013-2013 Rubén Caro
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import GObject, Gedit, Gtk, Gio, Gdk, GLib
import os, os.path

def spit(obj):
    print( str(obj) )

# essential interface
class ClickRegexPluginInstance:
    def __init__( self, plugin, window ):
        self._window = window
        self._plugin = plugin
        self._insert_menu()

    def deactivate( self ):
        self._remove_menu()
        self._action_group = None
        self._window = None
        self._plugin = None

    def update_ui( self ):
        pass

    # MENU STUFF
    def _insert_menu( self ):
        manager = self._window.get_ui_manager()

        self._action_group = Gtk.ActionGroup( "ClickRegexPluginActions" )
        self._action_group.add_actions([
            ("ConfigureClickRegexAction", Gtk.STOCK_FIND, "Configure click regex...",
             '<Ctrl><Alt>R', "Configure click regex",
             lambda a: self.on_configure_action()),
        ])

        manager.insert_action_group(self._action_group)

        ui_str = """
          <ui>
            <menubar name="MenuBar">
              <menu name="EditMenu" action="Edit">
                <placeholder name="EditOps_7">
                  <menuitem name="ClickRegex" action="ConfigureClickRegexAction"/>
                </placeholder>
              </menu>
            </menubar>
          </ui>
          """

        self._ui_id = manager.add_ui_from_string(ui_str)

    def _remove_menu( self ):
        manager = self._window.get_ui_manager()
        manager.remove_ui( self._ui_id )
        manager.remove_action_group( self._action_group )
        manager.ensure_update()


# STANDARD PLUMMING
class ClickRegexPlugin(GObject.Object, Gedit.WindowActivatable):
    __gtype_name__ = "ClickRegexPlugin"
    DATA_TAG = "ClickRegexPluginInstance"

    window = GObject.property(type=Gedit.Window)

    def __init__(self):
        GObject.Object.__init__(self)

    def _get_instance( self ):
        return self.window.DATA_TAG

    def _set_instance( self, instance ):
        self.window.DATA_TAG = instance

    def do_activate( self ):
        self._set_instance( ClickRegexPluginInstance( self, self.window ) )

    def do_deactivate( self ):
        if self._get_instance():
            self._get_instance().deactivate()
        self._set_instance( None )

    def do_update_ui( self ):
        self._get_instance().update_ui()
